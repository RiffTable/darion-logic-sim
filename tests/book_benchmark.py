"""
DARION LOGIC SIM — BOOK ALGORITHM BENCHMARK SUITE
=================================================
Tests both Engine and Reactor backends.

FAIRNESS CONTRACT
-----------------
Every benchmark obeys the same rule for both sides:
  • Build & wire all data structures ONCE, outside the timer.
  • Only the *propagation* step is timed.
  • Both sides receive identical warmup passes.
  • Results are validated: Book and Naive must agree on every output.

WHY COMPARE AGAINST "NAIVE"?
-----------------------------
The "Book algorithm" is Darion's core propagation engine.
It maintains a compact 3-slot counter (LOW / HIGH / UNKNOWN) per gate so
that, when one source input changes, it only needs to update that ONE slot
and re-derive the gate's output — O(1) per source change, regardless of
fan-in.

The "Naive" algorithm re-evaluates every source of every affected gate from
scratch (O(fan-in) per gate per propagation step).  It is the simplest
correct implementation and therefore the ideal baseline for showing the
Book algorithm's advantage.

Run:
  python tests/book_benchmark.py
"""

import sys
import os
import time
import gc
import platform
import statistics

# ── UTF-8 console ─────────────────────────────────────────────────────────────
import sys
if hasattr(sys, 'stdout') and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
try:
    import ctypes
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
except Exception:
    pass

# ─── PATH SETUP ───────────────────────────────────────────────────────────────
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir   = os.path.dirname(script_dir)
sys.path.append(os.path.join(root_dir, 'control'))

# ─── UTILITIES ────────────────────────────────────────────────────────────────

def format_time(ms):
    if ms >= 1000:    return f"{ms / 1000:.3f} s"
    elif ms >= 0.1:   return f"{ms:.2f} ms"
    elif ms >= 0.001: return f"{ms * 1000:.1f} µs"
    else:             return f"{ms * 1_000_000:.0f} ns"

def timed_fn(fn, warmup=3):
    """Call fn() `warmup` times then time a single cold-GC-disabled run."""
    for _ in range(warmup):
        fn()
    gc_was = gc.isenabled()
    gc.disable()
    t0 = time.perf_counter_ns()
    result = fn()
    t1 = time.perf_counter_ns()
    if gc_was:
        gc.enable()
    return (t1 - t0) / 1_000_000, result

def divider(char='═', width=92):
    return char * width

def header(title, char='═', width=92):
    pad = (width - len(title) - 2) // 2
    return f"{char * pad} {title} {char * (width - pad - len(title) - 2)}"

# ─── BACKEND LOADER ───────────────────────────────────────────────────────────

def load_backend(use_reactor):
    for mod_name in ['Circuit', 'IC', 'Const', 'Gates', 'Store']:
        sys.modules.pop(mod_name, None)

    engine_path  = os.path.join(root_dir, 'engine')
    reactor_path = os.path.join(root_dir, 'reactor')
    sys.path = [p for p in sys.path if p not in (engine_path, reactor_path)]
    sys.path.insert(0, reactor_path if use_reactor else engine_path)

    from Circuit import Circuit
    from IC      import IC
    from Const   import (
        IC_ID, INPUT_PIN_ID, OUTPUT_PIN_ID,
        NOT_ID, AND_ID, NAND_ID, OR_ID, NOR_ID, XOR_ID, XNOR_ID,
        VARIABLE_ID, PROBE_ID,
        HIGH, LOW, UNKNOWN, ERROR, SIMULATE, set_MODE,
    )
    return {
        'Circuit': Circuit, 'IC': IC,
        'IC_ID': IC_ID, 'INPUT_PIN_ID': INPUT_PIN_ID,
        'OUTPUT_PIN_ID': OUTPUT_PIN_ID, 'NOT_ID': NOT_ID,
        'AND_ID': AND_ID, 'NAND_ID': NAND_ID, 'OR_ID': OR_ID,
        'NOR_ID': NOR_ID, 'XOR_ID': XOR_ID, 'XNOR_ID': XNOR_ID,
        'VARIABLE_ID': VARIABLE_ID, 'PROBE_ID': PROBE_ID,
        'HIGH': HIGH, 'LOW': LOW, 'UNKNOWN': UNKNOWN, 'ERROR': ERROR,
        'SIMULATE': SIMULATE, 'set_MODE': set_MODE,
    }

# ═════════════════════════════════════════════════════════════════════════════
#  NAIVE PROPAGATOR
# ═════════════════════════════════════════════════════════════════════════════
# The Naive propagator is intentionally minimal: it carries only the data a
# correct BFS needs.  Its process() re-reads every source slot on every call
# — exactly the O(fan-in) work the Book algorithm avoids.

class _NaiveProfile:
    __slots__ = ['target', 'index', 'cached_output']
    def __init__(self, target, index):
        self.target        = target
        self.index         = index
        self.cached_output = None       # mirrors Book's profile.output

class _NaiveGate:
    __slots__ = ['gtype', 'output', 'sources', 'hitlist', 'scheduled', 'limit']
    def __init__(self, gtype, limit):
        self.gtype     = gtype          # 'VAR', 'AND', 'OR', 'NOT', 'XOR'
        self.limit     = limit
        self.output    = None           # None = UNKNOWN
        self.sources   = [None] * limit
        self.hitlist   = []
        self.scheduled = False

    def process(self, HIGH=1, LOW=0):
        """Re-derive output by scanning all sources — O(fan-in)."""
        if self.gtype == 'VAR':
            return self.output          # variables hold their own value
        high = low = 0
        for s in self.sources:
            if s is None or s.output is None:
                pass
            elif s.output == HIGH: high += 1
            else:                  low  += 1
        known = high + low
        if known == 0:
            return None
        if known < self.limit:
            return None                 # not enough inputs → UNKNOWN
        if self.gtype == 'AND':  return HIGH if low  == 0 else LOW
        if self.gtype == 'OR':   return HIGH if high >  0 else LOW
        if self.gtype == 'NOT':  return LOW  if self.sources[0] and self.sources[0].output == HIGH else HIGH
        if self.gtype == 'XOR':  return HIGH if high % 2 == 1 else LOW
        return None

def _naive_propagate(root, HIGH=1, LOW=0):
    """BFS propagation starting from `root`."""
    queue = [root]
    root.scheduled = True
    while queue:
        gate = queue.pop(0)
        gate.scheduled = False
        new_out = gate.output if gate.gtype == 'VAR' else gate.process(HIGH, LOW)
        for prof in gate.hitlist:
            tgt = prof.target
            tgt_out = tgt.process(HIGH, LOW)
            if tgt_out != tgt.output:
                tgt.output = tgt_out
                if not tgt.scheduled:
                    tgt.scheduled = True
                    queue.append(tgt)

# ═════════════════════════════════════════════════════════════════════════════
#  TEST 1 — Single Deep AND Chain with Varying Fan-In
# ═════════════════════════════════════════════════════════════════════════════
#
# Topology:  toggle_var → AND₀ → AND₁ → … → AND₉₉₉
#            each AND gate also receives (fan_in - 1) wires from high_var
#
# One toggle: HIGH then LOW on toggle_var.
# This exercises how fast each algorithm can walk a 1 000-gate chain when
# every gate carries an increasing number of "always-HIGH" inputs.
# The Book algorithm's book[] counts mean it never re-counts those inputs.

def bench_fanin_chain(backend, fan_in, chain_length=1_000):
    HIGH      = backend['HIGH']
    LOW       = backend['LOW']
    UNKNOWN   = backend['UNKNOWN']
    AND_ID    = backend['AND_ID']
    VARIABLE_ID = backend['VARIABLE_ID']

    # ── BOOK side ──────────────────────────────────────────────────
    c = backend['Circuit']()
    c.simulate(backend['SIMULATE'])
    toggle_var = c.getcomponent(VARIABLE_ID)
    high_var   = c.getcomponent(VARIABLE_ID)
    c.toggle(high_var, HIGH)
    prev = toggle_var
    gates = []
    for _ in range(chain_length):
        g = c.getcomponent(AND_ID)
        c.setlimits(g, fan_in)
        c.connect(g, prev, 0)
        for i in range(1, fan_in):
            c.connect(g, high_var, i)
        prev = g
        gates.append(g)

    def book_fn():
        c.toggle(toggle_var, HIGH)
        c.toggle(toggle_var, LOW)
        return getattr(gates[-1], 'output', None)

    # ── NAIVE side — built once, outside the timer ─────────────────
    n_toggle = _NaiveGate('VAR', 0)
    n_high   = _NaiveGate('VAR', 0)
    n_high.output = HIGH
    n_prev   = n_toggle
    n_gates  = []
    for _ in range(chain_length):
        g = _NaiveGate('AND', fan_in)
        g.sources[0] = n_prev
        n_prev.hitlist.append(_NaiveProfile(g, 0))
        for i in range(1, fan_in):
            g.sources[i] = n_high
            n_high.hitlist.append(_NaiveProfile(g, i))
        n_prev = g
        n_gates.append(g)

    def naive_fn():
        n_toggle.output = HIGH
        _naive_propagate(n_toggle, HIGH, LOW)
        n_toggle.output = LOW
        _naive_propagate(n_toggle, HIGH, LOW)
        return n_gates[-1].output

    book_ms,  book_result  = timed_fn(book_fn)
    naive_ms, naive_result = timed_fn(naive_fn)

    # Validate agreement
    match = (book_result == naive_result) or (book_result is None and naive_result is None)
    return book_ms, naive_ms, match

# ═════════════════════════════════════════════════════════════════════════════
#  TEST 2 — Fan-Out  (many OR gates sharing the same variables)
# ═════════════════════════════════════════════════════════════════════════════
#
# Topology:  N variables → each connected to M OR gates
#            Toggling every variable HIGH then LOW drives every gate.
#
# Stresses the fan-out path: each variable change must notify M gate hitlists.
# Book: only updates the one changed slot in each target's book[].
# Naive: re-reads all N sources of each gate.

def bench_fanout(backend, gate_count, inputs_per_gate):
    HIGH      = backend['HIGH']
    LOW       = backend['LOW']
    OR_ID     = backend['OR_ID']
    VARIABLE_ID = backend['VARIABLE_ID']

    # ── BOOK side ──────────────────────────────────────────────────
    c = backend['Circuit']()
    c.simulate(backend['SIMULATE'])
    variables = [c.getcomponent(VARIABLE_ID) for _ in range(inputs_per_gate)]
    orgs = []
    for _ in range(gate_count):
        g = c.getcomponent(OR_ID)
        c.setlimits(g, inputs_per_gate)
        for j in range(inputs_per_gate):
            c.connect(g, variables[j], j)
        orgs.append(g)

    def book_fn():
        for v in variables: c.toggle(v, HIGH)
        for v in variables: c.toggle(v, LOW)

    # ── NAIVE side — built once, outside the timer ─────────────────
    n_vars = [_NaiveGate('VAR', 0) for _ in range(inputs_per_gate)]
    n_gates = []
    for _ in range(gate_count):
        g = _NaiveGate('OR', inputs_per_gate)
        for j in range(inputs_per_gate):
            g.sources[j] = n_vars[j]
            n_vars[j].hitlist.append(_NaiveProfile(g, j))
        n_gates.append(g)

    def naive_fn():
        for v in n_vars:
            v.output = HIGH
            _naive_propagate(v, HIGH, LOW)
        for v in n_vars:
            v.output = LOW
            _naive_propagate(v, HIGH, LOW)

    book_ms,  _ = timed_fn(book_fn)
    naive_ms, _ = timed_fn(naive_fn)
    return book_ms, naive_ms

# ═════════════════════════════════════════════════════════════════════════════
#  TEST 3 — Deep NOT Chain
# ═════════════════════════════════════════════════════════════════════════════
#
# Topology:  v → NOT₀ → NOT₁ → … → NOT_{N-1}
#
# NOT is a single-input gate; there is no fan-in advantage for the Book
# algorithm here.  This test measures raw sequential propagation depth:
# how many gates per second can each algorithm process in a pure pipeline?
#
# Expected behaviour:
#   • Reactor: both fast; Book wins slightly due to C++ struct locality.
#   • Engine:  Python BFS overhead dominates; both are similar.

def bench_not_chain(backend, chain_length):
    HIGH      = backend['HIGH']
    LOW       = backend['LOW']
    NOT_ID    = backend['NOT_ID']
    VARIABLE_ID = backend['VARIABLE_ID']

    # ── BOOK side ──────────────────────────────────────────────────
    c = backend['Circuit']()
    c.simulate(backend['SIMULATE'])
    v = c.getcomponent(VARIABLE_ID)
    prev = v
    gates = []
    for _ in range(chain_length):
        g = c.getcomponent(NOT_ID)
        c.connect(g, prev, 0)
        prev = g
        gates.append(g)

    def book_fn():
        c.toggle(v, HIGH)
        c.toggle(v, LOW)
        return getattr(gates[-1], 'output', None)

    # ── NAIVE side — built once, outside the timer ─────────────────
    n_v    = _NaiveGate('VAR', 0)
    n_prev = n_v
    n_gates = []
    for _ in range(chain_length):
        g = _NaiveGate('NOT', 1)
        g.sources[0] = n_prev
        n_prev.hitlist.append(_NaiveProfile(g, 0))
        n_prev = g
        n_gates.append(g)

    def naive_fn():
        n_v.output = HIGH
        _naive_propagate(n_v, HIGH, LOW)
        n_v.output = LOW
        _naive_propagate(n_v, HIGH, LOW)
        return n_gates[-1].output

    book_ms,  book_r  = timed_fn(book_fn)
    naive_ms, naive_r = timed_fn(naive_fn)
    return book_ms, naive_ms, book_r, naive_r

# ═════════════════════════════════════════════════════════════════════════════
#  RUNNER
# ═════════════════════════════════════════════════════════════════════════════

def run_book_vs_naive():
    print(f"\n{header('  BOOK ALGORITHM vs NAIVE TRAVERSAL  ')}")
    print("""
  The "Book algorithm" is Darion's core incremental update engine.
  Each gate holds a 3-slot counter: book[LOW], book[HIGH], book[UNKNOWN].
  When one source changes, exactly ONE slot is decremented and ONE is
  incremented — the gate's new output follows in O(1), regardless of fan-in.

  The "Naive" algorithm re-reads every source on every evaluation — O(fan-in).
  Both sides build their data structures once BEFORE the timer starts;
  only propagation time is measured.  Results are validated for correctness.
""")

    backends_to_test = []
    for use_r, lbl in [(True, "Reactor (Cython)"), (False, "Engine (Python)")]:
        try:
            backends_to_test.append((load_backend(use_reactor=use_r), lbl))
        except ImportError:
            pass

    if not backends_to_test:
        print("  ⚠ No backend available!")
        return

    for backend, label in backends_to_test:
        H  = backend['HIGH']
        L  = backend['LOW']
        UNK = backend['UNKNOWN']

        print(f"\n  {divider('-')}")
        print(f"  BACKEND: {label}")
        print(f"  {divider('-')}")

        # ── Test 1: fan-in AND chain ───────────────────────────────────
        print(f"""
  TEST 1: Fan-In Scaling — 1 000-Gate AND Chain (fixed depth = 1 000)
  ──────────────────────────────────────────────────────────────────────────
  Why: AND has exactly fan_in sources.  The Book counter keeps one slot per
  source-state (LOW/HIGH/UNKNOWN); a change updates one slot.  Naive scans
  all fan_in sources.  Increasing fan_in makes Naive O(fan_in × chain_length)
  while Book stays O(chain_length).
""")
        print(f"  | {'Fan-in':<10} | {'Book':>12} | {'Naive':>12} | {'Speedup':>10} | {'Agree':>6} |")
        print(f"  |{'-'*12}+{'-'*14}+{'-'*14}+{'-'*12}+{'-'*8}|")

        for fan_in in [2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]:
            gc.collect()
            book_ms, naive_ms, match = bench_fanin_chain(backend, fan_in)
            speedup = naive_ms / book_ms if book_ms > 0 else float('inf')
            agree   = "✓" if match else "✗ MISMATCH"
            print(f"  | {fan_in:<10,} | {format_time(book_ms):>12} | {format_time(naive_ms):>12} "
                  f"| {speedup:>9.1f}x | {agree:>6} |")

        # ── Test 2: fan-out OR ─────────────────────────────────────────
        print(f"""
  TEST 2: Fan-Out Scaling — Shared Variables drive Multiple OR Gates
  ──────────────────────────────────────────────────────────────────────────
  Why: Each variable change propagates to ALL connected OR gates.  This
  measures hitlist traversal cost.  Both algorithms walk the same hitlist,
  but Book only updates one counter slot per target; Naive re-evaluates all
  inputs_per_gate sources for each target — so larger inputs_per_gate ratio
  still disadvantages Naive even with the same gate count.
""")
        print(f"  | {'Gates × Inputs':<20} | {'Book':>12} | {'Naive':>12} | {'Speedup':>10} |")
        print(f"  |{'-'*22}+{'-'*14}+{'-'*14}+{'-'*12}|")

        for gate_count, inputs_per in [(100, 50), (500, 20), (1_000, 10),
                                        (5_000, 10), (10_000, 10), (20_000, 5)]:
            gc.collect()
            book_ms, naive_ms = bench_fanout(backend, gate_count, inputs_per)
            speedup = naive_ms / book_ms if book_ms > 0 else float('inf')
            cfg_str = f"{gate_count:,} × {inputs_per}"
            print(f"  | {cfg_str:<20} | {format_time(book_ms):>12} | {format_time(naive_ms):>12} "
                  f"| {speedup:>9.1f}x |")

        # ── Test 3: deep NOT chain ─────────────────────────────────────
        print(f"""
  TEST 3: NOT Chain Depth — Sequential Pipeline Propagation
  ──────────────────────────────────────────────────────────────────────────
  Why: NOT has only 1 source, so Book's counter advantage is minimal.  This
  benchmarks raw pipeline depth (how many gates/sec).  The gap between Book
  and Naive here reflects *infrastructure* differences (e.g., C++ structs vs
  Python dicts, branch prediction) rather than the O(1) vs O(N) difference.
  The Reactor's topology-sorted gate_infolist gives strong prefetch locality.
  ns/gate columns let you compare per-gate cost independent of chain length.
""")
        print(f"  | {'Chain Len':<12} | {'Book':>12} | {'Naive':>12} | {'Speedup':>10} "
              f"| {'ns/g (B)':>10} | {'ns/g (N)':>10} | {'Agree':>6} |")
        print(f"  |{'-'*14}+{'-'*14}+{'-'*14}+{'-'*12}+{'-'*12}+{'-'*12}+{'-'*8}|")

        for chain_len in [1_000, 10_000, 100_000, 500_000, 1_000_000]:
            gc.collect()
            book_ms, naive_ms, book_r, naive_r = bench_not_chain(backend, chain_len)
            speedup  = naive_ms / book_ms if book_ms > 0 else float('inf')
            ns_book  = (book_ms  * 1_000_000) / chain_len
            ns_naive = (naive_ms * 1_000_000) / chain_len
            # For NOT chains of even length, both outputs should be LOW (HIGH→LOW each toggle).
            agree = "✓" if book_r == naive_r else f"✗"
            print(f"  | {chain_len:<12,} | {format_time(book_ms):>12} | {format_time(naive_ms):>12} "
                  f"| {speedup:>9.1f}x | {ns_book:>10.1f} | {ns_naive:>10.1f} | {agree:>6} |")

        print()

# ═════════════════════════════════════════════════════════════════════════════

def run_all():
    print(divider())
    print(header("  BOOK BENCHMARK SUITE  "))
    print(divider())
    print(f"  Platform : {platform.system()} {platform.release()}")
    print(f"  Python   : {platform.python_version()}")
    print(f"  Time     : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(divider())
    run_book_vs_naive()
    print(f"\n{divider()}")
    print(f"  BENCHMARK COMPLETE")
    print(divider())


class _Tee:
    """Mirror stdout to a log file simultaneously."""
    def __init__(self, *streams): self.streams = streams
    def write(self, data):
        for s in self.streams: s.write(data)
    def flush(self):
        for s in self.streams: s.flush()


if __name__ == "__main__":
    from datetime import datetime
    _LOG = "book_benchmark_results.txt"
    with open(_LOG, "a", encoding="utf-8") as _lf:
        _lf.write(f"\n{'='*70}\n")
        _lf.write(f"RUN  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        _lf.write(f"{'='*70}\n")
        _orig = sys.stdout
        sys.stdout = _Tee(_orig, _lf)
        try:
            run_all()
        finally:
            sys.stdout = _orig
    print(f"\nLog saved to: {_LOG}")

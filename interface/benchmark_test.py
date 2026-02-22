"""
DARION LOGIC SIM — BENCHMARK TEST SUITE
========================================
Benchmarks both Engine and Reactor backends for:
  1. IC Creation & Loading
  2. Full Circuit Creation & Loading
  3. Book Algorithm vs Naive Traversal

Run:
  python interface/benchmark_test.py
"""

import sys
import os
import time
import gc
import tempfile
import platform
import statistics

# ─── PATH SETUP ───────────────────────────────────────────────────
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
sys.path.append(os.path.join(root_dir, 'control'))


# ─── UTILITIES ────────────────────────────────────────────────────

def format_time(ms):
    """Format time in ms with adaptive units."""
    if ms >= 1000:
        return f"{ms / 1000:.3f} s"
    elif ms >= 0.1:
        return f"{ms:.2f} ms"
    elif ms >= 0.001:
        return f"{ms * 1000:.1f} µs"
    else:
        return f"{ms * 1_000_000:.0f} ns"


def timed(func, warmup=0):
    """Run func with GC disabled, return elapsed ms."""
    for _ in range(warmup):
        func()

    gc_was = gc.isenabled()
    gc.disable()
    start = time.perf_counter_ns()
    result = func()
    end = time.perf_counter_ns()
    if gc_was:
        gc.enable()
    return (end - start) / 1_000_000, result


def timed_n(func, n=5):
    """Run func n times, return (median_ms, min_ms, max_ms, all_ms)."""
    times = []
    for _ in range(n):
        gc.collect()
        ms, _ = timed(func)
        times.append(ms)
    return statistics.median(times), min(times), max(times), times


def divider(char='═', width=72):
    return char * width


def header(title, char='═', width=72):
    pad = (width - len(title) - 2) // 2
    return f"{char * pad} {title} {char * (width - pad - len(title) - 2)}"


# ─── BACKEND LOADER ──────────────────────────────────────────────

def load_backend(use_reactor):
    """Load engine or reactor backend, return module dict."""
    # Reset module cache for clean import
    for mod_name in ['Circuit', 'IC', 'Const', 'Gates', 'Store']:
        if mod_name in sys.modules:
            del sys.modules[mod_name]

    # Remove old paths
    engine_path = os.path.join(root_dir, 'engine')
    reactor_path = os.path.join(root_dir, 'reactor')
    sys.path = [p for p in sys.path if p not in (engine_path, reactor_path)]

    if use_reactor:
        sys.path.insert(0, reactor_path)
    else:
        sys.path.insert(0, engine_path)

    from Circuit import Circuit
    from IC import IC
    from Const import (
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


# ═══════════════════════════════════════════════════════════════════
#  BENCHMARK 1: IC CREATION & LOADING
# ═══════════════════════════════════════════════════════════════════

def bench_ic_create(backend, gate_count, pin_count):
    """
    Create an IC with `pin_count` input/output pins and `gate_count`
    internal NOT gates chained together (pin → NOT → NOT → ... → pin).
    Returns (creation_time_ms, circuit, ic).
    """
    C = backend['Circuit']
    SIMULATE = backend['SIMULATE']

    def create():
        c = C()
        c.simulate(SIMULATE)
        ic = c.getcomponent(backend['IC_ID'])

        # Create input pins
        in_pins = []
        for _ in range(pin_count):
            in_pins.append(ic.getcomponent(backend['INPUT_PIN_ID']))

        # Create output pins
        out_pins = []
        for _ in range(pin_count):
            out_pins.append(ic.getcomponent(backend['OUTPUT_PIN_ID']))

        # Create internal NOT chain per pin-pair
        gates_per_chain = gate_count // pin_count
        for p in range(pin_count):
            prev = in_pins[p]
            for _ in range(gates_per_chain):
                g = ic.getcomponent(backend['NOT_ID'])
                c.connect(g, prev, 0)
                prev = g
            c.connect(out_pins[p], prev, 0)

        c.counter += ic.counter
        return c, ic, in_pins

    ms, (c, ic, in_pins) = timed(create)
    return ms, c, ic, in_pins


def bench_ic_save_load(backend, circuit, ic, tmp_path):
    """Save an IC to disk, then load it into a fresh circuit. Return (save_ms, load_ms)."""
    C = backend['Circuit']
    SIMULATE = backend['SIMULATE']

    # Save
    def do_save():
        # save_as_ic clears and reloads, so we write raw json instead
        import orjson
        data = ic.json_data()
        with open(tmp_path, 'wb') as f:
            f.write(orjson.dumps(data))

    save_ms, _ = timed(do_save)

    # Load
    def do_load():
        c2 = C()
        c2.simulate(SIMULATE)
        loaded = c2.getIC(tmp_path)
        c2.counter += loaded.counter if loaded else 0
        return c2, loaded

    load_ms, (c2, loaded) = timed(do_load)
    return save_ms, load_ms, c2, loaded


# ═══════════════════════════════════════════════════════════════════
#  BENCHMARK 2: FULL CIRCUIT CREATION & LOADING
# ═══════════════════════════════════════════════════════════════════

def bench_circuit_create(backend, chain_length):
    """Create a flat NOT-chain circuit. Return (creation_ms, circuit)."""
    C = backend['Circuit']
    SIMULATE = backend['SIMULATE']

    def create():
        c = C()
        c.simulate(SIMULATE)
        v = c.getcomponent(backend['VARIABLE_ID'])
        prev = v
        for _ in range(chain_length):
            g = c.getcomponent(backend['NOT_ID'])
            c.connect(g, prev, 0)
            prev = g
        return c

    ms, c = timed(create)
    return ms, c


def bench_circuit_save_load(backend, circuit, tmp_path):
    """Save a flat circuit to JSON then load it fresh. Return (save_ms, load_ms)."""
    C = backend['Circuit']
    SIMULATE = backend['SIMULATE']

    def do_save():
        circuit.writetojson(tmp_path)

    save_ms, _ = timed(do_save)

    def do_load():
        c2 = C()
        c2.readfromjson(tmp_path)
        return c2

    load_ms, c2 = timed(do_load)
    return save_ms, load_ms, c2


# ═══════════════════════════════════════════════════════════════════
#  BENCHMARK 3: BOOK ALGORITHM vs NAIVE TRAVERSAL
# ═══════════════════════════════════════════════════════════════════

def bench_book_vs_naive(backend, input_count, chain_length=1000):
    """
    Compare the simulator's book-based O(1) gate evaluation against
    a naive approach that scans all inputs every time within a propagation chain.
    """
    C = backend['Circuit']
    SIMULATE = backend['SIMULATE']
    HIGH = backend['HIGH']
    LOW = backend['LOW']
    UNKNOWN = backend['UNKNOWN']
    AND_ID = backend['AND_ID']
    VARIABLE_ID = backend['VARIABLE_ID']

    c = C()
    c.simulate(SIMULATE)
    
    toggle_var = c.getcomponent(VARIABLE_ID)
    high_var = c.getcomponent(VARIABLE_ID)
    c.toggle(high_var, HIGH)
    
    prev = toggle_var
    gates = []
    for _ in range(chain_length):
        g = c.getcomponent(AND_ID)
        c.setlimits(g, input_count)
        c.connect(g, prev, 0)
        # the remaining pins are just HIGH inputs
        for i in range(1, input_count):
            c.connect(g, high_var, i)
        prev = g
        gates.append(g)

    # ── BOOK ALGORITHM (the real simulator) ──
    def run_book():
        c.toggle(toggle_var, HIGH)
        c.toggle(toggle_var, LOW)
        return gates[-1].output

    # ── NAIVE TRAVERSAL (re-scan all sources every time) ──
    def run_naive():
        class MockProfile:
            __slots__ = ['target']
            def __init__(self, target):
                self.target = target

        class MockGate:
            __slots__ = ['output', 'hitlist', 'scheduled', 'sources']
            def __init__(self, limit):
                self.output = UNKNOWN
                self.hitlist = []
                self.scheduled = False
                self.sources = [None] * limit

            def process(self):
                high = 0
                low = 0
                uk = 0
                sz = len(self.sources)
                for s in self.sources:
                    if s is None: uk += 1
                    elif s.output == HIGH: high += 1
                    elif s.output == LOW: low += 1
                    else: uk += 1
                
                realsource = high + low
                if realsource == sz or (realsource and realsource + uk == sz):
                    return HIGH if low == 0 else LOW
                return UNKNOWN

        # Build equivalent structure
        toggle_m = MockGate(0)
        high_m = MockGate(0)
        high_m.output = HIGH
        
        prev_m = toggle_m
        gates_m = []
        for _ in range(chain_length):
            g = MockGate(input_count)
            g.sources[0] = prev_m
            prev_m.hitlist.append(MockProfile(g))
            for i in range(1, input_count):
                g.sources[i] = high_m
                high_m.hitlist.append(MockProfile(g))
            prev_m = g
            gates_m.append(g)

        def propagate_naive(val):
            toggle_m.output = val
            queue = [toggle_m]
            while queue:
                gate = queue.pop(0)
                gate.scheduled = False
                for profile in gate.hitlist:
                    target = profile.target
                    target_output = target.process()
                    if target_output != target.output:
                        target.output = target_output
                        if not target.scheduled:
                            target.scheduled = True
                            queue.append(target)
                            
        propagate_naive(HIGH)
        propagate_naive(LOW)
        return gates_m[-1].output

    book_ms, book_result = timed(run_book)
    naive_ms, naive_result = timed(run_naive)

    return book_ms, naive_ms, book_result, naive_result


def bench_book_vs_naive_multi_gate(backend, gate_count, inputs_per_gate):
    """
    Scale test: Many gates, each with multiple inputs.
    Compare book-tracked propagation vs naive full-scan.

    Creates `gate_count` OR gates, each with `inputs_per_gate` inputs.
    All share the same variables (fan-out scenario).
    """
    C = backend['Circuit']
    SIMULATE = backend['SIMULATE']
    HIGH = backend['HIGH']
    LOW = backend['LOW']
    UNKNOWN = backend['UNKNOWN']
    OR_ID = backend['OR_ID']
    VARIABLE_ID = backend['VARIABLE_ID']

    # ── BOOK (real simulator) ──
    c = C()
    c.simulate(SIMULATE)

    variables = []
    for i in range(inputs_per_gate):
        v = c.getcomponent(VARIABLE_ID)
        variables.append(v)

    gates = []
    for _ in range(gate_count):
        g = c.getcomponent(OR_ID)
        c.setlimits(g, inputs_per_gate)
        for j in range(inputs_per_gate):
            c.connect(g, variables[j], j)
        gates.append(g)
        
    # ── BOOK (real simulator) ──
    def run_book():
        # Toggle all HIGH
        for v in variables:
            c.toggle(v, HIGH)

        # Toggle all LOW
        for v in variables:
            c.toggle(v, LOW)

        return [g.output for g in gates]

    # ── NAIVE ──
    def run_naive():
        class MockProfile:
            __slots__ = ['target']
            def __init__(self, target):
                self.target = target
                
        class MockGate:
            __slots__ = ['output', 'hitlist', 'scheduled', 'sources']
            def __init__(self, limit=0):
                self.output = UNKNOWN
                self.hitlist = []
                self.scheduled = False
                self.sources = [None] * limit

            def process(self):
                high = 0
                low = 0
                for s in self.sources:
                    if s and s.output == HIGH: high += 1
                    elif s and s.output == LOW: low += 1
                realsource = high + low
                if realsource == len(self.sources) or realsource > 0:
                    return HIGH if high > 0 else LOW
                return UNKNOWN
                
        variables_m = [MockGate() for _ in range(inputs_per_gate)]
        gates_m = []
        for _ in range(gate_count):
            g = MockGate(inputs_per_gate)
            for j in range(inputs_per_gate):
                g.sources[j] = variables_m[j]
                variables_m[j].hitlist.append(MockProfile(g))
            gates_m.append(g)

        def propagate_naive(var, val):
            var.output = val
            queue = [var]
            while queue:
                gate = queue.pop(0)
                gate.scheduled = False
                for profile in gate.hitlist:
                    target = profile.target
                    target_output = target.process()
                    if target_output != target.output:
                        target.output = target_output
                        if not target.scheduled:
                            target.scheduled = True
                            queue.append(target)

        # Toggle all HIGH
        for v in variables_m:
            propagate_naive(v, HIGH)

        # Toggle all LOW
        for v in variables_m:
            propagate_naive(v, LOW)

        return [g.output for g in gates_m]

    book_ms, _ = timed(run_book)
    naive_ms, _ = timed(run_naive)

    return book_ms, naive_ms


def bench_book_vs_naive_chain(backend, chain_length):
    """
    Chain test: A long chain of NOT gates.
    Book: each NOT has inputlimit=1 → fast single-profile path.
    Naive: walks the chain and re-reads source output at each step.

    This shows the overhead difference in propagation approach,
    not just evaluation.
    """
    C = backend['Circuit']
    SIMULATE = backend['SIMULATE']
    HIGH = backend['HIGH']
    LOW = backend['LOW']
    UNKNOWN = backend['UNKNOWN']
    NOT_ID = backend['NOT_ID']
    VARIABLE_ID = backend['VARIABLE_ID']

    # ── BOOK (real simulator) ──
    c = C()
    c.simulate(SIMULATE)
    v = c.getcomponent(VARIABLE_ID)
    prev = v
    for _ in range(chain_length):
        g = c.getcomponent(NOT_ID)
        c.connect(g, prev, 0)
        prev = g
        
    # ── BOOK (real simulator) ──
    def run_book():
        c.toggle(v, HIGH)
        c.toggle(v, LOW)
        return prev.output

    # ── NAIVE (manual queue, check source output each step) ──
    def run_naive():
        class MockProfile:
            __slots__ = ['target']
            def __init__(self, target):
                self.target = target
                
        class MockGate:
            __slots__ = ['output', 'hitlist', 'scheduled', 'source']
            def __init__(self):
                self.output = UNKNOWN
                self.hitlist = []
                self.scheduled = False
                self.source = None

            def process(self):
                if self.source is not None and self.source.output != UNKNOWN:
                    return self.source.output ^ 1
                return UNKNOWN
                
        v_m = MockGate()
        prev_m = v_m
        for _ in range(chain_length):
            g = MockGate()
            g.source = prev_m
            prev_m.hitlist.append(MockProfile(g))
            prev_m = g
            
        def propagate_naive(val):
            v_m.output = val
            queue = [v_m]
            while queue:
                gate = queue.pop(0)
                gate.scheduled = False
                for profile in gate.hitlist:
                    target = profile.target
                    target_output = target.process()
                    if target_output != target.output:
                        target.output = target_output
                        if not target.scheduled:
                            target.scheduled = True
                            queue.append(target)
                            
        propagate_naive(HIGH)
        propagate_naive(LOW)
        return prev_m.output

    book_ms, book_result = timed(run_book)
    naive_ms, naive_result = timed(run_naive)

    return book_ms, naive_ms, book_result, naive_result


# ═══════════════════════════════════════════════════════════════════
#  RUNNER
# ═══════════════════════════════════════════════════════════════════

def run_single_backend(label, use_reactor):
    """Run all benchmarks for one backend. Return results dict."""
    print(f"\n{header(f'  {label}  ')}")

    try:
        backend = load_backend(use_reactor)
    except ImportError as e:
        print(f"  ⚠ SKIPPED — Cannot import {label}: {e}")
        return None

    results = {}
    tmp_dir = tempfile.mkdtemp()

    # ──────────────────────────────────────────
    # 1. IC CREATION
    # ──────────────────────────────────────────
    print(f"\n  {'─' * 50}")
    print(f"  IC CREATION & LOADING")
    print(f"  {'─' * 50}")

    ic_configs = [
        ("Small IC",    100,  2),    # 100 gates, 2 pin pairs
        ("Medium IC",   1_000, 4),   # 1K gates, 4 pin pairs
        ("Large IC",    10_000, 8),  # 10K gates, 8 pin pairs
        ("Massive IC",  50_000, 16), # 50K gates, 16 pin pairs
    ]

    for name, gate_count, pin_count in ic_configs:
        gc.collect()

        # Create
        create_ms, c, ic, in_pins = bench_ic_create(backend, gate_count, pin_count)

        # Save & Load
        tmp_path = os.path.join(tmp_dir, f"bench_ic_{gate_count}.json")
        save_ms, load_ms, c2, loaded = bench_ic_save_load(backend, c, ic, tmp_path)

        # Simulate (toggle first variable)
        for p in in_pins:
            v = c.getcomponent(backend['VARIABLE_ID'])
            c.connect(p, v, 0)
            
        sim_ms = 0
        if c.varlist:
            sim_start = time.perf_counter_ns()
            c.toggle(c.varlist[0], backend['HIGH'])
            sim_ms = (time.perf_counter_ns() - sim_start) / 1_000_000

        results[f'ic_create_{gate_count}'] = create_ms
        results[f'ic_save_{gate_count}'] = save_ms
        results[f'ic_load_{gate_count}'] = load_ms
        results[f'ic_sim_{gate_count}'] = sim_ms

        print(f"  {name:>12s} ({gate_count:>6,} gates, {pin_count:>2} pins):")
        print(f"    Create : {format_time(create_ms):>12s}   "
              f"Save : {format_time(save_ms):>12s}   "
              f"Load : {format_time(load_ms):>12s}   "
              f"Sim  : {format_time(sim_ms):>12s}")

        # Cleanup temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # ──────────────────────────────────────────
    # 2. CIRCUIT CREATION & LOADING
    # ──────────────────────────────────────────
    print(f"\n  {'─' * 50}")
    print(f"  CIRCUIT CREATION & LOADING")
    print(f"  {'─' * 50}")

    circuit_sizes = [
        ("Small Circuit",    1_000),
        ("Medium Circuit",   10_000),
        ("Large Circuit",    100_000),
        ("Massive Circuit",  500_000),
    ]

    for name, chain_len in circuit_sizes:
        gc.collect()

        # Create
        create_ms, c = bench_circuit_create(backend, chain_len)

        # Save & Load
        tmp_path = os.path.join(tmp_dir, f"bench_circuit_{chain_len}.json")
        save_ms, load_ms, c2 = bench_circuit_save_load(backend, c, tmp_path)

        # Simulate (toggle the variable)
        sim_start = time.perf_counter_ns()
        v = c2.varlist[0]
        c2.toggle(v, backend['HIGH'])
        sim_ms = (time.perf_counter_ns() - sim_start) / 1_000_000

        results[f'circ_create_{chain_len}'] = create_ms
        results[f'circ_save_{chain_len}'] = save_ms
        results[f'circ_load_{chain_len}'] = load_ms
        results[f'circ_sim_{chain_len}'] = sim_ms

        print(f"  {name:>16s} ({chain_len:>7,} NOT gates):")
        print(f"    Create : {format_time(create_ms):>12s}   "
              f"Save : {format_time(save_ms):>12s}   "
              f"Load : {format_time(load_ms):>12s}   "
              f"Sim  : {format_time(sim_ms):>12s}")

        # Cleanup
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Cleanup temp dir
    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass

    return results


def run_book_vs_naive(backends_available):
    """Run book vs naive comparison using the first available backend."""
    print(f"\n{header('  BOOK ALGORITHM vs NAIVE TRAVERSAL  ')}")
    print(f"  Book: O(1) incremental update per signal change")
    print(f"  Naive: O(N) full source scan per signal change\n")

    backends_to_test = []
    if 'reactor' in backends_available:
        try:
            backends_to_test.append((load_backend(use_reactor=True), "Reactor"))
        except ImportError:
            pass
            
    if 'engine' in backends_available:
        try:
            backends_to_test.append((load_backend(use_reactor=False), "Engine"))
        except ImportError:
            pass

    if not backends_to_test:
        print("  ⚠ No backend available!")
        return

    for backend, label in backends_to_test:
        print(f"\n  Using: {label}\n")

        # ── Test 1: Single large AND gate ──
        print(f"  {'─' * 56}")
        print(f"  TEST 1: Single AND Gate — Varying Input Count ({label})")
        print(f"  {'─' * 56}")
        print(f"  {'Inputs':>10}  {'Book':>12}  {'Naive':>12}  {'Speedup':>10}  {'Winner':>8}")
        print(f"  {'─'*10}  {'─'*12}  {'─'*12}  {'─'*10}  {'─'*8}")

        for input_count in [2, 4, 8, 16, 32, 64, 128]:
            gc.collect()
            book_ms, naive_ms, _, _ = bench_book_vs_naive(backend, input_count)
            speedup = naive_ms / book_ms if book_ms > 0 else float('inf')
            winner = "BOOK" if book_ms < naive_ms else "NAIVE"
            # Note: book includes full simulator overhead (object creation, profiles, etc.)
            # while naive is pure Python loops. The comparison highlights the ALGORITHM
            # difference, not the implementation overhead.
            print(f"  {input_count:>10,}  {format_time(book_ms):>12s}  "
                  f"{format_time(naive_ms):>12s}  {speedup:>9.2f}x  {winner:>8s}")

        # ── Test 2: Many gates, shared variables (fan-out) ──
        print(f"\n  {'─' * 56}")
        print(f"  TEST 2: Fan-Out — Multiple OR Gates, Shared Variables ({label})")
        print(f"  {'─' * 56}")
        print(f"  {'Gates':>8} x {'Inputs':>6}  {'Book':>12}  {'Naive':>12}  {'Speedup':>10}")
        print(f"  {'─'*8}   {'─'*6}  {'─'*12}  {'─'*12}  {'─'*10}")

        for gate_count, inputs_per in [(100, 50), (500, 20), (1_000, 10), (5_000, 10)]:
            gc.collect()
            book_ms, naive_ms = bench_book_vs_naive_multi_gate(backend, gate_count, inputs_per)
            speedup = naive_ms / book_ms if book_ms > 0 else float('inf')
            print(f"  {gate_count:>8,} x {inputs_per:>6}  {format_time(book_ms):>12s}  "
                  f"{format_time(naive_ms):>12s}  {speedup:>9.2f}x")

        # ── Test 3: NOT chain propagation ──
        print(f"\n  {'─' * 56}")
        print(f"  TEST 3: NOT Chain Propagation — Book vs Naive Walk ({label})")
        print(f"  {'─' * 56}")
        print(f"  {'Chain Len':>12}  {'Book':>12}  {'Naive':>12}  {'Speedup':>10}  {'ns/gate(B)':>11}  {'ns/gate(N)':>11}")
        print(f"  {'─'*12}  {'─'*12}  {'─'*12}  {'─'*10}  {'─'*11}  {'─'*11}")

        for chain_len in [1_000, 10_000, 100_000, 500_000]:
            gc.collect()
            book_ms, naive_ms, book_r, naive_r = bench_book_vs_naive_chain(backend, chain_len)
            speedup = naive_ms / book_ms if book_ms > 0 else float('inf')
            ns_book = (book_ms * 1_000_000) / chain_len
            ns_naive = (naive_ms * 1_000_000) / chain_len
            print(f"  {chain_len:>12,}  {format_time(book_ms):>12s}  "
                  f"{format_time(naive_ms):>12s}  {speedup:>9.2f}x  "
                  f"{ns_book:>10.1f}  {ns_naive:>10.1f}")


def run_all():
    """Main entry point."""
    print(divider())
    print(header("  DARION LOGIC SIM — BENCHMARK SUITE  "))
    print(divider())
    print(f"  Platform : {platform.system()} {platform.release()}")
    print(f"  Python   : {platform.python_version()}")
    print(f"  Time     : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(divider())

    all_results = {}

    # ── Run Engine benchmarks ──
    engine_results = run_single_backend("ENGINE (Python)", use_reactor=False)
    if engine_results:
        all_results['engine'] = engine_results

    # ── Run Reactor benchmarks ──
    reactor_results = run_single_backend("REACTOR (Cython)", use_reactor=True)
    if reactor_results:
        all_results['reactor'] = reactor_results

    # ── Head-to-head comparison (if both available) ──
    if 'engine' in all_results and 'reactor' in all_results:
        print(f"\n{header('  HEAD-TO-HEAD COMPARISON  ')}")
        e = all_results['engine']
        r = all_results['reactor']

        common_keys = sorted(set(e.keys()) & set(r.keys()))

        # Group by type
        ic_keys = [k for k in common_keys if k.startswith('ic_')]
        circ_keys = [k for k in common_keys if k.startswith('circ_')]

        for group_name, keys in [("IC Benchmarks", ic_keys), ("Circuit Benchmarks", circ_keys)]:
            if not keys:
                continue
            print(f"\n  {group_name}:")
            print(f"  {'Benchmark':<30s}  {'Engine':>12s}  {'Reactor':>12s}  {'Speedup':>10s}")
            print(f"  {'─'*30}  {'─'*12}  {'─'*12}  {'─'*10}")

            for key in keys:
                e_ms = e[key]
                r_ms = r[key]
                speedup = e_ms / r_ms if r_ms > 0 else float('inf')
                label = key.replace('_', ' ').title()
                print(f"  {label:<30s}  {format_time(e_ms):>12s}  "
                      f"{format_time(r_ms):>12s}  {speedup:>9.1f}x")

    # ── Book vs Naive ──
    run_book_vs_naive(all_results)

    # ── Final Summary ──
    print(f"\n{divider()}")
    print(f"  BENCHMARK COMPLETE")
    print(divider())


if __name__ == "__main__":
    run_all()

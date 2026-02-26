"""
DARION LOGIC SIM — BOOK ALGORITHM BENCHMARK SUITE
=================================================
Benchmarks both Engine and Reactor backends for:
  1. Book Algorithm vs Naive Traversal
  2. Fan-out tests
  3. NOT Chain Propagation

Run:
  python Testing_script/book_benchmark.py
"""

import sys
import os
import time
import gc
import platform
import statistics

# Force the standard output to use UTF-8
import sys
if hasattr(sys, 'stdout') and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
try:
    import ctypes
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
except Exception:
    pass


# ─── PATH SETUP ───────────────────────────────────────────────────
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
sys.path.append(os.path.join(root_dir, 'control'))

# ─── UTILITIES ────────────────────────────────────────────────────

def format_time(ms):
    if ms >= 1000:
        return f"{ms / 1000:.3f} s"
    elif ms >= 0.1:
        return f"{ms:.2f} ms"
    elif ms >= 0.001:
        return f"{ms * 1000:.1f} µs"
    else:
        return f"{ms * 1_000_000:.0f} ns"

def timed(func, warmup=0):
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

def divider(char='═', width=90):
    return char * width

def header(title, char='═', width=90):
    pad = (width - len(title) - 2) // 2
    return f"{char * pad} {title} {char * (width - pad - len(title) - 2)}"

# ─── BACKEND LOADER ──────────────────────────────────────────────

def load_backend(use_reactor):
    for mod_name in ['Circuit', 'IC', 'Const', 'Gates', 'Store']:
        if mod_name in sys.modules:
            del sys.modules[mod_name]

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
#  BENCHMARK: BOOK ALGORITHM vs NAIVE TRAVERSAL
# ═══════════════════════════════════════════════════════════════════

def bench_book_vs_naive(backend, input_count, chain_length=1000):
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
        for i in range(1, input_count):
            c.connect(g, high_var, i)
        prev = g
        gates.append(g)

    def run_book():
        c.toggle(toggle_var, HIGH)
        c.toggle(toggle_var, LOW)
        return gates[-1].output

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
    C = backend['Circuit']
    SIMULATE = backend['SIMULATE']
    HIGH = backend['HIGH']
    LOW = backend['LOW']
    UNKNOWN = backend['UNKNOWN']
    OR_ID = backend['OR_ID']
    VARIABLE_ID = backend['VARIABLE_ID']

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
        
    def run_book():
        for v in variables:
            c.toggle(v, HIGH)
        for v in variables:
            c.toggle(v, LOW)
        return [g.output for g in gates]

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

        for v in variables_m:
            propagate_naive(v, HIGH)
        for v in variables_m:
            propagate_naive(v, LOW)

        return [g.output for g in gates_m]

    book_ms, _ = timed(run_book)
    naive_ms, _ = timed(run_naive)

    return book_ms, naive_ms


def bench_book_vs_naive_chain(backend, chain_length):
    C = backend['Circuit']
    SIMULATE = backend['SIMULATE']
    HIGH = backend['HIGH']
    LOW = backend['LOW']
    UNKNOWN = backend['UNKNOWN']
    NOT_ID = backend['NOT_ID']
    VARIABLE_ID = backend['VARIABLE_ID']

    c = C()
    c.simulate(SIMULATE)
    v = c.getcomponent(VARIABLE_ID)
    prev = v
    for _ in range(chain_length):
        g = c.getcomponent(NOT_ID)
        c.connect(g, prev, 0)
        prev = g
        
    def run_book():
        c.toggle(v, HIGH)
        c.toggle(v, LOW)
        return prev.output

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

def run_book_vs_naive():
    print(f"\n{header('  BOOK ALGORITHM vs NAIVE TRAVERSAL  ')}")
    print(f"  Book: O(1) incremental update per signal change")
    print(f"  Naive: O(N) full source scan per signal change\n")

    backends_to_test = []
    try:
        backends_to_test.append((load_backend(use_reactor=True), "Reactor"))
    except ImportError:
        pass
        
    try:
        backends_to_test.append((load_backend(use_reactor=False), "Engine"))
    except ImportError:
        pass

    if not backends_to_test:
        print("  ⚠ No backend available!")
        return

    for backend, label in backends_to_test:
        print(f"\n  {divider('-')}")
        print(f"  BACKEND: {label}")
        print(f"  {divider('-')}")

        # ── Test 1: Single large AND gate ──
        print(f"\n  TEST 1: Single AND Gate — Varying Input Count")
        print(f"  | {'Inputs':<10} | {'Book':>12} | {'Naive':>12} | {'Speedup':>10} | {'Winner':>8} |")
        print(f"  |{'-'*12}+{'-'*14}+{'-'*14}+{'-'*12}+{'-'*10}|")

        input_counts = [2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]
        for input_count in input_counts:
            gc.collect()
            book_ms, naive_ms, _, _ = bench_book_vs_naive(backend, input_count)
            speedup = naive_ms / book_ms if book_ms > 0 else float('inf')
            winner = "BOOK" if book_ms < naive_ms else "NAIVE"
            print(f"  | {input_count:<10,} | {format_time(book_ms):>12} | {format_time(naive_ms):>12} | {speedup:>9.2f}x | {winner:>8} |")

        # ── Test 2: Many gates, shared variables (fan-out) ──
        print(f"\n  TEST 2: Fan-Out — Multiple OR Gates, Shared Variables")
        print(f"  | {'Gates x Inputs':<18} | {'Book':>12} | {'Naive':>12} | {'Speedup':>10} |")
        print(f"  |{'-'*20}+{'-'*14}+{'-'*14}+{'-'*12}|")

        configs = [(100, 50), (500, 20), (1_000, 10), (5_000, 10), (10_000, 10), (20_000, 5)]
        for gate_count, inputs_per in configs:
            gc.collect()
            book_ms, naive_ms = bench_book_vs_naive_multi_gate(backend, gate_count, inputs_per)
            speedup = naive_ms / book_ms if book_ms > 0 else float('inf')
            config_str = f"{gate_count:,} x {inputs_per}"
            print(f"  | {config_str:<18} | {format_time(book_ms):>12} | {format_time(naive_ms):>12} | {speedup:>9.2f}x |")

        # ── Test 3: NOT chain propagation ──
        print(f"\n  TEST 3: NOT Chain Propagation — Book vs Naive Walk")
        print(f"  | {'Chain Len':<12} | {'Book':>12} | {'Naive':>12} | {'Speedup':>10} | {'ns/g(B)':>10} | {'ns/g(N)':>10} |")
        print(f"  |{'-'*14}+{'-'*14}+{'-'*14}+{'-'*12}+{'-'*12}+{'-'*12}|")

        chain_lengths = [1_000, 10_000, 100_000, 500_000, 1_000_000]
        for chain_len in chain_lengths:
            gc.collect()
            book_ms, naive_ms, book_r, naive_r = bench_book_vs_naive_chain(backend, chain_len)
            speedup = naive_ms / book_ms if book_ms > 0 else float('inf')
            ns_book = (book_ms * 1_000_000) / chain_len if chain_len else 0
            ns_naive = (naive_ms * 1_000_000) / chain_len if chain_len else 0
            
            print(f"  | {chain_len:<12,} | {format_time(book_ms):>12} | {format_time(naive_ms):>12} | {speedup:>9.2f}x | {ns_book:>10.1f} | {ns_naive:>10.1f} |")


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


if __name__ == "__main__":
    run_all()

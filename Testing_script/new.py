"""
DARION LOGIC SIM — PURE THROUGHPUT BENCHMARK
Measures raw engine performance (MGates/sec) without state-sync overhead.
"""

import time
import sys
import os
import gc
import platform

# --- SETUP ---
sys.setrecursionlimit(10_000)

import argparse
parser = argparse.ArgumentParser(description='Run Pure Benchmarks')
parser.add_argument('--engine', action='store_true', help='Use Python engine backend (default: Reactor/Cython)')
args, unknown = parser.parse_known_args()

script_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(script_dir, 'reactor')) or os.path.exists(os.path.join(script_dir, 'engine')):
    root_dir = script_dir
elif getattr(sys, 'frozen', False):
    root_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
else:
    root_dir = os.path.dirname(script_dir)

sys.path.insert(0, os.path.join(root_dir, 'control'))
if args.engine:
    sys.path.insert(0, os.path.join(root_dir, 'engine'))
else:
    sys.path.insert(0, os.path.join(root_dir, 'reactor'))

try:
    import psutil
    process = psutil.Process(os.getpid())
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from Circuit import Circuit
import Const


class DarionBenchmark:
    def __init__(self):
        self.circuit = Circuit()
        self.results = []
        self.total_evals = 0
        self.total_time_ms = 0

    def print_header(self):
        print(f"\n{'='*75}")
        print(f"  DARION LOGIC SIM - RAW DOD THROUGHPUT PROFILER")
        print(f"{'='*75}")
        print(f"  System: {platform.system()} | Python {platform.python_version()}")
        if HAS_PSUTIL:
            print(f"  Base RAM: {process.memory_info().rss / 1024 / 1024:.1f} MB")
        print(f"{'-'*75}\n")

    def profile(self, name, setup_func, trigger_func):
        """Runs a setup, warms up the cache, and measures pure execution time."""
        print(f"Building {name:<35}", end="", flush=True)
        
        # NUKE THE ENTIRE ENGINE MEMORY INSTEAD OF CLEARING
        self.circuit = Circuit() 
        setup_func(self.circuit)
        
        # Force GC before run to prevent mid-benchmark collections
        gc.collect()
        gc.disable()
        
        has_hw_counter = hasattr(self.circuit, 'eval_count')
        start_evals = self.circuit.eval_count if has_hw_counter else 0
        
        # Benchmark Execution
        start_ns = time.perf_counter_ns()
        trigger_func(self.circuit)
        end_ns = time.perf_counter_ns()
        
        gc.enable()
        
        duration_ms = (end_ns - start_ns) / 1_000_000
        evals = (self.circuit.eval_count - start_evals) if has_hw_counter else 0
        
        # Calculate MGates/sec (Millions of gates evaluated per second)
        mgates_sec = (evals / (duration_ms / 1000)) / 1_000_000 if duration_ms > 0 else 0
        
        self.results.append({
            'name': name,
            'time': duration_ms,
            'evals': evals,
            'mgates': mgates_sec
        })
        
        self.total_evals += evals
        self.total_time_ms += duration_ms
        
        print(f"\r[DONE] {name:<35} | {duration_ms:>8.2f} ms | {mgates_sec:>8.2f} MG/s")

    # =========================================================================
    # TOPOLOGY SETUPS
    # =========================================================================
    def bench_marathon(self, count=100_000):
        trigger_gate = []
        def setup(c):
            inp = c.getcomponent(Const.VARIABLE_ID)
            prev = inp
            for _ in range(count):
                g = c.getcomponent(Const.NOT_ID)
                c.connect(g, prev, 0)
                prev = g
            c.simulate(Const.SIMULATE)
            c.toggle(inp, 0)
            c.toggle(inp, 1) # Warmup
            c.toggle(inp, 0)
            trigger_gate.append(inp)
            
        self.profile(f"Marathon ({count//1000}K NOT Chain)", setup, lambda c: c.toggle(trigger_gate[0], 1))

    def bench_avalanche(self, layers=18):
        trigger_gate = []
        def setup(c):
            root = c.getcomponent(Const.VARIABLE_ID)
            const_high = c.getcomponent(Const.VARIABLE_ID)
            
            layer = [root]
            for _ in range(layers):
                next_l = []
                for p in layer:
                    g1 = c.getcomponent(Const.AND_ID); c.connect(g1, p, 0); c.connect(g1, const_high, 1)
                    g2 = c.getcomponent(Const.AND_ID); c.connect(g2, p, 0); c.connect(g2, const_high, 1)
                    next_l.extend([g1, g2])
                layer = next_l
                
            # Inject state AFTER connections are made
            c.toggle(const_high, Const.HIGH) 
            c.simulate(Const.SIMULATE)
            
            c.toggle(root, 0)
            c.toggle(root, 1) # Warmup
            c.toggle(root, 0)
            trigger_gate.append(root)
            
        total_gates = (2**layers)-1
        self.profile(f"Avalanche ({total_gates//1000}K Tree)", setup, lambda c: c.toggle(trigger_gate[0], 1))

    def bench_gridlock(self, size=200):
        trigger_gate = []
        def setup(c):
            grid = [[None]*size for _ in range(size)]
            trig = c.getcomponent(Const.VARIABLE_ID)
            const_low = c.getcomponent(Const.VARIABLE_ID)
            c.toggle(const_low, Const.LOW)

            for r in range(size):
                for k in range(size):
                    grid[r][k] = c.getcomponent(Const.OR_ID)
            
            for r in range(size):
                for k in range(size):
                    g = grid[r][k]
                    if r > 0: c.connect(g, grid[r-1][k], 0)
                    elif r == 0 and k == 0: c.connect(g, trig, 0)
                    else: c.connect(g, const_low, 0)
                    
                    if k > 0: c.connect(g, grid[r][k-1], 1)
                    else: c.connect(g, const_low, 1)
                    
            c.simulate(Const.SIMULATE)
            c.toggle(trig, 0)
            c.toggle(trig, 1) # Warmup
            c.toggle(trig, 0)
            trigger_gate.append(trig)

        self.profile(f"Gridlock ({size}x{size} Mesh)", setup, lambda c: c.toggle(trigger_gate[0], 1))

    def bench_echo_chamber(self, count=10_000):
        trigger_gate = []
        def setup(c):
            set_line = c.getcomponent(Const.VARIABLE_ID)
            rst_line = c.getcomponent(Const.VARIABLE_ID)
            for _ in range(count):
                q = c.getcomponent(Const.NOR_ID)
                qb = c.getcomponent(Const.NOR_ID)
                c.connect(q, rst_line, 0)
                c.connect(qb, set_line, 0)
                c.connect(q, qb, 1)
                c.connect(qb, q, 1)
            c.simulate(Const.SIMULATE)
            c.toggle(set_line, 0)
            c.toggle(rst_line, 1)
            c.toggle(rst_line, 0)
            # Warmup
            c.toggle(set_line, 1)
            c.toggle(set_line, 0)
            trigger_gate.append(set_line)

        self.profile(f"Echo Chamber ({count//1000}K SR Latches)", setup, lambda c: c.toggle(trigger_gate[0], 1))

    def bench_black_hole(self, inputs=100_000):
        trigger_gate = []
        def setup(c):
            black_hole = c.getcomponent(Const.AND_ID)
            c.setlimits(black_hole, inputs)
            vars_list = []
            for i in range(inputs):
                v = c.getcomponent(Const.VARIABLE_ID)
                c.connect(black_hole, v, i)
                vars_list.append(v)
            c.simulate(Const.SIMULATE)
            for i in range(inputs - 1):
                c.toggle(vars_list[i], 1)
            trigger = vars_list[-1]
            c.toggle(trigger, 1) # Warmup
            c.toggle(trigger, 0)
            trigger_gate.append(trigger)

        self.profile(f"Black Hole ({inputs//1000}K Inputs)", setup, lambda c: c.toggle(trigger_gate[0], 1))

    def bench_paradox_burn(self):
        trigger_gate = []
        def setup(c):
            source = c.getcomponent(Const.VARIABLE_ID)
            xor_gate = c.getcomponent(Const.XOR_ID)
            c.connect(xor_gate, source, 0)
            c.connect(xor_gate, xor_gate, 1)
            c.simulate(Const.SIMULATE)
            trigger_gate.append(source)

        def trigger(c):
            try:
                c.toggle(trigger_gate[0], 1)
            except RecursionError:
                pass
            except Exception:
                pass

        self.profile("Paradox (XOR loop)", setup, trigger)

    def bench_mega_chain(self):
        count = 1_000_000
        trigger_gate = []
        def setup(c):
            inp = c.getcomponent(Const.VARIABLE_ID)
            prev = inp
            for i in range(count):
                g = c.getcomponent(Const.NOT_ID)
                c.connect(g, prev, 0)
                prev = g
            c.simulate(Const.SIMULATE)
            c.toggle(inp, 0)
            c.toggle(inp, 1)
            c.toggle(inp, 0)
            trigger_gate.append(inp)
            
        self.profile(f"Mega Chain ({count//1_000_000}M NOT Gates)", setup, lambda c: c.toggle(trigger_gate[0], 1))

    def bench_extreme_fanout(self, count=50_000):
        trigger_gate = []
        def setup(c):
            v = c.getcomponent(Const.VARIABLE_ID)
            const_high = c.getcomponent(Const.VARIABLE_ID)
            c.toggle(const_high, Const.HIGH)
            for _ in range(count):
                g = c.getcomponent(Const.AND_ID)
                c.connect(g, v, 0)
                c.connect(g, const_high, 1)
            c.simulate(Const.SIMULATE)
            c.toggle(v, 0)
            c.toggle(v, 1) # Warmup
            c.toggle(v, 0)
            trigger_gate.append(v)
            
        self.profile(f"Extreme Fanout ({count//1000}K Targets)", setup, lambda c: c.toggle(trigger_gate[0], 1))

    def bench_extreme_fanin(self, count=50_000):
        trigger_gate = []
        def setup(c):
            g = c.getcomponent(Const.AND_ID)
            c.setlimits(g, count)
            vars_list = []
            for i in range(count):
                v = c.getcomponent(Const.VARIABLE_ID)
                c.connect(g, v, i)
                vars_list.append(v)
            c.simulate(Const.SIMULATE)
            for v in vars_list:
                c.toggle(v, 1)
            c.toggle(vars_list[0], 0)
            c.toggle(vars_list[0], 1)
            trigger_gate.append(vars_list[0])

        self.profile(f"Extreme Fan-in ({count//1000}K Inputs)", setup, lambda c: c.toggle(trigger_gate[0], 0))

    def bench_extreme_fanin_fanout(self, count=50_000):
        trigger_gate = []
        def setup(c):
            central = c.getcomponent(Const.AND_ID)
            c.setlimits(central, count)
            const_high = c.getcomponent(Const.VARIABLE_ID)
            c.toggle(const_high, Const.HIGH)
            
            inputs_list = []
            for i in range(count):
                v = c.getcomponent(Const.VARIABLE_ID)
                c.connect(central, v, i)
                inputs_list.append(v)
            
            for i in range(count):
                g = c.getcomponent(Const.AND_ID)
                c.connect(g, central, 0)
                c.connect(g, const_high, 1)
            
            c.simulate(Const.SIMULATE)
            for v in inputs_list:
                c.toggle(v, 1)
            
            c.toggle(inputs_list[0], 0)
            c.toggle(inputs_list[0], 1)
            trigger_gate.append(inputs_list[0])

        self.profile(f"Ext. Fan-in+Out ({count//1000}K In/Out)", setup, lambda c: c.toggle(trigger_gate[0], 0))

    def bench_cpu_datapath(self, bit_width=8192):
        clock_trigger = []
        def setup(c):
            clock = c.getcomponent(Const.VARIABLE_ID)
            c.toggle(clock, Const.LOW)
            prev_carry = c.getcomponent(Const.VARIABLE_ID)
            c.toggle(prev_carry, Const.LOW)
            
            a_inputs, b_inputs = [], []
            for i in range(bit_width):
                a = c.getcomponent(Const.VARIABLE_ID)
                b = c.getcomponent(Const.VARIABLE_ID)
                a_inputs.append(a)
                b_inputs.append(b)
                
                xor1 = c.getcomponent(Const.XOR_ID)
                c.connect(xor1, a, 0); c.connect(xor1, b, 1)
                sum_g = c.getcomponent(Const.XOR_ID)
                c.connect(sum_g, xor1, 0); c.connect(sum_g, prev_carry, 1)
                and1 = c.getcomponent(Const.AND_ID)
                c.connect(and1, a, 0); c.connect(and1, b, 1)
                and2 = c.getcomponent(Const.AND_ID)
                c.connect(and2, prev_carry, 0); c.connect(and2, xor1, 1)
                cout = c.getcomponent(Const.OR_ID)
                c.connect(cout, and1, 0); c.connect(cout, and2, 1)
                prev_carry = cout
                
                set_g = c.getcomponent(Const.AND_ID)
                c.connect(set_g, sum_g, 0); c.connect(set_g, clock, 1)
                not_sum = c.getcomponent(Const.NOT_ID)
                c.connect(not_sum, sum_g, 0)
                rst_g = c.getcomponent(Const.AND_ID)
                c.connect(rst_g, not_sum, 0); c.connect(rst_g, clock, 1)
                q = c.getcomponent(Const.NOR_ID)
                qb = c.getcomponent(Const.NOR_ID)
                c.connect(q, rst_g, 0); c.connect(q, qb, 1)
                c.connect(qb, set_g, 0); c.connect(qb, q, 1)

            c.simulate(Const.SIMULATE)
            for a in a_inputs: c.toggle(a, Const.HIGH)
            for b in b_inputs: c.toggle(b, Const.LOW)
            
            # Fire the ripple cascade once as warmup/setup
            c.toggle(b_inputs[0], Const.HIGH)
            clock_trigger.append(clock)
            
        # Benchmark the massive parallel fanout of clocking 8192 registers simultaneously
        self.profile(f"CPU Datapath ({bit_width}-bit Clock Trigger)", setup, lambda c: c.toggle(clock_trigger[0], Const.HIGH))

    def bench_cache_thrashing(self, count=20_000):
        trigger_gate = []
        def setup(c):
            root = c.getcomponent(Const.VARIABLE_ID)
            const_high = c.getcomponent(Const.VARIABLE_ID)
            c.toggle(const_high, Const.HIGH)
            const_low = c.getcomponent(Const.VARIABLE_ID)
            c.toggle(const_low, Const.LOW)
            
            prev = root
            for i in range(count):
                if i % 2 == 0:
                    g = c.getcomponent(Const.AND_ID)
                    c.connect(g, prev, 0)
                    c.connect(g, const_high, 1)
                else:
                    g = c.getcomponent(Const.OR_ID)
                    c.connect(g, prev, 0)
                    c.connect(g, const_low, 1)
                prev = g
            c.simulate(Const.SIMULATE)
            c.toggle(root, 0)
            c.toggle(root, 1)
            c.toggle(root, 0)
            trigger_gate.append(root)

        self.profile(f"Cache Thrashing ({count//1000}K Layers)", setup, lambda c: c.toggle(trigger_gate[0], 1))

    def print_summary(self):
        print(f"\n{'='*75}")
        print(f"  PERFORMANCE SUMMARY")
        print(f"{'='*75}")
        print(f"  {'Topology':<35} | {'Evals':>10} | {'Time (ms)':>9} | {'MGates/s':>10}")
        print(f"  {'-'*35}-+-{'-'*10}-+-{'-'*9}-+-{'-'*10}")
        
        for r in self.results:
            print(f"  {r['name']:<35} | {r['evals']:>10,} | {r['time']:>9.2f} | {r['mgates']:>10.2f}")
            
        print(f"  {'-'*35}-+-{'-'*10}-+-{'-'*9}-+-{'-'*10}")
        
        avg_throughput = (self.total_evals / (self.total_time_ms / 1000) / 1_000_000) if self.total_time_ms > 0 else 0
        print(f"  {'TOTALS / AVG THROUGHPUT':<35} | {self.total_evals:>10,} | {self.total_time_ms:>9.2f} | {avg_throughput:>10.2f}")
        
        if HAS_PSUTIL:
            print(f"\n  Final RAM Usage: {process.memory_info().rss / 1024 / 1024:.1f} MB")
        print(f"{'='*75}\n")

    def run(self):
        self.print_header()
        self.bench_cache_thrashing(count=20_000)
        
        self.bench_marathon(count=100_000)
        self.bench_avalanche(layers=18)
        self.bench_gridlock(size=200)
        self.bench_echo_chamber(count=10_000)
        self.bench_black_hole(inputs=100_000)
        self.bench_paradox_burn()
        self.bench_mega_chain()
        self.bench_extreme_fanout(count=50_000)
        self.bench_extreme_fanin(count=50_000)
        self.bench_extreme_fanin_fanout(count=50_000)
        self.bench_cpu_datapath(bit_width=8192)
        
        self.print_summary()

if __name__ == "__main__":
    benchmark = DarionBenchmark()
    try:
        benchmark.run()
    except KeyboardInterrupt:
        print("\n[!] Benchmark Aborted.")
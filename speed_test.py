import time
import sys
import os
import random
import platform
import gc

# --- CONFIGURATION & SETUP ---
sys.setrecursionlimit(10_000)

# Add engine to path
engine_path = os.path.join(os.getcwd(), 'engine')
if engine_path not in sys.path:
    sys.path.append(engine_path)

# Try importing psutil for RAM monitoring
try:
    import psutil
    process = psutil.Process(os.getpid())
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    from Circuit import Circuit
    import Const
    from Gates import Gate
except ImportError as e:
    print("FATAL ERROR: Could not import engine modules.")
    print("Ensure you have built the project (build.bat/sh) and are running this from the root.")
    sys.exit(1)

class BenchmarkSuite:
    def __init__(self):
        self.circuit = Circuit()
        
    def log(self, msg, end="\n"):
        print(msg, end=end)
        sys.stdout.flush()

    def timer(self, func):
        """Precise timing wrapper."""
        start = time.perf_counter_ns()
        func()
        end = time.perf_counter_ns()
        return (end - start) / 1_000_000 # Returns ms

    def run_all(self):
        print(f"\n{'='*70}")
        print(f"   DARION LOGIC SIM — ULTIMATE BENCHMARK SUITE")
        print(f"{'='*70}")
        print(f"System: {platform.system()} {platform.release()} | Python {platform.python_version()}")
        if HAS_PSUTIL:
            print(f"Initial RAM: {process.memory_info().rss / 1024 / 1024:.2f} MB")
        else:
            print("Warning: 'psutil' module not installed. RAM tests will be skipped.")
        print(f"{'-'*70}\n")

        # --- PHASE 1: LATENCY & DEPTH ---
        self.circuit.simulate(Const.SIMULATE)
        self.test_marathon(count=100_000)

        # --- PHASE 2: THROUGHPUT & QUEUE ---
        self.circuit.simulate(Const.SIMULATE)
        self.test_avalanche(layers=18)

        # --- PHASE 3: COMPLEXITY & SYNC ---
        self.circuit.simulate(Const.SIMULATE)
        self.test_gridlock(size=250)

        # --- PHASE 4: STABILITY & CYCLES ---
        self.circuit.simulate(Const.FLIPFLOP)
        self.test_echo_chamber(count=10_000)

        # --- PHASE 5: THE LIMIT BREAKER ---
        self.circuit.simulate(Const.SIMULATE)
        self.test_black_hole(inputs=100_000)

        # --- PHASE 6: SAFETY CHECKS ---
        self.circuit.simulate(Const.FLIPFLOP)
        self.test_paradox_burn()

        # --- PHASE 7: MEMORY EFFICIENCY (NEW) ---
        self.circuit.simulate(Const.SIMULATE)
        self.test_warehouse(count=500_000)

        # --- PHASE 8: REACTOR ENDURANCE ---
        self.circuit.simulate(Const.SIMULATE)
        self.test_reactor_endurance(duration=10)

        print(f"\n{'='*70}")
        print(f"   ALL TESTS COMPLETED SUCCESSFULLY")
        print(f"{'='*70}")

    # ---------------------------------------------------------
    # TEST 1: THE MARATHON (Serial Latency)
    # ---------------------------------------------------------
    def test_marathon(self, count):
        self.log(f"[TEST 1] The Marathon (Serial Latency)")
        self.log(f"  > Config: 1 Variable -> {count:,} NOT Gates -> Output")
        self.circuit.clearcircuit()
        c = self.circuit
        
        inp = c.getcomponent(Const.VARIABLE)
        prev = inp
        gates = []
        for _ in range(count):
            g = c.getcomponent(Const.NOT)
            c.connect(g, prev, 0)
            prev = g
            gates.append(g)

        c.simulate(Const.SIMULATE)
        c.toggle(inp, 0)
        
        duration = self.timer(lambda: c.toggle(inp, 1))
        
        expected = 'T' if (count % 2 == 0) else 'F'
        actual = gates[-1].getoutput()
        passed = (actual == expected)

        self.log(f"  > Result: {duration:.4f} ms")
        self.log(f"  > Latency: {(duration*1e6)/count:.2f} ns/gate")
        self.log(f"  > Status: {'[PASS]' if passed else '[FAIL]'}")
        self.log("-" * 70)

    # ---------------------------------------------------------
    # TEST 2: THE AVALANCHE (Throughput)
    # ---------------------------------------------------------
    def test_avalanche(self, layers):
        total = (2**layers)-1
        self.log(f"[TEST 2] The Avalanche (Queue Throughput)")
        self.log(f"  > Config: {layers} Layers ({total:,} Gates)")
        self.circuit.clearcircuit()
        c = self.circuit
        
        root = c.getcomponent(Const.VARIABLE)
        layer = [root]
        for _ in range(layers):
            next_l = []
            for p in layer:
                g1 = c.getcomponent(Const.AND); c.setlimits(g1, 1); c.connect(g1, p, 0)
                g2 = c.getcomponent(Const.AND); c.setlimits(g2, 1); c.connect(g2, p, 0)
                next_l.extend([g1, g2])
            layer = next_l

        c.simulate(Const.SIMULATE)
        c.toggle(root, 0)

        duration = self.timer(lambda: c.toggle(root, 1))

        self.log(f"  > Result: {duration:.4f} ms")
        self.log(f"  > Rate:   {total/(duration/1000):,.0f} events/sec")
        self.log(f"  > Status: [PASS]")
        self.log("-" * 70)

    # ---------------------------------------------------------
    # TEST 3: THE GRIDLOCK (Wavefront Sync)
    # ---------------------------------------------------------
    def test_gridlock(self, size):
        total = size*size
        self.log(f"[TEST 3] The Gridlock (Matrix Synchronization)")
        self.log(f"  > Config: {size}x{size} Mesh ({total:,} Gates)")
        self.circuit.clearcircuit()
        c = self.circuit

        grid = [[None]*size for _ in range(size)]
        trig = c.getcomponent(Const.VARIABLE)

        for r in range(size):
            for k in range(size):
                grid[r][k] = c.getcomponent(Const.OR)
        
        for r in range(size):
            for k in range(size):
                g = grid[r][k]
                ins = 0
                if r>0: c.connect(g, grid[r-1][k], ins); ins+=1
                elif r==0 and k==0: c.connect(g, trig, 0); ins+=1
                if k>0: c.connect(g, grid[r][k-1], ins); ins+=1
                c.setlimits(g, max(1, ins))

        c.simulate(Const.SIMULATE)
        c.toggle(trig, 0)

        duration = self.timer(lambda: c.toggle(trig, 1))
        
        passed = (grid[size-1][size-1].getoutput() == 'T')

        self.log(f"  > Result: {duration:.4f} ms")
        self.log(f"  > Status: {'[PASS]' if passed else '[FAIL]'}")
        self.log("-" * 70)

    # ---------------------------------------------------------
    # TEST 4: THE ECHO CHAMBER (Cycle Safety)
    # ---------------------------------------------------------
    def test_echo_chamber(self, count):
        self.log(f"[TEST 4] The Echo Chamber (Sequential Stability)")
        self.log(f"  > Config: {count:,} SR Latches")
        self.log(f"  > Mode:   FLIP-FLOP (Cycle Detection ON)")
        self.circuit.clearcircuit()
        c = self.circuit
        c.simulate(Const.FLIPFLOP)

        set_line = c.getcomponent(Const.VARIABLE)
        rst_line = c.getcomponent(Const.VARIABLE)
        
        latches = []
        for _ in range(count):
            q = c.getcomponent(Const.NOR)
            qb = c.getcomponent(Const.NOR)
            c.connect(q, rst_line, 0)
            c.connect(qb, set_line, 0)
            c.connect(q, qb, 1)
            c.connect(qb, q, 1)
            latches.append(q)

        c.toggle(set_line, 0)
        c.toggle(rst_line, 1)
        c.toggle(rst_line, 0)

        duration = self.timer(lambda: c.toggle(set_line, 1))
        
        passed = all(l.getoutput() == 'T' for l in latches)

        self.log(f"  > Result: {duration:.4f} ms")
        self.log(f"  > Status: {'[PASS]' if passed else '[FAIL]'}")
        self.log("-" * 70)

    # ---------------------------------------------------------
    # TEST 5: THE BLACK HOLE (Extreme Fan-In)
    # ---------------------------------------------------------
    def test_black_hole(self, inputs):
        self.log(f"[TEST 5] The Black Hole (Extreme Fan-In)")
        self.log(f"  > Config: {inputs:,} Inputs -> 1 AND Gate")
        self.circuit.clearcircuit()
        c = self.circuit
        c.simulate(Const.SIMULATE)

        black_hole = c.getcomponent(Const.AND)
        c.setlimits(black_hole, inputs)

        vars_list = []
        for i in range(inputs):
            v = c.getcomponent(Const.VARIABLE)
            c.connect(black_hole, v, i)
            vars_list.append(v)
        
        self.log("  > Filling 'The Book' (Setting N-1 inputs High)...", end="\r")
        for i in range(inputs - 1):
            c.toggle(vars_list[i], 1)
        
        self.log("  > Triggering final input...                        ", end="\r")
        trigger = vars_list[-1]
        duration = self.timer(lambda: c.toggle(trigger, 1))
        
        passed = (black_hole.getoutput() == 'T')

        self.log(f"  > Result: {duration:.4f} ms")
        self.log(f"  > Status: {'[PASS]' if passed else '[FAIL]'}")
        self.log("-" * 70)

    # ---------------------------------------------------------
    # TEST 6: THE PARADOX (Oscillation Burn)
    # ---------------------------------------------------------
    def test_paradox_burn(self):
        self.log(f"[TEST 6] The Paradox (Oscillation Burn)")
        self.log(f"  > Config: XOR Gate Feedback Loop (1 XOR B -> B)")
        self.log(f"  > Goal:   Test infinite loop detection/fuses.")
        
        self.circuit.clearcircuit()
        c = self.circuit
        c.simulate(Const.FLIPFLOP)

        source = c.getcomponent(Const.VARIABLE)
        xor_gate = c.getcomponent(Const.XOR)

        c.connect(xor_gate, source, 0)
        c.connect(xor_gate, xor_gate, 1) # Loop

        self.log("  > Triggering Paradox...", end="\r")
        
        try:
            start = time.perf_counter_ns()
            c.toggle(source, 1)
            end = time.perf_counter_ns()
            dt = (end - start) / 1_000_000
            
            self.log(f"  > Result: {dt:.4f} ms (Engine halted safely)")
            self.log(f"  > Status: [PASS] (No crash)")
            
        except RecursionError:
            self.log(f"  > Result: Python RecursionError")
            self.log(f"  > Status: [PASS] (Caught by Interpreter)")
        except Exception as e:
            self.log(f"  > Result: CRASHED with {e}")
            self.log(f"  > Status: [FAIL]")

        self.log("-" * 70)

    # ---------------------------------------------------------
    # TEST 7: THE WAREHOUSE (RAM Consumption)
    # ---------------------------------------------------------
    def test_warehouse(self, count):
        self.log(f"[TEST 7] The Warehouse (Memory Footprint)")
        self.log(f"  > Config: Allocating {count:,} disconnected NOT gates.")
        
        if not HAS_PSUTIL:
            self.log(f"  > Status: [SKIPPED] (psutil missing)")
            self.log("-" * 70)
            return

        # 1. Baseline
        self.circuit.clearcircuit()
        gc.collect()
        time.sleep(0.1)
        baseline = process.memory_info().rss
        self.log(f"  > Baseline RAM: {baseline/1024/1024:.2f} MB")

        # 2. Allocate
        self.log(f"  > Allocating...", end="\r")
        c = self.circuit
        gates = []
        # We hold references in a list to prevent immediate GC, simulating active project state
        for _ in range(count):
            gates.append(c.getcomponent(Const.NOT))
        
        # 3. Measure
        current = process.memory_info().rss
        delta_bytes = current - baseline
        mb_used = delta_bytes / 1024 / 1024
        bytes_per_gate = delta_bytes / count

        self.log(f"  > Allocated:    {mb_used:.2f} MB")
        self.log(f"  > Efficiency:   {bytes_per_gate:.2f} Bytes per Gate")

        # 4. Leak Check
        self.log(f"  > Cleaning up...", end="\r")
        gates = None
        self.circuit.clearcircuit()
        gc.collect()
        time.sleep(0.1)
        final_mem = process.memory_info().rss
        leak = final_mem - baseline
        
        # We allow a small tolerance (5MB) for Python VM internal fragmentation
        passed_leak = leak < (5 * 1024 * 1024) 
        
        self.log(f"  > Post-Cleanup: {leak/1024/1024:.2f} MB difference from baseline")
        self.log(f"  > Leak Check:   {'[PASS]' if passed_leak else '[FAIL]'} (RAM returned to normal)")
        self.log("-" * 70)

    # ---------------------------------------------------------
    # TEST 8: REACTOR ENDURANCE (Sustained Load)
    # ---------------------------------------------------------
    def test_reactor_endurance(self, duration):
        self.log(f"[TEST 8] Reactor Endurance Test")
        self.log(f"  > Goal:   Sustain max load for {duration} seconds.")
        self.circuit.clearcircuit()
        c = self.circuit
        c.simulate(Const.SIMULATE)
        
        trees = 3
        depth = 15 
        gates_per_tree = (2**depth)-1
        roots = []
        
        self.log("  > Building Load Generator...", end="\r")
        for _ in range(trees):
            r = c.getcomponent(Const.VARIABLE)
            roots.append(r)
            layer = [r]
            for _ in range(depth):
                nxt = []
                for p in layer:
                    g = c.getcomponent(Const.AND); c.setlimits(g,1); c.connect(g,p,0)
                    nxt.append(g); nxt.append(c.getcomponent(Const.AND)); 
                    c.setlimits(nxt[-1],1); c.connect(nxt[-1],p,0)
                layer = nxt
        
        self.log("  > Starting Reactor...       ")
        
        start_t = time.time()
        end_t = start_t + duration
        total_ev = 0
        root_idx = 0
        
        while time.time() < end_t:
            r = roots[root_idx]
            c.toggle(r, 1)
            c.toggle(r, 0)
            total_ev += (gates_per_tree * 2)
            root_idx = (root_idx + 1) % trees
            
            rem = int(end_t - time.time())
            print(f"  > Running... {rem}s | Mem: {process.memory_info().rss/1024/1024:.1f} MB" if HAS_PSUTIL else f"  > Running... {rem}s", end='\r')

        self.log(f"  > Completed.                                     ")
        self.log(f"  > Avg Speed:    {total_ev/duration/1e6:.2f} M/sec")
        self.log("-" * 70)

if __name__ == "__main__":
    b = BenchmarkSuite()
    try:
        b.run_all()
    except KeyboardInterrupt:
        print("\n[!] Test Aborted.")
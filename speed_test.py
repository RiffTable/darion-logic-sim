import time
import sys
import os
import random

# --- CONFIGURATION ---
engine_path = os.path.join(os.getcwd(), 'engine')
if engine_path not in sys.path:
    sys.path.append(engine_path)

try:
    from Circuit import Circuit
    import Const
    from Gates import Gate
except ImportError as e:
    print("FATAL ERROR: Could not import engine modules.")
    sys.exit(1)

class StressTest:
    def __init__(self):
        self.circuit = Circuit()

    def run(self):
        print(f"\n{'#'*60}")
        print(f"   DARION LOGIC SIM — EXTREME STRESS TEST")
        print(f"{'#'*60}\n")
        
        # 1. The Marathon (100k Serial Gates)
        self.circuit.simulate(Const.SIMULATE) # DAG Mode
        self.test_marathon(count=100_000)

        # 2. The Avalanche (Binary Tree, ~260k Gates)
        self.circuit.simulate(Const.SIMULATE) # DAG Mode
        self.test_avalanche(layers=18) 

        # 3. The Gridlock (Mesh Propagation, 250x250)
        self.circuit.simulate(Const.SIMULATE) # DAG Mode
        self.test_gridlock(size=250)

        # 4. The Echo Chamber (Sequential SR Latches)
        self.circuit.simulate(Const.FLIPFLOP) # Cycle-Safe Mode
        self.test_echo_chamber(count=10_000)

        print(f"\n{'#'*60}")
        print(f"   STRESS TEST COMPLETE")
        print(f"{'#'*60}")

    def timer(self, name, func):
        """Helper to measure execution time of a specific action."""
        start = time.perf_counter_ns()
        func()
        end = time.perf_counter_ns()
        dt_ms = (end - start) / 1_000_000
        return dt_ms

    # ---------------------------------------------------------
    # TEST 1: THE MARATHON (Serial)
    # ---------------------------------------------------------
    def test_marathon(self, count):
        print(f"[TEST 1] The Marathon (Serial Chain)")
        print(f"Config: 1 Variable -> {count:,} NOT Gates -> Output")
        print(f"Mode:   SIMULATION (Fast, No loop checks)")
        
        print("Status: Building circuit...", end='\r')
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

        print(f"Status: Initializing...                             ", end='\r')
        c.simulate(Const.SIMULATE)
        c.toggle(inp, 0)

        print(f"Status: Running Engine...                           ", end='\r')
        def run_sim():
            c.toggle(inp, 1)

        duration = self.timer("Marathon", run_sim)

        expected = 'T' if (count % 2 == 0) else 'F'
        actual = gates[-1].getoutput()
        passed = (actual == expected)

        print(f"Status: DONE                                        ")
        print(f"  > Total Time:       {duration:.4f} ms")
        print(f"  > Latency/Gate:     {(duration * 1_000_000) / count:.2f} ns")
        print(f"  > Logic Check:      {'PASS' if passed else 'FAIL'}")
        print("-" * 60)

    # ---------------------------------------------------------
    # TEST 2: THE AVALANCHE (Tree)
    # ---------------------------------------------------------
    def test_avalanche(self, layers):
        total_gates = (2 ** layers) - 1
        print(f"\n[TEST 2] The Avalanche (Binary Tree)")
        print(f"Config: {layers} Layers ({total_gates:,} Gates)")
        print(f"Mode:   SIMULATION (Fast, No loop checks)")
        
        print("Status: Building circuit...", end='\r')
        self.circuit.clearcircuit()
        c = self.circuit

        root_inp = c.getcomponent(Const.VARIABLE)
        current_layer = [root_inp]
        all_gates = []

        for i in range(layers):
            next_layer = []
            for parent in current_layer:
                g1 = c.getcomponent(Const.AND)
                c.setlimits(g1, 1)
                c.connect(g1, parent, 0)
                next_layer.append(g1)
                all_gates.append(g1)

                g2 = c.getcomponent(Const.AND)
                c.setlimits(g2, 1)
                c.connect(g2, parent, 0)
                next_layer.append(g2)
                all_gates.append(g2)
            current_layer = next_layer
        
        print(f"Status: Initializing...                             ", end='\r')
        c.simulate(Const.SIMULATE)
        c.toggle(root_inp, 0)

        print(f"Status: TRIGGERING AVALANCHE...                     ", end='\r')
        def run_sim():
            c.toggle(root_inp, 1)
        duration = self.timer("Avalanche", run_sim)

        sample = random.choice(current_layer)
        actual = sample.getoutput()
        passed = (actual == 'T')

        print(f"Status: DONE                                        ")
        print(f"  > Execution Time:   {duration:.4f} ms")
        if duration > 0:
            print(f"  > Event Rate:       {len(all_gates) / (duration/1000):,.0f} events/sec")
        print(f"  > Logic Check:      {'PASS' if passed else 'FAIL'}")
        print("-" * 60)

    # ---------------------------------------------------------
    # TEST 3: THE GRIDLOCK (Mesh)
    # ---------------------------------------------------------
    def test_gridlock(self, size):
        total_gates = size * size
        print(f"\n[TEST 3] The Gridlock (Mesh Matrix)")
        print(f"Config: {size}x{size} Grid ({total_gates:,} Gates)")
        print(f"Mode:   SIMULATION (Fast, No loop checks)")

        print("Status: Building circuit...", end='\r')
        self.circuit.clearcircuit()
        c = self.circuit

        grid = [[None for _ in range(size)] for _ in range(size)]
        trigger = c.getcomponent(Const.VARIABLE)

        for r in range(size):
            for col in range(size):
                g = c.getcomponent(Const.OR)
                grid[r][col] = g

        for r in range(size):
            for col in range(size):
                g = grid[r][col]
                inputs_needed = 0
                if r > 0:
                    c.connect(g, grid[r-1][col], inputs_needed)
                    inputs_needed += 1
                elif r == 0 and col == 0:
                    c.connect(g, trigger, 0)
                    inputs_needed += 1
                if col > 0:
                    c.connect(g, grid[r][col-1], inputs_needed)
                    inputs_needed += 1
                c.setlimits(g, max(1, inputs_needed))

        print(f"Status: Initializing...                                   ", end='\r')
        c.simulate(Const.SIMULATE)
        c.toggle(trigger, 0)

        print(f"Status: Running Engine...                                 ", end='\r')
        def run_sim():
            c.toggle(trigger, 1)
        duration = self.timer("Gridlock", run_sim)

        last_gate = grid[size-1][size-1]
        passed = (last_gate.getoutput() == 'T')

        print(f"Status: DONE                                              ")
        print(f"  > Execution Time:   {duration:.4f} ms")
        print(f"  > Logic Check:      {'PASS' if passed else 'FAIL'}")
        print("-" * 60)

    # ---------------------------------------------------------
    # TEST 4: THE ECHO CHAMBER (Sequential Logic)
    # ---------------------------------------------------------
    def test_echo_chamber(self, count):
        print(f"\n[TEST 4] The Echo Chamber (Sequential Latches)")
        print(f"Config: {count:,} SR Latches (Cross-coupled NORs)")
        print(f"Mode:   FLIP-FLOP (Cycle detection overhead ACTIVE)")
        print(f"Goal:   Test stability of {count*2:,} gates with feedback loops.")
        
        print("Status: Building circuit... (This is slow in Python)", end='\r')
        self.circuit.clearcircuit()
        c = self.circuit
        c.simulate(Const.FLIPFLOP) # Enable Sequential Mode

        set_line = c.getcomponent(Const.VARIABLE)
        reset_line = c.getcomponent(Const.VARIABLE)

        latches = []

        for _ in range(count):
            # SR Latch using NOR gates
            # Q = NOR(R, Q_bar) | Q_bar = NOR(S, Q)
            nor_q = c.getcomponent(Const.NOR)
            nor_qb = c.getcomponent(Const.NOR)

            c.connect(nor_q, reset_line, 0) # R -> NOR_Q
            c.connect(nor_qb, set_line, 0)  # S -> NOR_QB
            
            # Feedback
            c.connect(nor_q, nor_qb, 1)     # QB -> NOR_Q
            c.connect(nor_qb, nor_q, 1)     # Q  -> NOR_QB
            
            latches.append(nor_q)

        print(f"Status: Initializing...                             ", end='\r')
        # Reset: S=0, R=1 => Q=0
        c.toggle(set_line, 0)
        c.toggle(reset_line, 1)
        # Hold:  S=0, R=0 => Q=0 (Memory)
        c.toggle(reset_line, 0)

        # BENCHMARK
        print(f"Status: FLIPPING STATES...                          ", end='\r')
        def run_sim():
            # Set: S=1, R=0 => Q=1
            c.toggle(set_line, 1)
            
        duration = self.timer("Echo Chamber", run_sim)

        # Verify: All Qs should be T
        passed = all(l.getoutput() == 'T' for l in latches)

        print(f"Status: DONE                                        ")
        print(f"  > Latches:          {count:,} (2 Gates each)")
        print(f"  > Execution Time:   {duration:.4f} ms")
        if duration > 0:
            print(f"  > Throughput:       {count / (duration/1000):,.0f} latches/sec")
        print(f"  > Logic Check:      {'PASS' if passed else 'FAIL'}")
        print("-" * 60)

if __name__ == "__main__":
    t = StressTest()
    t.run()
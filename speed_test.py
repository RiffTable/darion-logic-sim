import time
import sys
import os
import random

# --- CONFIGURATION ---
# Add engine to path
engine_path = os.path.join(os.getcwd(), 'engine')
if engine_path not in sys.path:
    sys.path.append(engine_path)

try:
    from Circuit import Circuit
    import Const
    from Gates import Gate
except ImportError as e:
    print("FATAL ERROR: Could not import engine modules.")
    print("Ensure you have built the project (build.bat/sh) and are running this from the root.")
    sys.exit(1)

class StressTest:
    def __init__(self):
        self.circuit = Circuit()
        # Use Simulation Mode (Optimized for speed, no cycle checks)
        self.circuit.simulate(Const.SIMULATE)

    def run(self):
        print(f"\n{'#'*60}")
        print(f"   DARION LOGIC SIM — EXTREME STRESS TEST")
        print(f"{'#'*60}\n")
        print(f"Mode: SIMULATION (DAG Optimized)")
        print(f"Note: Python acts as the bottleneck during 'Building'.")
        print(f"      The 'Running' phase measures the C++ Engine speed.\n")

        # 1. The Marathon (100k Serial Gates)
        self.test_marathon(count=100_000)

        # 2. The Avalanche (Binary Tree, ~260k Gates)
        self.test_avalanche(layers=18) 

        # 3. The Gridlock (Mesh Propagation, 250x250 = 62.5k Gates)
        self.test_gridlock(size=250)

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
    # TEST 1: THE MARATHON
    # Long daisy chain. Tests recursion depth limit and single-thread latency.
    # ---------------------------------------------------------
    def test_marathon(self, count):
        print(f"[TEST 1] The Marathon (Serial Chain)")
        print(f"Config: 1 Variable -> {count:,} NOT Gates -> Output")
        print(f"Goal:   Stress recursion and event queue overhead.")
        
        print("Status: Building circuit... (Python is working hard)", end='\r')
        self.circuit.clearcircuit()
        c = self.circuit
        
        # Build Chain
        inp = c.getcomponent(Const.VARIABLE)
        prev = inp
        gates = []
        
        # Create gates in bulk to check memory handling
        for _ in range(count):
            g = c.getcomponent(Const.NOT)
            c.connect(g, prev, 0)
            prev = g
            gates.append(g)

        print(f"Status: Initializing...                             ", end='\r')
        c.simulate(Const.SIMULATE)
        c.toggle(inp, 0) # Warmup

        # BENCHMARK
        print(f"Status: Running Engine...                           ", end='\r')
        
        def run_sim():
            c.toggle(inp, 1)

        duration = self.timer("Marathon", run_sim)

        # VERIFY
        # 1 -> NOT -> 0 -> NOT -> 1 ... 
        # Even depth = Same as input (T). Odd depth = Inverted (F).
        expected = 'T' if (count % 2 == 0) else 'F'
        actual = gates[-1].getoutput()
        passed = (actual == expected)

        print(f"Status: DONE                                        ")
        print(f"  > Gates:            {count:,}")
        print(f"  > Total Time:       {duration:.4f} ms")
        print(f"  > Latency/Gate:     {(duration * 1_000_000) / count:.2f} ns")
        if duration > 0:
            print(f"  > Throughput:       {count / (duration/1000):,.0f} events/sec")
        print(f"  > Logic Check:      {'PASS' if passed else 'FAIL'} (Expected {expected}, Got {actual})")
        print("-" * 60)

    # ---------------------------------------------------------
    # TEST 2: THE AVALANCHE
    # Binary Tree. 1 -> 2 -> 4 -> 8 ...
    # Tests queue throughput and memory allocation for events.
    # ---------------------------------------------------------
    def test_avalanche(self, layers):
        total_gates = (2 ** layers) - 1 # Geometric series sum
        print(f"\n[TEST 2] The Avalanche (Binary Tree)")
        print(f"Config: {layers} Layers of Buffers (Binary Tree structure)")
        print(f"Count:  {total_gates:,} Gates")
        print(f"Goal:   Triggers {total_gates:,} events from a SINGLE input toggle.")
        
        print("Status: Building circuit... (This may take a moment)", end='\r')
        self.circuit.clearcircuit()
        c = self.circuit

        root_inp = c.getcomponent(Const.VARIABLE)
        current_layer = [root_inp]
        all_gates = []

        # Build Tree
        # We use AND gates with inputlimit=1 to act as Buffers (1->1)
        for i in range(layers):
            next_layer = []
            for parent in current_layer:
                # Left Child
                g1 = c.getcomponent(Const.AND)
                c.setlimits(g1, 1) # Make it a buffer
                c.connect(g1, parent, 0)
                next_layer.append(g1)
                all_gates.append(g1)

                # Right Child
                g2 = c.getcomponent(Const.AND)
                c.setlimits(g2, 1) # Make it a buffer
                c.connect(g2, parent, 0)
                next_layer.append(g2)
                all_gates.append(g2)
            
            current_layer = next_layer
        
        print(f"Status: Initializing...                             ", end='\r')
        c.simulate(Const.SIMULATE)
        c.toggle(root_inp, 0)

        # BENCHMARK
        print(f"Status: TRIGGERING AVALANCHE...                     ", end='\r')
        
        def run_sim():
            c.toggle(root_inp, 1)

        duration = self.timer("Avalanche", run_sim)

        # VERIFY
        # Pick a random leaf node. It should be High (T).
        sample = random.choice(current_layer)
        actual = sample.getoutput()
        passed = (actual == 'T')

        print(f"Status: DONE                                        ")
        print(f"  > Total Events:     {len(all_gates):,}")
        print(f"  > Execution Time:   {duration:.4f} ms")
        if duration > 0:
            print(f"  > Event Rate:       {len(all_gates) / (duration/1000):,.0f} events/sec")
        print(f"  > Logic Check:      {'PASS' if passed else 'FAIL'} (Random Leaf Node is {actual})")
        print("-" * 60)

    # ---------------------------------------------------------
    # TEST 3: THE GRIDLOCK
    # NxN Mesh. Each gate feeds Down and Right.
    # Tests complex dependency resolution and fan-out/fan-in mixing.
    # ---------------------------------------------------------
    def test_gridlock(self, size):
        total_gates = size * size
        print(f"\n[TEST 3] The Gridlock (Mesh Matrix)")
        print(f"Config: {size}x{size} Grid of OR Gates")
        print(f"Count:  {total_gates:,} Gates")
        print(f"Goal:   Simulate wavefront propagation (Manhattan distance).")

        print("Status: Building circuit... (Python overhead is high here)", end='\r')
        self.circuit.clearcircuit()
        c = self.circuit

        # Grid array to store references: grid[row][col]
        grid = [[None for _ in range(size)] for _ in range(size)]
        
        # Source Trigger
        trigger = c.getcomponent(Const.VARIABLE)

        # 1. Instantiate all gates
        for r in range(size):
            for col in range(size):
                g = c.getcomponent(Const.OR)
                grid[r][col] = g

        # 2. Connect Gates
        # Logic: Gate(r, c) inputs come from (r-1, c) and (r, c-1)
        for r in range(size):
            for col in range(size):
                g = grid[r][col]
                inputs_needed = 0
                
                # Connection from Top
                if r > 0:
                    c.connect(g, grid[r-1][col], inputs_needed)
                    inputs_needed += 1
                elif r == 0 and col == 0:
                    # Top-Left gets the Trigger
                    c.connect(g, trigger, 0)
                    inputs_needed += 1
                
                # Connection from Left
                if col > 0:
                    c.connect(g, grid[r][col-1], inputs_needed)
                    inputs_needed += 1
                
                # IMPORTANT: Gates in SIMULATE mode only process if ALL inputs are connected.
                # We must reduce the input limit for edge gates that only have 1 neighbor.
                c.setlimits(g, max(1, inputs_needed))

        print(f"Status: Initializing...                                   ", end='\r')
        c.simulate(Const.SIMULATE)
        c.toggle(trigger, 0)

        # BENCHMARK
        print(f"Status: Running Engine...                                 ", end='\r')
        
        def run_sim():
            c.toggle(trigger, 1)

        duration = self.timer("Gridlock", run_sim)

        # VERIFY
        # The bottom-right gate (size-1, size-1) should eventually turn High.
        last_gate = grid[size-1][size-1]
        actual = last_gate.getoutput()
        passed = (actual == 'T')

        print(f"Status: DONE                                              ")
        print(f"  > Total Gates:      {total_gates:,}")
        print(f"  > Execution Time:   {duration:.4f} ms")
        if duration > 0:
            print(f"  > Throughput:       {total_gates / (duration/1000):,.0f} updates/sec")
        print(f"  > Logic Check:      {'PASS' if passed else 'FAIL'} (Bottom-Right is {actual})")
        print("-" * 60)

if __name__ == "__main__":
    t = StressTest()
    t.run()
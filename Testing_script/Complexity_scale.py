"""
DARION LOGIC SIM - TOPOLOGY COMPLEXITY PROFILER v4.2 (True Hardware Metrics)
Calculates exact C-level evaluation counts by querying the engine directly.
Includes statistical jitter filtering and zero-overhead timing loops.
"""

import time
import gc
import sys
import os
import random
import argparse

script_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(script_dir, 'reactor')) or os.path.exists(os.path.join(script_dir, 'engine')):
    root_dir = script_dir
elif getattr(sys, 'frozen', False):
    root_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
else:
    root_dir = os.path.abspath(os.path.join(script_dir, '..'))

parser = argparse.ArgumentParser(description='Topology Complexity Profiler')
parser.add_argument('--engine', action='store_true', help='Use Python engine backend (default: Reactor/Cython)')
args, _ = parser.parse_known_args()

if args.engine:
    sys.path.insert(0, os.path.join(root_dir, 'engine'))
    backend_name = "Engine"
else:
    sys.path.insert(0, os.path.join(root_dir, 'reactor'))
    backend_name = "Reactor"

from Circuit import Circuit as CircuitClass
from Const import AND_ID, XOR_ID, OR_ID, NOT_ID, VARIABLE_ID, HIGH, LOW, SIMULATE, DESIGN


# =====================================================================
# TOPOLOGIES
# =====================================================================

def build_level_0_linear(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    prev = master
    for _ in range(target_gates - 1):
        g = circuit.getcomponent(NOT_ID)
        circuit.connect(g, prev, 0)
        prev = g
    return master, target_gates, target_gates, "L0: Linear Chain"

def build_level_1_parallel(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    lanes = max(1, target_gates // 50) 
    depth = target_gates // lanes
    total_physical = 1
    for _ in range(lanes):
        prev = master
        for _ in range(depth):
            g = circuit.getcomponent(NOT_ID)
            circuit.connect(g, prev, 0)
            prev = g
            total_physical += 1
    return master, total_physical, total_physical, "L1: Wide Fan-Out"

def build_level_2_fanout_tree(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    current_layer = [master]
    count = 1
    while count < target_gates:
        next_layer = []
        for node in current_layer:
            if count >= target_gates: break
            g1, g2 = circuit.getcomponent(NOT_ID), circuit.getcomponent(NOT_ID)
            circuit.connect(g1, node, 0); circuit.connect(g2, node, 0)
            next_layer.extend([g1, g2])
            count += 2
        current_layer = next_layer
    return master, count, count, "L2: Binary Tree"

def build_level_3_memory_maze(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    gates = [circuit.getcomponent(NOT_ID) for _ in range(target_gates - 1)]
    random.seed(42)
    random.shuffle(gates) 
    prev = master
    for g in gates:
        circuit.connect(g, prev, 0)
        prev = g
    return master, target_gates, target_gates, "L3: Memory Maze"

def build_level_4_glitch_avalanche(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    half = target_gates // 2
    chain = [master]
    for _ in range(half):
        g = circuit.getcomponent(NOT_ID)
        circuit.connect(g, chain[-1], 0)
        chain.append(g)
    for i in range(1, len(chain)):
        g = circuit.getcomponent(XOR_ID)
        circuit.connect(g, master, 0)    
        circuit.connect(g, chain[i], 1)  
    physical_count = half * 2
    theoretical_evals = half * 3  
    return master, physical_count, theoretical_evals, "L4: Glitch Avalanche"

def build_level_5_event_hurricane(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    size = target_gates # Removed artificial cap to allow natural scaling math
    xors = [circuit.getcomponent(XOR_ID) for _ in range(size)]
    static_low = circuit.getcomponent(VARIABLE_ID)
    circuit.toggle(static_low, 0)
    for i in range(size-1, -1, -1):
        circuit.connect(xors[i], master, 0)
    circuit.connect(xors[0], static_low, 1)
    for i in range(1, size):
        circuit.connect(xors[i], xors[i-1], 1)
    physical_count = size + 2
    theoretical_evals = (size * (size + 1)) // 2 
    return master, physical_count, theoretical_evals, "L5: Queue Thrash O(N^2)"

def build_level_6_sparse_fanin(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    leaves = [master]
    static_low = circuit.getcomponent(VARIABLE_ID)
    circuit.toggle(static_low, 0)
    
    while len(leaves) * 2 <= target_gates:
        var = circuit.getcomponent(VARIABLE_ID)
        circuit.toggle(var, 0)
        leaves.append(var)
        
    current_layer = leaves
    total_physical = len(leaves) + 1
    exact_evals = 1 
    
    while len(current_layer) > 1:
        next_layer = []
        for i in range(0, len(current_layer), 2):
            if i+1 < len(current_layer):
                g = circuit.getcomponent(XOR_ID)
                circuit.connect(g, current_layer[i], 0)
                circuit.connect(g, current_layer[i+1], 1)
                next_layer.append(g)
                total_physical += 1
            else:
                next_layer.append(current_layer[i])
        current_layer = next_layer
        exact_evals += 1
        
    return master, total_physical, exact_evals, "L6: Sparse Fan-In"

def build_level_7_braid(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    width = 4
    num_layers = target_gates // width
    
    prev_layer = [master] * width 
    total_physical = 1
    exact_evals = 1
    
    for _ in range(num_layers):
        current_layer = []
        for i in range(width):
            g = circuit.getcomponent(AND_ID)
            circuit.connect(g, prev_layer[i], 0)
            circuit.connect(g, prev_layer[(i+1)%width], 1)
            current_layer.append(g)
            total_physical += 1
        prev_layer = current_layer
        exact_evals += width
        
    return master, total_physical, exact_evals, "L7: Dense Braid"

def build_level_8_diamond(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    current_layer = [master]
    total_physical = 1
    exact_evals = 1
    expand_target = max(2, target_gates // 2)
    
    while total_physical < expand_target:
        next_layer = []
        for node in current_layer:
            g1, g2 = circuit.getcomponent(NOT_ID), circuit.getcomponent(NOT_ID)
            circuit.connect(g1, node, 0); circuit.connect(g2, node, 0)
            next_layer.extend([g1, g2])
            total_physical += 2
            exact_evals += 2
        current_layer = next_layer
        
    while len(current_layer) > 1:
        next_layer = []
        for i in range(0, len(current_layer), 2):
            if i+1 < len(current_layer):
                g = circuit.getcomponent(AND_ID)
                circuit.connect(g, current_layer[i], 0)
                circuit.connect(g, current_layer[i+1], 1)
                next_layer.append(g)
                total_physical += 1
                exact_evals += 1
            else:
                next_layer.append(current_layer[i])
        current_layer = next_layer
        
    return master, total_physical, exact_evals, "L8: Diamond (Exp/Con)"

def build_level_9_hamming_ecc(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    
    # We need 4 data lines for Hamming(7,4). We will make them toggle differently.
    # d1 = master
    # d2 = master delayed by 1 gate
    # d3 = master delayed by 2 gates
    # d4 = master delayed by 3 gates
    d1 = master
    
    n1 = circuit.getcomponent(NOT_ID)
    circuit.connect(n1, master, 0)
    d2 = circuit.getcomponent(NOT_ID)
    circuit.connect(d2, n1, 0)
    
    n2 = circuit.getcomponent(NOT_ID)
    circuit.connect(n2, d2, 0)
    d3 = circuit.getcomponent(NOT_ID)
    circuit.connect(d3, n2, 0)
    
    n3 = circuit.getcomponent(NOT_ID)
    circuit.connect(n3, d3, 0)
    d4 = circuit.getcomponent(NOT_ID)
    circuit.connect(d4, n3, 0)
    
    total_physical = 7
    exact_evals = 7
    
    # Each Hamming block needs 6 XOR gates
    blocks = max(1, target_gates // 6)
    
    for _ in range(blocks):
        # p1 = d1 ^ d2 ^ d4
        x1 = circuit.getcomponent(XOR_ID)
        circuit.connect(x1, d1, 0); circuit.connect(x1, d2, 1)
        p1 = circuit.getcomponent(XOR_ID)
        circuit.connect(p1, x1, 0); circuit.connect(p1, d4, 1)
        
        # p2 = d1 ^ d3 ^ d4
        x2 = circuit.getcomponent(XOR_ID)
        circuit.connect(x2, d1, 0); circuit.connect(x2, d3, 1)
        p2 = circuit.getcomponent(XOR_ID)
        circuit.connect(p2, x2, 0); circuit.connect(p2, d4, 1)
        
        # p3 = d2 ^ d3 ^ d4
        x3 = circuit.getcomponent(XOR_ID)
        circuit.connect(x3, d2, 0); circuit.connect(x3, d3, 1)
        p3 = circuit.getcomponent(XOR_ID)
        circuit.connect(p3, x3, 0); circuit.connect(p3, d4, 1)
        
        total_physical += 6
        exact_evals += 15
        
    return master, total_physical, exact_evals, "L9: Hamming(7,4) ECC"

# =====================================================================
# MAIN PROFILER
# =====================================================================

def run_profiler():
    print("="*82)
    print(" DARION LOGIC SIM: TOPOLOGY SCALING PROFILER (V4.2) ")
    print("="*82)
    print(f"[+] Backend: {backend_name}")

    temp_circ = CircuitClass()
    has_hw_counter = hasattr(temp_circ, 'activate_eval')
    del temp_circ

    TEST_SIZES = [1_000, 5_000, 10_000, 50_000, 100_000]
    TARGET_TOTAL_THEORETICAL_EVALS = 20_000_000 
    MAX_EVALS_PER_PASS = 250_000_000 # Hard limit to prevent hours of waiting on O(N^2)
    NUM_PASSES = 3 # Statistical multi-pass to filter OS jitter
    
    print(f"\nBenchmarking Backend: {backend_name}")
    print("Testing structural scale from 1K to 100K gates to stress RAM & CPU Caches.")
    
    if has_hw_counter:
        print("[+] Hardware Counter Detected: Using absolute engine-level evaluation metrics.\n")
    else:
        print("[-] WARNING: 'activate_eval()' not found in Circuit class.")
        print("[-] Using theoretical math for ME/s. L4 and L5 scores WILL be artificially inflated.\n")

    levels = [
        build_level_0_linear, build_level_1_parallel, build_level_2_fanout_tree,
        build_level_3_memory_maze, build_level_4_glitch_avalanche, build_level_5_event_hurricane,
        build_level_6_sparse_fanin, build_level_7_braid, build_level_8_diamond, build_level_9_hamming_ecc
    ]

    print(f"{'Topology':<26} | {'1K Size':>14} | {'5K Size':>14} | {'10K Size':>14} | {'50K Size':>14} | {'100K Size':>14} | {'Scaling':>2}")
    print("-" * 120)

    for builder in levels:
        desc_name = ""
        results = []
        
        for size in TEST_SIZES:
            circuit = CircuitClass()
            if hasattr(circuit, 'activate_eval'):
                circuit.activate_eval()
            gc.disable()
            
            master, count, theoretical_evals, desc = builder(circuit, size, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=AND_ID)
            if not desc_name: desc_name = desc
            
            # Skip if theoretical load exceeds extreme bounds (prevents L5 100K hang)
            if theoretical_evals > MAX_EVALS_PER_PASS:
                results.append(-1.0)
                circuit.clearcircuit()
                del circuit
                gc.enable()
                continue
                
            vectors = max(4, TARGET_TOTAL_THEORETICAL_EVALS // theoretical_evals)
            vectors += (vectors % 2) # Ensure even number for HIGH/LOW pairing
            
            best_time = float('inf')
            best_evals = 0
            
            # Multi-pass execution loop
            for _ in range(NUM_PASSES):
                master.value = LOW
                circuit.simulate(DESIGN)
                circuit.simulate(SIMULATE)
                
                start_evals = circuit.eval_count if has_hw_counter else 0
                
                # Zero-overhead timing block
                t_start = time.perf_counter()
                for _ in range(vectors // 2):
                    circuit.toggle(master, HIGH)
                    circuit.toggle(master, LOW)
                t_end = time.perf_counter()
                
                pass_time = t_end - t_start
                pass_evals = (circuit.eval_count - start_evals) if has_hw_counter else (theoretical_evals * vectors)
                
                if pass_time < best_time:
                    best_time = pass_time
                    best_evals = pass_evals

            m_evals_per_sec = (best_evals / best_time) / 1_000_000 if best_time > 0 else 0
            results.append(m_evals_per_sec)

            circuit.clearcircuit()
            del circuit
            gc.collect()
            gc.enable()

        # Format columns based on whether they were skipped
        def fmt(val): return f"{val:>9.2f} ME/s" if val >= 0 else f"{'N/A (Skip)':>14}"
        
        val_1k = results[0]
        # Calculate retention using the highest completed tier
        completed_vals = [r for r in results if r >= 0]
        highest_tier_val = completed_vals[-1] if completed_vals else val_1k
        retention = (highest_tier_val / val_1k) * 100 if val_1k > 0 else 0.0
            
        retention_str = f"{retention:>5.1f}%"
            
        print(f"{desc_name:<26} | {fmt(results[0])} | {fmt(results[1])} | {fmt(results[2])} | {fmt(results[3])} | {fmt(results[4])} | {retention_str}")

    print("-" * 120)

class _Tee:
    """Mirror stdout to a log file simultaneously."""
    def __init__(self, *streams):
        self.streams = streams
    def write(self, data):
        for s in self.streams:
            s.write(data)
    def flush(self):
        for s in self.streams:
            s.flush()

if __name__ == "__main__":
    from datetime import datetime
    _LOG = "complexity_scale_results.txt"
    with open(_LOG, "a", encoding="utf-8") as _lf:
        _lf.write(f"\n{'='*70}\n")
        _lf.write(f"RUN  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        _lf.write(f"ARGS : backend={backend_name}\n")
        _lf.write(f"{'='*70}\n")
        _orig = sys.stdout
        sys.stdout = _Tee(_orig, _lf)
        try:
            run_profiler()
        finally:
            sys.stdout = _orig
    print(f"\nLog saved to: {_LOG}")
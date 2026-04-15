"""
DARION LOGIC SIM - ADVANCED TOPOLOGY DEFRAGMENTATION PROOF (V4 - TRUE MATH)
"""

import time
import os
import sys
import random
import gc

script_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(script_dir, 'reactor')):
    sys.path.insert(0, os.path.join(script_dir, 'reactor'))
else:
    sys.path.insert(0, os.path.join(script_dir, '..', 'reactor'))

from Circuit import Circuit
import Const

GATE_COUNT = 1_500_000  
VECTORS = 100           

# =====================================================================
# TOPOLOGY BUILDERS
# =====================================================================

def wire_linear_chain(circuit, master, pool):
    circuit.toggle(master, Const.LOW)
    prev = master
    for g in pool:
        circuit.setlimits(g, 1)
        circuit.connect(g, prev, 0)
        prev = g
    return len(pool)

def wire_dense_braid(circuit, master, pool):
    circuit.toggle(master, Const.LOW)
    width = 4
    prev_layer = [master] * width 
    pool_idx = 0
    
    while pool_idx + width <= len(pool):
        current_layer = []
        for i in range(width):
            g = pool[pool_idx]
            pool_idx += 1
            circuit.setlimits(g, 2)
            circuit.connect(g, prev_layer[i], 0)
            circuit.connect(g, prev_layer[(i+1) % width], 1)
            current_layer.append(g)
        prev_layer = current_layer
    return pool_idx

# =====================================================================
# PROFILER LOGIC
# =====================================================================

def execute_pass(circuit, master, actual_count):
    fast_toggle = circuit.toggle
    
    # SNAPSHOT
    start_evals = circuit.eval_count if hasattr(circuit, 'eval_count') else 0
    
    start_time = time.perf_counter()
    for _ in range(VECTORS // 2):
        fast_toggle(master, Const.HIGH)
        fast_toggle(master, Const.LOW)
    end_time = time.perf_counter()
    
    duration = end_time - start_time
    
    # DELTA
    if hasattr(circuit, 'eval_count'):
        pass_evals = circuit.eval_count - start_evals
    else:
        pass_evals = actual_count * VECTORS
        
    throughput = (pass_evals / duration) / 1_000_000
    return throughput

def run_test(topology_name, wiring_func):
    print(f"\n{topology_name:<15} | ", end="", flush=True)
    
    # --- PASS 1: PRISTINE ---
    circuit = Circuit()
    master = circuit.getcomponent(Const.VARIABLE_ID)
    gates_pool = [circuit.getcomponent(Const.AND_ID if topology_name == "Dense Braid" else Const.NOT_ID) for _ in range(GATE_COUNT)]
    
    actual_count = wiring_func(circuit, master, gates_pool)
    circuit.simulate(Const.SIMULATE)
    
    t_pristine = execute_pass(circuit, master, actual_count)
    print(f"{t_pristine:>11.2f} ME/s | ", end="", flush=True)
    
    circuit.clearcircuit()
    del circuit, gates_pool
    gc.collect()

    # --- PASS 2: FRAGMENTED ---
    circuit = Circuit()
    master = circuit.getcomponent(Const.VARIABLE_ID)
    gates_pool = [circuit.getcomponent(Const.AND_ID if topology_name == "Dense Braid" else Const.NOT_ID) for _ in range(GATE_COUNT)]
    
    random.seed(42)
    random.shuffle(gates_pool) 
    wiring_func(circuit, master, gates_pool)
    circuit.simulate(Const.SIMULATE)
    
    t_fragmented = execute_pass(circuit, master, actual_count)
    print(f"{t_fragmented:>11.2f} ME/s | ", end="", flush=True)
    
    # --- PASS 3: OPTIMIZED ---
    circuit.optimize() 
    
    t_optimized = execute_pass(circuit, master, actual_count)
    
    recovery = ((t_optimized - t_fragmented) / t_fragmented) * 100 if t_fragmented > 0 else 0
    print(f"{t_optimized:>11.2f} ME/s (+{recovery:.0f}%)", flush=True)

    circuit.clearcircuit()
    del circuit, gates_pool
    gc.collect()


# =====================================================================
# EXECUTION SUITE
# =====================================================================

if __name__ == "__main__":
    print("=======================================================================")
    print(" DARION LOGIC SIM: ADVANCED TOPOLOGY RAM/CACHE PROFILER (V4)")
    print("=======================================================================")
    print(f"Gate Count per Test: ~{GATE_COUNT:,} | Vectors: {VECTORS}\n")
    
    topologies = [
        ("Linear Chain", wire_linear_chain),
        ("Dense Braid", wire_dense_braid)
    ]
    
    print(f"{'Topology':<15} | {'Pristine (Ideal)':>16} | {'GUI Fragmented':>16} | {'Optimized (DOD)':>16}")
    print("-" * 75, end="")
    
    for name, func in topologies:
        run_test(name, func)
        
    print("\n=======================================================================")
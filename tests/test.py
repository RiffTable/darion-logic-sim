import os
import sys
import time
import random
import argparse

# --- DYNAMIC PATH RESOLUTION ---
# --- DYNAMIC PATH RESOLUTION ---
base_dir = os.getcwd()
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)

if os.path.exists(os.path.join(script_dir, 'reactor')):
    sys.path.insert(0, os.path.join(script_dir, 'reactor'))
elif os.path.exists(os.path.join(parent_dir, 'reactor')):
    sys.path.insert(0, os.path.join(parent_dir, 'reactor'))
else:
    print("Error: Could not find 'reactor' directory.")
    sys.exit(1)

import Circuit
import Const

def build_array_multiplier(N):
    """
    Programmatically builds an NxN Array Multiplier natively in the engine.
    Total Gates ≈ N^2 (Partial Products) + 5 * N * (N-1) (Adders) ≈ 6N^2
    """
    circuit = Circuit.Circuit()
    
    # 1. Create Input Masters
    A = [circuit.getcomponent(Const.VARIABLE_ID) for _ in range(N)]
    B = [circuit.getcomponent(Const.VARIABLE_ID) for _ in range(N)]
    
    # 2. Setup Ground
    gnd = circuit.getcomponent(Const.VARIABLE_ID)
    circuit.toggle(gnd, Const.LOW)
    
    # 3. Generate Partial Products (A_i AND B_j)
    pps = [[None for _ in range(N)] for _ in range(N)]
    for i in range(N):
        for j in range(N):
            and_g = circuit.getcomponent(Const.AND_ID)
            circuit.setlimits(and_g, 2)
            circuit.connect(and_g, A[i], 0)
            circuit.connect(and_g, B[j], 1)
            pps[i][j] = and_g
            
    # 4. Full Adder Helper
    def create_full_adder(a, b, cin):
        # S = A ^ B ^ Cin
        # Cout = (A & B) | (Cin & (A ^ B))
        x1 = circuit.getcomponent(Const.XOR_ID)
        circuit.setlimits(x1, 2)
        circuit.connect(x1, a, 0)
        circuit.connect(x1, b, 1)
        
        x2 = circuit.getcomponent(Const.XOR_ID)
        circuit.setlimits(x2, 2)
        circuit.connect(x2, x1, 0)
        circuit.connect(x2, cin, 1)
        
        a1 = circuit.getcomponent(Const.AND_ID)
        circuit.setlimits(a1, 2)
        circuit.connect(a1, a, 0)
        circuit.connect(a1, b, 1)
        
        a2 = circuit.getcomponent(Const.AND_ID)
        circuit.setlimits(a2, 2)
        circuit.connect(a2, x1, 0)
        circuit.connect(a2, cin, 1)
        
        o1 = circuit.getcomponent(Const.OR_ID)
        circuit.setlimits(o1, 2)
        circuit.connect(o1, a1, 0)
        circuit.connect(o1, a2, 1)
        
        return x2, o1 # Sum, Cout
        
    # 5. Build the Array Grid
    sums = [[None for _ in range(N)] for _ in range(N)]
    couts = [[None for _ in range(N)] for _ in range(N)]
    
    for j in range(N):
        sums[0][j] = pps[0][j]
        couts[0][j] = gnd
        
    for i in range(1, N):
        cin = gnd
        for j in range(N-1):
            a_in = sums[i-1][j+1]
            b_in = pps[i][j]
            s, cout = create_full_adder(a_in, b_in, cin)
            sums[i][j] = s
            cin = cout
            
        # Edge of the row
        a_in = couts[i-1][N-1]
        b_in = pps[i][N-1]
        s, cout = create_full_adder(a_in, b_in, cin)
        sums[i][N-1] = s
        couts[i][N-1] = cout
        
    return circuit, A, B

def run_benchmark():
    # Scales to test: N bits (N x N multiplier)
    # N=400 yields ~960,000 gates
    scales = [8, 16, 32, 64, 128, 256, 400]
    
    # We must drastically lower the vector count as N scales up, 
    # otherwise the billion-evaluation avalanches will take days.
    vectors_for_scale = {
        8: 5000, 16: 2000, 32: 500, 
        64: 100, 128: 25, 256: 5, 400: 2
    }

    print("\n" + "="*85)
    print(" DARION LOGIC SIM - GLITCH AVALANCHE SCALING TEST (REACTOR)")
    print("="*85)
    
    # Removed Wavefront and Toggle % columns
    col_format = "{:<10} | {:>10} | {:>8} | {:>15} | {:>15} | {:>10}"
    print(col_format.format("Bits (NxN)", "Gates", "Vectors", "Total Evals", "Evals/Vector", "Batch M/s"))
    print("-" * 85)

    for N in scales:
        vectors = vectors_for_scale[N]
        
        # 1. Build & Optimize
        circuit, A, B = build_array_multiplier(N)
        circuit.optimize()
        circuit.simulate(Const.COMPILE)
        
        gate_count = N*N + 5*N*(N-1) + 2*N + 1 # Approx including inputs/gnd
        
        # 2. Prepare Vectors
        masters = A + B
        batched_instructions = []
        for _ in range(vectors):
            vec = [(m.location, Const.HIGH if random.random() > 0.5 else Const.LOW) for m in masters]
            batched_instructions.append(vec)
            
        fast_batch_toggle = circuit.batch_toggle
        
        # 3. Execute Bench
        t0 = time.perf_counter_ns()
        for vec in batched_instructions:
            fast_batch_toggle(vec)
        t1 = time.perf_counter_ns()
        
        # 4. Metrics
        duration_ms = (t1 - t0) / 1_000_000.0
        total_evals = circuit.eval_count
        evals_per_sec = (total_evals / (duration_ms / 1000.0)) if duration_ms > 0 else 0
        batch_ms = evals_per_sec / 1_000_000.0
        
        evals_per_vector = total_evals // vectors

        print(col_format.format(
            f"{N}x{N}", 
            f"{gate_count:,}", 
            f"{vectors:,}", 
            f"{total_evals:,}", 
            f"{evals_per_vector:,}", 
            f"{batch_ms:.2f}"
        ))

    print("="*85 + "\n")

if __name__ == "__main__":
    run_benchmark()
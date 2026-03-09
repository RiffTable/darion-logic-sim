import time
import random

# =======================================================
# CHANGE THIS IMPORT TO TEST THE OTHER ENGINE
# =======================================================
import Circuit as Engine
# import reactor2.Circuit as Engine

# Gate IDs based on Store.pyx decoding
AND_ID = 0
OR_ID = 2
XOR_ID = 4
VARIABLE_ID = 6
SIMULATE = 1

def build_rca(circuit, bits):
    """Builds an N-Bit Ripple Carry Adder and returns the input/output nodes."""
    A_vars = [circuit.getcomponent(VARIABLE_ID) for _ in range(bits)]
    B_vars = [circuit.getcomponent(VARIABLE_ID) for _ in range(bits)]
    cin_var = circuit.getcomponent(VARIABLE_ID)
    
    carry = cin_var
    
    for i in range(bits):
        # axor = A ^ B
        axb = circuit.getcomponent(XOR_ID)
        circuit.connect(axb, A_vars[i], 0)
        circuit.connect(axb, B_vars[i], 1)
        
        # sum_out = (A ^ B) ^ Cin
        sum_out = circuit.getcomponent(XOR_ID)
        circuit.connect(sum_out, axb, 0)
        circuit.connect(sum_out, carry, 1)
        
        # a_and_b = A & B
        a_and_b = circuit.getcomponent(AND_ID)
        circuit.connect(a_and_b, A_vars[i], 0)
        circuit.connect(a_and_b, B_vars[i], 1)
        
        # cin_and_axb = Cin & (A ^ B)
        cin_and_axb = circuit.getcomponent(AND_ID)
        circuit.connect(cin_and_axb, carry, 0)
        circuit.connect(cin_and_axb, axb, 1)
        
        # Cout = (A & B) | (Cin & (A ^ B))
        cout = circuit.getcomponent(OR_ID)
        circuit.connect(cout, a_and_b, 0)
        circuit.connect(cout, cin_and_axb, 1)
        
        carry = cout
        
    return A_vars, B_vars, cin_var

def run_benchmark():
    circuit = Engine.Circuit()
    
    # reactor2 requires activating the eval pointer to track gate evaluations
    if hasattr(circuit, 'activate_eval'):
        circuit.activate_eval()
        
    BITS = 2500
    TOGGLES_WORST_CASE = 500
    TOGGLES_CHAOTIC = 5000
    
    print(f"--- Engine: {Engine.__name__} ---")
    print(f"Building {BITS}-bit RCA ({BITS * 5} gates)...")
    A_vars, B_vars, cin_var = build_rca(circuit, BITS)
    
    circuit.simulate(SIMULATE)
    
    # ---------------------------------------------------------
    # TEST 1: WORST-CASE DEEP RIPPLE
    # ---------------------------------------------------------
    # Setup: A = 111...1, B = 000...0. 
    # Toggling Cin forces a ripple through every single Carry bit.
    for i in range(BITS):
        circuit.toggle(A_vars[i], 1)
        circuit.toggle(B_vars[i], 0)
    
    print("\n[Test 1] Warming up deep ripple...")
    for i in range(10):
        circuit.toggle(cin_var, i % 2)
        
    start_evals = getattr(circuit, 'eval_count', 0)
    start_time = time.perf_counter()
    
    for i in range(TOGGLES_WORST_CASE):
        circuit.toggle(cin_var, i % 2)
        
    end_time = time.perf_counter()
    end_evals = getattr(circuit, 'eval_count', 0)
    
    t1_time = end_time - start_time
    t1_evals = end_evals - start_evals
    t1_throughput = t1_evals / t1_time if t1_time > 0 else 0

    # ---------------------------------------------------------
    # TEST 2: CHAOTIC RANDOM FLIPS
    # ---------------------------------------------------------
    # Setup: Pre-calculate random bit flips to keep python RNG out of the timing loop.
    random.seed(42)
    test_vectors = []
    all_inputs = A_vars + B_vars + [cin_var]
    
    for _ in range(TOGGLES_CHAOTIC):
        target_gate = random.choice(all_inputs)
        val = random.randint(0, 1)
        test_vectors.append((target_gate, val))
        
    start_evals = getattr(circuit, 'eval_count', 0)
    start_time = time.perf_counter()
    
    for gate, val in test_vectors:
        circuit.toggle(gate, val)
        
    end_time = time.perf_counter()
    end_evals = getattr(circuit, 'eval_count', 0)
    
    t2_time = end_time - start_time
    t2_evals = end_evals - start_evals
    t2_throughput = t2_evals / t2_time if t2_time > 0 else 0

    # ---------------------------------------------------------
    # RESULTS
    # ---------------------------------------------------------
    print("\n" + "="*45)
    print("                RESULTS")
    print("="*45)
    print("TEST 1: Sustained Deep Ripple (Max Wave Size)")
    print(f"  Time:        {t1_time:.5f} sec")
    print(f"  Evals:       {t1_evals:,}")
    print(f"  Throughput:  {t1_throughput:,.0f} evals/sec")
    
    print("\nTEST 2: Chaotic Branching (Random Flips)")
    print(f"  Time:        {t2_time:.5f} sec")
    print(f"  Evals:       {t2_evals:,}")
    print(f"  Throughput:  {t2_throughput:,.0f} evals/sec")
    print("="*45 + "\n")

if __name__ == "__main__":
    run_benchmark()
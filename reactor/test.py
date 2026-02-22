import time
import os
from Circuit import Circuit

# --- CONFIGURATION ---
CHAIN_LENGTH = 100000 
GATE_CHOICE_NOT = 6    
VAR_CHOICE = 7         
FILENAME = "benchmark_dump.json"

def run_pipeline():
    print("--- Darion Logic Sim Full Pipeline Benchmark ---")
    sim_circuit = Circuit()
    
    # ---------------------------------------------------------
    # 1. CIRCUIT CREATION
    # ---------------------------------------------------------
    print(f"\n[1] Building a cascade of {CHAIN_LENGTH:,} NOT gates...")
    start_time = time.perf_counter()
    
    head_var = sim_circuit.getcomponent(VAR_CHOICE) 
    previous_gate = head_var
    
    for i in range(CHAIN_LENGTH):
        new_gate = sim_circuit.getcomponent(GATE_CHOICE_NOT)
        sim_circuit.connect(new_gate, previous_gate, 0)
        previous_gate = new_gate

    build_time = time.perf_counter() - start_time
    print(f"    Creation Time: {build_time * 1000:.2f} ms")

    # ---------------------------------------------------------
    # 2. SAVE (Extract & Dump to Disk)
    # ---------------------------------------------------------
    print(f"\n[2] Saving circuit state to {FILENAME}...")
    start_time = time.perf_counter()
    
    # Use the native Cython method which iterates over self.canvas
    sim_circuit.writetojson(FILENAME)
        
    save_time = time.perf_counter() - start_time
    print(f"    Save Time (Extract + File Write): {save_time * 1000:.2f} ms")

    # ---------------------------------------------------------
    # 3. LOAD (Read from Disk, Parse, & Reconstruct C++ Graph)
    # ---------------------------------------------------------
    print(f"\n[3] Loading circuit state from {FILENAME}...")
    start_time = time.perf_counter()
    
    # Instantiate a brand new circuit to ensure a true cold-load
    loaded_circuit = Circuit()
    loaded_circuit.readfromjson(FILENAME)
    
    load_time = time.perf_counter() - start_time
    print(f"    Load Time (Read + Parse + Graph Rebuild): {load_time * 1000:.2f} ms")
    print(f"    Reconstructed {len(loaded_circuit.canvas):,} components.")

    # ---------------------------------------------------------
    # 4. SIMULATE
    # ---------------------------------------------------------
    print("\n[4] Toggling input and running simulation...")
    start_time = time.perf_counter()
    
    # Grab the head variable from the newly loaded circuit 
    # (It will be the first item in varlist)
    loaded_head_var = loaded_circuit.varlist[0]
    
    # Toggle to trigger the propagation wave
    loaded_circuit.toggle(loaded_head_var, 1) 
    
    sim_time = time.perf_counter() - start_time
    print(f"    Simulation Time: {sim_time * 1000:.2f} ms")
    
    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------
    print("\n--- Summary ---")
    total_time = build_time + save_time + load_time + sim_time
    print(f"Total Pipeline Time: {total_time * 1000:.2f} ms")
    print(f"Simulation Throughput: {CHAIN_LENGTH / sim_time:,.0f} eval/sec")
    
    if os.path.exists(FILENAME):
        os.remove(FILENAME)

if __name__ == "__main__":
    run_pipeline()
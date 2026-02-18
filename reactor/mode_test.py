import time
import sys
sys.path.append('.')

from Circuit import Circuit
from Const import SIMULATE, FLIPFLOP, NAND_ID, VARIABLE_ID

# ==========================================================
# CONFIGURATION: THE EVENT HORIZON
# ==========================================================
# We need enough gates to overflow the CPU's L3 Cache.
# 1 Gate ~ 64-128 bytes. 3 Million gates > 200MB RAM.
# This forces 'clear_fuse' to fetch from main RAM, not Cache.
FAN_OUT_SIZE = 3_000_000 
# ==========================================================

def build_black_hole(circuit):
    print(f"  [GRAVITY] Compressing {FAN_OUT_SIZE:,} gates into singularity...")
    print(f"            (This Python build step will be slow, wait for it...)")
    
    driver = circuit.getcomponent(VARIABLE_ID)
    driver.name = "SINGULARITY"
    
    vcc = circuit.getcomponent(VARIABLE_ID)
    vcc.name = "VCC"
    circuit.toggle(vcc, 1)

    # Creating the array. We use a raw loop for speed, avoiding print overhead
    # We use AND gates to force the 'complex' logic path.
    for i in range(FAN_OUT_SIZE):
        gate = circuit.getcomponent(NAND_ID)
        circuit.connect(gate, driver, 0)
        circuit.connect(gate, vcc, 1)
        
        if i % 250_000 == 0:
            print(f"            ... {i // 1000}k gates added")
            
    print(f"  [GRAVITY] Mass critical. Event Horizon established.")
    return driver

def run_event_horizon(mode_name, mode_const):
    c = Circuit()
    driver = build_black_hole(c)
    
    print(f"  [WARP] Switching to {mode_name}...")
    c.simulate(mode_const)
    
    # Warmup (get everything into a known state)
    print("  [WARP] Warmup toggle...")
    c.toggle(driver, 1)
    c.toggle(driver, 0)
    
    print(f"  [WARP] Engaging Drive (1 Massive Pulse)...")
    
    # We only need ONE pulse to measure the cleanup cost
    # because the cleanup happens once per propagation chain.
    start = time.perf_counter()
    c.toggle(driver, 1)
    end = time.perf_counter()
    
    duration = end - start
    ops_sec = FAN_OUT_SIZE / duration
    ns_per_gate = (duration / FAN_OUT_SIZE) * 1_000_000_000
    
    print(f"  > Pulse Duration: {duration:.4f}s")
    print(f"  > Throughput:     {ops_sec/1_000_000:.2f} M ops/sec")
    print(f"  > Latency:        {ns_per_gate:.2f} ns/gate")
    return ns_per_gate

if __name__ == "__main__":
    print("\n==================================================")
    print("       THE BLACK HOLE - CACHE EVICTION TEST       ")
    print("==================================================")
    print("Rationale: Overflow L3 Cache to expose 'clear_fuse'")
    print("           memory bandwidth cost.")
    print("--------------------------------------------------")

    # 1. SIMULATE (One Pass: Read/Write)
    print("\n[PHASE 1] SIMULATE Mode")
    t_sim = run_event_horizon("SIMULATE", SIMULATE)

    # 2. FLIPFLOP (Two Passes: Read/Write -> Read/Clear)
    print("\n[PHASE 2] FLIPFLOP Mode")
    t_ff = run_event_horizon("FLIPFLOP", FLIPFLOP)

    # 3. ANALYSIS
    print("\n==================================================")
    print("                  DAMAGE REPORT                   ")
    print("==================================================")
    
    overhead_ns = t_ff - t_sim
    overhead_pct = (overhead_ns / t_sim) * 100
    
    print(f"SIMULATE Latency:    {t_sim:.2f} ns")
    print(f"FLIPFLOP Latency:    {t_ff:.2f} ns")
    print(f"--------------------------------------------------")
    print(f"MEMORY LAG:          {overhead_ns:.2f} ns (+{overhead_pct:.1f}%)")
    print(f"--------------------------------------------------")
    
    if overhead_pct > 30:
        print("VERDICT: SUCCESS. Massive lag detected.")
        print("Reason: 'clear_fuse' is forced to re-fetch data from RAM.")
    else:
        print("VERDICT: FAILED. Your engine is too efficient.")
        print("Reason: Hardware prefetcher is predicting the cleanup pattern.")
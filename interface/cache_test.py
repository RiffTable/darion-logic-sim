"""
DARION LOGIC SIM - CACHE & MEMORY BOUNDARY PROFILER
Finds the 0-10% cache sweet spot, stops at 50% degradation,
and specifies CPU hardware limits.
"""

import time
import gc
import sys
import os 
import random
import argparse
import platform
import subprocess

try:
    import psutil
    process = psutil.Process(os.getpid())
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

parser = argparse.ArgumentParser(description='Run Cache Profiler')
parser.add_argument('--reactor', action='store_true', help='Use Cython reactor backend')
parser.add_argument('--engine', action='store_true', help='Use Python engine backend')
parser.add_argument('--linear', action='store_true', help='Use linear chaining (allows hardware prefetching)')
args, unknown = parser.parse_known_args()

base_dir = os.getcwd()
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)

sys.path.append(os.path.join(root_dir, 'control'))

use_reactor = False
if args.reactor:
    use_reactor = True
elif args.engine:
    use_reactor = False
else:
    print("\nSelect Backend:")
    print("1. Engine (Python) [Default]")
    print("2. Reactor (Cython)")
    choice = input("Choice (1/2): ").strip()
    if choice == '2':
        use_reactor = True

if use_reactor:
    print("Using Reactor (Cython) Backend")
    sys.path.insert(0, os.path.join(root_dir, 'reactor'))
else:
    print("Using Engine (Python) Backend")
    sys.path.insert(0, os.path.join(root_dir, 'engine'))

try:
    from Circuit import Circuit
    import Const
except ImportError:
    print("Error: Could not import reactor. Run this from the project root.")
    sys.exit(1)

def get_cpu_info():
    """Fetches exact CPU Name and Hardware Cache Limits from the OS."""
    cpu_name = platform.processor()
    l2, l3 = "Unknown", "Unknown"
    try:
        if platform.system() == "Windows":
            out_name = subprocess.check_output(["wmic", "cpu", "get", "Name"], text=True)
            lines_name = [l.strip() for l in out_name.split('\n') if l.strip()]
            if len(lines_name) > 1:
                cpu_name = lines_name[1]
            
            out_cache = subprocess.check_output(["wmic", "cpu", "get", "L2CacheSize,L3CacheSize"], text=True)
            lines_cache = [l.strip() for l in out_cache.split('\n') if l.strip()]
            if len(lines_cache) > 1:
                parts = lines_cache[1].split()
                if len(parts) >= 2:
                    l2 = f"{parts[0]} KB"
                    l3 = f"{parts[1]} KB"
        elif platform.system() == "Linux":
            out = subprocess.check_output(["lscpu"], text=True)
            for line in out.split('\n'):
                if "Model name:" in line: cpu_name = line.split(':')[1].strip()
                elif "L2 cache:" in line: l2 = line.split(':')[1].strip()
                elif "L3 cache:" in line: l3 = line.split(':')[1].strip()
    except Exception:
        pass
    return cpu_name, l2, l3

def build_chain(active_size, linear=False):
    c = Circuit()
    first_gate = c.getcomponent(Const.VARIABLE_ID)
    
    const_high = c.getcomponent(Const.VARIABLE_ID)
    const_low = c.getcomponent(Const.VARIABLE_ID)
    c.toggle(const_high, Const.HIGH)
    c.toggle(const_low, Const.LOW)
    
    gate_types = [Const.AND_ID, Const.OR_ID, Const.XOR_ID, Const.NOT_ID]
    active_gates = []
    
    for i in range(active_size - 1):
        g_type = gate_types[i % 4]
        g = c.getcomponent(g_type)
        active_gates.append((g, g_type))
    
    if not linear:
        random.shuffle(active_gates)
        
    prev_gate = first_gate
    for g, g_type in active_gates:
        c.connect(g, prev_gate, 0)
        if g_type == Const.AND_ID:
            c.connect(g, const_high, 1)
        elif g_type in (Const.OR_ID, Const.XOR_ID):
            c.connect(g, const_low, 1)
        prev_gate = g
        
    c.simulate(Const.SIMULATE)
    return c, first_gate

def get_ram_mb():
    if HAS_PSUTIL:
        return process.memory_info().rss / (1024 * 1024)
    return 0.0

def profile_cache():
    cpu_name, l2_cache, l3_cache = get_cpu_info()
    
    print("======================================================================")
    print("  DARION LOGIC SIM: HARDWARE & CACHE PROFILER")
    print("======================================================================")
    print(f"CPU DETECTED: {cpu_name}")
    print(f"OS CACHE LIMITS: L2: {l2_cache} | L3: {l3_cache}")
    print(f"Memory Mode: {'Linear (Hardware Prefetching)' if args.linear else 'Scrambled (True Random Access)'}")
    print("Metric: 'Evals/sec' = Active logic evaluations processed per second.\n")

    test_sizes = [
        100, 500, 2500, 5000, 10000, 25000, 50000, 
        100000, 250000, 500000, 1000000, 2000000
    ]

    results = []
    peak_throughput = 0
    sweet_spot_min = None
    sweet_spot_max = None
    
    base_ram = get_ram_mb()
    
    print(f"{'Active Gates':>12} | {'Actual RAM':>10} | {'ns/eval':>9} | {'Evals/sec':>11} | {'Speed Drop':>11} | {'Visual'}")
    print("-" * 84)

    gc.disable()

    for size in test_sizes:
        c, start_node = build_chain(size, linear=args.linear)
        current_ram = get_ram_mb() - base_ram
        
        # Calibration
        start_calib = time.perf_counter_ns()
        c.toggle(start_node, Const.HIGH)
        c.toggle(start_node, Const.LOW)
        calib_time = time.perf_counter_ns() - start_calib
        
        iterations = max(5, int(100_000_000 / calib_time)) if calib_time > 0 else max(5, 5_000_000 // (size * 2))
        iterations = min(iterations, 10) if size >= 500000 else iterations

        # Warmup
        c.toggle(start_node, Const.HIGH)
        c.toggle(start_node, Const.LOW)

        best_time_ns = float('inf')
        num_passes = 3 if size >= 100000 else 5
        
        for _ in range(num_passes):
            start_time = time.perf_counter_ns()
            for _ in range(iterations):
                c.toggle(start_node, Const.HIGH)
                c.toggle(start_node, Const.LOW)
            end_time = time.perf_counter_ns()
            if (end_time - start_time) < best_time_ns:
                best_time_ns = end_time - start_time

        total_evaluations = size * iterations * 2
        ns_per_eval = best_time_ns / total_evaluations if best_time_ns > 0 else 0.0
        evals_per_sec = 1_000_000_000 / ns_per_eval if ns_per_eval > 0 else 0.0
        
        if evals_per_sec > peak_throughput:
            peak_throughput = evals_per_sec

        drop_pct = ((peak_throughput - evals_per_sec) / peak_throughput) * 100 if peak_throughput > 0 else 0
        
        # Track 0-10% Sweet Spot
        if drop_pct <= 10.0:
            if sweet_spot_min is None: sweet_spot_min = size
            sweet_spot_max = size

        bar_length = int((evals_per_sec / peak_throughput) * 20) if peak_throughput > 0 else 20
        visual_bar = "█" * max(1, bar_length)

        # Dynamic cliff detection
        tag = ""
        latency_jump = ((ns_per_eval - results[-1]['ns_per_eval']) / results[-1]['ns_per_eval']) * 100 if results else 0
        if size >= 500 and latency_jump > 15:
            tag = f"<-- CACHE CLIFF (+{latency_jump:.0f}% latency)"
            
        results.append({
            "size": size, "ns_per_eval": ns_per_eval, "evals_per_sec": evals_per_sec,
            "drop_pct": drop_pct, "mem_mb": current_ram
        })

        cliff_indicator = "!" if latency_jump > 15 else " "
        print(f"{size:>12,} | {current_ram:>7.1f} MB | {ns_per_eval:>7.2f} ns | {evals_per_sec/1_000_000:>6.2f} M/s | {drop_pct:>9.1f}% | {cliff_indicator}{visual_bar} {tag}")

        c.clearcircuit()
        del c
        del start_node
        gc.collect() 

        # --- EARLY STOPPING CONDITION ---
        # if drop_pct >= 50.0:
        #     print(f"\n[!] STOPPING EARLY: Performance dropped by {drop_pct:.1f}% (Exceeded 50% limit).")
        #     break

    gc.enable()
    print("-" * 84)
    print("======================================================================")
    print("  FINAL CACHE INTELLIGENCE REPORT")
    print("======================================================================")
    print(f"-> PEAK THROUGHPUT:   {peak_throughput / 1_000_000:.2f} Million evals/sec")
    print(f"-> SWEET SPOT RANGE:  {sweet_spot_min:,} to {sweet_spot_max:,} concurrent active gates")
    print("                      (Throughput remains within 0% - 10% of maximum cache speeds).")
    print(f"-> HARDWARE MATCH:    Review the MB column above against your {l3_cache} L3 cache.")
    print("======================================================================")

if __name__ == "__main__":
    profile_cache()
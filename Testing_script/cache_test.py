"""
DARION LOGIC SIM - ADVANCED HARDWARE CACHE PROFILER
Dynamically detects hardware boundaries using latency derivatives.
"""

import time
import gc
import sys
import os 
import random
import argparse
import platform
import subprocess
import io
# Force the standard output to use UTF-8
# Force the standard output to use UTF-8
import sys
if hasattr(sys, 'stdout') and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
try:
    import ctypes
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
except Exception:
    pass
try:
    import psutil
    process = psutil.Process(os.getpid())
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

parser = argparse.ArgumentParser(description='Run Cache Profiler')
parser.add_argument('--reactor', action='store_true', help='Use Cython reactor backend')
parser.add_argument('--engine', action='store_true', help='Use Python engine backend')
parser.add_argument('--mode', type=str, choices=['linear', 'realistic', 'chaotic'], default='realistic',
                    help="Memory fragmentation mode (default: realistic)")
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
    cpu_name = platform.processor()
    l2, l3 = "Unknown", "Unknown"
    try:
        if platform.system() == "Windows":
            out_name = subprocess.check_output(["wmic", "cpu", "get", "Name"], text=True)
            lines_name = [l.strip() for l in out_name.split('\n') if l.strip()]
            if len(lines_name) > 1: cpu_name = lines_name[1]
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

def build_chain(active_size, mode='realistic'):
    c = Circuit()
    first_gate = c.getcomponent(Const.VARIABLE_ID)
    
    const_high = c.getcomponent(Const.VARIABLE_ID)
    const_low = c.getcomponent(Const.VARIABLE_ID)
    c.toggle(const_high, Const.HIGH)
    c.toggle(const_low, Const.LOW)
    
    gate_types = [Const.AND_ID, Const.OR_ID, Const.XOR_ID, Const.NOT_ID]
    active_gates = []
    
    # Allocate Gates
    for i in range(active_size - 1):
        g_type = gate_types[i % 4]
        g = c.getcomponent(g_type)
        active_gates.append((g, g_type))
    
    # --- FRAGMENTATION LOGIC ---
    if mode == 'chaotic':
        # Absolute Worst Case (100% Cache Misses)
        random.shuffle(active_gates)
    elif mode == 'realistic':
        # Real-World Workflow: Users build in discrete sub-circuits (e.g., 64-gate chunks).
        # Memory is sequential inside the chunk, but jumps randomly between chunks.
        chunk_size = 64
        chunks = [active_gates[i:i + chunk_size] for i in range(0, len(active_gates), chunk_size)]
        random.shuffle(chunks) # Shuffle the sub-circuits
        active_gates = [gate for chunk in chunks for gate in chunk] # Flatten back out

    # Wire Gates
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
    print("  DARION LOGIC SIM: ADVANCED CACHE PROFILER (HARDWARE AGNOSTIC)")
    print("======================================================================")
    print(f"CPU DETECTED: {cpu_name}")
    print(f"OS CACHE LIMITS: L2: {l2_cache} | L3: {l3_cache}")
    print(f"Memory Mode: {args.mode.upper()}")
    
    if args.mode == 'realistic':
        print(" -> Simulating temporal locality: sequential RAM inside sub-circuits,")
        print("    but fragmented wire routing between major components.")
        
    print("Metric: 'Evals/sec' = Active logic evaluations processed per second.\n")

    # Geometric Progression ~15% growth
    test_sizes = []
    current_size = 100
    while current_size <= 2_500_000:
        test_sizes.append(current_size)
        current_size = int(current_size * 1.15)

    results = []
    base_ram = get_ram_mb()
    
    print(f"{'Active Gates':>12} | {'Actual RAM':>10} | {'ns/eval':>9} | {'Evals/sec':>11} | {'Degradation':>11} | {'Visual'}")
    print("-" * 88)

    gc.disable()
    
    baseline_ns = None
    profile_cache.current_zone = 1
    profile_cache.zone_limits = {1: 0, 2: 0, 3: 0}

    for idx, size in enumerate(test_sizes):
        c, start_node = build_chain(size, mode=args.mode)
        current_ram = get_ram_mb() - base_ram
        
        # Calibration
        start_calib = time.perf_counter_ns()
        c.toggle(start_node, Const.HIGH)
        c.toggle(start_node, Const.LOW)
        calib_time = time.perf_counter_ns() - start_calib
        
        iterations = max(5, int(100_000_000 / calib_time)) if calib_time > 0 else max(5, 5_000_000 // (size * 2))
        iterations = min(iterations, 10) if size >= 500000 else iterations

        # Warmup
        for _ in range(3):
            c.toggle(start_node, Const.HIGH)
            c.toggle(start_node, Const.LOW)

        if hasattr(c, 'activate_eval'):
            c.activate_eval()

        best_time_ns = float('inf')
        best_evals = 0
        num_passes = 3 if size >= 100000 else 5
        
        for _ in range(num_passes):
            start_evals = c.eval_count if hasattr(c, 'activate_eval') else 0
            start_time = time.perf_counter_ns()
            for _ in range(iterations):
                c.toggle(start_node, Const.HIGH)
                c.toggle(start_node, Const.LOW)
            end_time = time.perf_counter_ns()
            end_evals = c.eval_count if hasattr(c, 'activate_eval') else 0
            
            if (end_time - start_time) < best_time_ns:
                best_time_ns = end_time - start_time
                best_evals = end_evals - start_evals

        total_evaluations = best_evals if hasattr(c, 'activate_eval') else size * iterations * 2
        ns_per_eval = best_time_ns / total_evaluations if best_time_ns > 0 else 0.0
        evals_per_sec = 1_000_000_000 / ns_per_eval if ns_per_eval > 0 else 0.0
        
        # Establish a stable L1/L2 baseline using the first few valid measurements
        if baseline_ns is None and idx >= 2: 
            baseline_ns = sum(r['ns_per_eval'] for r in results) / len(results)

        degradation_pct = 0.0
        if baseline_ns:
            degradation_pct = ((ns_per_eval - baseline_ns) / baseline_ns) * 100

        # --- UNIVERSAL HARDWARE-AGNOSTIC ZONE DETECTION ---
        tag = ""
        cliff_indicator = " "
        
        if len(results) >= 2:
            rolling_avg_ns = sum(r['ns_per_eval'] for r in results[-3:]) / min(3, len(results))
            local_jump_pct = ((ns_per_eval - rolling_avg_ns) / rolling_avg_ns) * 100
            
            if local_jump_pct > 15.0 and size > 1000:
                if profile_cache.current_zone == 1:
                    tag = f"<-- CACHE BOUNDARY EVACUATION (+{local_jump_pct:.0f}%)"
                    cliff_indicator = "!"
                    profile_cache.current_zone = 2
                elif profile_cache.current_zone == 2 and local_jump_pct > 20.0:
                    tag = f"<-- MAIN RAM WALL (+{local_jump_pct:.0f}%)"
                    cliff_indicator = "!"
                    profile_cache.current_zone = 3
            
            elif degradation_pct > 100 and profile_cache.current_zone < 3:
                profile_cache.current_zone = 3
                tag = "(RAM BOUND)"

        profile_cache.zone_limits[profile_cache.current_zone] = size

        # Visual Bar
        anchor_ns = baseline_ns if baseline_ns else ns_per_eval
        speed_ratio = anchor_ns / ns_per_eval if ns_per_eval > 0 else 0
        bar_length = int(speed_ratio * 20)
        visual_bar = "=" * max(1, min(bar_length, 20))

        results.append({
            "size": size, "ns_per_eval": ns_per_eval, "evals_per_sec": evals_per_sec,
            "mem_mb": current_ram
        })

        print(f"{size:>12,} | {current_ram:>7.1f} MB | {ns_per_eval:>7.2f} ns | {evals_per_sec/1_000_000:>6.2f} M/s | {degradation_pct:>9.1f}% | {cliff_indicator}{visual_bar} {tag}")

        c.clearcircuit()
        del c
        del start_node
        gc.collect() 

        if degradation_pct >= 400.0:
            print(f"\n[!] STOPPING EARLY: Latency degraded by 400%. CPU is fully RAM-bound.")
            break

    gc.enable()
    print("-" * 88)
    print("======================================================================")
    print("  FINAL CACHE INTELLIGENCE REPORT (HARDWARE AGNOSTIC)")
    print("======================================================================")
    print(f"-> BASELINE L1/L2 SPEED: {1_000 / baseline_ns if baseline_ns else 0:.2f} M evals/sec ({baseline_ns:.2f} ns/eval)")
    print("")
    print("--- DYNAMICALLY DETECTED HARDWARE BOUNDARIES ---")
    
    z1_max = profile_cache.zone_limits.get(1, 0)
    print(f"-> TIER 1 (Core Cache):  Up to {z1_max:,} active gates")
    print("                         Absolute peak hardware throughput.")
    
    z2_max = profile_cache.zone_limits.get(2, 0)
    if z2_max > z1_max:
        print(f"-> TIER 2 (Last Level):  {z1_max + 1:,} to {z2_max:,} active gates")
        print("                         Evicted from Core Cache. Running in shared cache or unified memory.")
    
    z3_max = profile_cache.zone_limits.get(3, 0)
    if z3_max > z2_max:
        print(f"-> TIER 3 (Main RAM):    {z2_max + 1:,}+ active gates")
        print("                         CPU is bounded by memory bus speed.")
    print("======================================================================")

if __name__ == "__main__":
    profile_cache()
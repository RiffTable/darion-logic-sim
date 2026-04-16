"""
DARION LOGIC SIM - HIGH-INTEGRITY CACHE & OPTIMIZATION PROFILER
Compares unoptimized fragmented memory vs. topologically sorted memory in a single pass.
Features dynamic cliff detection and tests both Worst-Case and Real-World fragmentation.
"""
import asyncio
import time
import gc
import sys
import os 
import random
import argparse
import platform
import subprocess

# Force the standard output to use UTF-8
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

parser = argparse.ArgumentParser(description='Run High-Integrity Cache Profiler Comparison')
parser.add_argument('--engine', action='store_true', help='Use Python engine backend (default: Reactor/Cython)')
args, unknown = parser.parse_known_args()

base_dir = os.getcwd()
script_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(script_dir, 'reactor')) or os.path.exists(os.path.join(script_dir, 'engine')):
    root_dir = script_dir
else:
    root_dir = os.path.dirname(script_dir)

sys.path.append(os.path.join(root_dir, 'control'))

use_reactor = not args.engine

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

def build_chain(active_size, mode='chaotic'):
    """Builds a chain with configurable memory allocation modes."""
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
        # Real-World Workflow: Sequential inside sub-circuits, fragmented routing between them
        chunk_size = 64
        chunks = [active_gates[i:i + chunk_size] for i in range(0, len(active_gates), chunk_size)]
        random.shuffle(chunks)
        active_gates = [gate for chunk in chunks for gate in chunk]

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

def benchmark_pass(c, start_node, size, iterations):
    """Runs a benchmark pass on the current circuit state."""
    # Warmup
    for _ in range(3):
        c.toggle(start_node, Const.HIGH)
        c.toggle(start_node, Const.LOW)

    best_time_ns = float('inf')
    best_evals = 0
    num_passes = 3 if size >= 100000 else 5
    
    for _ in range(num_passes):
        start_evals = c.eval_count if hasattr(c, 'eval_count') else 0
        start_time = time.perf_counter_ns()
        for _ in range(iterations):
            c.toggle(start_node, Const.HIGH)
            c.toggle(start_node, Const.LOW)
        end_time = time.perf_counter_ns()
        end_evals = c.eval_count if hasattr(c, 'eval_count') else 0
        
        if (end_time - start_time) < best_time_ns:
            best_time_ns = end_time - start_time
            best_evals = end_evals - start_evals

    total_evaluations = best_evals if hasattr(c, 'eval_count') else size * iterations * 2
    ns_per_eval = best_time_ns / total_evaluations if best_time_ns > 0 else 0.0
    return ns_per_eval

async def run_profiler_suite(mode_name):
    print(f"\n[{mode_name.upper()} FRAGMENTATION vs OPTIMIZED]")
    if mode_name == 'chaotic':
        print(" -> Testing Absolute Worst Case: 100% memory fragmentation.")
    else:
        print(" -> Testing Real-World Workflows: Sequential chunks, fragmented routing.")

    test_sizes = []
    current_size = 100
    while current_size <= 2_000_000:
        test_sizes.append(current_size)
        current_size = int(current_size * 1.30)  # 30% jump to move through tiers faster

    base_ram = get_ram_mb()
    results = []
    current_zone = 1
    
    print(f"{'Active Gates':>12} | {'RAM (MB)':>8} | {'Unopt (ns)':>10} | {'Unopt (ME/s)':>12} | {'Opt (ns)':>8} | {'Opt (ME/s)':>10} | {'Speedup':>7} | {'Hardware Bounds'}")
    print("-" * 120)

    gc.disable()

    for size in test_sizes:
        c, start_node = build_chain(size, mode=mode_name)
        current_ram = get_ram_mb() - base_ram
        
        # Calibration to determine iterations
        start_calib = time.perf_counter_ns()
        c.toggle(start_node, Const.HIGH)
        c.toggle(start_node, Const.LOW)
        calib_time = time.perf_counter_ns() - start_calib
        iterations = max(5, int(50_000_000 / calib_time)) if calib_time > 0 else max(5, 5_000_000 // (size * 2))
        iterations = min(iterations, 10) if size >= 200000 else iterations

        # --- PASS 1: UNOPTIMIZED ---
        unopt_ns = benchmark_pass(c, start_node, size, iterations)
        unopt_me = 1000.0 / unopt_ns if unopt_ns > 0 else 0.0
        
        # --- PASS 2: OPTIMIZED ---
        c.optimize()
        opt_ns = benchmark_pass(c, start_node, size, iterations)
        opt_me = 1000.0 / opt_ns if opt_ns > 0 else 0.0

        # Metrics
        speedup = unopt_ns / opt_ns if opt_ns > 0 else 0
        
        # --- DYNAMIC CLIFF DETECTION (Using Unoptimized Latency) ---
        tag = ""
        results.append(unopt_ns)
        if len(results) >= 2:
            rolling_avg_ns = sum(results[-3:-1]) / min(2, len(results)-1)
            local_jump_pct = ((unopt_ns - rolling_avg_ns) / rolling_avg_ns) * 100
            
            if local_jump_pct > 15.0 and size > 1000:
                if current_zone == 1:
                    tag = f"<-- CACHE BOUNDARY EVACUATION (+{local_jump_pct:.0f}%)"
                    current_zone = 2
                elif current_zone == 2 and local_jump_pct > 20.0:
                    tag = f"<-- MAIN RAM WALL (+{local_jump_pct:.0f}%)"
                    current_zone = 3
            elif unopt_ns > (results[1] * 2.5 if len(results)>1 else 50) and current_zone < 3:
                current_zone = 3
                tag = "(RAM BOUND)"

        print(f"{size:>12,} | {current_ram:>8.1f} | {unopt_ns:>10.2f} | {unopt_me:>12.2f} | {opt_ns:>8.2f} | {opt_me:>10.2f} | {speedup:>6.2f}x | {tag}")

        # Cleanup
        if getattr(c, 'runner', None) is not None and not c.runner.done():
            c.runner.cancel()
        c.clearcircuit()
        del c
        del start_node
        gc.collect() 

    gc.enable()
    print("-" * 120)

async def main_profile():
    cpu_name, l2_cache, l3_cache = get_cpu_info()
    
    print("========================================================================================================================")
    print("  DARION LOGIC SIM: HIGH-INTEGRITY CACHE & OPTIMIZER PROFILER")
    print("========================================================================================================================")
    print(f"CPU DETECTED: {cpu_name}")
    print(f"OS CACHE LIMITS: L2: {l2_cache} | L3: {l3_cache}")
    print("This profiler determines the performance gap between unoptimized user circuits and topologies")
    print("rectified by the optimize() pass. It dynamically detects hardware cliffs (L2/L3 evictions) to prove")
    print("that the optimizer successfully flattens the RAM-Bound curve.")
    print("========================================================================================================================\n")

    await run_profiler_suite('chaotic')
    await run_profiler_suite('realistic')
    
    print("\n========================================================================================================================")
    print("  PROFILING COMPLETE.")
    print("  The 'Speedup' column validates the performance recovery granted by topological linearization.")
    print("========================================================================================================================")

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
    _LOG = "comparison_test_results.txt"
    _backend = 'Reactor' if use_reactor else 'Engine'
    with open(_LOG, "a", encoding="utf-8") as _lf:
        _lf.write(f"\n{'='*70}\n")
        _lf.write(f"RUN  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        _lf.write(f"ARGS : backend={_backend} HIGH-INTEGRITY COMPARISON\n")
        _lf.write(f"{'='*70}\n")
        _orig = sys.stdout
        sys.stdout = _Tee(_orig, _lf)
        try:
            asyncio.run(main_profile())
        except KeyboardInterrupt:
            print("\n[!] Profiling Aborted by User.")
        finally:
            sys.stdout = _orig
    print(f"\nLog saved to: {_LOG}")
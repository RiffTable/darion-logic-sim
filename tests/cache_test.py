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
import matplotlib.pyplot as plt
import numpy as np

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
    
    for i in range(active_size - 1):
        g_type = gate_types[i % 4]
        g = c.getcomponent(g_type)
        active_gates.append((g, g_type))
    
    if mode == 'chaotic':
        random.shuffle(active_gates)
    elif mode == 'realistic':
        chunk_size = 64
        chunks = [active_gates[i:i + chunk_size] for i in range(0, len(active_gates), chunk_size)]
        random.shuffle(chunks)
        active_gates = [gate for chunk in chunks for gate in chunk]

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
    print(f"\n[{mode_name.upper()} FRAGMENTATION vs OPTIMIZED BFS vs OPTIMIZED SWEEP]")
    
    test_sizes = []
    current_size = 100
    while current_size <= 2_000_000:
        test_sizes.append(current_size)
        current_size = int(current_size * 1.30)

    base_ram = get_ram_mb()
    results = []
    current_zone = 1
    
    plot_data = {"sizes": [], "unopt_me": [], "opt_bfs_me": [], "opt_sweep_me": []}
    
    print(f"{'Active Gates':>12} | {'RAM (MB)':>8} | {'Unopt (ME/s)':>12} | {'Opt BFS (ME/s)':>14} | {'Opt Sweep (ME/s)':>16} | {'Speedup (BFS/Swp)':>17} | {'Hardware Bounds'}")
    print("-" * 120)

    gc.disable()

    for size in test_sizes:
        c, start_node = build_chain(size, mode=mode_name)
        current_ram = get_ram_mb() - base_ram
        
        start_calib = time.perf_counter_ns()
        c.toggle(start_node, Const.HIGH)
        c.toggle(start_node, Const.LOW)
        calib_time = time.perf_counter_ns() - start_calib
        iterations = max(5, int(50_000_000 / calib_time)) if calib_time > 0 else max(5, 5_000_000 // (size * 2))
        iterations = min(iterations, 10) if size >= 200000 else iterations

        # PASS 1: UNOPTIMIZED (BFS)
        c.simulate(Const.SIMULATE)
        unopt_ns = benchmark_pass(c, start_node, size, iterations)
        unopt_me = 1000.0 / unopt_ns if unopt_ns > 0 else 0.0
        
        # PASS 2: OPTIMIZED (BFS)
        c.optimize()
        opt_bfs_ns = benchmark_pass(c, start_node, size, iterations)
        opt_bfs_me = 1000.0 / opt_bfs_ns if opt_bfs_ns > 0 else 0.0

        # PASS 3: OPTIMIZED (SWEEP / COMPILE MODE)
        c.simulate(Const.COMPILE)
        opt_sweep_ns = benchmark_pass(c, start_node, size, iterations)
        opt_sweep_me = 1000.0 / opt_sweep_ns if opt_sweep_ns > 0 else 0.0

        plot_data["sizes"].append(size)
        plot_data["unopt_me"].append(unopt_me)
        plot_data["opt_bfs_me"].append(opt_bfs_me)
        plot_data["opt_sweep_me"].append(opt_sweep_me)

        speedup_bfs = unopt_ns / opt_bfs_ns if opt_bfs_ns > 0 else 0
        speedup_sweep = unopt_ns / opt_sweep_ns if opt_sweep_ns > 0 else 0
        speedup_str = f"{speedup_bfs:.1f}x / {speedup_sweep:.1f}x"
        
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

        print(f"{size:>12,} | {current_ram:>8.1f} | {unopt_me:>12.2f} | {opt_bfs_me:>14.2f} | {opt_sweep_me:>16.2f} | {speedup_str:>17} | {tag}")

        if getattr(c, 'runner', None) is not None and not c.runner.done():
            c.runner.cancel()
        c.clearcircuit()
        del c
        del start_node
        gc.collect() 

    gc.enable()
    print("-" * 120)
    return plot_data

def generate_cache_plot(data_chaotic, data_realistic, cpu_name, output_dir):
    """Generates beautiful separate plots for Realistic and Chaotic fragmentation."""
    os.makedirs(output_dir, exist_ok=True)
    plt.style.use('dark_background')

    def create_plot(title, data, save_name, line1_label, line2_label):
        fig, ax = plt.subplots(figsize=(11, 6.5), facecolor='#121212')
        ax.set_facecolor('#121212')
        
        sizes = data['sizes']
        unopt = data['unopt_me']
        opt = data['opt_bfs_me']
        
        # Unoptimized Line (The Baseline)
        ax.plot(sizes, unopt, marker='o', markersize=6, linestyle='-', color='#FF3366', linewidth=2.5, alpha=0.9, label=line1_label)
        
        # Optimized Line (The Bridge)
        ax.plot(sizes, opt, marker='s', markersize=6, linestyle='--', color='#00FFCC', linewidth=2.5, alpha=0.9, label=line2_label)
        
        # Fill between to highlight the performance gained
        ax.fill_between(sizes, unopt, opt, color='#00FFCC', alpha=0.08)

        ax.set_xscale('log')
        ax.set_title(f"{title}\nCPU: {cpu_name}", fontsize=15, fontweight='bold', color='#FFFFFF', pad=15)
        ax.set_xlabel("Circuit Size (Number of Active Logic Gates) - Log Scale", fontsize=12, color='#E0E0E0', labelpad=10)
        ax.set_ylabel("Throughput (Million Evaluations / Sec)", fontsize=12, color='#E0E0E0', labelpad=10)
        
        # Decluttering chart junk
        ax.grid(True, color='#333333', linestyle=':', linewidth=1, alpha=0.8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('#444444')
        ax.spines['left'].set_color('#444444')
        ax.tick_params(colors='#E0E0E0', which='both')

        # Cleaner legend
        legend = ax.legend(frameon=True, facecolor='#1A1A1A', edgecolor='#333333', fontsize=11, loc='upper right')
        for text in legend.get_texts():
            text.set_color('#E0E0E0')
            
        save_path = os.path.join(output_dir, save_name)
        plt.tight_layout()
        plt.savefig(save_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
        plt.close()
        print(f"Performance Graph saved to: {save_path}")

    # 1. Generate Realistic Plot
    create_plot(
        "Realistic Memory Fragmentation: Unoptimized vs Optimized",
        data_realistic,
        "cache_profiler_realistic.png",
        "Realistic (Unoptimized BFS)",
        "Optimized (BFS Queue)"
    )
    
    # 2. Generate Chaotic Plot
    create_plot(
        "Chaotic Memory Fragmentation: Unoptimized vs Optimized",
        data_chaotic,
        "cache_profiler_chaotic.png",
        "Chaotic (Unoptimized BFS)",
        "Optimized (BFS Queue)"
    )

async def main_profile():
    cpu_name, l2_cache, l3_cache = get_cpu_info()
    
    print("========================================================================================================================")
    print("  DARION LOGIC SIM: HIGH-INTEGRITY CACHE & OPTIMIZER PROFILER")
    print("========================================================================================================================")
    
    data_chaotic = await run_profiler_suite('chaotic')
    data_realistic = await run_profiler_suite('realistic')
    
    plots_dir = os.path.join(script_dir, 'benchmark_plots')
    generate_cache_plot(data_chaotic, data_realistic, cpu_name, plots_dir)

class _Tee:
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
        _orig = sys.stdout
        sys.stdout = _Tee(_orig, _lf)
        try:
            asyncio.run(main_profile())
        except KeyboardInterrupt:
            print("\n[!] Profiling Aborted by User.")
        finally:
            sys.stdout = _orig
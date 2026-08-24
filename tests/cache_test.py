"""
DARION LOGIC SIM - HIGH-INTEGRITY CACHE & OPTIMIZATION PROFILER
Compares unoptimized fragmented memory vs. topologically sorted memory in a single pass.
Features dynamic cliff detection and tests both Worst-Case (Chaotic) and Homogeneous gate chains.
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
parser.add_argument('--chaotic', action='store_true', help='Run mixed chaotic test')
parser.add_argument('--realistic', action='store_true', help='Run mixed realistic test')
parser.add_argument('--mixed', action='store_true', help='Run all mixed tests')
parser.add_argument('--and', dest='gate_and', action='store_true', help='Run homogeneous AND test')
parser.add_argument('--nand', dest='gate_nand', action='store_true', help='Run homogeneous NAND test')
parser.add_argument('--or', dest='gate_or', action='store_true', help='Run homogeneous OR test')
parser.add_argument('--nor', dest='gate_nor', action='store_true', help='Run homogeneous NOR test')
parser.add_argument('--xor', dest='gate_xor', action='store_true', help='Run homogeneous XOR test')
parser.add_argument('--xnor', dest='gate_xnor', action='store_true', help='Run homogeneous XNOR test')
parser.add_argument('--not', dest='gate_not', action='store_true', help='Run homogeneous NOT test')
parser.add_argument('--dump', action='store_true', help='Dump output to time-stamped txt in test_results')
parser.add_argument('--plot', action='store_true', help='Generate plots in test_results')
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

# ---------------------------------------------------------------------------
# Gate metadata helpers
# ---------------------------------------------------------------------------

# Maps a gate type to (needs_second_input, second_input_value)
# NOT is unary; all others need a second constant input.
_GATE_META = {
    Const.AND_ID:  (True,  Const.HIGH),   # AND  : keep second input HIGH
    Const.NAND_ID: (True,  Const.HIGH),   # NAND : keep second input HIGH
    Const.OR_ID:   (True,  Const.LOW),    # OR   : keep second input LOW
    Const.NOR_ID:  (True,  Const.LOW),    # NOR  : keep second input LOW
    Const.XOR_ID:  (True,  Const.LOW),    # XOR  : keep second input LOW
    Const.XNOR_ID: (True,  Const.LOW),    # XNOR : keep second input LOW
    Const.NOT_ID:  (False, None),          # NOT  : unary, no second input
}

GATE_NAMES = {
    Const.AND_ID:  "AND",
    Const.NAND_ID: "NAND",
    Const.OR_ID:   "OR",
    Const.NOR_ID:  "NOR",
    Const.XOR_ID:  "XOR",
    Const.XNOR_ID: "XNOR",
    Const.NOT_ID:  "NOT",
}

ALL_GATE_TYPES = [
    Const.AND_ID, Const.NAND_ID,
    Const.OR_ID,  Const.NOR_ID,
    Const.XOR_ID, Const.XNOR_ID,
    Const.NOT_ID,
]

def _connect_gate(c, g, g_type, prev_gate, const_high, const_low):
    """Wire a gate to its predecessor and apply a constant second input if needed."""
    c.connect(g, prev_gate, 0)
    needs_second, second_val = _GATE_META[g_type]
    if needs_second:
        const_gate = const_high if second_val == Const.HIGH else const_low
        c.connect(g, const_gate, 1)


def build_chain(active_size, mode='chaotic'):
    """Builds a mixed-gate chain with configurable memory allocation modes."""
    c = Circuit()
    first_gate = c.getcomponent(Const.VARIABLE_ID)

    const_high = c.getcomponent(Const.VARIABLE_ID)
    const_low  = c.getcomponent(Const.VARIABLE_ID)
    c.toggle(const_high, Const.HIGH)
    c.toggle(const_low,  Const.LOW)

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
        _connect_gate(c, g, g_type, prev_gate, const_high, const_low)
        prev_gate = g

    c.simulate(Const.SIMULATE)
    return c, first_gate


def build_homogeneous_chain(active_size, gate_type):
    """Builds a chain made entirely of one gate type, with chaotic allocation order."""
    c = Circuit()
    first_gate = c.getcomponent(Const.VARIABLE_ID)

    const_high = c.getcomponent(Const.VARIABLE_ID)
    const_low  = c.getcomponent(Const.VARIABLE_ID)
    c.toggle(const_high, Const.HIGH)
    c.toggle(const_low,  Const.LOW)

    # Allocate all gates first (chaotic allocation order comes naturally from
    # the interleaved VARIABLE allocs above, but we also shuffle the list).
    gates = [c.getcomponent(gate_type) for _ in range(active_size - 1)]
    random.shuffle(gates)

    prev_gate = first_gate
    for g in gates:
        _connect_gate(c, g, gate_type, prev_gate, const_high, const_low)
        prev_gate = g

    c.simulate(Const.SIMULATE)
    return c, first_gate


def get_ram_mb():
    if HAS_PSUTIL:
        return process.memory_info().rss / (1024 * 1024)
    return 0.0

def benchmark_pass(c, start_node, size, iterations, is_sweep=False, const=None):
    """Runs a benchmark pass on the current circuit state."""
    if is_sweep and hasattr(c, 'batch_toggle'):
        batch = [(start_node.location, const.HIGH), (start_node.location, const.LOW)] * 3
        c.batch_toggle(batch, 1)
    else:
        for _ in range(3):
            c.toggle(start_node, const.HIGH)
            c.toggle(start_node, const.LOW)

    best_time_ns = float('inf')
    best_evals = 0
    num_passes = 3 if size >= 100000 else 5

    for _ in range(num_passes):
        start_evals = c.eval_count if hasattr(c, 'eval_count') else 0
        start_time = time.perf_counter_ns()
        
        if is_sweep and hasattr(c, 'batch_toggle'):
            batch = [(start_node.location, const.HIGH), (start_node.location, const.LOW)] * iterations
            c.batch_toggle(batch, 1)
        else:
            for _ in range(iterations):
                c.toggle(start_node, const.HIGH)
                c.toggle(start_node, const.LOW)
                
        end_time = time.perf_counter_ns()
        end_evals = c.eval_count if hasattr(c, 'eval_count') else 0

        if (end_time - start_time) < best_time_ns:
            best_time_ns = end_time - start_time
            best_evals = end_evals - start_evals

    total_evaluations = best_evals if hasattr(c, 'eval_count') else size * iterations * 2
    best_time_ms = best_time_ns / 1_000_000.0
    return best_time_ms, total_evaluations


# ---------------------------------------------------------------------------
# Profiler suites
# ---------------------------------------------------------------------------

async def run_profiler_suite(mode_name):
    """Mixed-gate chaotic/realistic fragmentation profiler (Unopt BFS vs Opt BFS)."""
    print("=" * 145)
    print(f"  [{mode_name.upper()} FRAGMENTATION — MIXED GATE CHAIN]")
    print("=" * 145)

    test_sizes = []
    current_size = 100
    while current_size <= 1_000_000:
        test_sizes.append(current_size)
        current_size = int(current_size * 1.30)

    base_ram = get_ram_mb()
    results = []
    current_zone = 1

    plot_data = {"sizes": [], "unopt_me": [], "opt_bfs_me": []}

    hdr = (
        f"| {'Active Gates':<12} | {'RAM (MB)':>8} | "
        f"{'Unopt(ms)':>10} | {'Opt(ms)':>10} | {'Sweep(ms)':>10} | "
        f"{'Unopt-ev':>11} | {'Opt-ev':>11} | {'Sweep-ev':>11} | "
        f"{'Opt-spd':>8} | {'Swp-spd':>8} | {'Mean Jump':>9} | {'Bounds'}"
    )
    print(hdr)
    print("-" * len(hdr))

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
        unopt_ms, unopt_ev = benchmark_pass(c, start_node, size, iterations, const=Const)

        jumps = c.geometry()
        mean_jump = sum(jumps) / len(jumps) if jumps else 0.0

        # PASS 2: OPTIMIZED (BFS)
        c.optimize()
        opt_ms, opt_ev = benchmark_pass(c, start_node, size, iterations, const=Const)

        # PASS 3: OPTIMIZED (SWEEP)
        sweep_ms, sweep_ev = None, None
        has_sweep = (
            hasattr(Const, 'COMPILE')
            and hasattr(Const, 'set_MODE')
            and hasattr(c, 'simulate')
        )
        if has_sweep:
            c.simulate(Const.COMPILE)
            Const.set_MODE(Const.COMPILE)
            sweep_ms, sweep_ev = benchmark_pass(c, start_node, size, iterations, is_sweep=True, const=Const)
            Const.set_MODE(Const.SIMULATE)

        plot_data["sizes"].append(size)
        plot_data["unopt_me"].append(unopt_ms)
        plot_data["opt_bfs_me"].append(opt_ms)

        opt_spd = unopt_ms / opt_ms if opt_ms > 0 else 0.0
        swp_spd = unopt_ms / sweep_ms if sweep_ms and sweep_ms > 0 else 0.0

        unopt_ms_str = f"{unopt_ms:.1f}"
        opt_ms_str = f"{opt_ms:.1f}"
        sweep_ms_str = f"{sweep_ms:.1f}" if sweep_ms is not None else "N/A"

        unopt_ev_str = f"{unopt_ev:,}"
        opt_ev_str = f"{opt_ev:,}"
        sweep_ev_str = f"{sweep_ev:,}" if sweep_ev is not None else "N/A"

        opt_spd_str = f"{opt_spd:.1f}x"
        swp_spd_str = f"{swp_spd:.1f}x" if sweep_ms is not None else "N/A"

        tag = ""
        results.append(unopt_ms)
        if len(results) >= 2:
            rolling_avg_ms = sum(results[-3:-1]) / min(2, len(results) - 1)
            local_jump_pct = ((unopt_ms - rolling_avg_ms) / rolling_avg_ms) * 100 if rolling_avg_ms > 0 else 0.0

            if local_jump_pct > 15.0 and size > 1000:
                if current_zone == 1:
                    tag = f"<-- CACHE BOUNDARY EVACUATION (+{local_jump_pct:.0f}%)"
                    current_zone = 2
                elif current_zone == 2 and local_jump_pct > 20.0:
                    tag = f"<-- MAIN RAM WALL (+{local_jump_pct:.0f}%)"
                    current_zone = 3
            elif unopt_ms > (results[1] * 2.5 if len(results) > 1 else 0.05) and current_zone < 3:
                current_zone = 3
                tag = "(RAM BOUND)"

        row = (
            f"| {size:<12,} | {current_ram:>8.1f} | "
            f"{unopt_ms_str:>10} | {opt_ms_str:>10} | {sweep_ms_str:>10} | "
            f"{unopt_ev_str:>11} | {opt_ev_str:>11} | {sweep_ev_str:>11} | "
            f"{opt_spd_str:>8} | {swp_spd_str:>8} | {mean_jump:>9.1f} | {tag}"
        )
        print(row)

        if getattr(c, 'runner', None) is not None and not c.runner.done():
            c.runner.cancel()
        c.clearcircuit()
        del c
        del start_node
        gc.collect()

    gc.enable()
    print("=" * len(hdr))
    return plot_data


async def run_homogeneous_suite(gate_type):
    """Chaotic chain made of a single gate type — Unopt BFS vs Opt BFS."""
    gate_name = GATE_NAMES[gate_type]
    print("=" * 145)
    print(f"  [HOMOGENEOUS CHAOTIC — {gate_name} GATE CHAIN]")
    print("=" * 145)

    test_sizes = []
    current_size = 100
    while current_size <= 1_000_000:
        test_sizes.append(current_size)
        current_size = int(current_size * 1.30)

    base_ram = get_ram_mb()
    results = []
    current_zone = 1

    plot_data = {"sizes": [], "unopt_me": [], "opt_bfs_me": [], "gate": gate_name}

    hdr = (
        f"| {'Active Gates':<12} | {'RAM (MB)':>8} | "
        f"{'Unopt(ms)':>10} | {'Opt(ms)':>10} | {'Sweep(ms)':>10} | "
        f"{'Unopt-ev':>11} | {'Opt-ev':>11} | {'Sweep-ev':>11} | "
        f"{'Opt-spd':>8} | {'Swp-spd':>8} | {'Mean Jump':>9} | {'Bounds'}"
    )
    print(hdr)
    print("-" * len(hdr))

    gc.disable()

    for size in test_sizes:
        c, start_node = build_homogeneous_chain(size, gate_type)
        current_ram = get_ram_mb() - base_ram

        start_calib = time.perf_counter_ns()
        c.toggle(start_node, Const.HIGH)
        c.toggle(start_node, Const.LOW)
        calib_time = time.perf_counter_ns() - start_calib
        iterations = max(5, int(50_000_000 / calib_time)) if calib_time > 0 else max(5, 5_000_000 // (size * 2))
        iterations = min(iterations, 10) if size >= 200000 else iterations

        # PASS 1: UNOPTIMIZED (BFS)
        c.simulate(Const.SIMULATE)
        unopt_ms, unopt_ev = benchmark_pass(c, start_node, size, iterations, const=Const)

        jumps = c.geometry()
        mean_jump = sum(jumps) / len(jumps) if jumps else 0.0

        # PASS 2: OPTIMIZED (BFS)
        c.optimize()
        opt_ms, opt_ev = benchmark_pass(c, start_node, size, iterations, const=Const)

        # PASS 3: OPTIMIZED (SWEEP)
        sweep_ms, sweep_ev = None, None
        has_sweep = (
            hasattr(Const, 'COMPILE')
            and hasattr(Const, 'set_MODE')
            and hasattr(c, 'simulate')
        )
        if has_sweep:
            c.simulate(Const.COMPILE)
            Const.set_MODE(Const.COMPILE)
            sweep_ms, sweep_ev = benchmark_pass(c, start_node, size, iterations, is_sweep=True, const=Const)
            Const.set_MODE(Const.SIMULATE)

        plot_data["sizes"].append(size)
        plot_data["unopt_me"].append(unopt_ms)
        plot_data["opt_bfs_me"].append(opt_ms)

        opt_spd = unopt_ms / opt_ms if opt_ms > 0 else 0.0
        swp_spd = unopt_ms / sweep_ms if sweep_ms and sweep_ms > 0 else 0.0

        unopt_ms_str = f"{unopt_ms:.1f}"
        opt_ms_str = f"{opt_ms:.1f}"
        sweep_ms_str = f"{sweep_ms:.1f}" if sweep_ms is not None else "N/A"

        unopt_ev_str = f"{unopt_ev:,}"
        opt_ev_str = f"{opt_ev:,}"
        sweep_ev_str = f"{sweep_ev:,}" if sweep_ev is not None else "N/A"

        opt_spd_str = f"{opt_spd:.1f}x"
        swp_spd_str = f"{swp_spd:.1f}x" if sweep_ms is not None else "N/A"

        tag = ""
        results.append(unopt_ms)
        if len(results) >= 2:
            rolling_avg_ms = sum(results[-3:-1]) / min(2, len(results) - 1)
            local_jump_pct = ((unopt_ms - rolling_avg_ms) / rolling_avg_ms) * 100 if rolling_avg_ms > 0 else 0.0

            if local_jump_pct > 15.0 and size > 1000:
                if current_zone == 1:
                    tag = f"<-- CACHE BOUNDARY EVACUATION (+{local_jump_pct:.0f}%)"
                    current_zone = 2
                elif current_zone == 2 and local_jump_pct > 20.0:
                    tag = f"<-- MAIN RAM WALL (+{local_jump_pct:.0f}%)"
                    current_zone = 3
            elif unopt_ms > (results[1] * 2.5 if len(results) > 1 else 0.05) and current_zone < 3:
                current_zone = 3
                tag = "(RAM BOUND)"

        row = (
            f"| {size:<12,} | {current_ram:>8.1f} | "
            f"{unopt_ms_str:>10} | {opt_ms_str:>10} | {sweep_ms_str:>10} | "
            f"{unopt_ev_str:>11} | {opt_ev_str:>11} | {sweep_ev_str:>11} | "
            f"{opt_spd_str:>8} | {swp_spd_str:>8} | {mean_jump:>9.1f} | {tag}"
        )
        print(row)

        if getattr(c, 'runner', None) is not None and not c.runner.done():
            c.runner.cancel()
        c.clearcircuit()
        del c
        del start_node
        gc.collect()

    gc.enable()
    print("=" * len(hdr))
    return plot_data


# ---------------------------------------------------------------------------
# Plot generators
# ---------------------------------------------------------------------------

def _base_ax(fig, ax, title, cpu_name):
    ax.set_facecolor('#121212')
    ax.set_xscale('log')
    ax.set_title(f"{title}\nCPU: {cpu_name}", fontsize=14, fontweight='bold', color='#FFFFFF', pad=15)
    ax.set_xlabel("Circuit Size (Number of Active Logic Gates) — Log Scale", fontsize=11, color='#E0E0E0', labelpad=10)
    ax.set_ylabel("Execution Time (ms)", fontsize=11, color='#E0E0E0', labelpad=10)
    ax.grid(True, color='#333333', linestyle=':', linewidth=1, alpha=0.8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#444444')
    ax.spines['left'].set_color('#444444')
    ax.tick_params(colors='#E0E0E0', which='both')


def generate_cache_plot(data_chaotic, data_realistic, cpu_name, output_dir):
    """Generates separate plots for Chaotic and Realistic mixed-gate fragmentation."""
    os.makedirs(output_dir, exist_ok=True)
    plt.style.use('dark_background')

    def create_plot(title, data, save_name):
        if not data:
            return
        fig, ax = plt.subplots(figsize=(11, 6.5), facecolor='#121212')
        _base_ax(fig, ax, title, cpu_name)

        sizes  = data['sizes']
        unopt  = data['unopt_me']
        opt    = data['opt_bfs_me']

        ax.plot(sizes, unopt, marker='o', markersize=6, linestyle='-',
                color='#FF3366', linewidth=2.5, alpha=0.9, label='Unoptimized (BFS)')
        ax.plot(sizes, opt,   marker='s', markersize=6, linestyle='--',
                color='#00FFCC', linewidth=2.5, alpha=0.9, label='Optimized (BFS)')
        ax.fill_between(sizes, unopt, opt, color='#00FFCC', alpha=0.08)

        legend = ax.legend(frameon=True, facecolor='#1A1A1A', edgecolor='#333333',
                           fontsize=11, loc='upper right')
        for text in legend.get_texts():
            text.set_color('#E0E0E0')

        save_path = os.path.join(output_dir, save_name)
        plt.tight_layout()
        plt.savefig(save_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
        plt.close()
        print(f"Performance Graph saved to: {save_path}")

    create_plot(
        "Chaotic Memory Fragmentation: Unoptimized vs Optimized (Mixed Gates)",
        data_chaotic, "cache_profiler_chaotic.png"
    )
    create_plot(
        "Realistic Memory Fragmentation: Unoptimized vs Optimized (Mixed Gates)",
        data_realistic, "cache_profiler_realistic.png"
    )


# Colour palette for the 7 gate types on the homogeneous overview plot
_GATE_COLOURS = {
    "AND":  "#FF3366",
    "NAND": "#FF9933",
    "OR":   "#FFFF33",
    "NOR":  "#33FF99",
    "XOR":  "#33CCFF",
    "XNOR": "#CC66FF",
    "NOT":  "#FF66CC",
}


def generate_homogeneous_plots(homo_results, cpu_name, output_dir):
    """
    Generates:
      1. One individual plot per gate type (Unopt vs Opt BFS).
      2. One overview plot comparing Opt BFS across all gate types.
    """
    os.makedirs(output_dir, exist_ok=True)
    plt.style.use('dark_background')

    # --- Individual per-gate plots ---
    for data in homo_results:
        gate_name = data['gate']
        colour    = _GATE_COLOURS.get(gate_name, '#FFFFFF')

        fig, ax = plt.subplots(figsize=(11, 6.5), facecolor='#121212')
        _base_ax(fig, ax,
                 f"Homogeneous Chaotic Chain — {gate_name} Gate: Unoptimized vs Optimized",
                 cpu_name)

        sizes  = data['sizes']
        unopt  = data['unopt_me']
        opt    = data['opt_bfs_me']

        ax.plot(sizes, unopt, marker='o', markersize=6, linestyle='-',
                color='#FF3366', linewidth=2.5, alpha=0.9, label='Unoptimized (BFS)')
        ax.plot(sizes, opt,   marker='s', markersize=6, linestyle='--',
                color=colour,   linewidth=2.5, alpha=0.9, label=f'Optimized (BFS) — {gate_name}')
        ax.fill_between(sizes, unopt, opt, color=colour, alpha=0.08)

        legend = ax.legend(frameon=True, facecolor='#1A1A1A', edgecolor='#333333',
                           fontsize=11, loc='upper right')
        for text in legend.get_texts():
            text.set_color('#E0E0E0')

        save_path = os.path.join(output_dir, f"cache_profiler_homo_{gate_name.lower()}.png")
        plt.tight_layout()
        plt.savefig(save_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
        plt.close()
        print(f"Performance Graph saved to: {save_path}")

    # --- Overview: Opt BFS across all gate types ---
    if not homo_results:
        return
    fig, ax = plt.subplots(figsize=(13, 7), facecolor='#121212')
    _base_ax(fig, ax,
             "Homogeneous Chaotic Chains — Optimized BFS Throughput by Gate Type",
             cpu_name)

    for data in homo_results:
        gate_name = data['gate']
        colour    = _GATE_COLOURS.get(gate_name, '#FFFFFF')
        ax.plot(data['sizes'], data['opt_bfs_me'],
                marker='o', markersize=5, linestyle='-',
                color=colour, linewidth=2.0, alpha=0.9, label=gate_name)

    legend = ax.legend(frameon=True, facecolor='#1A1A1A', edgecolor='#333333',
                       fontsize=11, loc='upper right', title='Gate Type',
                       title_fontsize=11)
    legend.get_title().set_color('#E0E0E0')
    for text in legend.get_texts():
        text.set_color('#E0E0E0')

    save_path = os.path.join(output_dir, "cache_profiler_homo_overview.png")
    plt.tight_layout()
    plt.savefig(save_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    print(f"Performance Graph saved to: {save_path}")


# ---------------------------------------------------------------------------
# Bottleneck proof
# ---------------------------------------------------------------------------

def print_bottleneck_proof(data_chaotic, homo_results):
    """Isolates and compares the exact penalties of Branching vs Memory at max scale."""
    if not data_chaotic or not homo_results:
        return
    print("\n" + "=" * 100)
    print("  THE BOTTLENECK PROOF: BRANCHING vs. MEMORY (At Maximum Scale)")
    print("=" * 100)

    # Extract AND gate data
    and_data = next((d for d in homo_results if d['gate'] == "AND"), None)
    if not and_data or not data_chaotic['sizes']:
        print("Insufficient data for proof.")
        return

    # Look at the largest circuit size tested (usually ~1,000,000 gates)
    target_size = data_chaotic['sizes'][-1]
    mixed_idx = data_chaotic['sizes'].index(target_size)
    and_idx = and_data['sizes'].index(target_size)

    # 1. Perfect Baseline (Homogeneous + Optimized)
    # 0 Branch Penalty, 0 Memory Penalty
    baseline_me = and_data['opt_bfs_me'][and_idx]

    # 2. Branch Penalty (Mixed + Optimized)
    # Massive Branch Penalty, 0 Memory Penalty
    branch_me = data_chaotic['opt_bfs_me'][mixed_idx]
    branch_penalty = baseline_me - branch_me

    # 3. Memory Penalty (Homogeneous + Unoptimized)
    # 0 Branch Penalty, Massive Memory Penalty
    memory_me = and_data['unopt_me'][and_idx]
    memory_penalty = baseline_me - memory_me

    print(f"Target Circuit Size: {target_size:,} gates\n")
    print(f"1. THE BASELINE (Perfect Memory, No Branches)   : {baseline_me:>8.2f} ME/s (AND Opt)")
    print(f"2. THE BRANCH PENALTY (Perfect Memory, Branches): {branch_me:>8.2f} ME/s (Mixed Opt)")
    print(f"3. THE MEMORY PENALTY (Bad Memory, No Branches) : {memory_me:>8.2f} ME/s (AND Unopt)\n")

    print("-" * 55)

    # Calculate percentage drops (safeguard against division by zero)
    if baseline_me > 0:
        print(f"Cost of Branch Mispredictions : -{branch_penalty:>6.2f} ME/s ({(branch_penalty/baseline_me)*100:>5.1f}% drop)")
        print(f"Cost of L3 Cache/RAM Misses   : -{memory_penalty:>6.2f} ME/s ({(memory_penalty/baseline_me)*100:>5.1f}% drop)")

    print("-" * 55)

    if memory_penalty > branch_penalty and branch_penalty > 0:
        ratio = memory_penalty / branch_penalty
        print(f"CONCLUSION: Memory Latency is {ratio:.1f}x more devastating than Branch Misprediction.")
    elif memory_penalty > branch_penalty:
        print("CONCLUSION: Memory Latency is the absolute dominant bottleneck.")
    else:
        print("CONCLUSION: Branch Misprediction is the dominant bottleneck.")

    print("=" * 100 + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main_profile():
    cpu_name, l2_cache, l3_cache = get_cpu_info()

    print("=" * 100)
    print("  DARION LOGIC SIM: HIGH-INTEGRITY CACHE & OPTIMIZER PROFILER")
    print("=" * 100)

    run_chaotic = args.chaotic or args.mixed
    run_realistic = args.realistic or args.mixed
    run_gates = []
    
    gate_args = {
        'gate_and': Const.AND_ID,
        'gate_nand': Const.NAND_ID,
        'gate_or': Const.OR_ID,
        'gate_nor': Const.NOR_ID,
        'gate_xor': Const.XOR_ID,
        'gate_xnor': Const.XNOR_ID,
        'gate_not': Const.NOT_ID,
    }
    
    for arg_name, gate_id in gate_args.items():
        if getattr(args, arg_name, False):
            run_gates.append(gate_id)
            
    if not (run_chaotic or run_realistic or run_gates):
        run_chaotic = True
        run_realistic = True
        run_gates = ALL_GATE_TYPES

    data_chaotic = None
    data_realistic = None

    # 1. Mixed-gate chains (existing chaotic + realistic)
    if run_chaotic:
        data_chaotic  = await run_profiler_suite('chaotic')
    if run_realistic:
        data_realistic = await run_profiler_suite('realistic')

    # 2. Homogeneous single-gate chaotic chains
    homo_results = []
    for gate_type in run_gates:
        homo_results.append(await run_homogeneous_suite(gate_type))

    if getattr(args, 'plot', False):
        plots_dir = os.path.join(script_dir, 'test_results', 'cache_test', 'plots')
        os.makedirs(plots_dir, exist_ok=True)
        generate_cache_plot(data_chaotic, data_realistic, cpu_name, plots_dir)
        generate_homogeneous_plots(homo_results, cpu_name, plots_dir)

    print_bottleneck_proof(data_chaotic, homo_results)


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
    
    _orig = sys.stdout
    if getattr(args, 'dump', False):
        dump_dir = os.path.join(script_dir, 'test_results', 'cache_test', 'datas')
        os.makedirs(dump_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _LOG = os.path.join(dump_dir, f"cache_test_{timestamp}.txt")
        _lf = open(_LOG, "a", encoding="utf-8")
        sys.stdout = _Tee(_orig, _lf)
    else:
        _lf = None

    _backend = 'Reactor' if use_reactor else 'Engine'
    try:
        asyncio.run(main_profile())
    except KeyboardInterrupt:
        print("\n[!] Profiling Aborted by User.")
    finally:
        sys.stdout = _orig
        if _lf:
            _lf.close()
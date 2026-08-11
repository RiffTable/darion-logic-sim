import os
import sys
import glob
import numpy as np
import matplotlib.pyplot as plt

# --- PATH RESOLUTION ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.insert(0, os.path.join(root_dir, 'reactor'))
sys.path.insert(0, current_dir)

import Circuit
import Const
from iscas_test import VerilogRunner

def analyze_file(filepath, output_dir):
    filename = os.path.basename(filepath)
    print(f"\nLoading {filename}...")
    
    try:
        runner = VerilogRunner(filepath, Circuit.Circuit, Const)
        jumps = runner.circuit.geometry()
    except Exception as e:
        print(f"Error processing {filename}: {e}")
        return None
    
    if not jumps:
        print(f"No connection jumps found for {filename}.")
        return None

    # 1. Calculate Distribution Stats
    jumps_arr = np.array(jumps)
    total_edges = len(jumps_arr)
    mean_jump = np.mean(jumps_arr)
    max_jump = np.max(jumps_arr)
    p50 = np.percentile(jumps_arr, 50)
    p90 = np.percentile(jumps_arr, 90)
    p99 = np.percentile(jumps_arr, 99)
    
    # Assuming > 8 indices crosses a 64-byte cache line
    cache_misses = np.sum(jumps_arr > 8)
    miss_percent = (cache_misses / total_edges) * 100 if total_edges > 0 else 0.0

    print(f"\n{'-'*50}")
    print(f" GEOMETRY PROFILE: {filename}")
    print(f"{'-'*50}")
    print(f" Total Connections : {total_edges:,}")
    print(f" Mean Jump Dist    : {mean_jump:.1f} indices")
    print(f" Median (P50)      : {p50:.0f} indices")
    print(f" 90th Percentile   : {p90:.0f} indices")
    print(f" 99th Percentile   : {p99:.0f} indices")
    print(f" Maximum Jump      : {max_jump:,} indices")
    print(f" Cache Miss Risk   : {cache_misses:,} edges ({miss_percent:.1f}%)")
    print(f"{'-'*50}")

    # 2. Generate Histogram Plot
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))

    bins = np.logspace(0, np.log10(max_jump) if max_jump > 0 else 1, 100)
    
    ax.hist(jumps_arr, bins=bins, color='cyan', alpha=0.7, edgecolor='black')
    
    ax.axvline(8, color='red', linestyle='--', alpha=0.8, label='L1 Cache Line Boundary (>8)')
    ax.axvline(mean_jump, color='orange', linestyle='-', alpha=0.8, label=f'Mean Jump: {mean_jump:.1f}')

    ax.set_xscale('log')
    ax.set_yscale('log')
    
    ax.set_title(f"Memory Locality Profile: {filename}", fontsize=14, pad=15)
    ax.set_xlabel("Jump Distance in RAM (Indices)", fontsize=12)
    ax.set_ylabel("Frequency (Number of Edges)", fontsize=12)
    
    ax.grid(True, alpha=0.15)
    ax.legend()
    
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        save_path = os.path.join(output_dir, f"{filename}_geometry.png")
        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
    plt.close()

    return {
        'circuit': filename,
        'edges': total_edges,
        'mean': mean_jump,
        'p50': p50,
        'p90': p90,
        'p99': p99,
        'max': max_jump,
        'misses': cache_misses,
        'miss_percent': miss_percent
    }

def print_batch_summary(results):
    if not results:
        return
    print("\n" + "="*115)
    print(" BATCH GEOMETRY ANALYSIS SUMMARY REPORT")
    print("="*115)
    print(f"{'Circuit':<18} | {'Edges':>10} | {'Mean Jump':>11} | {'P50':>6} | {'P90':>7} | {'P99':>7} | {'Max Jump':>10} | {'Cache Miss %':>12}")
    print("-" * 115)
    
    for r in results:
        print(f"{r['circuit']:<18} | {r['edges']:10,} | {r['mean']:11.1f} | {r['p50']:6.0f} | {r['p90']:7.0f} | {r['p99']:7.0f} | {r['max']:10,} | {r['miss_percent']:11.1f}%")
    
    print("="*115 + "\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Circuit Geometry Analyzer')
    parser.add_argument('target', nargs='?', type=str, help='Path to a .v file or directory containing .v files')
    parser.add_argument('--dump', action='store_true', help='Dump output to time-stamped txt in test_results')
    parser.add_argument('--plot', action='store_true', help='Generate plots in test_results')
    args = parser.parse_args()

    target = args.target
    if not target:
        target = input("Enter path to .v file or directory: ").strip()

    target = os.path.abspath(target)
    if not os.path.exists(target):
        print(f"Error: Target path '{target}' does not exist.")
        sys.exit(1)

    v_files = []
    if os.path.isdir(target):
        v_files = sorted(glob.glob(os.path.join(target, "*.v")))
        if not v_files:
            v_files = sorted(glob.glob(os.path.join(target, "**", "*.v"), recursive=True))
        if not v_files:
            print(f"No .v files found in directory '{target}'.")
            sys.exit(1)
    elif os.path.isfile(target):
        v_files = [target]
    else:
        print(f"Invalid target: '{target}'")
        sys.exit(1)

    if getattr(args, 'plot', False):
        plots_dir = os.path.join(current_dir, 'test_results', 'geometry', 'plots')
    else:
        plots_dir = None

    results = []
    
    class _Tee:
        def __init__(self, *streams):
            self.streams = streams
        def write(self, data):
            for s in self.streams:
                s.write(data)
        def flush(self):
            for s in self.streams:
                s.flush()

    _orig = sys.stdout
    if getattr(args, 'dump', False):
        import datetime
        dump_dir = os.path.join(current_dir, 'test_results', 'geometry', 'datas')
        os.makedirs(dump_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        _LOG = os.path.join(dump_dir, f"geometry_{timestamp}.txt")
        _lf = open(_LOG, "a", encoding="utf-8")
        sys.stdout = _Tee(_orig, _lf)
    else:
        _lf = None

    try:
        for filepath in v_files:
            res = analyze_file(filepath, plots_dir)
            if res:
                results.append(res)
                
        if len(results) > 0:
            print_batch_summary(results)
        
        if plots_dir:
            print(f"Saved plots to: {plots_dir}")
    finally:
        sys.stdout = _orig
        if _lf:
            _lf.close()
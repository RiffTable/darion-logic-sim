import os
import sys
import numpy as np
import matplotlib.pyplot as plt

# --- PATH RESOLUTION (Same as your iscas_test) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.insert(0, os.path.join(root_dir, 'reactor'))

import Circuit
import Const
from iscas_test import VerilogRunner

def generate_geometry_report(circuit_name, jumps, output_dir):
    if not jumps:
        return

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
    miss_percent = (cache_misses / total_edges) * 100

    print(f"\n{'-'*50}")
    print(f" GEOMETRY PROFILE: {circuit_name}")
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

    # Use a log scale for the X-axis because jumps span from 1 to 50,000
    bins = np.logspace(0, np.log10(max_jump) if max_jump > 0 else 1, 100)
    
    ax.hist(jumps_arr, bins=bins, color='cyan', alpha=0.7, edgecolor='black')
    
    ax.axvline(8, color='red', linestyle='--', alpha=0.8, label='L1 Cache Line Boundary (>8)')
    ax.axvline(mean_jump, color='orange', linestyle='-', alpha=0.8, label=f'Mean Jump: {mean_jump:.1f}')

    ax.set_xscale('log')
    ax.set_yscale('log') # Log scale Y to see the rare massive jumps
    
    ax.set_title(f"Memory Locality Profile: {circuit_name}", fontsize=14, pad=15)
    ax.set_xlabel("Jump Distance in RAM (Indices)", fontsize=12)
    ax.set_ylabel("Frequency (Number of Edges)", fontsize=12)
    
    ax.grid(True, alpha=0.15)
    ax.legend()
    
    os.makedirs(output_dir, exist_ok=True)
    save_path = os.path.join(output_dir, f"{circuit_name}_geometry.png")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Circuit Geometry Analyzer')
    parser.add_argument('file', type=str, help='Path to a single .v file to analyze')
    args = parser.parse_args()

    filename = os.path.basename(args.file)
    print(f"Loading {filename}...")
    
    runner = VerilogRunner(args.file, Circuit.Circuit, Const)
    jumps = runner.circuit.geometry()
    
    plots_dir = os.path.join(current_dir, 'geometry_plots')
    generate_geometry_report(filename, jumps, plots_dir)
    print(f"Saved plot to: {plots_dir}")
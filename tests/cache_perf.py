import os
import sys
import subprocess
import argparse
import datetime

if sys.platform != "linux":
    print("Error: Profiling tools ('perf' and FIFOs) are Linux-exclusive. Aborting.")
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Cache Performance Scaling Profiler")
    parser.add_argument('--chaotic', action='store_true', help='Run mixed chaotic test')
    parser.add_argument('--realistic', action='store_true', help='Run mixed realistic test')
    parser.add_argument('--and', dest='gate_and', action='store_true', help='Run homogeneous AND test')
    parser.add_argument('--or', dest='gate_or', action='store_true', help='Run homogeneous OR test')
    parser.add_argument('--not', dest='gate_not', action='store_true', help='Run homogeneous NOT test')
    parser.add_argument('--plot', action='store_true', help='Generate plots')
    
    args, unknown = parser.parse_known_args()
    
    test_args = []
    mode_name = "chaotic"
    if args.realistic: 
        test_args.append('--realistic')
        mode_name = "realistic"
    elif args.gate_and:
        test_args.append('--and')
        mode_name = "homogeneous_and"
    elif args.gate_or:
        test_args.append('--or')
        mode_name = "homogeneous_or"
    elif args.gate_not:
        test_args.append('--not')
        mode_name = "homogeneous_not"
    else:
        test_args.append('--chaotic')

    fifo_path = "/tmp/cache_perf_ctrl"
    if os.path.exists(fifo_path):
        try: os.remove(fifo_path)
        except: pass
    os.mkfifo(fifo_path)

    events = "L1-dcache-loads:u,L1-dcache-load-misses:u,l2_cache_req_stat.ic_dc_miss_in_l2:u,cache-misses:u,ex_ret_brn:u,instructions:u,cycles:u"

    sizes = []
    current_size = 100
    while current_size <= 500_000:
        sizes.append(current_size)
        current_size = int(current_size * 1.3)
        
    data = {
        "oop": {"l1_miss_rate": [], "l2_miss_rate": [], "l3_miss_rate": [], "ipc": [], "l1_miss": [], "l2_miss": [], "l3_miss": [], "l1_loads": [], "brn": [], "iters": [], "time_ms": [], "evals": []},
        "unopt": {"l1_miss_rate": [], "l2_miss_rate": [], "l3_miss_rate": [], "ipc": [], "l1_miss": [], "l2_miss": [], "l3_miss": [], "l1_loads": [], "brn": [], "iters": [], "time_ms": [], "evals": []},
        "opt": {"l1_miss_rate": [], "l2_miss_rate": [], "l3_miss_rate": [], "ipc": [], "l1_miss": [], "l2_miss": [], "l3_miss": [], "l1_loads": [], "brn": [], "iters": [], "time_ms": [], "evals": []},
        "sweep": {"l1_miss_rate": [], "l2_miss_rate": [], "l3_miss_rate": [], "ipc": [], "l1_miss": [], "l2_miss": [], "l3_miss": [], "l1_loads": [], "brn": [], "iters": [], "time_ms": [], "evals": []}
    }

    print(f"Starting cache performance profiling ({mode_name})... This will take a few minutes.")
    
    for s in sizes:
        print(f"Profiling size {s:<9,} ... ", end="", flush=True)
        for pass_name in ["oop", "unopt", "opt", "sweep"]:
            pass_args = test_args + ["--reactor_oop"] if pass_name == "oop" else test_args
            cmd = [
                "perf", "stat", "-D", "-1", f"--control=fifo:{fifo_path}", "-e", events, "-x,",
                "--", sys.executable, "tests/cache_test.py", *pass_args, "--perf-size", str(s), "--perf-pass", pass_name, "--perf-fifo", fifo_path
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            stats = {}
            for line in res.stderr.split("\n"):
                if not line.strip() or line.startswith("#"): continue
                parts = line.split(",")
                if len(parts) >= 3:
                    val_str = parts[0].strip()
                    evt_name = parts[2].strip()
                    if val_str and val_str != "<not counted>":
                        try:
                            stats[evt_name] = float(val_str)
                        except: pass
                elif line.startswith("ITERATIONS:"):
                    stats["_iterations"] = float(line.split(":")[1].strip())
                elif line.startswith("TIME_MS:"):
                    stats["_time_ms"] = float(line.split(":")[1].strip())
                elif line.startswith("EVAL_COUNT:"):
                    stats["_evals"] = float(line.split(":")[1].strip())
                        
            def get_stat(names):
                for n in names:
                    if n in stats: return stats[n]
                return 0.0

            l1_loads = get_stat(["L1-dcache-loads:u", "L1-dcache-loads"])
            l1_miss = get_stat(["L1-dcache-load-misses:u", "L1-dcache-load-misses"])
            l2_miss = get_stat(["l2_cache_req_stat.ic_dc_miss_in_l2:u", "l2_cache_req_stat.ic_dc_miss_in_l2"])
            l3_miss = get_stat(["cache-misses:u", "cache-misses"])
            brn = get_stat(["ex_ret_brn:u", "ex_ret_brn"])
            inst = get_stat(["instructions:u", "instructions"])
            if inst == 0:
                print(f"\nERROR: `perf stat` returned '<not counted>' for size {s} {pass_name}. This usually happens if another `perf` instance is running in parallel and monopolizing the hardware PMU counters. Please ensure no other profilers are running.")
                sys.exit(1)
                
            cyc = get_stat(["cycles:u", "cycles"])

            ipc = inst / cyc if cyc > 0 else 0
            l1_mr = (l1_miss / l1_loads * 100) if l1_loads > 0 else 0
            l2_mr = (l2_miss / l1_miss * 100) if l1_miss > 0 else 0
            l3_mr = (l3_miss / l2_miss * 100) if l2_miss > 0 else 0

            data[pass_name]["l1_miss_rate"].append(100.0 - l1_mr)
            data[pass_name]["l2_miss_rate"].append(100.0 - l2_mr)
            data[pass_name]["l3_miss_rate"].append(100.0 - l3_mr)
            data[pass_name]["l1_miss"].append(l1_miss)
            data[pass_name]["l2_miss"].append(l2_miss)
            data[pass_name]["l3_miss"].append(l3_miss)
            data[pass_name]["l1_loads"].append(l1_loads)
            data[pass_name]["brn"].append(brn)
            data[pass_name]["iters"].append(stats.get("_iterations", 1.0))
            data[pass_name]["time_ms"].append(stats.get("_time_ms", 0.0))
            data[pass_name]["evals"].append(stats.get("_evals", 0.0))
            data[pass_name]["ipc"].append(ipc)
        print("Done")

    if os.path.exists(fifo_path):
        os.remove(fifo_path)

    os.makedirs("tests/test_result/perf", exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"tests/test_result/perf/cache_perf_{mode_name}_{ts}.md"
    
    with open(report_file, "w") as f:
        f.write(f"# Cache Fragmentation Profile ({mode_name.upper()})\n\n")
        f.write("Isolated purely via hardware `perf` boundaries tightly hugging the core `batch_toggle` simulation logic.\n\n")
        
        def fmt(n):
            if n >= 1e9: return f"{n/1e9:.2f}B"
            if n >= 1e6: return f"{n/1e6:.2f}M"
            if n >= 1e3: return f"{n/1e3:.2f}K"
            return str(n)

        # 1. Core Performance Table
        f.write("## 1. Core Performance (IPC & Branches)\n")
        f.write("| Size | OOP IPC | OOP Branch | Unopt IPC | Unopt Branch | Opt IPC | Opt Branch | Sweep IPC | Sweep Branch |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for i, s in enumerate(sizes):
            def cols_core(p):
                return f"{data[p]['ipc'][i]:.2f} | {fmt(data[p]['brn'][i])}"
            f.write(f"| {s:,} | {cols_core('oop')} | {cols_core('unopt')} | {cols_core('opt')} | {cols_core('sweep')} |\n")
        f.write("\n")

        # 2. L1 Cache Table
        f.write("## 2. L1 Cache Performance\n")
        f.write("| Size | OOP L1 Load | OOP L1 Hit% | Unopt L1 Load | Unopt L1 Hit% | Opt L1 Load | Opt L1 Hit% | Sweep L1 Load | Sweep L1 Hit% |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for i, s in enumerate(sizes):
            def cols_l1(p):
                return f"{fmt(data[p]['l1_loads'][i])} | {data[p]['l1_miss_rate'][i]:.2f}%"
            f.write(f"| {s:,} | {cols_l1('oop')} | {cols_l1('unopt')} | {cols_l1('opt')} | {cols_l1('sweep')} |\n")
        f.write("\n")

        # 3. L2, L3, and RAM Table
        f.write("## 3. L2, L3 & RAM Performance\n")
        f.write("| Size | OOP L2 Load | OOP L2 Hit% | OOP L3 Load | OOP L3 Hit% | OOP RAM (L3 Miss) | Unopt L2 Load | Unopt L2 Hit% | Unopt L3 Load | Unopt L3 Hit% | Unopt RAM (L3 Miss) | Opt L2 Load | Opt L2 Hit% | Opt L3 Load | Opt L3 Hit% | Opt RAM (L3 Miss) | Sweep L2 Load | Sweep L2 Hit% | Sweep L3 Load | Sweep L3 Hit% | Sweep RAM (L3 Miss) |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for i, s in enumerate(sizes):
            def cols_l23(p):
                return f"{fmt(data[p]['l1_miss'][i])} | {data[p]['l2_miss_rate'][i]:.2f}% | {fmt(data[p]['l2_miss'][i])} | {data[p]['l3_miss_rate'][i]:.2f}% | {fmt(data[p]['l3_miss'][i])}"
            f.write(f"| {s:,} | {cols_l23('oop')} | {cols_l23('unopt')} | {cols_l23('opt')} | {cols_l23('sweep')} |\n")
        f.write("\n")

        # 4. Evaluation and Time Table
        f.write("## 4. Execution Time (per Iteration)\n")
        f.write("| Size | OOP Eval | OOP Time (ms) | Unopt Eval | Unopt Time (ms) | Opt Eval | Opt Time (ms) | Sweep Eval | Sweep Time (ms) |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for i, s in enumerate(sizes):
            def cols_time(p):
                time_ms = data[p]['time_ms'][i]
                evals = data[p]['evals'][i]
                iters = data[p]['iters'][i]
                t_str = f"{time_ms / iters:.4f}" if iters > 0 else "0.0000"
                e_str = f"{evals / iters:,.0f}" if iters > 0 else "0"
                return f"{e_str} | {t_str}"
            f.write(f"| {s:,} | {cols_time('oop')} | {cols_time('unopt')} | {cols_time('opt')} | {cols_time('sweep')} |\n")
        f.write("\n")

    print(f"\nReport saved to {report_file}")

    if args.plot:
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            
            # Helper to normalize by iterations
            def norm(pass_name, metric):
                return np.array(data[pass_name][metric]) / np.array(data[pass_name]["iters"])
            
            # Helper to calculate percentages of L1 loads
            def perc(pass_name, hit_level):
                l1_loads = np.array(data[pass_name]["l1_loads"], dtype=float)
                l1_loads = np.where(l1_loads == 0, 1e-9, l1_loads)
                l1_miss = np.array(data[pass_name]["l1_miss"], dtype=float)
                l2_miss = np.array(data[pass_name]["l2_miss"], dtype=float)
                l3_miss = np.array(data[pass_name]["l3_miss"], dtype=float)
                
                if hit_level == "l1_hit":
                    return np.maximum(0, l1_loads - l1_miss) / l1_loads * 100.0
                elif hit_level == "l2_hit":
                    return np.maximum(0, l1_miss - l2_miss) / l1_loads * 100.0
                elif hit_level == "l3_hit":
                    return np.maximum(0, l2_miss - l3_miss) / l1_loads * 100.0
                elif hit_level == "ram":
                    return l3_miss / l1_loads * 100.0

            def meps(pass_name):
                e = np.array(data[pass_name]["evals"])
                t = np.array(data[pass_name]["time_ms"])
                t = np.where(t == 0, 1e-9, t)
                return e / t / 1000.0

            def add_cliffs(ax):
                ax.axvline(x=1000, color='gray', linestyle='--', alpha=0.7)
                ax.text(1000 * 1.2, 0.5, "L1 Capacity Spill", color='gray', rotation=90, verticalalignment='center', transform=ax.get_xaxis_transform())
                
                ax.axvline(x=10000, color='black', linestyle='--', alpha=0.7)
                ax.text(10000 * 1.2, 0.5, "L2 Saturation / RAM Wall", color='black', rotation=90, verticalalignment='center', transform=ax.get_xaxis_transform())

            plt.figure(figsize=(14, 25))
            
            # Subplot 1: L1 Loads
            ax1 = plt.subplot(5, 1, 1)
            plt.title(f"L1 Cache Loads per iteration ({mode_name.upper()})")
            plt.plot(sizes, norm("oop", "l1_loads"), label="Reactor OOP", marker="d", color="purple")
            plt.plot(sizes, norm("unopt", "l1_loads"), label="Unoptimized (BFS)", marker="o", color="red")
            plt.plot(sizes, norm("opt", "l1_loads"), label="Optimized (BFS)", marker="s", color="blue")
            plt.xscale("log")
            plt.yscale("log")
            plt.ylabel("L1 Loads / Iter")
            add_cliffs(ax1)
            plt.grid(True, alpha=0.3)
            plt.legend()
            
            # Subplot 2: L1 Misses / L2 Loads
            ax2 = plt.subplot(5, 1, 2)
            plt.title(f"L1 Cache Misses / L2 Loads per iteration ({mode_name.upper()})")
            plt.plot(sizes, norm("oop", "l1_miss"), marker="d", color="purple")
            plt.plot(sizes, norm("unopt", "l1_miss"), marker="o", color="red")
            plt.plot(sizes, norm("opt", "l1_miss"), marker="s", color="blue")
            plt.xscale("log")
            plt.yscale("log")
            plt.ylabel("L1 Misses / Iter")
            add_cliffs(ax2)
            plt.grid(True, alpha=0.3)
            
            # Subplot 3: L2 Misses / L3 Loads
            ax3 = plt.subplot(5, 1, 3)
            plt.title(f"L2 Cache Misses / L3 Loads per iteration ({mode_name.upper()})")
            plt.plot(sizes, norm("oop", "l2_miss"), marker="d", color="purple")
            plt.plot(sizes, norm("unopt", "l2_miss"), marker="o", color="red")
            plt.plot(sizes, norm("opt", "l2_miss"), marker="s", color="blue")
            plt.xscale("log")
            plt.yscale("log")
            plt.ylabel("L2 Misses / Iter")
            add_cliffs(ax3)
            plt.grid(True, alpha=0.3)
            
            # Subplot 4: L3 Misses / RAM Loads
            ax4 = plt.subplot(5, 1, 4)
            plt.title(f"L3 Cache Misses / RAM Loads per iteration ({mode_name.upper()})")
            plt.plot(sizes, norm("oop", "l3_miss"), marker="d", color="purple")
            plt.plot(sizes, norm("unopt", "l3_miss"), marker="o", color="red")
            plt.plot(sizes, norm("opt", "l3_miss"), marker="s", color="blue")
            plt.xscale("log")
            plt.yscale("log")
            plt.ylabel("L3 Misses / Iter")
            add_cliffs(ax4)
            plt.grid(True, alpha=0.3)
            
            # Subplot 5: MEPS
            ax5 = plt.subplot(5, 1, 5)
            plt.title(f"Throughput (Mega-Evaluations Per Second) ({mode_name.upper()})")
            plt.plot(sizes, meps("oop"), marker="d", color="purple")
            plt.plot(sizes, meps("unopt"), marker="o", color="red")
            plt.plot(sizes, meps("opt"), marker="s", color="blue")
            plt.xscale("log")
            plt.yscale("linear")
            plt.ylabel("MEPS")
            plt.xlabel("Circuit Size (Gates)")
            add_cliffs(ax5)
            plt.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plot_file = f"tests/test_result/perf/cache_perf_{mode_name}_{ts}.png"
            plt.savefig(plot_file)
            plt.close()

            print(f"Plot saved to {plot_file}")
        except Exception as e:
            print(f"Plotting failed: {e}")

if __name__ == '__main__':
    main()

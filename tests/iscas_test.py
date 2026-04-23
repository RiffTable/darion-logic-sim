import os
import re
import sys
import time
import random
import argparse
import statistics
import gc
import json
import subprocess
import matplotlib.pyplot as plt
import numpy as np

# --- CLI ARGUMENTS ---
parser = argparse.ArgumentParser(description='Darion Logic Sim - Final ISCAS Batch Benchmark')
parser.add_argument('target', nargs='?', type=str, help='Path to .v file or directory')
parser.add_argument('--engine', action='store_true', help='Run pure Python Engine exclusively')
parser.add_argument('--reactor', action='store_true', help='Run Cython Reactor exclusively')
parser.add_argument('--optimize', action='store_true', help='Enable Data-Oriented topological sorting')
parser.add_argument('--vectors', type=int, default=None, help='Override default vector count')
parser.add_argument('--dump_json', type=str, help=argparse.SUPPRESS) # Internal use for IPC

args, unknown = parser.parse_known_args()

run_dual = not (args.engine or args.reactor) and not args.dump_json

# --- VECTOR SCALING ---
if args.vectors is not None:
    VECTORS_ENGINE = args.vectors
    VECTORS_REACTOR = args.vectors
else:
    VECTORS_ENGINE = 5000 
    VECTORS_REACTOR = 50000

VECTORS_RUN = VECTORS_ENGINE if args.engine else VECTORS_REACTOR

# --- DYNAMIC PATH RESOLUTION ---
base_dir = os.getcwd()
script_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(script_dir, 'reactor')) or os.path.exists(os.path.join(script_dir, 'engine')):
    root_dir = script_dir
else:
    root_dir = os.path.dirname(script_dir)

# --- ISOLATED IMPORTS ---
BackendCircuit, BackendConst = None, None

if not run_dual:
    if args.engine:
        sys.path.insert(0, os.path.join(root_dir, 'engine'))
    elif args.reactor:
        sys.path.insert(0, os.path.join(root_dir, 'reactor'))
        
    import Circuit
    import Const
    BackendCircuit = Circuit.Circuit
    BackendConst = Const

def generate_trigger_plot(circuit_name, engine_data, reactor_data, output_dir):
    """Generates side-by-side spectrum scatter plots with stats HUD."""
    if not engine_data and not reactor_data:
        return
        
    plt.style.use('dark_background')
    
    has_both = bool(engine_data and reactor_data)
    fig_width = 18 if has_both else 10
    fig, axes = plt.subplots(1, 2 if has_both else 1, figsize=(fig_width, 6.5), facecolor='#121212')
    
    if not has_both:
        axes = [axes]
        
    fig.suptitle(f"Trigger Event Profiling: {circuit_name}", fontsize=18, fontweight='bold', color='#FFFFFF', y=1.05)
    
    plot_idx = 0
    
    def plot_backend(ax, data, title, cmap_name, hline_color, vline_color):
        speeds = np.array([d[0] for d in data])
        evals = np.array([d[1] for d in data])
        
        avg_spd, peak_spd = np.mean(speeds), np.max(speeds)
        avg_evals = np.mean(evals)
        
        scatter = ax.scatter(evals, speeds, c=speeds, cmap=cmap_name, alpha=0.7, s=25, edgecolors='none')
        
        cbar = plt.colorbar(scatter, ax=ax, pad=0.02)
        cbar.set_label('Execution Speed (M/s)', rotation=270, labelpad=20, color='#E0E0E0', fontsize=10)
        cbar.outline.set_visible(False)
        cbar.ax.yaxis.set_tick_params(colors='#E0E0E0')
        
        ax.axhline(avg_spd, color=hline_color, linestyle='--', linewidth=1.5, alpha=0.8, label=f'Mean Speed: {avg_spd:.2f} M/s')
        ax.axvline(avg_evals, color=vline_color, linestyle=':', linewidth=1.5, alpha=0.6, label=f'Mean Evals: {int(avg_evals)}')
        
        ax.set_title(title, fontsize=14, color='#E0E0E0', pad=10)
        ax.set_xlabel("Cascade Size (Evaluations per Trigger)", fontsize=11, color='#E0E0E0', labelpad=10)
        if plot_idx == 0:
            ax.set_ylabel("Execution Speed (Million evals / sec)", fontsize=11, color='#E0E0E0', labelpad=10)
            
        if max(evals) > 10 * min(evals) and min(evals) > 0:
            ax.set_xscale('log')
            
        stats_text = f"Avg:  {avg_spd:>6.2f} M/s\nPeak: {peak_spd:>6.2f} M/s"
        props = dict(boxstyle='round,pad=0.6', facecolor='#1A1A1A', alpha=0.9, edgecolor='#333333')
        ax.text(0.03, 0.95, stats_text, transform=ax.transAxes, fontsize=11,
                verticalalignment='top', bbox=props, color='#E0E0E0', family='monospace')
                
        ax.grid(True, color='#333333', linestyle=':', linewidth=1, alpha=0.8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('#444444')
        ax.spines['left'].set_color('#444444')
        ax.tick_params(colors='#E0E0E0', which='both')
        
        legend = ax.legend(frameon=True, facecolor='#1A1A1A', edgecolor='#333333', fontsize=10, loc='upper right')
        for text in legend.get_texts():
            text.set_color('#E0E0E0')

    if engine_data:
        plot_backend(axes[plot_idx], engine_data, "Engine (Pure Python)", "plasma", "#00FFCC", "#FF3366")
        plot_idx += 1
        
    if reactor_data:
        plot_backend(axes[plot_idx], reactor_data, "Reactor (Cython DOD)", "viridis", "#FF3366", "#00FFCC")

    os.makedirs(output_dir, exist_ok=True)
    save_path = os.path.join(output_dir, f"{circuit_name}_comparison.png")
    plt.tight_layout()
    plt.savefig(save_path, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    
class VerilogRunner:
    def __init__(self, v_file_path, circuit_cls, const_mod):
        self.Circuit = circuit_cls
        self.const = const_mod
        self.circuit = self.Circuit()
        self.nodes = {}       
        self.outputs = []     

        self.VERILOG_GATE_MAP = {
            'and': self.const.AND_ID, 'nand': self.const.NAND_ID, 'or': self.const.OR_ID,
            'nor': self.const.NOR_ID, 'xor': self.const.XOR_ID, 'xnor': self.const.XNOR_ID, 'not': self.const.NOT_ID
        }
        
        self.master_vars = [self.circuit.getcomponent(self.const.VARIABLE_ID) for _ in range(8)]
        for i, m in enumerate(self.master_vars):
            m.rename(f"MASTER_{i}")
        
        self.const_high = self.circuit.getcomponent(self.const.VARIABLE_ID)
        self.const_high.rename("VCC")
        self.circuit.toggle(self.const_high, self.const.HIGH)
        
        self.const_low = self.circuit.getcomponent(self.const.VARIABLE_ID)
        self.const_low.rename("GND")
        self.circuit.toggle(self.const_low, self.const.LOW)

        self._parse_verilog(v_file_path)

    def _create_driven_input(self, name):
        in_gate = self.circuit.getcomponent(self.const.XOR_ID)
        in_gate.rename(name)
        self.circuit.setlimits(in_gate, 2)
        master = random.choice(self.master_vars)
        self.circuit.connect(in_gate, master, 0)
        polarity = self.const_high if random.random() > 0.5 else self.const_low
        self.circuit.connect(in_gate, polarity, 1)
        return in_gate

    def _parse_verilog(self, filepath):
        with open(filepath, 'r') as f:
            content = f.read()

        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'//.*', '', content)
        statements = [s.strip() for s in content.split(';') if s.strip()]
        connections = []

        for stmt in statements:
            if stmt.startswith('input '):
                ports = stmt.replace('input', '').strip().split(',')
                for p in ports:
                    p = p.strip()
                    self.nodes[p] = self._create_driven_input(f"IN_{p}")
            elif stmt.startswith('output '):
                ports = stmt.replace('output', '').strip().split(',')
                for p in ports:
                    self.outputs.append(p.strip())
            elif stmt.startswith('wire ') or stmt.startswith('module ') or stmt.startswith('endmodule'):
                continue
            else:
                match = re.match(r'^([a-zA-Z_]\w*)\s+([a-zA-Z_0-9]+)?\s*\((.*)\)$', stmt)
                if match:
                    gate_type = match.group(1).lower()
                    ports_str = match.group(3)
                    if gate_type in self.VERILOG_GATE_MAP:
                        ports = [p.strip() for p in ports_str.split(',')]
                        out_wire = ports[0]
                        in_wires = ports[1:]
                        gate_id = self.VERILOG_GATE_MAP[gate_type]
                        gate = self.circuit.getcomponent(gate_id)
                        gate.rename(f"G_{out_wire}")
                        if gate_id != self.const.NOT_ID:
                            self.circuit.setlimits(gate, len(in_wires))
                        self.nodes[out_wire] = gate
                        connections.append((out_wire, in_wires))
                    elif gate_type == 'dff':
                        ports = [p.strip() for p in ports_str.split(',')]
                        out_wire = ports[0] 
                        self.nodes[out_wire] = self._create_driven_input(f"DFF_{out_wire}")

        for target_id, source_ids in connections:
            target_gate = self.nodes.get(target_id)
            if not target_gate: continue
            for pin_index, source_id in enumerate(source_ids):
                if source_id in ["1'b0", "1'h0", "GND", "gnd"]:
                    self.circuit.connect(target_gate, self.const_low, pin_index)
                elif source_id in ["1'b1", "1'h1", "VDD", "VCC", "vdd", "vcc"]:
                    self.circuit.connect(target_gate, self.const_high, pin_index)
                else:
                    source_gate = self.nodes.get(source_id)
                    if source_gate:
                        self.circuit.connect(target_gate, source_gate, pin_index)
                    else:
                        missing_var = self._create_driven_input(f"MISSING_{source_id}")
                        self.nodes[source_id] = missing_var
                        self.circuit.connect(target_gate, missing_var, pin_index)

        for wire_name in self.outputs:
            driver = self.nodes.get(wire_name)
            if driver is not None:
                probe = self.circuit.getcomponent(self.const.PROBE_ID)
                probe.rename(f"OUT_{wire_name}")
                self.circuit.connect(probe, driver, 0)

    def run_benchmark(self, vectors=10_000, use_optimize=True):
        if len(self.nodes) == 0:
            raise ValueError("No valid nodes parsed.")
            
        if use_optimize:
            self.circuit.simulate(self.const.COMPILE)
            if hasattr(self.circuit, 'optimize'):
                self.circuit.optimize()
        else:
            self.circuit.optimize()
            self.circuit.simulate(self.const.SIMULATE)
            
        fast_batch_toggle = self.circuit.batch_toggle 
        batched_instructions = []
        for _ in range(vectors):
            current_vector = [(m.location, self.const.HIGH if random.random() > 0.5 else self.const.LOW) for m in self.master_vars]
            batched_instructions.append(current_vector)
                
        burst_data = [] 
        prev_evals = self.circuit.eval_count

        gc.disable()
        active_start = time.perf_counter_ns()
        
        for vector_batch in batched_instructions:
            t0 = time.perf_counter_ns()
            fast_batch_toggle(vector_batch)
            t1 = time.perf_counter_ns()
            
            curr_evals = self.circuit.eval_count
            evals_diff = curr_evals - prev_evals
            prev_evals = curr_evals
            
            delta_ns = t1 - t0
            if delta_ns > 0 and evals_diff > 0:
                burst_m_s = (evals_diff / delta_ns) * 1000.0
                burst_data.append((burst_m_s, evals_diff))
                
        active_end = time.perf_counter_ns()
        gc.enable()
        
        pure_execution_ns = active_end - active_start
        duration_ms = pure_execution_ns / 1_000_000.0
        total_evals = self.circuit.eval_count 
        evals_per_sec = (total_evals / (duration_ms / 1000.0)) if duration_ms > 0 else 0
        
        distribution = {"bottom_5": 0, "lower_tail": 0, "core": 0, "upper_tail": 0, "top_5": 0, "boundaries": (0, 0, 0, 0)}

        if burst_data:
            valid_bursts = [b for b in burst_data if b[1] >= 10]
            search_data = valid_bursts if valid_bursts else burst_data
            m_s_values = [b[0] for b in search_data]
            
            mean_burst_ms = statistics.mean(m_s_values)
            mean_burst_evals = statistics.mean(b[1] for b in search_data)
            peak_burst = max(search_data, key=lambda x: x[0])
            min_burst = min(search_data, key=lambda x: x[0])
            
            if len(m_s_values) >= 100:
                cuts = statistics.quantiles(m_s_values, n=100)
                p5, p25, p75, p95 = cuts[4], cuts[24], cuts[74], cuts[94]
                distribution["boundaries"] = (p5, p25, p75, p95)
                for val in m_s_values:
                    if val <= p5: distribution["bottom_5"] += 1
                    elif val <= p25: distribution["lower_tail"] += 1
                    elif val <= p75: distribution["core"] += 1
                    elif val <= p95: distribution["upper_tail"] += 1
                    else: distribution["top_5"] += 1
        else:
            mean_burst_ms, mean_burst_evals, peak_burst, min_burst = 0.0, 0, (0.0, 0), (0.0, 0)
            search_data = []

        return {
            "nodes": len(self.nodes), "duration": duration_ms, "evals": total_evals,
            "batch_ms": evals_per_sec / 1_000_000.0, "mean_burst_ms": mean_burst_ms,
            "mean_burst_evals": mean_burst_evals, "peak_burst": peak_burst,
            "min_burst": min_burst, "total_valid_bursts": len(search_data),
            "distribution": distribution, "raw_trigger_data": search_data
        }

def print_and_log(text, log_file):
    print(text)
    log_file.write(text + "\n")

def get_files(target):
    if not target:
        target = input("Enter path to .v file or directory: ").strip().strip('"').strip("'")
    
    if os.path.isfile(target):
        return [target]
    
    v_files = []
    for root, dirs, files in os.walk(target):
        for file in files:
            if file.endswith(".v"):
                v_files.append(os.path.join(root, file))
    return v_files

if __name__ == "__main__":

    v_files = get_files(args.target)
    if not v_files:
        print(f"Error: No .v files found in '{args.target}'")
        sys.exit(1)
        
    v_files.sort(key=os.path.getsize)
    plots_dir = os.path.join(script_dir, 'benchmark_plots')

    # ==========================================
    # MASTER CONTROLLER: DUAL MODE (PER FILE)
    # ==========================================
    if run_dual:
        print("\n" + "="*60)
        print(" [MASTER] PER-FILE DUAL COMPARISON INITIATED")
        print(f" [MASTER] Engine Vectors: {VECTORS_ENGINE:,} | Reactor Vectors: {VECTORS_REACTOR:,}")
        print("="*60)
        
        os.makedirs(plots_dir, exist_ok=True)
        engine_json = os.path.join(script_dir, "temp_engine_data.json")
        reactor_json = os.path.join(script_dir, "temp_reactor_data.json")
        final_results = []
        
        try:
            for idx, filepath in enumerate(v_files):
                filename = os.path.basename(filepath)
                print(f"\n[{idx+1}/{len(v_files)}] Benchmarking {filename}...")
                
                cmd_base = [sys.executable, os.path.abspath(__file__), filepath]
                if args.optimize: cmd_base.append("--optimize")
                
                e_stat, r_stat = None, None
                
                # RUN ENGINE
                print(f"  -> Profiling Pure Python Engine... ", end="", flush=True)
                cmd_e = cmd_base + ["--engine", "--dump_json", engine_json, "--vectors", str(VECTORS_ENGINE)]
                subprocess.run(cmd_e, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                with open(engine_json, 'r') as f: 
                    e_results = json.load(f)
                    if e_results: e_stat = e_results[0]
                
                if e_stat and 'error' not in e_stat:
                    print(f"OK (Peak: {e_stat['peak_burst'][0]:.2f} M/s)")
                else:
                    print(f"FAILED")
                    
                # RUN REACTOR
                print(f"  -> Profiling Cython Reactor...   ", end="", flush=True)
                cmd_r = cmd_base + ["--reactor", "--dump_json", reactor_json, "--vectors", str(VECTORS_REACTOR)]
                subprocess.run(cmd_r, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                with open(reactor_json, 'r') as f: 
                    r_results = json.load(f)
                    if r_results: r_stat = r_results[0]
                
                if r_stat and 'error' not in r_stat:
                    print(f"OK (Peak: {r_stat['peak_burst'][0]:.2f} M/s)")
                else:
                    print(f"FAILED")

                # PLOT IMMEDIATELY
                e_data = e_stat.pop('raw_trigger_data', []) if e_stat and 'error' not in e_stat else []
                r_data = r_stat.pop('raw_trigger_data', []) if r_stat and 'error' not in r_stat else []
                
                if e_data or r_data:
                    generate_trigger_plot(filename, e_data, r_data, plots_dir)
                    print(f"  -> Generated plot: {filename}_comparison.png")
                
                if e_stat: final_results.append(e_stat)
                if r_stat: final_results.append(r_stat)

            # GENERATE REPORT
            report_path = os.path.join(script_dir, 'iscas89_summary.txt')
            with open(report_path, 'w', encoding='utf-8') as f:
                header = f"\n{'='*120}\n DARION LOGIC SIM - ISCAS BATCH BENCHMARK REPORT\n{'='*120}\n"
                header += f"Backend  : DUAL COMPARISON\n"
                header += f"Vectors  : Engine ({VECTORS_ENGINE:,}) | Reactor ({VECTORS_REACTOR:,})\n"
                header += f"Optimize : {'Enabled' if args.optimize else 'Disabled'}\n{'-'*120}\n"
                print_and_log(header, f)
                
                col_format = "{:<22} | {:>7} | {:>9} | {:>12} | {:>9} | {:>18} | {:>18} | {:>18}\n"
                print_and_log(col_format.format("Circuit [Mode]", "Nodes", "Time (ms)", "Total Evals", "Batch M/s", "Mean Burst (Evals)", "Peak Burst (Evals)", "Min Burst (Evals)"), f)
                print_and_log("-" * 120, f)
                
                for r in final_results:
                    if 'error' in r:
                        print_and_log(f"{r['file']:<22} | ERROR: {r['error']}", f)
                    else:
                        mean_str = f"{r['mean_burst_ms']:.2f} ({int(r['mean_burst_evals'])})"
                        peak_str = f"{r['peak_burst'][0]:.2f} ({r['peak_burst'][1]})"
                        min_str  = f"{r['min_burst'][0]:.2f} ({r['min_burst'][1]})"
                        print_and_log(col_format.format(
                            r['file'], f"{r['nodes']:,}", f"{r['duration']:.2f}", 
                            f"{r['evals']:,}", f"{r['batch_ms']:.2f}", mean_str, peak_str, min_str
                        ).strip(), f)
                        
                e_evals, e_time, e_runs = 0, 0, 0
                r_evals, r_time, r_runs = 0, 0, 0
                for r in final_results:
                    if 'error' not in r:
                        if "[Engine]" in r['file']:
                            e_evals += r['evals']; e_time += r['duration']; e_runs += 1
                        else:
                            r_evals += r['evals']; r_time += r['duration']; r_runs += 1
                            
                footer = f"\n{'-'*120}\n"
                if e_runs > 0 and e_time > 0:
                    e_avg = (e_evals / (e_time / 1000)) / 1_000_000
                    footer += f"ENGINE AVERAGE THROUGHPUT  : {e_avg:.2f} Million evals/sec ({e_runs} valid circuits)\n"
                if r_runs > 0 and r_time > 0:
                    r_avg = (r_evals / (r_time / 1000)) / 1_000_000
                    footer += f"REACTOR AVERAGE THROUGHPUT : {r_avg:.2f} Million evals/sec ({r_runs} valid circuits)\n"
                footer += "="*120 + "\n"
                print_and_log(footer, f)
                
            print(f"\n[SUCCESS] Benchmark report saved to: {report_path}")

        finally:
            if os.path.exists(engine_json): os.remove(engine_json)
            if os.path.exists(reactor_json): os.remove(reactor_json)
        sys.exit(0)

    # ==========================================
    # WORKER / SINGLE EXECUTION
    # ==========================================
    results = []
    for idx, filepath in enumerate(v_files):
        filename = os.path.basename(filepath)
        
        if not args.dump_json:
            print(f"[{idx+1}/{len(v_files)}] Testing {filename}... ", end="", flush=True)
            
        try:
            runner = VerilogRunner(filepath, BackendCircuit, BackendConst)
            stats = runner.run_benchmark(vectors=VECTORS_RUN, use_optimize=args.optimize)
            suffix = " [Engine]" if args.engine else " [Reactor]"
            stats['file'] = filename + suffix
            
            if not args.dump_json:
                print(f"OK ({stats['nodes']} nodes | Peak Trigger: {stats['peak_burst'][0]:.2f} M/s)")
                raw_data = stats.pop('raw_trigger_data', [])
                if args.engine: generate_trigger_plot(filename, raw_data, [], plots_dir)
                else: generate_trigger_plot(filename, [], raw_data, plots_dir)
            
            results.append(stats)
            
        except Exception as e:
            if not args.dump_json: print(f"FAILED ({e})")
            suffix = " [Engine]" if args.engine else " [Reactor]"
            results.append({'file': filename + suffix, 'error': str(e)})

    if args.dump_json:
        with open(args.dump_json, 'w') as f: json.dump(results, f)
        sys.exit(0)
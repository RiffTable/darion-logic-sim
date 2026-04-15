import os
import re
import sys
import time
import random
import argparse
import glob

# --- CLI ARGUMENTS ---
parser = argparse.ArgumentParser(description='Darion Logic Sim - Final ISCAS Batch Benchmark')
parser.add_argument('directory', nargs='?', type=str, help='Path to the directory containing .v files')
parser.add_argument('--engine', action='store_true', help='Use pure Python Engine (default: Cython Reactor)')
parser.add_argument('--no-optimize', action='store_true', help='Disable Data-Oriented topological sorting')
parser.add_argument('--vectors', type=int, default=None, help='Override default vector count')
args, unknown = parser.parse_known_args()

# --- DYNAMIC VECTOR SCALING ---
# Python is too slow for 50k vectors on large meshes. Throttle it automatically.
if args.vectors is not None:
    VECTORS_TO_RUN = args.vectors
else:
    VECTORS_TO_RUN = 500 if args.engine else 50000

# --- DYNAMIC PATH RESOLUTION ---
base_dir = os.getcwd()
script_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(script_dir, 'reactor')) or os.path.exists(os.path.join(script_dir, 'engine')):
    root_dir = script_dir
else:
    root_dir = os.path.dirname(script_dir)

if args.engine:
    print("[INIT] Backend: Pure Python Engine")
    sys.path.insert(0, os.path.join(root_dir, 'engine'))   
else:
    print("[INIT] Backend: Cython Reactor")
    sys.path.insert(0, os.path.join(root_dir, 'reactor'))   

from Circuit import Circuit
import Const

VERILOG_GATE_MAP = {
    'and': Const.AND_ID, 'nand': Const.NAND_ID, 'or': Const.OR_ID,
    'nor': Const.NOR_ID, 'xor': Const.XOR_ID, 'xnor': Const.XNOR_ID, 'not': Const.NOT_ID
}

class VerilogRunner:
    def __init__(self, v_file_path):
        self.circuit = Circuit()
        self.nodes = {}       
        self.outputs = []     
        
        # 8 Hardware-Accelerated Master Variables for Chaos Generation
        self.master_vars = [self.circuit.getcomponent(Const.VARIABLE_ID) for _ in range(8)]
        for i, m in enumerate(self.master_vars):
            m.rename(f"MASTER_{i}")
        
        self.const_high = self.circuit.getcomponent(Const.VARIABLE_ID)
        self.const_high.rename("VCC")
        self.circuit.toggle(self.const_high, Const.HIGH)
        
        self.const_low = self.circuit.getcomponent(Const.VARIABLE_ID)
        self.const_low.rename("GND")
        self.circuit.toggle(self.const_low, Const.LOW)

        self._parse_verilog(v_file_path)

    def _create_driven_input(self, name):
        """Creates a hardware-accelerated random noise generator attached to the master clock."""
        in_gate = self.circuit.getcomponent(Const.XOR_ID)
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
                    
                    if gate_type in VERILOG_GATE_MAP:
                        ports = [p.strip() for p in ports_str.split(',')]
                        out_wire = ports[0]
                        in_wires = ports[1:]
                        
                        gate_id = VERILOG_GATE_MAP[gate_type]
                        gate = self.circuit.getcomponent(gate_id)
                        gate.rename(f"G_{out_wire}")
                        
                        if gate_id != Const.NOT_ID:
                            self.circuit.setlimits(gate, len(in_wires))
                            
                        self.nodes[out_wire] = gate
                        connections.append((out_wire, in_wires))
                        
                    elif gate_type == 'dff':
                        # DFF Loop Cut -> Turn output into Primary Input
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

        # Attach a Probe buffer to every declared output wire
        for wire_name in self.outputs:
            driver = self.nodes.get(wire_name)
            if driver is not None:
                probe = self.circuit.getcomponent(Const.PROBE_ID)
                probe.rename(f"OUT_{wire_name}")
                self.circuit.connect(probe, driver, 0)

    def run_benchmark(self, vectors=10_000, use_optimize=True):
        if len(self.nodes) == 0:
            raise ValueError("No valid nodes parsed. Unsupported Verilog syntax?")
            
        self.circuit.simulate(Const.SIMULATE)
        
        if use_optimize and hasattr(self.circuit, 'optimize'):
            self.circuit.optimize()
            
        # 1. Pre-compute random vectors and C-pointer to eliminate Python latency
        fast_toggle = self.circuit.toggle 
        instructions = []
        for _ in range(vectors):
            for m in self.master_vars:
                instructions.append((m, Const.HIGH if random.random() > 0.5 else Const.LOW))
                
        # 2. Calibration (Measure empty loop overhead)
        overhead_start = time.perf_counter_ns()
        for gate, state in instructions:
            pass 
        overhead_end = time.perf_counter_ns()
        loop_overhead_ns = overhead_end - overhead_start

        # 3. Active execution
        active_start = time.perf_counter_ns()
        for gate, state in instructions:
            fast_toggle(gate, state)
        active_end = time.perf_counter_ns()
        
        # 4. Math & Statistics
        pure_execution_ns = (active_end - active_start) - loop_overhead_ns
        if pure_execution_ns <= 0: pure_execution_ns = 1 
            
        duration_ms = pure_execution_ns / 1_000_000
        total_evals = self.circuit.eval_count 
        evals_per_sec = (total_evals / (duration_ms / 1000)) if duration_ms > 0 else 0
        
        return {
            "nodes": len(self.nodes),
            "duration": duration_ms,
            "evals": total_evals,
            "throughput": evals_per_sec / 1_000_000
        }

def print_and_log(text, log_file):
    print(text)
    log_file.write(text + "\n")

if __name__ == "__main__":
    directory = args.directory
    if not directory:
        directory = input("Enter directory path containing ISCAS .v files: ").strip().strip('"').strip("'")
    
    # Recursively find all .v files in the directory and subdirectories
    v_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".v"):
                v_files.append(os.path.join(root, file))
    
    if not v_files:
        print(f"Error: No .v files found in '{directory}'")
        sys.exit(1)
        
    print(f"Found {len(v_files)} Verilog files. Starting batch benchmark...")
    print(f"Executing {VECTORS_TO_RUN:,} vectors per file.")
    
    results = []
    v_files.sort(key=os.path.getsize) # Smallest first
    should_optimize = not args.no_optimize 

    for idx, filepath in enumerate(v_files):
        filename = os.path.basename(filepath)
        print(f"[{idx+1}/{len(v_files)}] Testing {filename}... ", end="", flush=True)
        
        try:
            runner = VerilogRunner(filepath)
            stats = runner.run_benchmark(vectors=VECTORS_TO_RUN, use_optimize=should_optimize)
            stats['file'] = filename
            results.append(stats)
            print(f"OK ({stats['nodes']} nodes | {stats['throughput']:.2f} M/s)")
        except Exception as e:
            print(f"FAILED ({e})")
            results.append({
                'file': filename, 'nodes': 0, 'duration': 0, 
                'evals': 0, 'throughput': 0, 'error': str(e)
            })

    results.sort(key=lambda x: x['nodes'])
    
    # --- GENERATE SUMMARY REPORT ---
    report_path = os.path.join(script_dir, 'iscas89_summary.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        header = f"\n{'='*80}\n DARION LOGIC SIM - ISCAS BATCH BENCHMARK REPORT\n{'='*80}\n"
        header += f"Backend  : {'Engine (Pure Python)' if args.engine else 'Reactor (Cython DOD)'}\n"
        header += f"Optimize : {'Enabled' if should_optimize else 'Disabled'}\n"
        header += f"Vectors  : {VECTORS_TO_RUN:,} per circuit\n{'-'*80}\n"
        
        print_and_log(header, f)
        
        col_format = "{:<15} | {:>10} | {:>12} | {:>15} | {:>15}\n"
        print_and_log(col_format.format("Circuit", "Nodes", "Time (ms)", "Total Evals", "Speed (M evals/s)"), f)
        print_and_log("-" * 80, f)
        
        total_evals = 0
        total_time = 0
        successful_runs = 0
        
        for r in results:
            if 'error' in r:
                print_and_log(f"{r['file']:<15} | ERROR: {r['error']}", f)
            else:
                total_evals += r['evals']
                total_time += r['duration']
                successful_runs += 1
                print_and_log(col_format.format(
                    r['file'], 
                    f"{r['nodes']:,}", 
                    f"{r['duration']:.2f}", 
                    f"{r['evals']:,}", 
                    f"{r['throughput']:.2f}"
                ).strip(), f)
                
        if successful_runs > 0 and total_time > 0:
            avg_throughput = (total_evals / (total_time / 1000)) / 1_000_000
            footer = f"\n{'-'*80}\n"
            footer += f"Total Valid Circuits : {successful_runs}\n"
            footer += f"Total Evaluations    : {total_evals:,}\n"
            footer += f"Total Benchmark Time : {total_time / 1000:.2f} seconds\n"
            footer += f"AVERAGE THROUGHPUT   : {avg_throughput:.2f} Million evals/sec\n"
            footer += f"{'='*80}\n"
            print_and_log(footer, f)
            
    print(f"\nReport saved to: {report_path}")
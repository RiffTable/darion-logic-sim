"""
unified_memory.py
=================
Universal Memory Benchmark: Measures the true RAM footprint (in MB) of loading 
ANY ISCAS circuit (Combinational or Sequential/ISCAS89) across 4 simulation engines.
"""

import os
import sys
import re
import argparse
import json
import subprocess
import shutil

try:
    import psutil
except ImportError:
    print("[-] Error: 'psutil' is required for RAM measurement. Run: pip install psutil")
    sys.exit(1)

_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

sys.path.insert(0, _SCRIPT_DIR)

# ===========================================================================
# 1. ENGINE / REACTOR RAM LOADER (Universal: Combo + Seq)
# ===========================================================================

class UniversalLoader:
    def __init__(self, v_file_path, circuit_cls, const_mod):
        self.Circuit = circuit_cls
        self.const = const_mod
        self.circuit = self.Circuit()
        self.circuit.simulate(self.const.DESIGN)
        self.nodes = {}
        self.dff_connections = []
        self.dff_crct = None

        # Try to locate DFF.json just in case this is a sequential circuit
        for p in [os.path.join(_SCRIPT_DIR, "DFF.json"), os.path.join(_PROJECT_ROOT, "DFF.json"), "DFF.json"]:
            if os.path.exists(p):
                try:
                    self.dff_crct = self.circuit.get_ic(p)
                    break
                except Exception: pass

        self.VERILOG_GATE_MAP = {
            'and': self.const.AND_ID, 'nand': self.const.NAND_ID, 'or': self.const.OR_ID,
            'nor': self.const.NOR_ID, 'xor': self.const.XOR_ID, 'xnor': self.const.XNOR_ID,
            'not': self.const.NOT_ID, 'buf': self.const.BUFFER_ID,
        }
        self._parse_verilog(v_file_path)

    def _parse_verilog(self, filepath):
        json_path = filepath.replace('.v', '.json')
        
        if os.path.exists(json_path) and hasattr(self.circuit, 'readfromjson'):
            self.circuit.readfromjson(json_path)
            # Use get_components to avoid direct list access differences between Python and Cython
            self.nodes = {str(i): c for i, c in enumerate(self.circuit.get_components())}
            return

        with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
        
        # Strip comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'//.*', '', content)

        # Isolate the main module (ignore inline DFF module definitions if present)
        module_body = content
        for m in re.finditer(r'\bmodule\s+([a-zA-Z0-9_]+)(.*?)\bendmodule\b', content, flags=re.DOTALL):
            if m.group(1).lower() != 'dff':
                module_body = m.group(0)
                break

        statements = [s.strip() for s in module_body.split(';') if s.strip()]
        connections = []

        for stmt in statements:
            if stmt.startswith('input '):
                for p in stmt.replace('input', '').strip().split(','):
                    if p.strip():
                        var_node = self.circuit.getcomponent(self.const.VARIABLE_ID)
                        var_node.rename(f"IN_{p.strip()}")
                        self.nodes[p.strip()] = var_node
            elif stmt.startswith('output '):
                for p in stmt.replace('output', '').strip().split(','):
                    if p.strip():
                        out_node = self.circuit.getcomponent(self.const.IC_OUTPUT_PIN_ID)
                        out_node.rename(f"OUT_{p.strip()}")
                        self.nodes[p.strip() + "_OUTPIN"] = out_node
                        connections.append((p.strip() + "_OUTPIN", [p.strip()]))
            elif stmt.startswith(('wire ', 'module ', 'endmodule', 'reg ')):
                continue
            else:
                # FAST STRING PARSING (O(1) lookups instead of Regex backtracking)
                paren_idx = stmt.find('(')
                if paren_idx == -1: continue
                
                left_part = stmt[:paren_idx].strip().split()
                if not left_part: continue
                
                gate_type = left_part[0].lower()
                ports_str = stmt[paren_idx+1:stmt.rfind(')')]

                # Handle Sequential DFFs
                if gate_type.startswith('dff'):
                    if not self.dff_crct: raise RuntimeError("DFF.json is required for sequential circuits but not found.")
                    
                    wires = {}
                    if '.' in ports_str:
                        for pm in re.finditer(r'\.\s*([a-zA-Z0-9_]+)\s*\(\s*([a-zA-Z0-9_]+)\s*\)', ports_str):
                            wires[pm.group(1).upper()] = pm.group(2)
                        d_wire, clk_wire, q_wire = wires.get('D'), wires.get('CK', wires.get('CLK', wires.get('C'))), wires.get('Q')
                    else:
                        pts = [p.strip() for p in ports_str.split(',')]
                        clk_wire, q_wire, d_wire = (pts[0] if len(pts)>0 else None, pts[1] if len(pts)>1 else None, pts[2] if len(pts)>2 else None)

                    dff_inst = self.circuit.load_ic(self.dff_crct)
                    if q_wire: self.nodes[q_wire] = dff_inst.outputs[0]
                    self.dff_connections.append((dff_inst, d_wire, clk_wire))
                    continue

                # Handle Standard Combinational Gates
                if gate_type in self.VERILOG_GATE_MAP:
                    ports = [p.strip() for p in ports_str.split(',')]
                    out_wire, in_wires = ports[0], ports[1:]
                    gate_id = self.VERILOG_GATE_MAP[gate_type]
                    gate = self.circuit.getcomponent(gate_id)
                    if gate_id < self.const.VARIABLE_ID and hasattr(self.circuit, 'setlimits'):
                        self.circuit.setlimits(gate, len(in_wires))
                    self.nodes[out_wire] = gate
                    connections.append((out_wire, in_wires))

        # Wire Combinational Logic
        for target_id, source_ids in connections:
            target_gate = self.nodes.get(target_id)
            if not target_gate: continue
            for pin_index, source_id in enumerate(source_ids):
                source_gate = self.nodes.get(source_id)
                if source_gate: self.circuit.connect(target_gate, source_gate, pin_index)

        # Wire Sequential Logic (if any)
        for dff_inst, d_wire, clk_wire in self.dff_connections:
            if clk_wire and clk_wire in self.nodes and len(dff_inst.inputs) > 0:
                self.circuit.connect(dff_inst.inputs[0], self.nodes[clk_wire], 0)
            if d_wire and d_wire in self.nodes and len(dff_inst.inputs) > 1:
                self.circuit.connect(dff_inst.inputs[1], self.nodes[d_wire], 0)



def internal_worker_main(filepath: str, mode: str):
    import gc
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    target_path = os.path.join(script_dir, mode)
    if not os.path.exists(target_path): target_path = os.path.join(project_root, mode)

    sys.path.insert(0, project_root)
    sys.path.insert(0, target_path)
    import Circuit
    import Const

    process = psutil.Process(os.getpid())
    
    # 1. Create a blank circuit to trigger any one-time initializations
    blank_circuit = Circuit.Circuit()
    gc.collect()
    
    # Measure the baseline memory with a blank circuit
    base_mem = process.memory_info().rss
    
    # Clean up the blank circuit (check for destructive clear or abandon)

    blank_circuit.clearcircuit()
    del blank_circuit
    gc.collect()

    try:
        import time
        t_start = time.perf_counter_ns()
        loader = UniversalLoader(filepath, Circuit.Circuit, Const)
        t_loaded = time.perf_counter_ns()
        load_time_ms = (t_loaded - t_start) / 1_000_000.0

        if hasattr(loader.circuit, 'optimize'):
            t_opt_start = time.perf_counter_ns()
            loader.circuit.optimize()
            t_opt_end = time.perf_counter_ns()
            opt_time_ms = (t_opt_end - t_opt_start) / 1_000_000.0
        else:
            opt_time_ms = 0.0
        
        # Extract pure circuit and destroy the parser/loader state
        pure_circuit = loader.circuit
        gates = len(loader.nodes)
        del loader
        gc.collect()
        
        loaded_mem = process.memory_info().rss
        delta_mb = max((loaded_mem - base_mem) / (1024 * 1024), 0.00)
        base_mb = base_mem / (1024 * 1024)
        
        peak_mb = 0
        try:
            with open(f"/proc/{os.getpid()}/status", "r") as f:
                for line in f:
                    if line.startswith("VmHWM:"):
                        peak_mb = int(line.split()[1]) / 1024.0
                        break
        except Exception:
            pass

        print(json.dumps({"prog_mb": base_mb, "circ_mb": delta_mb, "peak_mb": peak_mb, "gates": gates, "load_ms": load_time_ms, "opt_ms": opt_time_ms}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

# ===========================================================================
# 2. ICARUS VERILOG RAM LOADER (Zero-wire testbench)
# ===========================================================================
def measure_icarus_ram(v_file: str) -> dict:
    if not shutil.which("iverilog"): return {"error": "iverilog not found"}

    harness_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "harness_build")
    wait_tb = os.path.join(harness_dir, "icarus_memory_wait.v")
    dff_stub = os.path.join(harness_dir, "icarus_dff_stub.v")

    vvp_file = os.path.splitext(v_file)[0] + "_mem.vvp"
    empty_vvp_file = os.path.splitext(v_file)[0] + "_empty.vvp"
    
    try:
        # 1. Measure Empty VVP Baseline
        subprocess.run(["iverilog", "-o", empty_vvp_file, wait_tb], capture_output=True, text=True)
        
        p_empty = psutil.Popen(["vvp", empty_vvp_file], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in p_empty.stdout:
            if "READY" in line: break
        base_mem_mb = p_empty.memory_info().rss / (1024 * 1024)
        p_empty.kill()

        # 2. Compile and Measure Full Circuit
        with open(v_file, 'r', encoding='utf-8') as f: content = f.read()
        cmd = ["iverilog", "-o", vvp_file, v_file, wait_tb]
        if re.search(r'\bdff', content, re.IGNORECASE) and not re.search(r'\bmodule\s+dff\b', content, re.IGNORECASE):
            cmd.append(dff_stub)
            
        import time
        t_start = time.perf_counter_ns()
        res = subprocess.run(cmd, capture_output=True, text=True)
        t_end = time.perf_counter_ns()
        load_time_ms = (t_end - t_start) / 1_000_000.0
        
        if res.returncode != 0:
            return {"error": "Compile N/A"}
        
        p = psutil.Popen(["vvp", vvp_file], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in p.stdout:
            if "READY" in line: break
            
        loaded_mem_mb = p.memory_info().rss / (1024 * 1024)
        
        peak_mb = 0
        try:
            with open(f"/proc/{p.pid}/status", "r") as f:
                for line in f:
                    if line.startswith("VmHWM:"):
                        peak_mb = int(line.split()[1]) / 1024.0
                        break
        except Exception:
            peak_mb = loaded_mem_mb
            
        p.kill()
        
        # 3. Calculate true delta (isolated circuit memory)
        delta_mb = max(loaded_mem_mb - base_mem_mb, 0.01)
        return {"prog_mb": base_mem_mb, "circ_mb": delta_mb, "peak_mb": peak_mb, "load_ms": load_time_ms, "opt_ms": 0.0}
        
    except Exception as e:
        return {"error": "Subprocess N/A"}
    finally:
        for p in (vvp_file, empty_vvp_file):
            if os.path.exists(p): 
                try: os.remove(p)
                except: pass


def get_v_files(target):
    if os.path.isfile(target) and target.endswith('.v'): return [target]
    return sorted([os.path.join(r, f) for r, _, fs in os.walk(target) for f in fs if f.endswith('.v') and not f.endswith('_tb.v')], key=os.path.getsize)

def _parse_mem(res):
    if res.returncode == 0:
        try:
            return json.loads(res.stdout)
        except: pass
    return {"error": "N/A"}

def main():
    parser = argparse.ArgumentParser(description="Universal 4-Engine RAM Footprint Test")
    parser.add_argument('target', nargs='?', type=str, help="Path to .v file or directory")
    parser.add_argument('--no-engine', dest='engine', action='store_false', help='Skip Engine memory benchmark')
    parser.set_defaults(engine=True)
    parser.add_argument('--no-rx-prop', dest='rx_prop', action='store_false', help='Skip Reactor memory benchmark (compatibility)')
    parser.set_defaults(rx_prop=True)
    parser.add_argument('--no-rx-sweep', dest='rx_sweep', action='store_false', help='Skip Reactor memory benchmark (compatibility)')
    parser.set_defaults(rx_sweep=True)

    parser.add_argument('--no-icarus', dest='icarus', action='store_false', help='Skip Icarus Verilog benchmark')
    parser.set_defaults(icarus=True)
    parser.add_argument('--internal-worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--mode', type=str, choices=['engine', 'reactor'], help=argparse.SUPPRESS)
    parser.add_argument('--dump', action='store_true', help='Only generate final data')
    parser.add_argument('--json', action='store_true', help='Only generate json output')
    args = parser.parse_args()

    if args.internal_worker:
        internal_worker_main(args.target, args.mode)
        sys.exit(0)

    if not args.target:
        print("[-] Error: Target required."); sys.exit(1)

    v_files = get_v_files(args.target)

    W = 175
    cols1 = (
        f"| {'Circuit':<16} | {'Gates':<10} "
        f"| {'':<10} | {'':<10} | {'Engine':^10} | {'':<10} "
        f"| {'':<10} | {'':<10} | {'Reactor':^10} | {'':<10} | {'':<10} "
        f"| {'':<10} | {'':<10} | {'Icarus':^10} | {'':<10} |"
    )
    sep = (
        f"|{'-'*18}|{'-'*12}"
        f"|{'-'*12}|{'-'*12}|{'-'*12}|{'-'*12}"
        f"|{'-'*12}|{'-'*12}|{'-'*12}|{'-'*12}|{'-'*12}"
        f"|{'-'*12}|{'-'*12}|{'-'*12}|{'-'*12}|"
    )
    cols2 = (
        f"| {'':<16} | {'':<10} "
        f"| {'Prog(MB)':>10} | {'Circ(MB)':>10} | {'Peak(MB)':>10} | {'Load(ms)':>10} "
        f"| {'Prog(MB)':>10} | {'Circ(MB)':>10} | {'Peak(MB)':>10} | {'Load(ms)':>10} | {'Opt(ms)':>10} "
        f"| {'Prog(MB)':>10} | {'Circ(MB)':>10} | {'Peak(MB)':>10} | {'Comp(ms)':>10} |"
    )

    if not getattr(args, 'json', False):
        print("=" * W)
        print("  LOAD FOOTPRINT BENCHMARK (Combinational & Sequential)")
        print("  All Engines: Reporting Program Memory, Circuit Memory, Load time and compile/optimize times.")
        print("=" * W)
        print(cols1)
        print(sep)
        print(cols2)

    all_results = []
    markdown_lines = []
    markdown_lines.append("# Load Footprint Benchmark")
    markdown_lines.append("")
    markdown_lines.append(cols1)
    markdown_lines.append(sep)
    markdown_lines.append(cols2)

    for vf in v_files:
        fn = os.path.basename(vf)
        
        if args.engine:
            res_e = subprocess.run([sys.executable, __file__, "--internal-worker", vf, "--mode", "engine"], capture_output=True, text=True)
            e_dict = _parse_mem(res_e)
        else:
            e_dict = {"error": "N/A"}
            
        if args.rx_prop or args.rx_sweep:
            res_r = subprocess.run([sys.executable, __file__, "--internal-worker", vf, "--mode", "reactor"], capture_output=True, text=True)
            r_dict = _parse_mem(res_r)
        else:
            r_dict = {"error": "N/A"}
            

        if args.icarus:
            i_dict = measure_icarus_ram(vf)
        else:
            i_dict = {"error": "N/A"}

        def eng_cols(d):
            if "error" in d: return f"{'N/A':>10} | {'N/A':>10} | {'N/A':>10} | {'N/A':>10}"
            return f"{d.get('prog_mb',0.0):>10.1f} | {d.get('circ_mb',0.0):>10.1f} | {d.get('peak_mb',0.0):>10.1f} | {d.get('load_ms',0.0):>10.1f}"

        def rx_cols(d):
            if "error" in d: return f"{'N/A':>10} | {'N/A':>10} | {'N/A':>10} | {'N/A':>10} | {'N/A':>10}"
            return f"{d.get('prog_mb',0.0):>10.1f} | {d.get('circ_mb',0.0):>10.1f} | {d.get('peak_mb',0.0):>10.1f} | {d.get('load_ms',0.0):>10.1f} | {d.get('opt_ms',0.0):>10.1f}"

        def ic_cols(d):
            if "error" in d: return f"{'N/A':>10} | {'N/A':>10} | {'N/A':>10} | {'N/A':>10}"
            return f"{d.get('prog_mb',0.0):>10.1f} | {d.get('circ_mb',0.0):>10.1f} | {d.get('peak_mb',0.0):>10.1f} | {d.get('load_ms',0.0):>10.1f}"

        gates_val = r_dict.get('gates', e_dict.get('gates', 0)) if "gates" in r_dict or "gates" in e_dict else None
        
        if args.json:
            all_results.append({
                "circuit": fn,
                "gates": gates_val,
                "engine": e_dict,
                "reactor": r_dict,
                "icarus": i_dict
            })
        else:
            e_str = eng_cols(e_dict)
            r_str = rx_cols(r_dict)
            i_str = ic_cols(i_dict)
            
            gates_str = f"{gates_val:,}" if gates_val is not None else "N/A"
            row_str = f"| {fn:<16} | {gates_str:>10} | {e_str} | {r_str} | {i_str} |"
            
            if not getattr(args, 'json', False):
                print(row_str)
            markdown_lines.append(row_str)

    if args.json:
        print(json.dumps(all_results, indent=4))
    
    if args.dump:
        import datetime
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dump_dir = os.path.join(script_dir, 'test_result', 'load')
        os.makedirs(dump_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_path = os.path.join(dump_dir, f"unified_load_{timestamp}.md")
        with open(dump_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(markdown_lines) + "\n")
        print(f"\n[+] Markdown dump saved to -> {dump_path}")



if __name__ == '__main__':
    main()
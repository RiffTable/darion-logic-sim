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
try:
    from verilog_to_circ import convert_file, vector_file_path
except ImportError:
    try:
        from tests.verilog_to_circ import convert_file, vector_file_path
    except ImportError:
        convert_file = None

# ===========================================================================
# 1. ENGINE / REACTOR RAM LOADER (Universal: Combo + Seq)
# ===========================================================================

class UniversalLoader:
    def __init__(self, v_file_path, circuit_cls, const_mod):
        self.Circuit = circuit_cls
        self.const = const_mod
        self.circuit = self.Circuit()
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
            'not': self.const.NOT_ID, 'buf': self.const.INPUT_PIN_ID,
        }
        self._parse_verilog(v_file_path)

    def _parse_verilog(self, filepath):
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
            elif stmt.startswith(('wire ', 'module ', 'endmodule', 'reg ', 'output ')):
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
        loader = UniversalLoader(filepath, Circuit.Circuit, Const)
        if hasattr(loader.circuit, 'optimize'): loader.circuit.optimize()
        
        # Extract pure circuit and destroy the parser/loader state
        pure_circuit = loader.circuit
        del loader
        gc.collect()
        
        loaded_mem = process.memory_info().rss
        delta_mb = max((loaded_mem - base_mem) / (1024 * 1024), 0.00)
        base_mb = base_mem / (1024 * 1024)
        
        # Clean up the loaded circuit
        pure_circuit.clearcircuit()
            
        print(json.dumps({"prog_mb": base_mb, "circ_mb": delta_mb}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

# ===========================================================================
# 2. LOGISIM RAM LOADER (Custom Java GC Harness)
# ===========================================================================
def measure_logisim_ram(v_file: str, jar_path: str) -> dict:
    if convert_file is None: return {"error": "verilog_to_circ not available"}
    
    harness_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "harness_build")
    java_file = os.path.join(harness_dir, "LogisimMemoryHarness.java")
    class_file = os.path.join(harness_dir, "LogisimMemoryHarness.class")
    
    if not os.path.exists(class_file) or os.path.getmtime(java_file) > os.path.getmtime(class_file):
        try:
            subprocess.run(["javac", "-cp", jar_path, java_file], check=True)
        except Exception:
            pass

    circ_file = os.path.splitext(v_file)[0] + "_mem_converted.circ"
    vec_file = vector_file_path(circ_file) if vector_file_path else circ_file.replace('.circ', '.txt')
    
    try:
        convert_file(v_file, circ_file, max_ticks=0)
        cmd = ["java", "-cp", f"{jar_path}{os.pathsep}{harness_dir}", "LogisimMemoryHarness", circ_file]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
        out_dict = {}
        for line in res.stdout.splitlines():
            if line.startswith("PROG_MB:"): out_dict["prog_mb"] = float(line.split(":")[1])
            if line.startswith("MEM_MB:"): out_dict["circ_mb"] = float(line.split(":")[1])
        if "circ_mb" in out_dict and "prog_mb" in out_dict: return out_dict
        return {"error": "Failed to parse memory"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        for p in (circ_file, vec_file):
            if p and os.path.exists(p):
                try: os.remove(p)
                except OSError: pass

# ===========================================================================
# 3. ICARUS VERILOG RAM LOADER (Zero-wire testbench)
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
        
        p_empty = psutil.Popen(["vvp", empty_vvp_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in p_empty.stdout:
            if "READY" in line: break
        base_mem_mb = p_empty.memory_info().rss / (1024 * 1024)
        p_empty.kill()

        # 2. Compile and Measure Full Circuit
        with open(v_file, 'r', encoding='utf-8') as f: content = f.read()
        cmd = ["iverilog", "-o", vvp_file, v_file, wait_tb]
        if re.search(r'\bdff', content, re.IGNORECASE) and not re.search(r'\bmodule\s+dff\b', content, re.IGNORECASE):
            cmd.append(dff_stub)
            
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return {"error": "Compile ERR"}
        
        p = psutil.Popen(["vvp", vvp_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in p.stdout:
            if "READY" in line: break
            
        loaded_mem_mb = p.memory_info().rss / (1024 * 1024)
        p.kill()
        
        # 3. Calculate true delta (isolated circuit memory)
        delta_mb = max(loaded_mem_mb - base_mem_mb, 0.01)
        return {"prog_mb": base_mem_mb, "circ_mb": delta_mb}
        
    except Exception as e:
        return {"error": "Subprocess ERR"}
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
    return {"error": "ERR"}

def main():
    parser = argparse.ArgumentParser(description="Universal 4-Engine RAM Footprint Test")
    parser.add_argument('target', nargs='?', type=str, help="Path to .v file or directory")
    parser.add_argument('--jar', type=str, default="logisim-evolution.jar", help="Path to logisim-evolution JAR")
    parser.add_argument('--internal-worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--mode', type=str, choices=['engine', 'reactor'], help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.internal_worker:
        internal_worker_main(args.target, args.mode)
        sys.exit(0)

    if not args.target:
        print("[-] Error: Target required."); sys.exit(1)

    v_files = get_v_files(args.target)
    jar_path = os.path.abspath(args.jar)
    
    if convert_file and shutil.which("javac") and os.path.exists(jar_path):
        has_logisim = True
    else:
        has_logisim = False

    W = 100
    print("=" * W)
    print("  UNIVERSAL CIRCUIT RAM / MEMORY FOOTPRINT BENCHMARK (Combo & Sequential)")
    print("  All Engines: Reporting Program Memory / Circuit Memory in MB.")
    print("=" * W)
    print(f"{'Circuit':<16} | {'Engine (P/C MB)':<17} | {'Reactor (P/C MB)':<17} | {'Logisim (P/C MB)':<17} | {'Icarus (P/C MB)':<17}")
    print("-" * W)

    for vf in v_files:
        fn = os.path.basename(vf)
        
        res_e = subprocess.run([sys.executable, __file__, "--internal-worker", vf, "--mode", "engine"], capture_output=True, text=True)
        res_r = subprocess.run([sys.executable, __file__, "--internal-worker", vf, "--mode", "reactor"], capture_output=True, text=True)
        
        e_dict = _parse_mem(res_e)
        r_dict = _parse_mem(res_r)
        
        l_dict = measure_logisim_ram(vf, jar_path) if has_logisim else {"error": "N/A"}
        i_dict = measure_icarus_ram(vf)

        def fmt_dict(d):
            if "error" in d: return str(d["error"])
            return f"{d.get('prog_mb', 0.0):.2f} / {d.get('circ_mb', 0.0):.2f}"

        e_str = fmt_dict(e_dict)
        r_str = fmt_dict(r_dict)
        l_str = fmt_dict(l_dict)
        i_str = fmt_dict(i_dict)

        print(f"{fn:<16} | {e_str:>17} | {r_str:>17} | {l_str:>17} | {i_str:>17}")



if __name__ == '__main__':
    main()
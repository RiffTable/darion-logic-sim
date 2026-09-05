"""
unified_iscas_verifier.py
=========================
Combinational State Verification Testbench for ISCAS85 Circuits.

Compares simulation states across 4 execution engines:
  1. Icarus Verilog (base Model via Verilog File I/O)
  2. Pure Python Engine
  3. Cython Reactor - Propagate (SIMULATE mode / BFS Wavefront)
  4. Cython Reactor - Sweep (COMPILE mode / Topological Forward-Pass)

Outputs:
  - CLI validation summary (Pass/Fail, mismatch indices, values).
  - Detailed structured JSON verification report.
"""

import os
import re
import sys
import random
import argparse
import subprocess
import shutil

try:
    import orjson
    def dump_json_file(filepath, obj, indent=True):
        opts = orjson.OPT_INDENT_2 if indent else 0
        with open(filepath, 'wb') as f:
            f.write(orjson.dumps(obj, option=opts))

    def load_json_file(filepath):
        with open(filepath, 'rb') as f:
            return orjson.loads(f.read())
except ImportError:
    import json
    def dump_json_file(filepath, obj, indent=True):
        with open(filepath, 'w', encoding='utf-8') as f:
            if indent:
                json.dump(obj, f, indent=2)
            else:
                json.dump(obj, f)

    def load_json_file(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

sys.path.insert(0, _SCRIPT_DIR)
_HARNESS_DIR  = os.path.join(_PROJECT_ROOT, 'harness_build')


# ===========================================================================
# 1. VERILOG NETLIST PARSER
# ===========================================================================

def parse_verilog_ports(v_file: str):
    """Extract module name, ordered input ports, and ordered output ports."""
    with open(v_file, 'r', encoding='utf-8') as f:
        content = f.read()

    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'//.*', '', content)

    module_body = content
    module_name = "circuit"
    for m in re.finditer(r'\bmodule\s+([a-zA-Z0-9_]+)(.*?)\bendmodule\b', content, flags=re.DOTALL):
        if m.group(1).lower() != 'dff':
            module_name = m.group(1)
            module_body = m.group(0)
            break

    def extract_ports(keyword):
        ports = []
        for m in re.finditer(r'\b' + keyword + r'\s+([^;]+);', module_body):
            decl = m.group(1).strip()
            cleaned = re.sub(
                r'(\[[^\]]+\]|\bwire\b|\breg\b|\blogic\b|\bsigned\b|\bunsigned\b)',
                '', decl).strip()
            for p in cleaned.split(','):
                p = p.strip()
                if p:
                    ports.append(p)
        return ports

    return module_name, extract_ports('input'), extract_ports('output')


# ===========================================================================
# 2. ICARUS VERILOG base MODEL RUNNER
# ===========================================================================

def generate_icarus_tb(v_file: str, tb_file: str, vector_file: str, output_file: str, vectors_count: int):
    """Generates an Icarus testbench that writes outputs directly to file."""
    module_name, inputs, outputs = parse_verilog_ports(v_file)

    tb = []
    tb.append("`timescale 1ns/1ps\n")
    tb.append(f"module tb_{module_name};\n")

    for inp in inputs:
        tb.append(f"    reg {inp};\n")
    for outp in outputs:
        tb.append(f"    wire {outp};\n")

    total_inputs = len(inputs)
    tb.append(f"    reg [{total_inputs-1}:0] test_vectors [0:{vectors_count-1}];\n")
    tb.append("    integer i, outfile;\n\n")

    tb.append(f"    {module_name} uut (\n")
    conn = [f"        .{p}({p})" for p in inputs + outputs]
    tb.append(",\n".join(conn))
    tb.append("\n    );\n\n")

    v_path_str = str(vector_file).replace("\\", "/")
    out_path_str = str(output_file).replace("\\", "/")

    fmt_str = "%b" * len(outputs)
    out_args = ", ".join(outputs)

    tb.append("    initial begin\n")
    tb.append(f'        $readmemb("{v_path_str}", test_vectors);\n')
    tb.append(f'        outfile = $fopen("{out_path_str}", "w");\n')
    tb.append(f"        for (i = 0; i < {vectors_count}; i = i + 1) begin\n")

    for idx, inp in enumerate(inputs):
        tb.append(f"            {inp} = test_vectors[i][{idx}];\n")

    tb.append("            #1;\n")
    tb.append(f'            $fdisplay(outfile, "{fmt_str}", {out_args});\n')
    tb.append("        end\n")
    tb.append("        $fclose(outfile);\n")
    tb.append("        $finish;\n")
    tb.append("    end\n")
    tb.append("endmodule\n")

    with open(tb_file, 'w', encoding='utf-8') as f:
        f.write("".join(tb))


def run_icarus_base(v_file: str, vectors: list) -> list:
    """Runs Icarus Verilog and returns the normalized 2D list of output states."""
    base_path = os.path.splitext(v_file)[0]
    tb_file = base_path + "_base_tb.v"
    vvp_file = base_path + "_base.vvp"
    vec_file = base_path + "_base_inputs.txt"
    out_file = base_path + "_base_outputs.txt"

    if not shutil.which("iverilog") or not shutil.which("vvp"):
        raise RuntimeError("iverilog or vvp command not found in system PATH")

    try:
        with open(vec_file, 'w', encoding='utf-8') as f:
            for vec in vectors:
                bin_str = "".join(str(v) for v in reversed(vec))
                f.write(bin_str + "\n")

        generate_icarus_tb(v_file, tb_file, vec_file, out_file, len(vectors))

        comp_res = subprocess.run(["iverilog", "-o", vvp_file, v_file, tb_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if comp_res.returncode != 0:
            raise RuntimeError(f"Icarus compile error: {comp_res.stderr.strip()}")

        run_res = subprocess.run(["vvp", vvp_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if run_res.returncode != 0:
            raise RuntimeError(f"Icarus runtime error: {run_res.stderr.strip()}")

        # Parse and normalize output: '0' -> 0, '1' -> 1, ('x', 'z') -> 2 (Const.UNKNOWN)
        with open(out_file, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()

        normalized_results = []
        for line in lines:
            line = line.strip()
            if not line: continue
            normalized_results.append(
                [0 if b == '0' else (1 if b == '1' else 2) for b in line]
            )

        return normalized_results

    finally:
        for p in (tb_file, vvp_file, vec_file, out_file):
            if os.path.exists(p):
                try: os.remove(p)
                except OSError: pass


# ===========================================================================
# 3. INTERNAL WORKER FOR ENGINE & REACTOR
# ===========================================================================

class VerilogStateRunner:
    def __init__(self, v_file_path, circuit_cls, const_mod, is_reactor=False):
        self.Circuit = circuit_cls
        self.const = const_mod
        self.circuit = self.Circuit()
        self.circuit.simulate(self.const.DESIGN)
        self.is_reactor = is_reactor
        self.nodes = {}
        self.outputs = []
        self.input_vars = []

        self.VERILOG_GATE_MAP = {
            'and': self.const.AND_ID, 'nand': self.const.NAND_ID, 'or': self.const.OR_ID,
            'nor': self.const.NOR_ID, 'xor': self.const.XOR_ID, 'xnor': self.const.XNOR_ID,
            'not': self.const.NOT_ID, 'buf': self.const.BUFFER_ID
        }

        self._parse_verilog(v_file_path)
        
        # Maintain references to python Gate objects ordered strictly by the verilog outputs list.
        # Some circuits declare output ports that share a name with an input wire (passthroughs)
        # or alias an internal wire not directly keyed in self.nodes — skip with a warning.
        self.output_objects = []
        for p in self.outputs:
            node = self.nodes.get(p + "_OUTPIN")
            if not node:
                node = self.nodes.get(p)
            
            if node is None:
                print(f"[VerilogStateRunner] Warning: output port '{p}' not found in nodes dict — skipped.")
            else:
                self.output_objects.append(node)

    def _parse_verilog(self, filepath):
        json_path = filepath.replace('.v', '.json')
        if os.path.exists(json_path) and hasattr(self.circuit, 'readfromjson'):
            self.circuit.readfromjson(json_path)
            _, inputs, outputs = parse_verilog_ports(filepath)
            
            var_list = self.circuit.get_variables()
            var_dict = {}
            for v in var_list:
                name_str = getattr(v, 'custom_name', None) or getattr(v, 'codename', None) or str(v)
                var_dict[name_str] = v
                
            for inp in inputs:
                port_name = inp.split()[-1]
                expected_name = f"IN_{port_name}"
                if expected_name in var_dict:
                    self.input_vars.append(var_dict[expected_name])
                else:
                    found = False
                    for k, v in var_dict.items():
                        if port_name in k:
                            self.input_vars.append(v)
                            found = True
                            break
                    if not found:
                        print(f"Warning: Could not map pin {port_name} from JSON.")
            
            for outp in outputs:
                port_name = outp.split()[-1]
                self.outputs.append(port_name)

            for gate in self.circuit.get_components():
                name_str = getattr(gate, 'custom_name', None) or getattr(gate, 'codename', None) or str(gate)
                if name_str.startswith("G_"):
                    self.nodes[name_str[2:]] = gate
                elif name_str.startswith("IN_"):
                    self.nodes[name_str[3:]] = gate
                elif name_str.startswith("OUT_"):
                    self.nodes[name_str[4:] + "_OUTPIN"] = gate
                elif name_str == "CONST_1":
                    self.const_1_node = gate
                    self.nodes["1'b1"] = gate
                elif name_str == "CONST_0":
                    self.const_0_node = gate
                    self.nodes["1'b0"] = gate
                else:
                    self.nodes[name_str] = gate

            if hasattr(self.circuit, 'optimize'):
                self.circuit.optimize()
            self.circuit.simulate(self.const.COMPILE)
            return

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'//.*', '', content)
        statements = [s.strip() for s in content.split(';') if s.strip()]
        connections = []

        self.const_1_node = None
        self.const_0_node = None

        def get_const_node(val_str):
            if val_str == "1'b1":
                if not getattr(self, 'const_1_node', None):
                    self.const_1_node = self.circuit.getcomponent(self.const.VARIABLE_ID)
                    self.const_1_node.rename("CONST_1")
                    self.nodes["1'b1"] = self.const_1_node
                return self.const_1_node
            elif val_str == "1'b0":
                if not getattr(self, 'const_0_node', None):
                    self.const_0_node = self.circuit.getcomponent(self.const.VARIABLE_ID)
                    self.const_0_node.rename("CONST_0")
                    self.nodes["1'b0"] = self.const_0_node
                return self.const_0_node
            return None
        connections = []

        for stmt in statements:
            if stmt.startswith('input '):
                ports = stmt.replace('input', '').strip().split(',')
                for p in ports:
                    p = p.strip()
                    if p:
                        var_node = self.circuit.getcomponent(self.const.VARIABLE_ID)
                        var_node.rename(f"IN_{p}")
                        self.nodes[p] = var_node
                        self.input_vars.append(var_node)
            elif stmt.startswith('output '):
                ports = stmt.replace('output', '').strip().split(',')
                for p in ports:
                    p = p.strip()
                    if p:
                        out_node = self.circuit.getcomponent(self.const.IC_OUTPUT_PIN_ID)
                        out_node.rename(f"OUT_{p}")
                        self.nodes[p + "_OUTPIN"] = out_node
                        self.outputs.append(p)
                        connections.append((p + "_OUTPIN", [p]))
            elif stmt.startswith(('wire ', 'module ', 'endmodule', 'reg ')):
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
                        
                        for w in in_wires:
                            get_const_node(w)

                        if gate_id < getattr(self.const, 'VARIABLE_ID', 99) and hasattr(self.circuit, 'setlimits'):
                            self.circuit.setlimits(gate, len(in_wires))
                        self.nodes[out_wire] = gate
                        connections.append((out_wire, in_wires))

        for target_id, source_ids in connections:
            target_gate = self.nodes.get(target_id)
            if not target_gate: continue
            for pin_index, source_id in enumerate(source_ids):
                source_gate = self.nodes.get(source_id)
                if source_gate:
                    self.circuit.connect(target_gate, source_gate, pin_index)

        if hasattr(self.circuit, 'optimize'):
            self.circuit.optimize()
        self.circuit.simulate(self.const.COMPILE)

    def _get_current_state(self) -> list:
        """Extracts the state by calling output directly on the python Gate objects."""
        return [g.output for g in self.output_objects]

    def run_vectors(self, raw_vectors: list, target_mode: int) -> list:
        """Simulates all vectors via batch toggle and captures output states."""
        # Initialize the circuit into the targeted execution mode (SIMULATE vs COMPILE)
        self.circuit.simulate(target_mode)
        self.const.set_MODE(target_mode)

        batches = []
        is_oop = getattr(self, 'is_reactor_oop', False)
        for vec in raw_vectors:
            batch = []
            for var_node, val in zip(self.input_vars, vec):
                c_val = self.const.HIGH if val == 1 else self.const.LOW
                batch.append((var_node if is_oop else var_node.location, c_val))
            
            if getattr(self, 'const_1_node', None):
                batch.append((self.const_1_node if is_oop else self.const_1_node.location, self.const.HIGH))
            if getattr(self, 'const_0_node', None):
                batch.append((self.const_0_node if is_oop else self.const_0_node.location, self.const.LOW))
                
            batches.append(batch)

        results = []
        for b in batches:
            self.circuit.batch_toggle(b)
            results.append(self._get_current_state())

        # Safely restore execution context to SIMULATE
        self.const.set_MODE(self.const.SIMULATE)

        return results


def run_worker_process(filepath: str, exec_mode: str, vectors: list) -> list:
    """Spawns an isolated Python process to evaluate vectors."""
    temp_vec_json = filepath + f"_{exec_mode}_in.tmp.json"
    temp_out_json = filepath + f"_{exec_mode}_out.tmp.json"

    dump_json_file(temp_vec_json, vectors, indent=False)

    cmd = [
        sys.executable, os.path.abspath(__file__),
        "--internal-worker", filepath,
        "--exec-mode", exec_mode,
        "--in-file", temp_vec_json,
        "--out-file", temp_out_json,
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            print("RETURNCODE:", res.returncode)
            raise RuntimeError(f"Worker ({exec_mode}) failed: {res.stderr.strip() or res.stdout.strip()}")

        return load_json_file(temp_out_json)

    finally:
        for p in (temp_vec_json, temp_out_json):
            if os.path.exists(p):
                try: os.remove(p)
                except OSError: pass


def internal_worker_main(filepath: str, exec_mode: str, in_file: str, out_file: str):
    """Entry point for the isolated subprocess."""
    if exec_mode == 'reactor_oop':
        pkg_dir = 'reactor_oop'
    else:
        pkg_dir = 'reactor' if 'reactor' in exec_mode else 'engine'
        
    target_path = os.path.join(_SCRIPT_DIR, '..', pkg_dir)
    if not os.path.exists(target_path):
        target_path = os.path.join(_PROJECT_ROOT, pkg_dir)

    sys.path.insert(0, _PROJECT_ROOT)
    sys.path.insert(0, target_path)

    import Circuit
    import Const

    vectors = load_json_file(in_file)

    is_reactor = 'reactor' in exec_mode
    target_const_mode = Const.COMPILE if 'sweep' in exec_mode else Const.SIMULATE

    runner = VerilogStateRunner(filepath, Circuit.Circuit, Const, is_reactor=is_reactor)
    runner.is_reactor_oop = (exec_mode == 'reactor_oop')
    results = runner.run_vectors(vectors, target_mode=target_const_mode)

    dump_json_file(out_file, results, indent=False)



# ===========================================================================
# 4. EQUIVALENCE VERIFIER & COMPARATOR
# ===========================================================================

def verify_circuit(v_file: str, vector_count: int = 1000, seed: int = 42, use_icarus: bool = True, use_engine: bool = True, use_rx_prop: bool = True, use_rx_sweep: bool = True, use_reactor_oop: bool = True) -> dict:
    filename = os.path.basename(v_file)
    _, inputs, outputs = parse_verilog_ports(v_file)

    rng = random.Random(seed)
    raw_vectors = [
        [rng.randint(0, 1) for _ in range(len(inputs))]
        for _ in range(vector_count)
    ]

    # 1. base Reference (Icarus Verilog)
    icarus_states = run_icarus_base(v_file, raw_vectors) if use_icarus else [None] * vector_count

    # 2. Python Engine
    engine_states = run_worker_process(v_file, 'engine', raw_vectors) if use_engine else [None] * vector_count

    # 3. Cython Reactor (SIMULATE mode)
    rx_prop_states = run_worker_process(v_file, 'reactor_prop', raw_vectors) if use_rx_prop else [None] * vector_count

    # 4. Cython Reactor (COMPILE mode)
    rx_sweep_states = run_worker_process(v_file, 'reactor_sweep', raw_vectors) if use_rx_sweep else [None] * vector_count

    # 5. Cython Reactor OOP (SIMULATE mode)
    reactor_oop_states = run_worker_process(v_file, 'reactor_oop', raw_vectors) if use_reactor_oop else [None] * vector_count



    mismatches = []
    vector_logs = []

    for i in range(vector_count):
        g_out = icarus_states[i]
        e_out = engine_states[i]
        rp_out = rx_prop_states[i]
        rs_out = rx_sweep_states[i]
        ro_out = reactor_oop_states[i]

        ref_state = None
        ref_name = None
        if use_icarus:
            ref_state = g_out; ref_name = "Icarus"
        elif use_engine:
            ref_state = e_out; ref_name = "Engine"
        elif use_rx_prop:
            ref_state = rp_out; ref_name = "Rx-Prop"
        elif use_rx_sweep:
            ref_state = rs_out; ref_name = "Rx-Sweep"
        elif use_reactor_oop:
            ref_state = ro_out; ref_name = "Reactor OOP"

        match_icarus      = (g_out == ref_state) if use_icarus else True
        match_engine      = (e_out == ref_state) if use_engine else True
        match_rx_prop     = (rp_out == ref_state) if use_rx_prop else True
        match_rx_sweep    = (rs_out == ref_state) if use_rx_sweep else True
        match_reactor_oop = (ro_out == ref_state) if use_reactor_oop else True
        all_match = match_icarus and match_engine and match_rx_prop and match_rx_sweep and match_reactor_oop

        vector_logs.append({
            "vector_id": i,
            "inputs": raw_vectors[i],
            "expected": ref_state,
            "ref_source": ref_name,
            "icarus": g_out if use_icarus else "SKIPPED",
            "engine": e_out if use_engine else "SKIPPED",
            "rx_prop": rp_out if use_rx_prop else "SKIPPED",
            "rx_sweep": rs_out if use_rx_sweep else "SKIPPED",
            "reactor_oop": ro_out if use_reactor_oop else "SKIPPED",
            "pass": all_match,
        })

        if not all_match:
            mismatches.append({
                "vector_id": i,
                "inputs": raw_vectors[i],
                "expected": ref_state,
                "ref_source": ref_name,
                "icarus_actual":   g_out if not match_icarus else "MATCH" if use_icarus else "SKIPPED",
                "engine_actual":   e_out if not match_engine else "MATCH" if use_engine else "SKIPPED",
                "rx_prop_actual":  rp_out if not match_rx_prop else "MATCH" if use_rx_prop else "SKIPPED",
                "rx_sweep_actual": rs_out if not match_rx_sweep else "MATCH" if use_rx_sweep else "SKIPPED",
                "reactor_oop_actual":  ro_out if not match_reactor_oop  else "MATCH" if use_reactor_oop  else "SKIPPED",
            })

    return {
        "circuit": filename,
        "inputs_count": len(inputs),
        "outputs_count": len(outputs),
        "total_vectors": vector_count,
        "pass_count": vector_count - len(mismatches),
        "fail_count": len(mismatches),
        "status": "PASS" if len(mismatches) == 0 else "FAIL",
        "mismatches": mismatches,
        "vector_logs": vector_logs,
    }


# ===========================================================================
# 5. CLI & REPORT RUNNER
# ===========================================================================

def get_v_files(target):
    if os.path.isfile(target) and target.endswith('.v'):
        return [target]
    v_files = []
    for root, _, files in os.walk(target):
        for f in files:
            if f.endswith('.v') and not f.endswith('_base_tb.v'):
                v_files.append(os.path.join(root, f))
    return sorted(v_files, key=os.path.getsize)


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Unified 4-Engine ISCAS State & Equivalence Verifier")
    parser.add_argument('target', nargs='?', type=str, help="Path to .v file or directory")
    parser.add_argument('--vectors', type=int, default=1000, help="Number of test vectors per circuit")
    parser.add_argument('--seed', type=int, default=42, help="PRNG Seed")
    parser.add_argument('--output', type=str, default="verification_report", help="JSON output file prefix")
    parser.add_argument('--dump', action='store_true', help='Only generate final data to stdout')
    parser.add_argument('--json', action='store_true', help='Only generate JSON to stdout')
    
    parser.add_argument('--no-engine', dest='engine', action='store_false', help='Skip the Python Engine backend')
    parser.set_defaults(engine=True)
    parser.add_argument('--no-rx-prop', dest='rx_prop', action='store_false', help='Skip Reactor BFS propagate (SIMULATE mode)')
    parser.set_defaults(rx_prop=True)
    parser.add_argument('--no-rx-sweep', dest='rx_sweep', action='store_false', help='Skip Reactor linear fwd-pass (COMPILE mode)')
    parser.set_defaults(rx_sweep=True)
    parser.add_argument('--no-icarus', dest='icarus', action='store_false', help='Skip Icarus Verilog base model')
    parser.set_defaults(icarus=True)
    parser.add_argument('--no-reactor-oop', dest='reactor_oop', action='store_false', help='Skip Reactor OOP (SIMULATE mode)')
    parser.set_defaults(reactor_oop=True)

    parser.add_argument('--internal-worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--exec-mode', type=str, help=argparse.SUPPRESS)
    parser.add_argument('--in-file', type=str, help=argparse.SUPPRESS)
    parser.add_argument('--out-file', type=str, help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.internal_worker:
        internal_worker_main(args.target, args.exec_mode, args.in_file, args.out_file)
        sys.exit(0)

    if not args.target:
        print("[-] Error: No target path specified.")
        sys.exit(1)

    v_files = get_v_files(args.target)
    if not v_files:
        print("[-] Error: No .v files found.")
        sys.exit(1)

    if not getattr(args, 'json', False):
        print("=" * 105)
        print("  UNIFIED ISCAS COMBINATIONAL STATE VERIFICATION SUITE")
        print(f"  Vectors/Circuit : {args.vectors:,} | Seed: {args.seed} | base Model: Icarus Verilog")
        print("=" * 105)
        print(f"| {'Circuit':<18} | {'Inputs':<8} | {'Outputs':<8} | {'Vectors':<10} | {'Passed':<10} | {'Failed':<8} | {'Status':<8} |")
        print(f"|{'-'*20}|{'-'*10}|{'-'*10}|{'-'*12}|{'-'*12}|{'-'*10}|{'-'*10}|")

    all_reports = []
    md_lines = []
    md_lines.append("# Unified ISCAS Combinational State Verification")
    md_lines.append("")
    md_lines.append(f"- **Vectors/Circuit**: {args.vectors:,}")
    md_lines.append(f"- **Seed**: {args.seed}")
    md_lines.append("")
    md_lines.append(f"| {'Circuit':<18} | {'Inputs':<8} | {'Outputs':<8} | {'Vectors':<10} | {'Passed':<10} | {'Failed':<8} | {'Status':<8} |")
    md_lines.append(f"|{'-'*20}|{'-'*10}|{'-'*10}|{'-'*12}|{'-'*12}|{'-'*10}|{'-'*10}|")
    overall_pass = True

    for v_file in v_files:
        res = verify_circuit(v_file, vector_count=args.vectors, seed=args.seed,
                             use_icarus=args.icarus, use_engine=args.engine, 
                             use_rx_prop=args.rx_prop, use_rx_sweep=args.rx_sweep,
                             use_reactor_oop=args.reactor_oop)
        all_reports.append(res)

        status_str = "\033[92mPASS\033[0m" if res["status"] == "PASS" else "\033[91mFAIL\033[0m"
        if res["status"] != "PASS":
            overall_pass = False

        row_str = (
            f"| {res['circuit']:<18} | "
            f"{res['inputs_count']:<8} | "
            f"{res['outputs_count']:<8} | "
            f"{res['total_vectors']:<10,}| "
            f"{res['pass_count']:<10,}| "
            f"{res['fail_count']:<8} | "
            f"{status_str:<8} |"
        )
        md_lines.append(row_str)

        if not getattr(args, 'json', False):
            print(row_str)

            if res["fail_count"] > 0:
                mm = res['mismatches'][0]
                print(f"  └─> First mismatch at vector #{mm['vector_id']}:")
                print(f"      Inputs applied: {mm['inputs']}")
                print(f"      Expected ({mm['ref_source']}): {mm['expected']}")
                print(f"      Icarus   : {mm['icarus_actual']}")
                print(f"      Engine   : {mm['engine_actual']}")
                print(f"      Rx-Prop  : {mm['rx_prop_actual']}")
                print(f"      Rx-Sweep : {mm['rx_sweep_actual']}")
                print(f"      Reactor OOP: {mm['reactor_oop_actual']}")

    if getattr(args, 'json', False):
        import json as sys_json
        print(sys_json.dumps(all_reports, indent=4), file=sys.__stdout__)
        
    if getattr(args, 'dump', False):
        import datetime, os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dump_dir = os.path.join(script_dir, 'test_result', 'verifier')
        os.makedirs(dump_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_path = os.path.join(dump_dir, f"unified_iscas_verifier_{timestamp}.md")
        with open(dump_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(md_lines) + "\n")
        print(f"\n[+] Markdown dump saved to -> {dump_path}")

    if not getattr(args, 'json', False):
        print("=" * 105)
        json_path = args.output if args.output.endswith('.json') else args.output + '.json'
        dump_json_file(json_path, all_reports, indent=True)
        print(f"\n[+] Full JSON verification artifact generated -> {json_path}")
        
    sys.exit(0 if overall_pass else 1)


if __name__ == '__main__':
    main()

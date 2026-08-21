import os
import glob
import re
import sys

# Add the project root to sys.path so we can import engine/reactor dependencies
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'reactor')) # Force reactor mode
import Circuit
import Const

class VerilogRunner:
    def __init__(self, v_file_path, circuit_cls, const_mod):
        self.Circuit = circuit_cls
        self.const = const_mod
        self.circuit = self.Circuit()
        self.circuit.simulate(self.const.DESIGN)
        self.nodes = {}
        self.outputs = []
        self.input_vars = []

        self.VERILOG_GATE_MAP = {
            'and': self.const.AND_ID, 'nand': self.const.NAND_ID, 'or': self.const.OR_ID,
            'nor': self.const.NOR_ID, 'xor': self.const.XOR_ID, 'xnor': self.const.XNOR_ID,
            'not': self.const.NOT_ID, 'buf': getattr(self.const, 'INPUT_PIN_ID', self.const.NOT_ID)
        }

        self._parse_verilog(v_file_path)

    def _parse_verilog(self, filepath):
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
                    self.const_1_node = self.circuit.getcomponent(getattr(self.const, 'VARIABLE_ID', 6))
                    self.const_1_node.rename("CONST_1")
                    self.nodes["1'b1"] = self.const_1_node
                return self.const_1_node
            elif val_str == "1'b0":
                if not getattr(self, 'const_0_node', None):
                    self.const_0_node = self.circuit.getcomponent(getattr(self.const, 'VARIABLE_ID', 6))
                    self.const_0_node.rename("CONST_0")
                    self.nodes["1'b0"] = self.const_0_node
                return self.const_0_node
            return None

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
                    if p.strip(): self.outputs.append(p.strip())
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
        self.circuit.simulate(self.const.COMPILE)


def clean_var(v):
    # remove \ and replace [ ] with _
    v = v.strip()
    if v.startswith('\\'):
        v = v[1:]
    v = v.replace('[', '_').replace(']', '')
    return v

def process_file(in_path, out_path):
    print(f"Parsing {in_path} to {out_path}...")
    with open(in_path, 'r') as f:
        content = f.read()

    # Remove comments if any
    content = re.sub(r'//.*', '', content)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

    statements = [s.strip() for s in content.split(';') if s.strip()]

    module_name = "top"
    inputs = []
    outputs = []
    wires = []
    assigns = []

    for stmt in statements:
        if stmt.startswith('module'):
            # extract module name
            m = re.match(r'module\s+(\w+)', stmt)
            if m:
                module_name = m.group(1)
        elif stmt.startswith('input'):
            vars = stmt[len('input'):].split(',')
            inputs.extend([clean_var(v) for v in vars])
        elif stmt.startswith('output'):
            vars = stmt[len('output'):].split(',')
            outputs.extend([clean_var(v) for v in vars])
        elif stmt.startswith('wire'):
            vars = stmt[len('wire'):].split(',')
            wires.extend([clean_var(v) for v in vars])
        elif stmt.startswith('assign'):
            assigns.append(stmt[len('assign'):].strip())

    # Now process assigns to gates
    gates = []
    gate_count = 0
    negated_wires = {}

    def get_negated(var):
        nonlocal gate_count
        if var in ['1\'b0', '1\'b1']:
            return '1\'b1' if var == '1\'b0' else '1\'b0'
        
        var = clean_var(var)
        if var not in negated_wires:
            not_name = var + "_not"
            negated_wires[var] = not_name
            wires.append(not_name)
            gates.append(f"not NOT_{gate_count} ({not_name}, {var});")
            gate_count += 1
        return negated_wires[var]

    for a in assigns:
        parts = a.split('=')
        lhs = clean_var(parts[0])
        rhs = parts[1].strip()

        # check operators
        if '&' in rhs:
            op = '&'
            gate_type = 'and'
        elif '|' in rhs:
            op = '|'
            gate_type = 'or'
        elif '^' in rhs:
            op = '^'
            gate_type = 'xor'
        else:
            op = None
            gate_type = 'buf'

        if op:
            op1, op2 = [x.strip() for x in rhs.split(op)]
            if op1.startswith('~'):
                op1 = get_negated(op1[1:])
            else:
                op1 = clean_var(op1)

            if op2.startswith('~'):
                op2 = get_negated(op2[1:])
            else:
                op2 = clean_var(op2)

            gates.append(f"{gate_type} GATE_{gate_count} ({lhs}, {op1}, {op2});")
            gate_count += 1
        else:
            # Single operand (direct wire or direct inversion)
            if rhs.startswith('~'):
                op1 = clean_var(rhs[1:])
                gates.append(f"not NOT_{gate_count} ({lhs}, {op1});")
            else:
                op1 = clean_var(rhs)
                gates.append(f"buf BUF_{gate_count} ({lhs}, {op1});")
            gate_count += 1

    with open(out_path, 'w') as f:
        f.write(f"module {module_name} (")
        f.write(",".join(inputs + outputs))
        f.write(");\n\n")

        def chunk_write(type_str, lst):
            for i in range(0, len(lst), 10):
                f.write(f"{type_str} " + ",".join(lst[i:i+10]) + ";\n")

        if inputs:
            chunk_write("input", inputs)
            f.write("\n")
        if outputs:
            chunk_write("output", outputs)
            f.write("\n")
        if wires:
            chunk_write("wire", wires)
            f.write("\n")

        for g in gates:
            f.write(g + "\n")

        f.write("\nendmodule\n")

    # Load with VerilogRunner and dump to JSON
    json_path = out_path.replace('.v', '.json')
    print(f"Loading {out_path} into Reactor and dumping to {json_path}...")
    try:
        runner = VerilogRunner(out_path, Circuit.Circuit, Const)
        if hasattr(runner.circuit, 'optimize'):
            runner.circuit.optimize()
        runner.circuit.writetojson(json_path)
    except Exception as e:
        print(f"Failed to dump {json_path}: {e}")

def main():
    source_dir = os.path.join(_PROJECT_ROOT, 'tests', 'EPFL')
    target_dir = os.path.join(_PROJECT_ROOT, 'tests', 'EPFL_parsed')
    
    os.makedirs(target_dir, exist_ok=True)
    
    files = glob.glob(os.path.join(source_dir, '*.v'))
    for f in files:
        out_name = os.path.basename(f)
        out_path = os.path.join(target_dir, out_name)
        process_file(f, out_path)
    print("Done parsing and dumping EPFL benchmarks.")

if __name__ == '__main__':
    main()

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

class IscasVerilogRunner:
    def __init__(self, v_file_path, circuit_cls, const_mod):
        self.Circuit = circuit_cls
        self.const = const_mod
        self.circuit = self.Circuit()
        self.circuit.simulate(self.const.DESIGN)
        self.nodes = {}
        self.outputs = []
        self.input_vars = []
        self.dff_connections = []
        
        # Load DFF.json from common locations
        self.dff_crct = None
        for p in [
            os.path.join(_SCRIPT_DIR, "DFF.json"),
            os.path.join(_PROJECT_ROOT, "DFF.json"),
            "DFF.json",
        ]:
            if os.path.exists(p):
                self.dff_crct = self.circuit.get_ic(p)
                break

        self.VERILOG_GATE_MAP = {
            'and': self.const.AND_ID, 'nand': self.const.NAND_ID, 'or': self.const.OR_ID,
            'nor': self.const.NOR_ID, 'xor': self.const.XOR_ID, 'xnor': self.const.XNOR_ID,
            'not': self.const.NOT_ID, 'buf': self.const.PROBE_ID
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

        # Pass 1: create inputs and outputs
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
                        out_node = self.circuit.getcomponent(self.const.OUTPUT_PIN_ID)
                        out_node.rename(f"OUT_{p}")
                        self.nodes[p + "_OUTPIN"] = out_node
                        self.outputs.append(p)
                        connections.append((p + "_OUTPIN", [p]))

        # Pass 2: create gates
        for stmt in statements:
            if stmt.startswith(('input ', 'output ', 'wire ', 'module ', 'endmodule', 'reg ', 'always ')):
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
                        
                        inst_name = match.group(2)
                        gate.rename(f"G_{out_wire}")
                        
                        for w in in_wires:
                            get_const_node(w)

                        if gate_id < getattr(self.const, 'VARIABLE_ID', 99) and hasattr(self.circuit, 'setlimits'):
                            self.circuit.setlimits(gate, len(in_wires))
                        self.nodes[out_wire] = gate
                        connections.append((out_wire, in_wires))
                    elif gate_type == 'dff':
                        if not self.dff_crct:
                            raise RuntimeError("DFF.json is required for ISCAS89 sequential circuits but was not found.")

                        wires = {}
                        if '.' in ports_str:
                            for pm in re.finditer(r'\.\s*([a-zA-Z0-9_]+)\s*\(\s*([a-zA-Z0-9_]+)\s*\)', ports_str):
                                wires[pm.group(1).upper()] = pm.group(2)
                            d_wire   = wires.get('D')
                            clk_wire = wires.get('CK', wires.get('CLK', wires.get('C')))
                            q_wire   = wires.get('Q')
                        else:
                            pts = [p.strip() for p in ports_str.split(',')]
                            clk_wire = pts[0] if len(pts) > 0 else None
                            q_wire   = pts[1] if len(pts) > 1 else None
                            d_wire   = pts[2] if len(pts) > 2 else None

                        dff_inst = self.circuit.load_ic(self.dff_crct)
                        inst_name = match.group(2) or f"inst_{len(self.dff_connections)}"
                        if hasattr(dff_inst, 'rename'):
                            dff_inst.rename(f"DFF_{inst_name}")
                        else:
                            dff_inst.custom_name = f"DFF_{inst_name}"

                        if q_wire:
                            self.nodes[q_wire] = dff_inst.outputs[0]

                        self.dff_connections.append((dff_inst, d_wire, clk_wire))
                        continue

        for target_id, source_ids in connections:
            target_gate = self.nodes.get(target_id)
            if not target_gate: 
                continue
            for pin_index, source_id in enumerate(source_ids):
                source_gate = self.nodes.get(source_id)
                if source_gate:
                    self.circuit.connect(target_gate, source_gate, pin_index)
        for dff_inst, d_wire, clk_wire in self.dff_connections:
            # pin 0 = CLK, pin 1 = D
            if clk_wire:
                clk_src = self.nodes.get(clk_wire)
                if clk_src and len(dff_inst.inputs) > 0:
                    self.circuit.connect(dff_inst.inputs[0], clk_src, 0)
            if d_wire:
                d_src = self.nodes.get(d_wire)
                if d_src and len(dff_inst.inputs) > 1:
                    self.circuit.connect(dff_inst.inputs[1], d_src, 0)



def process_iscas_file(v_path, json_path):
    print(f"Loading {v_path} into Reactor and dumping to {json_path}...")
    try:
        runner = IscasVerilogRunner(v_path, Circuit.Circuit, Const)
        if hasattr(runner.circuit, 'optimize'):
            runner.circuit.optimize()
        runner.circuit.writetojson(json_path)
    except Exception as e:
        print(f"Failed to dump {json_path}: {e}")

def main():
    # Process ISCAS85
    iscas85_dir = os.path.join(_PROJECT_ROOT, 'tests', 'ISCAS85')
    if os.path.exists(iscas85_dir):
        for f in glob.glob(os.path.join(iscas85_dir, '*.v')):
            if not f.endswith('_base_tb.v'):
                json_path = f.replace('.v', '.json')
                process_iscas_file(f, json_path)

    # Process ISCAS89
    iscas89_dir = os.path.join(_PROJECT_ROOT, 'tests', 'ISCAS89')
    if os.path.exists(iscas89_dir):
        for f in glob.glob(os.path.join(iscas89_dir, '*.v')):
            if not f.endswith('_base_tb.v'):
                json_path = f.replace('.v', '.json')
                process_iscas_file(f, json_path)
                
    print("Done parsing and dumping ISCAS benchmarks.")

if __name__ == '__main__':
    main()

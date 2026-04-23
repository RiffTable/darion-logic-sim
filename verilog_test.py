import time
import re
import argparse
import os
import sys

# --- DYNAMIC PATH RESOLUTION ---
script_dir = os.path.dirname(os.path.abspath(__file__))

# Find the root directory that contains the 'reactor' or 'engine' folders
if os.path.exists(os.path.join(script_dir, 'reactor')) or os.path.exists(os.path.join(script_dir, 'engine')):
    root_dir = script_dir
else:
    root_dir = os.path.dirname(script_dir)

# Insert the Cython Reactor path into sys.path so Python can find Circuit.pyd/.so
# (Change 'reactor' to 'engine' if you ever want to test the pure Python backend)
sys.path.insert(0, os.path.join(root_dir, 'reactor'))

# Now the import will work flawlessly
from Circuit import Circuit
import Const

VERILOG_GATE_MAP = {
    'and': Const.AND_ID, 'nand': Const.NAND_ID, 'or': Const.OR_ID,
    'nor': Const.NOR_ID, 'xor': Const.XOR_ID, 'xnor': Const.XNOR_ID, 'not': Const.NOT_ID
}

def load_verilog(filepath: str):
    """Parses a .v file and returns the optimized Circuit and a node map."""
    circuit = Circuit()
    nodes = {}
    connections = []

    # Constants
    const_high = circuit.getcomponent(Const.VARIABLE_ID)
    circuit.toggle(const_high.location, Const.HIGH)
    const_low = circuit.getcomponent(Const.VARIABLE_ID)
    circuit.toggle(const_low.location, Const.LOW)

    with open(filepath, 'r') as f:
        content = f.read()

    # Clean comments
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'//.*', '', content)
    statements = [s.strip() for s in content.split(';') if s.strip()]

    # First Pass: Instantiate nodes
    for stmt in statements:
        if stmt.startswith('input '):
            for p in stmt.replace('input', '').strip().split(','):
                p = p.strip()
                nodes[p] = circuit.getcomponent(Const.VARIABLE_ID)
        elif stmt.startswith('wire ') or stmt.startswith('output ') or stmt.startswith('module ') or stmt.startswith('endmodule'):
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
                    gate = circuit.getcomponent(gate_id)
                    if gate_id != Const.NOT_ID:
                        circuit.setlimits(gate, len(in_wires))
                    nodes[out_wire] = gate
                    connections.append((out_wire, in_wires))

    # Second Pass: Connect nodes
    for target_id, source_ids in connections:
        target_gate = nodes.get(target_id)
        if not target_gate: continue
        for pin_index, source_id in enumerate(source_ids):
            if source_id in ["1'b0", "1'h0", "GND", "gnd"]:
                circuit.connect(target_gate, const_low.location, pin_index)
            elif source_id in ["1'b1", "1'h1", "VDD", "VCC", "vdd", "vcc"]:
                circuit.connect(target_gate, const_high.location, pin_index)
            else:
                source_gate = nodes.get(source_id)
                if source_gate:
                    circuit.connect(target_gate, source_gate.location, pin_index)
                else:
                    missing_var = circuit.getcomponent(Const.VARIABLE_ID)
                    nodes[source_id] = missing_var
                    circuit.connect(target_gate, missing_var.location, pin_index)

    # Topologically sort to guarantee correct sweep order
    circuit.optimize()
    return circuit, nodes

def run_cython_baseline(v_file: str, target_input: str, vectors: int = 50000):
    print(f"[INIT] Parsing {v_file}...")
    circuit, nodes = load_verilog(v_file)
    
    if target_input not in nodes:
        raise ValueError(f"Target input '{target_input}' not found in the netlist.")
        
    target_loc = nodes[target_input].location

    # Switch to COMPILE mode. In this mode, toggle() directly triggers sweep()
    circuit.simulate(Const.COMPILE)

    # In a sweep, every active gate is evaluated exactly once per cycle
    gate_count = circuit.infolist_size - circuit.hidden

    print("========================================")
    print(" CYTHON BASELINE (CYCLE-BASED SWEEP)    ")
    print("========================================")

    start_time = time.perf_counter()

    for i in range(vectors):
        # Automatically triggers self.sweep() exactly like top->eval()
        circuit.toggle(target_loc, i % 2)

    end_time = time.perf_counter()
    duration = end_time - start_time

    total_evals = float(gate_count) * vectors
    throughput = (total_evals / duration) / 1_000_000.0

    print(f"Duration   : {duration:.6f} seconds")
    print(f"Throughput : {throughput:.6f} ME/s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Direct Verilog Benchmark')
    parser.add_argument('file', type=str, help='Path to the .v file')
    parser.add_argument('--input', type=str, default='N1', help='Name of the input pin to toggle (Default: N1)')
    parser.add_argument('--vectors', type=int, default=50000, help='Number of cycles to run (Default: 50000)')
    
    args = parser.parse_args()
    run_cython_baseline(args.file, target_input=args.input, vectors=args.vectors)
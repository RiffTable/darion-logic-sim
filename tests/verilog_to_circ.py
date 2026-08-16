"""
verilog_to_circ.py
==================
Converts a Verilog gate-level netlist (.v) into:
  1. A Logisim-Evolution (.circ) file with proper Pin + Gate + Wire layout
  2. A test-vector file (.txt) suitable for:
       java -jar logisim-evolution.jar --test-vector <circuit_name> <vector_file> <circ_file>

The --test-vector mode runs a fixed number of input vectors against the named circuit
and exits immediately — giving us a deterministic, bounded benchmark.

Supports both combinational ISCAS85 circuits and sequential ISCAS89 circuits.
DFF instances are mapped to Logisim's built-in D Flip-Flop component (Memory lib).

Logisim D Flip-Flop port layout (east-facing, default orientation):
  - D   input : west  at (gx - 30, gy)
  - CK  input : south at (gx,      gy + 30)
  - Q   output: east  at (gx + 30, gy)
  - Q'  output: east  at (gx + 30, gy + 20)  [ignored for ISCAS89]

Test vector file format (tab-separated):
    N1  N2  N3  N6  N7       ← input pin labels (one column per input)
    0   0   0   0   0
    1   0   1   0   1
    ...

Usage:
    python verilog_to_circ.py c17.v -o c17.circ --vectors 1000
    # produces c17.circ  and  c17_vectors.txt
"""

import os
import re
import sys
import random
import argparse

# ---------------------------------------------------------------------------
# Grid layout constants (Logisim canvas units)
# ---------------------------------------------------------------------------
PIN_X       = 50
GATE_X      = 400
GATE_COL_W  = 220
GATE_ROW_H  = 80
MAX_ROWS    = 20
OUT_X       = 1400
ROW_STEP    = 40
BUS_Y_START = 100


# ---------------------------------------------------------------------------
# Verilog parser
# ---------------------------------------------------------------------------
class VerilogParser:
    SUPPORTED_GATES = {'and', 'nand', 'or', 'nor', 'xor', 'xnor', 'not', 'buf', 'dff'}
    LOGISIM_GATE = {
        'and':  'AND Gate',
        'nand': 'NAND Gate',
        'or':   'OR Gate',
        'nor':  'NOR Gate',
        'xor':  'XOR Gate',
        'xnor': 'XNOR Gate',
        'not':  'NOT Gate',
        'buf':  'Buffer',
        'dff':  'D Flip-Flop',  # Memory library (lib="4")
    }

    def __init__(self, v_filepath):
        self.inputs  = []
        self.outputs = []
        self.gates   = []  # list of (gate_type, out_wire, in_wires)
        self._parse(v_filepath)

    def _parse(self, path):
        with open(path, 'r') as f:
            content = f.read()
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'//.*', '', content)

        # Identify the main module body (skip inner dff module definitions)
        module_body = content
        for m in re.finditer(r'\bmodule\s+([a-zA-Z0-9_]+)(.*?)\bendmodule\b', content, flags=re.DOTALL):
            if m.group(1).lower() != 'dff':
                module_body = m.group(0)
                break

        for stmt in module_body.split(';'):
            stmt = re.sub(r'\s+', ' ', stmt.strip())
            if not stmt:
                continue
            if stmt.startswith('input '):
                for n in stmt[6:].split(','):
                    n = n.strip()
                    if n: self.inputs.append(n)
            elif stmt.startswith('output '):
                for n in stmt[7:].split(','):
                    n = n.strip()
                    if n: self.outputs.append(n)
            elif stmt.startswith(('wire ', 'module ', 'endmodule', 'reg ')):
                continue
            else:
                # Match: gate_type instance_name ( port_list )
                m = re.match(r'^([a-zA-Z_]\w*)\s+\w+\s*\((.+)\)$', stmt)
                if not m:
                    continue
                gt = m.group(1).lower()
                ports_str = m.group(2)

                if gt == 'dff':
                    # ISCAS89 DFF format: dff INST(CK, Q, D)  — positional
                    # or named: dff INST(.CK(ck_wire), .Q(q_wire), .D(d_wire))
                    if '.' in ports_str:
                        wires = {}
                        for pm in re.finditer(r'\.\s*([a-zA-Z0-9_]+)\s*\(\s*([a-zA-Z0-9_]+)\s*\)', ports_str):
                            wires[pm.group(1).upper()] = pm.group(2)
                        ck_wire = wires.get('CK', wires.get('CLK', wires.get('C')))
                        q_wire  = wires.get('Q')
                        d_wire  = wires.get('D')
                    else:
                        pts = [p.strip() for p in ports_str.split(',')]
                        # Positional: (CK, Q, D)
                        ck_wire = pts[0] if len(pts) > 0 else None
                        q_wire  = pts[1] if len(pts) > 1 else None
                        d_wire  = pts[2] if len(pts) > 2 else None

                    if q_wire:
                        # out_wire = Q (the DFF output)
                        # in_wires = [CK, D]  (clock first, then data)
                        in_wires = [w for w in (ck_wire, d_wire) if w is not None]
                        self.gates.append(('dff', q_wire, in_wires))

                elif gt in self.SUPPORTED_GATES:
                    ports = [p.strip() for p in ports_str.split(',')]
                    self.gates.append((gt, ports[0], ports[1:]))


# ---------------------------------------------------------------------------
# .circ builder — proper Pin + explicit Wire layout
# ---------------------------------------------------------------------------
class CircBuilder:
    def __init__(self, parser: VerilogParser):
        self.p = parser
        self._comps = []

    def _comp(self, lib, x, y, name, **attrs):
        parts = [f'    <comp lib="{lib}" loc="({x},{y})" name="{name}">']
        if attrs:
            for k, v in attrs.items():
                parts.append(f'      <a name="{k}" val="{v}"/>')
            parts.append('    </comp>')
        else:
            parts = [f'    <comp lib="{lib}" loc="({x},{y})" name="{name}"/>']
        self._comps.append('\n'.join(parts))

    def _tunnel(self, x, y, facing, label):
        self._comp('0', x, y, 'Tunnel', facing=facing, label=label)

    def _input_pins(self):
        for i, name in enumerate(self.p.inputs):
            py = BUS_Y_START + i * ROW_STEP
            self._comp('0', PIN_X, py, 'Pin', appearance='NewPins', label=name, output='false')
            self._tunnel(PIN_X + 20, py, 'west', name)

    def _gates(self):
        gate_positions = []
        for i in range(len(self.p.gates)):
            col = i // MAX_ROWS
            row = i % MAX_ROWS
            gx = GATE_X + col * GATE_COL_W
            gy = BUS_Y_START + row * GATE_ROW_H
            gate_positions.append((gx, gy))

        for idx, (gt, out_w, in_ws) in enumerate(self.p.gates):
            gx, gy = gate_positions[idx]
            ln = VerilogParser.LOGISIM_GATE[gt]
            n = len(in_ws)

            if gt == 'dff':
                self._comp('4', gx, gy, 'D Flip-Flop')
                # Q output (Logisim loc is the Q pin)
                self._tunnel(gx, gy, 'west', out_w)
                # CK input (bottom/south)
                if len(in_ws) > 0:
                    self._tunnel(gx - 20, gy + 20, 'north', in_ws[0])
                # D input (west)
                if len(in_ws) > 1:
                    self._tunnel(gx - 40, gy, 'east', in_ws[1])

            elif gt in ('not', 'buf'):
                self._comp('1', gx, gy, ln)
                self._tunnel(gx, gy, 'west', out_w)
                for i, iw in enumerate(in_ws):
                    self._tunnel(gx - 30, gy, 'east', iw)

            else:
                self._comp('1', gx, gy, ln, inputs=str(n))
                self._tunnel(gx, gy, 'west', out_w)
                for i, iw in enumerate(in_ws):
                    port_y = gy if n == 1 else gy - 10 * (n - 1) + 20 * i
                    self._tunnel(gx - 50, port_y, 'east', iw)

    def _output_pins(self):
        for i, name in enumerate(self.p.outputs):
            oy = BUS_Y_START + i * ROW_STEP
            self._comp('0', OUT_X, oy, 'Pin', appearance='NewPins', facing='west', label=f'OUT_{name}', output='true')
            self._tunnel(OUT_X - 20, oy, 'east', name)

    def build(self) -> str:
        self._input_pins()
        self._gates()
        self._output_pins()

        lines = [
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
            '<project source="3.8.0" version="1.0">',
            '  <lib desc="#Wiring" name="0"/>',
            '  <lib desc="#Gates" name="1"/>',
            '  <lib desc="#Plexers" name="2"/>',
            '  <lib desc="#Arithmetic" name="3"/>',
            '  <lib desc="#Memory" name="4"/>',
            '  <lib desc="#I/O" name="5"/>',
            '  <main name="main"/>',
            '  <circuit name="main">',
        ]
        lines += self._comps
        lines += ['  </circuit>', '</project>']
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Test vector generator
# ---------------------------------------------------------------------------
def generate_vectors(inputs: list, n_vectors: int, seed: int = 42,
                     clock_input: str = None) -> str:
    """
    Generate a tab-separated test vector file for Logisim --test mode.

    For sequential circuits, clock_input identifies the clock pin name.
    When clock_input is set, vectors are generated as clock-pairs:
      - Even rows: data settled, clock = 0
      - Odd rows : same data, clock = 1  (rising edge captures)

    Returns tab-separated rows with a header line.
    """
    rng = random.Random(seed)
    rows = ['\t'.join(inputs)]  # header

    if clock_input and clock_input in inputs:
        clk_idx = inputs.index(clock_input)
        count = 0
        while count < n_vectors:
            base = [rng.randint(0, 1) for _ in inputs]
            # setup: clock = 0
            setup = list(base)
            setup[clk_idx] = 0
            rows.append('\t'.join(str(v) for v in setup))
            count += 1
            if count >= n_vectors:
                break
            # trigger: clock = 1
            trigger = list(base)
            trigger[clk_idx] = 1
            rows.append('\t'.join(str(v) for v in trigger))
            count += 1
    else:
        for _ in range(n_vectors):
            row = '\t'.join(str(rng.randint(0, 1)) for _ in inputs)
            rows.append(row)

    return '\n'.join(rows) + '\n'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def convert_file(v_file: str, out_circ: str, max_ticks: int = 1000) -> int:
    """
    Convert Verilog netlist → Logisim .circ + test vector file.

    Parameters
    ----------
    v_file    : path to input .v file
    out_circ  : path for output .circ file
    max_ticks : number of test vectors to generate

    Returns
    -------
    Number of gates in the circuit.
    """
    parser = VerilogParser(v_file)
    builder = CircBuilder(parser)
    xml_str = builder.build()

    with open(out_circ, 'w', encoding='utf-8') as f:
        f.write(xml_str)

    # Detect if this is a sequential circuit — look for the clock pin
    clock_input = None
    for inp in parser.inputs:
        if inp.lower() in ('ck', 'clk', 'clock', 'g0'):
            clock_input = inp
            break

    # Write companion test vector file
    vec_file = os.path.splitext(out_circ)[0] + '_vectors.txt'
    vec_str = generate_vectors(parser.inputs, max_ticks, clock_input=clock_input)
    with open(vec_file, 'w', encoding='utf-8') as f:
        f.write(vec_str)

    return len(parser.gates)


def vector_file_path(circ_file: str) -> str:
    """Return the companion vector file path for a given .circ path."""
    return os.path.splitext(circ_file)[0] + '_vectors.txt'


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Convert Verilog .v netlist to Logisim-Evolution .circ + test vectors')
    ap.add_argument('input_v',   type=str, help='Path to input .v file')
    ap.add_argument('-o', '--output', type=str, default=None, help='Output .circ path')
    ap.add_argument('--vectors', type=int, default=1000, help='Number of test vectors to generate')
    args = ap.parse_args()

    out_file = args.output or os.path.splitext(args.input_v)[0] + '.circ'
    gate_cnt = convert_file(args.input_v, out_file, max_ticks=args.vectors)
    vec_file = vector_file_path(out_file)
    print(f'[+] Converted {args.input_v} -> {out_file} ({gate_cnt} gates)')
    print(f'[+] Test vectors -> {vec_file} ({args.vectors} rows)')
    print(f'[+] Run with: java -jar logisim-evolution.jar --test-vector main {vec_file} {out_file}')
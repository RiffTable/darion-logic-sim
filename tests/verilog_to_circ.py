"""
verilog_to_circ.py
==================
Converts a Verilog gate-level netlist (.v) into:
  1. A Logisim-Evolution (.circ) file with proper Pin + Gate + Wire layout
  2. A test-vector file (.txt) suitable for:
       java -jar logisim-evolution.jar --test-vector <circuit_name> <vector_file> <circ_file>

The --test-vector mode runs a fixed number of input vectors against the named circuit
and exits immediately — giving us a deterministic, bounded benchmark.

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
    SUPPORTED_GATES = {'and', 'nand', 'or', 'nor', 'xor', 'xnor', 'not', 'buf'}
    LOGISIM_GATE = {
        'and':  'AND Gate',
        'nand': 'NAND Gate',
        'or':   'OR Gate',
        'nor':  'NOR Gate',
        'xor':  'XOR Gate',
        'xnor': 'XNOR Gate',
        'not':  'NOT Gate',
        'buf':  'Buffer',
    }

    def __init__(self, v_filepath):
        self.inputs  = []
        self.outputs = []
        self.gates   = []
        self._parse(v_filepath)

    def _parse(self, path):
        with open(path, 'r') as f:
            content = f.read()
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'//.*', '', content)
        for stmt in content.split(';'):
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
                m = re.match(r'^([a-zA-Z_]\w*)\s+\w+\s*\((.+)\)$', stmt)
                if not m:
                    continue
                gt = m.group(1).lower()
                ports = [p.strip() for p in m.group(2).split(',')]
                if gt in self.SUPPORTED_GATES:
                    self.gates.append((gt, ports[0], ports[1:]))
                elif gt == 'dff':
                    if ports[0] not in self.inputs:
                        self.inputs.append(ports[0])


# ---------------------------------------------------------------------------
# .circ builder — proper Pin + explicit Wire layout
# ---------------------------------------------------------------------------
class CircBuilder:
    def __init__(self, parser: VerilogParser):
        self.p = parser
        self._comps = []
        self._wires = []
        self._src: dict[str, tuple[int,int]] = {}  # wire → output port (x,y)

    def _comp(self, lib, x, y, name, **attrs):
        parts = [f'    <comp lib="{lib}" loc="({x},{y})" name="{name}">']
        if attrs:
            for k, v in attrs.items():
                parts.append(f'      <a name="{k}" val="{v}"/>')
            parts.append('    </comp>')
        else:
            parts = [f'    <comp lib="{lib}" loc="({x},{y})" name="{name}"/>']
        self._comps.append('\n'.join(parts))

    def _wire(self, x1, y1, x2, y2):
        if (x1, y1) != (x2, y2):
            self._wires.append(f'    <wire from="({x1},{y1})" to="({x2},{y2})"/>')

    def _route(self, src, dst):
        """L-shaped route: horizontal then vertical."""
        sx, sy = src
        dx, dy = dst
        if sx != dx:
            self._wire(sx, sy, dx, sy)
        if sy != dy:
            self._wire(dx, sy, dx, dy)

    def _input_pins(self):
        for i, name in enumerate(self.p.inputs):
            py = BUS_Y_START + i * ROW_STEP
            self._comp('0', PIN_X, py, 'Pin',
                       appearance='NewPins', label=name, output='false')
            # Output port of an input pin faces east: (PIN_X + 30, py)
            self._src[name] = (PIN_X + 30, py)

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

            if gt in ('not', 'buf'):
                self._comp('1', gx, gy, ln)
            else:
                self._comp('1', gx, gy, ln, inputs=str(n))

            # Gate output port: east side at (gx + 30, gy)
            self._src[out_w] = (gx + 30, gy)

            # Input port offsets for N-input east-facing gate:
            # port i is at (gx - 30, gy - 10*(n-1) + 20*i)
            for i, iw in enumerate(in_ws):
                if n == 1:
                    port_y = gy
                else:
                    port_y = gy - 10 * (n - 1) + 20 * i
                port = (gx - 30, port_y)

                src = self._src.get(iw)
                if src is None:
                    # Undriven: tie to GND
                    cx, cy = gx - 120, port_y
                    self._comp('0', cx, cy, 'Constant', value='0x0')
                    src = (cx + 30, cy)
                    self._src[iw] = src

                self._route(src, port)

    def _output_pins(self):
        for i, name in enumerate(self.p.outputs):
            oy = BUS_Y_START + i * ROW_STEP
            self._comp('0', OUT_X, oy, 'Pin',
                       appearance='NewPins', facing='west',
                       label=f'OUT_{name}', output='true')
            src = self._src.get(name)
            if src:
                # Pin input port faces west: (OUT_X - 30, oy)
                self._route(src, (OUT_X - 30, oy))

    def build(self) -> str:
        self._input_pins()
        self._gates()
        self._output_pins()

        lines = [
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
            '<project source="2.13.8" version="1.0">',
            '  <lib desc="#Wiring" name="0"/>',
            '  <lib desc="#Gates" name="1"/>',
            '  <lib desc="#Plexers" name="2"/>',
            '  <lib desc="#Arithmetic" name="3"/>',
            '  <lib desc="#Memory" name="4"/>',
            '  <lib desc="#I/O" name="5"/>',
            '  <main name="main"/>',
            '  <options/>',
            '  <mappings/>',
            '  <toolbar/>',
            '  <circuit name="main">',
        ]
        lines += self._comps
        lines += self._wires
        lines += ['  </circuit>', '</project>']
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Test vector generator
# ---------------------------------------------------------------------------
def generate_vectors(inputs: list[str], n_vectors: int, seed: int = 42) -> str:
    """Generate a tab-separated test vector file for Logisim -test mode."""
    rng = random.Random(seed)
    rows = ['\t'.join(inputs)]  # header
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

    # Write companion test vector file
    vec_file = os.path.splitext(out_circ)[0] + '_vectors.txt'
    vec_str = generate_vectors(parser.inputs, max_ticks)
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
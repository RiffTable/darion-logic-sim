"""
verilog_to_circ.py
==================
Converts a Verilog gate-level netlist (.v) into:
  1. A Logisim-Evolution v4.0.0 (.circ) file with precise physical layout rules.
  2. A test-vector file (.txt) for Logisim --test-vector mode
"""

import os
import re
import random
import argparse

# ---------------------------------------------------------------------------
# Grid layout constants
# ---------------------------------------------------------------------------
PIN_X       = 100
GATE_X      = 600
GATE_COL_W  = 350
GATE_ROW_H  = 120
MAX_ROWS    = 25
OUT_X       = 1800
ROW_STEP    = 60
BUS_Y_START = 100

class IscasVerilogParser:
    SUPPORTED_GATES = {
        'and', 'nand', 'or', 'nor', 'xor', 'xnor', 'not', 'buf', 'dff',
    }

    LOGISIM_GATE = {
        'and':  'AND Gate', 'nand': 'NAND Gate',
        'or':   'OR Gate',  'nor':  'NOR Gate',
        'xor':  'XOR Gate', 'xnor': 'XNOR Gate',
        'not':  'NOT Gate', 'buf':  'Buffer',
        'dff':  'D Flip-Flop',   
    }

    _CLOCK_NAMES = {'ck', 'clk', 'clock', 'g0'}

    def __init__(self, v_filepath: str):
        self.module_name: str       = 'circuit'
        self.inputs:      list      = []
        self.outputs:     list      = []
        self.wires:       list      = []
        self.gates:       list      = []
        self.circuit_type: str      = 'combinational'
        self.clock_input:  str|None = None
        self._parse(v_filepath)

    def _parse(self, path: str) -> None:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'//[^\n]*', '', content)

        module_body = content
        for m in re.finditer(r'\bmodule\s+([a-zA-Z0-9_]+)(.*?)\bendmodule\b', content, flags=re.DOTALL):
            if m.group(1).lower() != 'dff':
                self.module_name = m.group(1)
                module_body      = m.group(0)
                break

        for stmt in module_body.split(';'):
            stmt = re.sub(r'\s+', ' ', stmt.strip())
            if not stmt:
                continue

            kw = stmt.split()[0].lower() if stmt.split() else ''
            if kw == 'input':
                self._parse_port_list(stmt, 'input', self.inputs)
            elif kw == 'output':
                self._parse_port_list(stmt, 'output', self.outputs)
            elif kw == 'wire':
                self._parse_port_list(stmt, 'wire', self.wires)
            elif kw in ('module', 'endmodule', 'reg'):
                continue
            else:
                self._parse_gate(stmt)

        if any(gt == 'dff' for gt, _, _ in self.gates):
            self.circuit_type = 'sequential'

        for inp in self.inputs:
            if inp.lower() in self._CLOCK_NAMES:
                self.clock_input = inp
                break

    @staticmethod
    def _parse_port_list(stmt: str, keyword: str, target: list) -> None:
        rest = stmt[len(keyword):].strip()
        rest = re.sub(r'\[[^\]]+\]', '', rest)
        for name in rest.split(','):
            name = name.strip()
            if name and name not in target:
                target.append(name)

    def _parse_gate(self, stmt: str) -> None:
        m = re.match(r'^([a-zA-Z_]\w*)\s+(?:\w+\s*)?\((.+)\)$', stmt, flags=re.DOTALL)
        if not m:
            return
        gt = m.group(1).lower()
        if gt not in self.SUPPORTED_GATES:
            return
        ports_str = m.group(2).strip()

        if gt == 'dff':
            self._parse_dff(ports_str)
        else:
            ports = [p.strip() for p in ports_str.split(',')]
            if not ports or not ports[0]:
                return
            out_wire = ports[0]
            in_wires = [p for p in ports[1:] if p]
            self.gates.append((gt, out_wire, in_wires))

    def _parse_dff(self, ports_str: str) -> None:
        if '.' in ports_str:
            wires: dict[str, str] = {}
            for pm in re.finditer(r'\.\s*([a-zA-Z0-9_]+)\s*\(\s*([a-zA-Z0-9_]+)\s*\)', ports_str):
                wires[pm.group(1).upper()] = pm.group(2)
            ck_wire = wires.get('CK', wires.get('CLK', wires.get('C')))
            q_wire  = wires.get('Q')
            d_wire  = wires.get('D')
        else:
            pts = [p.strip() for p in ports_str.split(',')]
            ck_wire = pts[0] if len(pts) > 0 else None
            q_wire  = pts[1] if len(pts) > 1 else None
            d_wire  = pts[2] if len(pts) > 2 else None

        if q_wire:
            in_wires = [w for w in (ck_wire, d_wire) if w is not None]
            self.gates.append(('dff', q_wire, in_wires))


class CircBuilder:
    def __init__(self, parser: IscasVerilogParser):
        self.p = parser
        self._comps: list[str] = []

    def _comp(self, lib: str, x: int, y: int, name: str, **attrs) -> None:
        if attrs:
            lines = [f'    <comp lib="{lib}" loc="({x},{y})" name="{name}">']
            for k, v in attrs.items():
                lines.append(f'      <a name="{k}" val="{v}"/>')
            lines.append('    </comp>')
            self._comps.append('\n'.join(lines))
        else:
            self._comps.append(f'    <comp lib="{lib}" loc="({x},{y})" name="{name}"/>')

    def _tunnel(self, x: int, y: int, facing: str, label: str) -> None:
        self._comp('0', x, y, 'Tunnel', facing=facing, label=label)

    def _wire(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self._comps.append(f'    <wire from="({x1},{y1})" to="({x2},{y2})"/>')

    @staticmethod
    def _get_gate_layout(gate_type: str, n_inputs: int) -> tuple[int, int, list[int]]:
        """
        Extracted directly from test.circ properties for Logisim-Evolution 4.0.0.
        Returns (gate_size, full_width, y_offsets).
        """
        if n_inputs <= 1:
            size, y_offsets = 30, [0]
        elif n_inputs <= 5:
            size = 50
            if n_inputs == 2: y_offsets = [-20, 20]
            elif n_inputs == 3: y_offsets = [-20, 0, 20]
            elif n_inputs == 4: y_offsets = [-20, -10, 10, 20]
            elif n_inputs == 5: y_offsets = [-20, -10, 0, 10, 20]
        elif n_inputs <= 7:
            size = 70
            if n_inputs == 6: y_offsets = [-30, -20, -10, 10, 20, 30]
            elif n_inputs == 7: y_offsets = [-30, -20, -10, 0, 10, 20, 30]
        else:
            size, y_offsets = 70, [-30 + 10 * i for i in range(n_inputs)]

        # Adjust physical reach for bubbles and curved backs verified in test.circ
        extra_width = 0
        if gate_type in ('nand', 'nor', 'xor'):
            extra_width = 10
        elif gate_type == 'xnor':
            extra_width = 20

        return size, size + extra_width, y_offsets

    def _input_pins(self) -> None:
        for i, name in enumerate(self.p.inputs):
            py = BUS_Y_START + i * ROW_STEP
            self._comp('0', PIN_X, py, 'Pin', appearance='NewPins', facing='east', output='false', label=name)
            t_x = PIN_X + 20
            self._tunnel(t_x, py, 'west', name)
            self._wire(PIN_X, py, t_x, py)

    def _gates(self) -> None:
        gate_positions = []
        for i in range(len(self.p.gates)):
            col = i // MAX_ROWS
            row = i % MAX_ROWS
            gx  = GATE_X + col * GATE_COL_W
            gy  = BUS_Y_START + row * GATE_ROW_H
            gate_positions.append((gx, gy))

        for idx, (gt, out_w, in_ws) in enumerate(self.p.gates):
            gx, gy = gate_positions[idx]
            n = len(in_ws)

            # Output tunnel configuration
            out_tunnel_x = gx + 20
            self._tunnel(out_tunnel_x, gy, 'west', out_w)
            self._wire(gx, gy, out_tunnel_x, gy)

            if gt == 'dff':
                # Anchor mathematical offset to ensure Output Q lands exactly on (gx, gy)
                dff_x = gx - 50
                dff_y = gy - 10
                self._comp('4', dff_x, dff_y, 'D Flip-Flop', appearance='logisim_evolution')
                
                ck_w = in_ws[0] if len(in_ws) > 0 else None
                d_w  = in_ws[1] if len(in_ws) > 1 else None

                if ck_w:
                    ck_px, ck_py = gx - 60, gy + 40
                    self._tunnel(ck_px - 40, ck_py, 'east', ck_w)
                    self._wire(ck_px - 40, ck_py, ck_px, ck_py)
                if d_w:
                    d_px, d_py = gx - 60, gy
                    self._tunnel(d_px - 40, d_py, 'east', d_w)
                    self._wire(d_px - 40, d_py, d_px, d_py)

            elif gt in ('not', 'buf'):
                ln = self.p.LOGISIM_GATE[gt]
                self._comp('1', gx, gy, ln)
                for iw in in_ws:
                    self._tunnel(gx - 70, gy, 'east', iw)
                    self._wire(gx - 70, gy, gx - 30, gy)

            else:
                ln = self.p.LOGISIM_GATE[gt]
                g_size, g_width, offsets = self._get_gate_layout(gt, n)
                attrs = {'inputs': str(max(n, 2))}
                if g_size != 50:
                    attrs['size'] = str(g_size)
                    
                self._comp('1', gx, gy, ln, **attrs)

                for i, iw in enumerate(in_ws):
                    port_y = gy + (offsets[i] if i < len(offsets) else 0)
                    port_x = gx - g_width
                    
                    # Tunnels staggered dynamically backward
                    dx = 40 + (i % 3) * 40
                    t_x = port_x - dx
                    self._tunnel(t_x, port_y, 'east', iw)
                    self._wire(t_x, port_y, port_x, port_y)

    def _output_pins(self) -> None:
        for i, name in enumerate(self.p.outputs):
            oy = BUS_Y_START + i * ROW_STEP
            self._comp('0', OUT_X, oy, 'Pin', appearance='NewPins', facing='west', output='true', label=name)
            t_x = OUT_X - 20
            self._tunnel(t_x, oy, 'east', name)
            self._wire(t_x, oy, OUT_X, oy)

    def build(self) -> str:
        self._input_pins()
        self._gates()
        self._output_pins()

        lines = [
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
            '<project source="4.0.0" version="1.0">',
            '  <lib desc="#Wiring" name="0"/>',
            '  <lib desc="#Gates" name="1"/>',
            '  <lib desc="#Memory" name="4"/>',
            '  <lib desc="#I/O" name="5"/>',
            '  <main name="main"/>',
            '  <circuit name="main">',
            '    <a name="appearance" val="logisim_evolution"/>',
            '    <a name="circuit" val="main"/>'
        ]
        lines += self._comps
        lines += ['  </circuit>', '</project>']
        return '\n'.join(lines)


def generate_vectors(inputs: list, n_vectors: int, seed: int = 42, clock_input: str = None) -> str:
    rng  = random.Random(seed)
    rows = ['\t'.join(inputs)]

    if clock_input and clock_input in inputs:
        clk_idx = inputs.index(clock_input)
        count   = 0
        while count < n_vectors:
            base = [rng.randint(0, 1) for _ in inputs]
            setup         = list(base); setup[clk_idx] = 0
            rows.append('\t'.join(str(v) for v in setup))
            count += 1
            if count >= n_vectors: break
            trigger       = list(base); trigger[clk_idx] = 1
            rows.append('\t'.join(str(v) for v in trigger))
            count += 1
    else:
        for _ in range(n_vectors):
            rows.append('\t'.join(str(rng.randint(0, 1)) for _ in inputs))

    return '\n'.join(rows) + '\n'


def convert_file(v_file: str, out_circ: str, max_ticks: int = 1000) -> int:
    parser  = IscasVerilogParser(v_file)
    builder = CircBuilder(parser)
    with open(out_circ, 'w', encoding='utf-8') as f:
        f.write(builder.build())

    vec_file = os.path.splitext(out_circ)[0] + '_vectors.txt'
    with open(vec_file, 'w', encoding='utf-8') as f:
        f.write(generate_vectors(parser.inputs, max_ticks, clock_input=parser.clock_input))
    return len(parser.gates)


def vector_file_path(circ_file: str) -> str:
    """Return the companion vector file path for a given .circ path."""
    return os.path.splitext(circ_file)[0] + '_vectors.txt'


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('input_v', type=str)
    ap.add_argument('-o', '--output', type=str, default=None)
    ap.add_argument('--vectors', type=int, default=1000)
    args = ap.parse_args()

    out_file = args.output or os.path.splitext(args.input_v)[0] + '.circ'
    gate_cnt = convert_file(args.input_v, out_file, max_ticks=args.vectors)
    vec_file = os.path.splitext(out_file)[0] + '_vectors.txt'

    print(f'[+] circ file   : {out_file} (Logisim-Evolution v4.0.0 mapping applied)')
    print(f'[+] vec file    : {vec_file} ({args.vectors} rows)')


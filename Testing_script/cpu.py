"""
DARION LOGIC SIM — 8-BIT CPU CORE BENCHMARK v3.0
==================================================
Gate-level 8-bit CPU with:
  ACC  - 8-bit accumulator         (master-slave DFF x 8)
  B    - 8-bit B register           (master-slave DFF x 8)
  ALU  - 8 operations               (ADD/SUB/AND/OR/XOR/PASS/NOT/ZERO, 3-bit op)
  SHL  - 8-bit barrel shift-left    (3-stage, shift by 1/2/4)
  SHR  - 8-bit barrel shift-right   (3-stage, shift by 1/2/4)
  MUL  - 8x8->8 lower-byte mult     (partial products, array method)
  RMUX - 4-way result mux           (ALU / SHL / SHR / MUL)
  ZF   - zero flag                  (NOR-8 reduction tree)
  CF   - carry flag                 (DFF on adder carry-out)
  SF   - sign flag                  (ACC[7] direct)
  OF   - overflow flag              (XNOR(A7,B7) AND XOR(A7,S7))
  PC   - 16-bit program counter     (DFF x16 + ripple +1 incrementer)

Usage: python cpu.py [--engine]
  --engine    Use Python engine backend (default: Reactor/Cython)
"""

import time
import sys
import os
import gc
import argparse
import platform
from datetime import datetime

# -- argument parsing (must come before any path manipulation) -----------------
parser = argparse.ArgumentParser(description='8-Bit CPU Core Benchmark')
parser.add_argument('--engine', action='store_true',
                    help='Use Python engine backend (default: Reactor/Cython)')
args, unknown = parser.parse_known_args()

# -- path resolution (PyInstaller / Nuitka / direct Python) -------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(script_dir, 'reactor')) or \
   os.path.exists(os.path.join(script_dir, 'engine')):
    root_dir = script_dir
elif getattr(sys, 'frozen', False):
    root_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
else:
    root_dir = os.path.dirname(script_dir)

sys.path.insert(0, os.path.join(root_dir, 'control'))

if args.engine:
    sys.path.insert(0, os.path.join(root_dir, 'engine'))
    backend_name = "Python Engine"
else:
    sys.path.insert(0, os.path.join(root_dir, 'reactor'))
    backend_name = "Reactor (Cython)"

# -- imports ------------------------------------------------------------------
try:
    from Circuit import Circuit
    import Const
    from Const import (AND_ID, OR_ID, NOR_ID, XOR_ID, NOT_ID,
                       VARIABLE_ID, HIGH, LOW, SIMULATE, DESIGN)
except ImportError as e:
    print(f"FATAL: Could not import backend modules: {e}")
    sys.exit(1)

LOG_FILE = "cpu_benchmark_results.txt"

# -- primitive gate helpers ---------------------------------------------------

def var(c, v=LOW):
    g = c.getcomponent(VARIABLE_ID); c.toggle(g, v); return g

def inv(c, a):
    g = c.getcomponent(NOT_ID);  c.connect(g, a, 0); return g

def and2(c, a, b):
    g = c.getcomponent(AND_ID);  c.connect(g, a, 0); c.connect(g, b, 1); return g

def or2(c, a, b):
    g = c.getcomponent(OR_ID);   c.connect(g, a, 0); c.connect(g, b, 1); return g

def nor2(c, a, b):
    g = c.getcomponent(NOR_ID);  c.connect(g, a, 0); c.connect(g, b, 1); return g

def xor2(c, a, b):
    g = c.getcomponent(XOR_ID);  c.connect(g, a, 0); c.connect(g, b, 1); return g

def mux2(c, a, b, sel):
    """2:1 mux: out = a if sel=LOW, b if sel=HIGH"""
    ns = inv(c, sel)
    return or2(c, and2(c, a, ns), and2(c, b, sel))

def full_adder(c, a, b, cin):
    ab   = xor2(c, a, b)
    s    = xor2(c, ab, cin)
    cout = or2(c, and2(c, a, b), and2(c, ab, cin))
    return s, cout

def ripple8(c, a8, b8, cin):
    sums = []; co = cin
    for ai, bi in zip(a8, b8):
        s, co = full_adder(c, ai, bi, co); sums.append(s)
    return sums, co

def d_latch(c, d, en):
    """Gated D-latch: transparent when en=HIGH. NOR-SR cross-coupled."""
    nd = inv(c, d)
    s  = and2(c, d,  en)
    r  = and2(c, nd, en)
    q  = c.getcomponent(NOR_ID)
    qb = c.getcomponent(NOR_ID)
    c.connect(q,  r, 0); c.connect(q,  qb, 1)
    c.connect(qb, s, 0); c.connect(qb, q,  1)
    return q

def dff(c, d, clk):
    """Positive-edge D flip-flop (master-slave pair)."""
    nclk = inv(c, clk)
    return d_latch(c, d_latch(c, d, nclk), clk)

def reg8(c, d8, clk):
    return [dff(c, d, clk) for d in d8]

def nor_tree(c, bits):
    """NOR-reduction tree: HIGH when all inputs are LOW."""
    layer = list(bits)
    while len(layer) > 1:
        nxt = []
        for i in range(0, len(layer), 2):
            nxt.append(nor2(c, layer[i], layer[i+1]) if i+1 < len(layer) else layer[i])
        layer = nxt
    return layer[0]

# -- ALU (3-bit opcode, 8 operations) -----------------------------------------
# op3 = [op0, op1, op2]  (LSB first)
# op2 op1 op0   Function
#  0   0   0    ADD  A+B        0   0   1    SUB  A-B
#  0   1   0    AND  A&B        0   1   1    OR   A|B
#  1   0   0    XOR  A^B        1   0   1    PASS A
#  1   1   0    NOT  ~A         1   1   1    ZERO 0x00

def alu8(c, a8, b8, op3, gnd):
    op0, op1, op2 = op3
    b_inv = [xor2(c, bi, op0) for bi in b8]
    cin_s = or2(c, gnd, op0)
    add8, co = ripple8(c, a8, b_inv, cin_s)
    and8 = [and2(c, ai, bi) for ai, bi in zip(a8, b8)]
    or8  = [or2 (c, ai, bi) for ai, bi in zip(a8, b8)]
    xor8 = [xor2(c, ai, bi) for ai, bi in zip(a8, b8)]
    ia   = [inv (c, ai)     for ai      in a8]
    z8   = [and2(c, a8[i], ia[i]) for i in range(8)]
    result = []
    for i in range(8):
        ml = mux2(c, and8[i], or8[i],  op0)
        mh = mux2(c, xor8[i], a8[i],   op0)
        me = mux2(c, ia[i],   z8[i],   op0)
        lo = mux2(c, add8[i], ml,      op1)
        hi = mux2(c, mh,      me,      op1)
        result.append(mux2(c, lo, hi, op2))
    return result, co

# -- Barrel shifter -----------------------------------------------------------

def barrel_shl8(c, data8, amt3, gnd):
    s0, s1, s2 = amt3
    st = data8
    st = [mux2(c, st[i], st[i-1] if i > 0 else gnd, s0) for i in range(8)]
    st = [mux2(c, st[i], st[i-2] if i > 1 else gnd, s1) for i in range(8)]
    st = [mux2(c, st[i], st[i-4] if i > 3 else gnd, s2) for i in range(8)]
    return st

def barrel_shr8(c, data8, amt3, gnd):
    s0, s1, s2 = amt3
    st = data8
    st = [mux2(c, st[i], st[i+1] if i < 7 else gnd, s0) for i in range(8)]
    st = [mux2(c, st[i], st[i+2] if i < 6 else gnd, s1) for i in range(8)]
    st = [mux2(c, st[i], st[i+4] if i < 4 else gnd, s2) for i in range(8)]
    return st

# -- 8x8 lower-byte multiplier ------------------------------------------------

def mul8_lo8(c, a8, b8, gnd):
    result = [and2(c, a8[j], b8[0]) for j in range(8)]
    for i in range(1, 8):
        pp    = [and2(c, a8[j], b8[i]) for j in range(8 - i)]
        carry = gnd
        for j in range(8 - i):
            result[i+j], carry = full_adder(c, result[i+j], pp[j], carry)
    return result

# -- 16-bit program counter ---------------------------------------------------

def pc16(c, clk, vcc):
    ph    = [var(c, LOW) for _ in range(16)]
    nxt   = []; carry = vcc
    for i in range(16):
        s = xor2(c, ph[i], carry); carry = and2(c, ph[i], carry); nxt.append(s)
    q = [dff(c, n, clk) for n in nxt]
    return q, ph

# -- CPU assembly -------------------------------------------------------------

def build_cpu(c):
    GND  = var(c, LOW)
    VCC  = var(c, HIGH)
    clk  = var(c, LOW)
    op3  = [var(c, LOW) for _ in range(3)]
    sh3  = [var(c, LOW) for _ in range(3)]
    sel2 = [var(c, LOW) for _ in range(2)]
    imm8 = [var(c, LOW) for _ in range(8)]

    acc_ph = [var(c, LOW) for _ in range(8)]

    alu_r, add_co = alu8(c, acc_ph, imm8, op3, GND)
    shl_r = barrel_shl8(c, acc_ph, sh3, GND)
    shr_r = barrel_shr8(c, acc_ph, sh3, GND)
    mul_r = mul8_lo8(c, acc_ph, imm8, GND)

    s0, s1 = sel2[0], sel2[1]
    result = []
    for i in range(8):
        lo = mux2(c, alu_r[i], shl_r[i], s0)
        hi = mux2(c, shr_r[i], mul_r[i], s0)
        result.append(mux2(c, lo, hi, s1))

    acc_q = reg8(c, result, clk)
    b_q   = reg8(c, imm8,   clk)

    cf  = dff(c, add_co, clk)
    zf  = nor_tree(c, acc_q)
    sf  = acc_q[7]
    of  = and2(c, inv(c, xor2(c, acc_ph[7], imm8[7])),
                  xor2(c, acc_ph[7], acc_q[7]))

    pc_q, pc_ph = pc16(c, clk, VCC)

    return (clk, GND, VCC,
            acc_q, acc_ph, b_q,
            zf, cf, sf, of,
            op3, sh3, sel2, imm8,
            pc_q, pc_ph)

# -- read helpers -------------------------------------------------------------

def rd8(bits):
    v = 0
    for i, b in enumerate(bits):
        if b.output == HIGH: v |= 1 << i
    return v

def rd16(bits):
    v = 0
    for i, b in enumerate(bits):
        if b.output == HIGH: v |= 1 << i
    return v

def flag_str(zf, cf, sf, of):
    return (("Z" if zf.output == HIGH else ".") +
            ("C" if cf.output == HIGH else ".") +
            ("S" if sf.output == HIGH else ".") +
            ("V" if of.output == HIGH else "."))

# -- benchmark phase ----------------------------------------------------------

def run_phase(c, clk, acc_q, acc_ph, zf, cf, sf, of,
              op3, sh3, sel2, imm8, pc_q, pc_ph,
              opcode, shift, sel, operand, cycles):
    for g, v in zip(op3,  opcode):  c.toggle(g, v)
    for g, v in zip(sh3,  shift):   c.toggle(g, v)
    for g, v in zip(sel2, sel):     c.toggle(g, v)
    for g, v in zip(imm8, operand): c.toggle(g, v)
    c.simulate(DESIGN); c.simulate(SIMULATE)

    ev0 = c.eval_count
    t0  = time.perf_counter()
    for _ in range(cycles):
        c.toggle(clk, HIGH)
        for ph, q in zip(acc_ph, acc_q): c.toggle(ph, q.output)
        for ph, q in zip(pc_ph,  pc_q):  c.toggle(ph, q.output)
        c.toggle(clk, LOW)
    elapsed = time.perf_counter() - t0
    evals   = c.eval_count - ev0

    return {
        'khz':   cycles / elapsed / 1e3,
        'mes':   evals  / elapsed / 1e6,
        'evals': evals,
        'acc':   rd8(acc_q),
        'pc':    rd16(pc_q),
        'flags': flag_str(zf, cf, sf, of),
        'time':  elapsed,
    }

# -- main benchmark -----------------------------------------------------------

def benchmark():
    W      = 110   # total line width including both border chars
    CYCLES = 100_000

    # opcode / operand constants
    ADD  = (LOW, LOW, LOW);   SUB  = (HIGH, LOW, LOW)
    AND  = (LOW, HIGH, LOW);  OR   = (HIGH, HIGH, LOW)
    XOR  = (LOW, LOW, HIGH);  PASS = (HIGH, LOW, HIGH)
    NOT_ = (LOW, HIGH, HIGH); ZERO = (HIGH, HIGH, HIGH)
    NO_SHIFT = (LOW, LOW, LOW)
    SH1 = (HIGH, LOW, LOW);  SH2 = (LOW, HIGH, LOW)
    SH4 = (LOW, LOW, HIGH);  SH7 = (HIGH, HIGH, HIGH)
    SEL_ALU = (LOW, LOW);  SEL_SHL = (HIGH, LOW)
    SEL_SHR = (LOW, HIGH); SEL_MUL = (HIGH, HIGH)
    B0  = (LOW,)*8
    B1  = (HIGH, LOW, LOW, LOW, LOW, LOW, LOW, LOW)
    B3  = (HIGH, HIGH, LOW, LOW, LOW, LOW, LOW, LOW)
    BFF = (HIGH,)*8
    BAA = (LOW, HIGH, LOW, HIGH, LOW, HIGH, LOW, HIGH)
    B55 = (HIGH, LOW, HIGH, LOW, HIGH, LOW, HIGH, LOW)

    # build
    gc.disable()
    c = Circuit(); c.activate_eval()
    t_build = time.perf_counter()
    (clk, GND, VCC, acc_q, acc_ph, b_q,
     zf, cf, sf, of, op3, sh3, sel2, imm8,
     pc_q, pc_ph) = build_cpu(c)
    build_ms = (time.perf_counter() - t_build) * 1000
    gates    = c.counter

    lines = []

    # -------------------------------------------------------------------------
    # Formatting helpers
    # All helpers guarantee exactly W characters (including both border chars).
    # -------------------------------------------------------------------------

    def out(s=""):
        print(s); lines.append(s)

    def box(content):
        """Pad/trim content to W-2 chars, wrap in border chars."""
        inner = content[:W-2]
        return "║" + f"{inner:<{W-2}}" + "║"

    def rule(lc="╠", mc="═", rc="╣"):
        out(lc + mc*(W-2) + rc)

    def hdr_line(text):
        # total: 1(║) + 2( ) + 2(─) + 1( ) + len(text) + 1( ) + fill(─) + 2( ) + 1(║) = W
        # fill = W - 10 - len(text)
        fill = max(0, W - 10 - len(text))
        out("║  ── " + text + " " + "─" * fill + "  ║")

    def divider():
        # ║ + 2 spaces + (W-4) dashes + ║ = W
        out("║  " + "─"*(W-4) + "║")

    # Table data columns — widths verified to sum exactly to W:
    # 1(║) + 2( ) + 34(label) + 3( | ) + 8(khz) + 3( | ) + 8(mes)
    # + 3( | ) + 16(evals) + 3( | ) + 5(acc) + 3( | ) + 4(flags)
    # + 3( | ) + 6(pc) + 2( ║) = 1+2+34+3+8+3+8+3+16+3+5+3+4+3+6+2 = 104  NOPE
    #
    # Adjusted to hit exactly W=110:
    # label=36, khz=8, mes=8, evals=16, acc=5, flags=4, pc=6
    # 1+2+36+3+8+3+8+3+16+3+5+3+4+3+6+2 = 106  NOPE
    #
    # label=36, khz=9, mes=9, evals=16, acc=5, flags=4, pc=6  (6 seps of 3 = 18)
    # 1+2+36 + 18 + 9+9+16+5+4+6 + 2 = 1+2+36+18+49+2 = 108  NOPE
    #
    # Easiest correct approach: build the row content then use box() to clamp.

    def tbl_header():
        s = (f"  {'Phase':<36}"
             f"  {'kHz':>8}  {'ME/s':>8}"
             f"  {'Eval Count':>16}  {'ACC':>5}  {'Flg':>4}  {'PC':>6}")
        out(box(s))

    def tbl_row(label, r):
        acc_s = f"{r['acc']:02X}h"
        pc_s  = f"{r['pc']:04X}h"
        s = (f"  {label:<36}"
             f"  {r['khz']:>8.1f}  {r['mes']:>8.2f}"
             f"  {r['evals']:>16,}  {acc_s:>5}  {r['flags']:>4}  {pc_s:>6}")
        out(box(s))

    # -------------------------------------------------------------------------
    # Header block
    # -------------------------------------------------------------------------
    rule("╔", "═", "╗")
    out(box(f"{'  DARION LOGIC SIM  ─  8-BIT CPU CORE BENCHMARK  v3.0':^{W-2}}"))
    rule()
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    out(box(f"  {ts}  |  Backend: {backend_name}  |  Gates: {gates:,}  |  Build: {build_ms:.1f} ms"))
    out(box(f"  System: {platform.system()} {platform.release()}   Python {platform.python_version()}"))
    rule()

    # Component breakdown
    comps = [
        ("ACC  register (8x master-slave DFF)",           "~88",  "NOR-SR latches, edge-triggered"),
        ("B    register (8x master-slave DFF)",            "~88",  "Secondary operand register"),
        ("ALU  8-op (ADD/SUB/AND/OR/XOR/PASS/NOT/ZERO)",  "~250", "3-level mux tree, parallel execution"),
        ("SHL  8-bit barrel shift-left   (3-stage)",       "~96",  "Cascaded 2:1 mux, zero-fill LSBs"),
        ("SHR  8-bit barrel shift-right  (3-stage)",       "~96",  "Reverse cascade, zero-fill MSBs"),
        ("MUL  8x8->8 lower-byte multiplier",              "~177", "Partial products + ripple adder"),
        ("RMUX 4-way result mux + flags (ZF/CF/SF/OF)",    "~60",  "NOR-8 tree, DFF flags, OF detect"),
        ("PC   16-bit program counter (+1 ripple)",        "~210", "DFF x16 + carry chain"),
    ]
    out(box(f"  {'Component':<44}  {'Gates':<5}  Description"))
    divider()
    for name, g, desc in comps:
        out(box(f"  {name:<44}  {g:<5}  {desc}"))
    rule()

    # Column header
    tbl_header()
    rule()

    results = {}

    def phase(label, key, opcode, shift, sel, operand):
        r = run_phase(c, clk, acc_q, acc_ph, zf, cf, sf, of,
                      op3, sh3, sel2, imm8, pc_q, pc_ph,
                      opcode, shift, sel, operand, CYCLES)
        tbl_row(label, r); results[key] = r; return r

    # -------------------------------------------------------------------------
    # ALU phases
    # -------------------------------------------------------------------------
    hdr_line("ALU  -- accumulator feedback")
    phase("ADD  ACC += 0x01  (count up)",           "add_01", ADD,  NO_SHIFT, SEL_ALU, B1  )
    phase("ADD  ACC += 0xFF  (carry-chain stress)",  "add_ff", ADD,  NO_SHIFT, SEL_ALU, BFF )
    phase("SUB  ACC -= 0x01  (count down)",          "sub_01", SUB,  NO_SHIFT, SEL_ALU, B1  )
    phase("AND  ACC &= 0xFF  (identity)",             "and_ff", AND,  NO_SHIFT, SEL_ALU, BFF )
    phase("AND  ACC &= 0x00  (force zero)",           "and_00", AND,  NO_SHIFT, SEL_ALU, B0  )
    phase("OR   ACC |= 0x55",                         "or_55",  OR,   NO_SHIFT, SEL_ALU, B55 )
    phase("XOR  ACC ^= 0xAA  (toggle pattern)",       "xor_aa", XOR,  NO_SHIFT, SEL_ALU, BAA )
    phase("XOR  ACC ^= 0xFF  (bitwise NOT each clk)", "xor_ff", XOR,  NO_SHIFT, SEL_ALU, BFF )
    phase("NOT  ACC = ~ACC",                           "not_",  NOT_, NO_SHIFT, SEL_ALU, B0  )
    phase("ZERO ACC = 0x00  (ZF trigger)",             "zero",  ZERO, NO_SHIFT, SEL_ALU, B0  )
    phase("PASS ACC unchanged  (register hold)",       "pass_", PASS, NO_SHIFT, SEL_ALU, B0  )

    # -------------------------------------------------------------------------
    # SHL phases
    # -------------------------------------------------------------------------
    rule(); hdr_line("SHL  -- barrel shift-left")
    run_phase(c,clk,acc_q,acc_ph,zf,cf,sf,of,op3,sh3,sel2,imm8,pc_q,pc_ph,
              OR,NO_SHIFT,SEL_ALU,B55,1)
    phase("SHL  ACC <<= 1",                        "shl_1", PASS, SH1, SEL_SHL, B0)
    phase("SHL  ACC <<= 2",                        "shl_2", PASS, SH2, SEL_SHL, B0)
    phase("SHL  ACC <<= 4",                        "shl_4", PASS, SH4, SEL_SHL, B0)
    phase("SHL  ACC <<= 7  (one bit survives)",    "shl_7", PASS, SH7, SEL_SHL, B0)

    # -------------------------------------------------------------------------
    # SHR phases
    # -------------------------------------------------------------------------
    rule(); hdr_line("SHR  -- barrel shift-right")
    run_phase(c,clk,acc_q,acc_ph,zf,cf,sf,of,op3,sh3,sel2,imm8,pc_q,pc_ph,
              OR,NO_SHIFT,SEL_ALU,BFF,1)
    phase("SHR  ACC >>= 1",                        "shr_1", PASS, SH1, SEL_SHR, B0)
    phase("SHR  ACC >>= 4",                        "shr_4", PASS, SH4, SEL_SHR, B0)

    # -------------------------------------------------------------------------
    # MUL phases
    # -------------------------------------------------------------------------
    rule(); hdr_line("MUL  -- 8x8 lower-byte multiplier")
    run_phase(c,clk,acc_q,acc_ph,zf,cf,sf,of,op3,sh3,sel2,imm8,pc_q,pc_ph,
              ADD,NO_SHIFT,SEL_ALU,B3,1)
    phase("MUL  ACC *= 0x03",                      "mul_03", PASS, NO_SHIFT, SEL_MUL, B3  )
    phase("MUL  ACC *= 0xAA",                      "mul_aa", PASS, NO_SHIFT, SEL_MUL, BAA )
    phase("MUL  ACC *= 0xFF  (max operand)",        "mul_ff", PASS, NO_SHIFT, SEL_MUL, BFF )

    # -------------------------------------------------------------------------
    # PC phase
    # -------------------------------------------------------------------------
    rule(); hdr_line("PC   -- 16-bit program counter")
    phase("PC   += 1  (instruction fetch rate)",   "pc_inc", PASS, NO_SHIFT, SEL_ALU, B0)

    rule("╚", "═", "╝")

    # -------------------------------------------------------------------------
    # Summary block
    # -------------------------------------------------------------------------
    total_evals = sum(r['evals'] for r in results.values())
    total_time  = sum(r['time']  for r in results.values())
    avg_mes     = (total_evals / total_time / 1e6) if total_time > 0 else 0
    peak_mes    = max(r['mes']  for r in results.values())
    peak_phase  = max(results, key=lambda k: results[k]['mes'])
    peak_khz    = max(r['khz']  for r in results.values())

    out("")
    rule("╔", "═", "╗")
    out(box(f"{'  BENCHMARK SUMMARY':^{W-2}}"))
    rule()

    def srow(label, val):
        out(box(f"  {label:<40}  {val}"))

    srow("Physical gates in CPU:",            f"{gates:,}")
    srow("Total eval cycles (all phases):",   f"{total_evals:,}")
    srow("Total benchmark time:",             f"{total_time:.3f} s")
    srow("Average throughput:",               f"{avg_mes:.2f} ME/s")
    srow("Peak throughput:",                  f"{peak_mes:.2f} ME/s  [{peak_phase}]")
    srow("Peak simulated clock speed:",       f"{peak_khz:.1f} kHz")
    srow("Flags key:",                        "Z=zero  C=carry  S=sign  V=overflow")
    rule()

    out(box(f"  {'Unit':<8}  {'Best ME/s':>10}  {'Avg kHz':>9}  {'Total Evals':>16}  Note"))
    divider()

    def unit_row(label, keys, note=""):
        rs = [results[k] for k in keys if k in results]
        if not rs: return
        bmes = max(r['mes']   for r in rs)
        akhz = sum(r['khz']   for r in rs) / len(rs)
        tevs = sum(r['evals'] for r in rs)
        out(box(f"  {label:<8}  {bmes:>10.2f}  {akhz:>9.1f}  {tevs:>16,}  {note}"))

    unit_row("ALU",  ["add_01","add_ff","sub_01","and_ff","and_00",
                       "or_55","xor_aa","xor_ff","not_","zero","pass_"],
             "All 8 ops via 3-bit opcode mux tree")
    unit_row("SHL",  ["shl_1","shl_2","shl_4","shl_7"],
             "3-stage barrel shift left")
    unit_row("SHR",  ["shr_1","shr_4"],
             "3-stage barrel shift right")
    unit_row("MUL",  ["mul_03","mul_aa","mul_ff"],
             "8x8 partial-product, lower-byte result")
    unit_row("PC",   ["pc_inc"],
             "16-bit ripple +1 counter")

    rule("╚", "═", "╝")
    out(f"\n  Log saved to: {LOG_FILE}")

    # -- write log file -------------------------------------------------------
    with open(LOG_FILE, 'a', encoding='utf-8') as lf:
        lf.write(f"\n{'='*70}\n")
        lf.write(f"RUN  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lf.write(f"ARGS : backend={backend_name}\n")
        lf.write(f"{'='*70}\n")
        for line in lines:
            lf.write(line + "\n")

    gc.enable()
    c.clearcircuit()


if __name__ == "__main__":
    benchmark()

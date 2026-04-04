"""
DARION LOGIC SIM — IC & CIRCUIT BENCHMARK + INTEGRITY SUITE
=============================================================
Tests both Engine and Reactor backends for:
  1. Complex topology correctness  (integrity)
  2. IC creation, save, load, simulation  (benchmark)
  3. Full circuit creation, save, load, simulation  (benchmark)
  4. Nested IC chains  (stress)
  5. Error propagation  (correctness)

Run:
  python Testing_script/ic_circuit_benchmark.py
"""

import sys, os, time, gc, tempfile, platform, statistics
import asyncio  # <--- Added


# ── UTF-8 console on Windows ──────────────────────────────────────
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
try:
    import ctypes
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
except Exception:
    pass

# ── PATH SETUP ────────────────────────────────────────────────────
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir   = os.path.dirname(script_dir)
sys.path.append(os.path.join(root_dir, 'control'))

# ══════════════════════════════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════════════════════════════

def stop_runner(c):
    """Safely stop the async oscillation breaker if it is running."""
    if getattr(c, 'runner', None) is not None and not c.runner.done():
        c.runner.cancel()


PASS = "OK"
FAIL = "FAIL"
_integrity_results = []   # (label, backend, passed)

def _check(cond, label, backend_label):
    status = PASS if cond else FAIL
    _integrity_results.append((label, backend_label, cond))
    tag = f"[{status}]"
    colour_tag = tag if cond else f"*** {tag} ***"
    print(f"    {'✓' if cond else '✗'} {label:<58} {colour_tag}")
    return cond

def format_time(ms):
    if ms >= 1000:   return f"{ms/1000:.3f} s"
    if ms >= 0.1:    return f"{ms:.2f} ms"
    if ms >= 0.001:  return f"{ms*1000:.1f} µs"
    return              f"{ms*1_000_000:.0f} ns"

def timed(func, warmup=0):
    for _ in range(warmup):
        func()
    was = gc.isenabled(); gc.disable()
    t0  = time.perf_counter_ns()
    res = func()
    t1  = time.perf_counter_ns()
    if was: gc.enable()
    return (t1 - t0) / 1_000_000, res

def divider(char='═', width=90): return char * width
def header(title, char='═', width=90):
    pad = (width - len(title) - 2) // 2
    return f"{char*pad} {title} {char*(width - pad - len(title) - 2)}"

# ══════════════════════════════════════════════════════════════════
#  BACKEND LOADER
# ══════════════════════════════════════════════════════════════════

def load_backend(use_reactor):
    for m in ['Circuit', 'IC', 'Const', 'Gates', 'Store']:
        sys.modules.pop(m, None)
    ep = os.path.join(root_dir, 'engine')
    rp = os.path.join(root_dir, 'reactor')
    sys.path = [p for p in sys.path if p not in (ep, rp)]
    sys.path.insert(0, rp if use_reactor else ep)

    from Circuit import Circuit
    from IC import IC
    from Const import (
        IC_ID, INPUT_PIN_ID, OUTPUT_PIN_ID,
        NOT_ID, AND_ID, NAND_ID, OR_ID, NOR_ID, XOR_ID, XNOR_ID,
        VARIABLE_ID, PROBE_ID,
        HIGH, LOW, UNKNOWN, ERROR, SIMULATE, set_MODE,
    )
    return dict(
        Circuit=Circuit, IC=IC,
        IC_ID=IC_ID, INPUT_PIN_ID=INPUT_PIN_ID, OUTPUT_PIN_ID=OUTPUT_PIN_ID,
        NOT_ID=NOT_ID, AND_ID=AND_ID, NAND_ID=NAND_ID,
        OR_ID=OR_ID, NOR_ID=NOR_ID, XOR_ID=XOR_ID, XNOR_ID=XNOR_ID,
        VARIABLE_ID=VARIABLE_ID, PROBE_ID=PROBE_ID,
        HIGH=HIGH, LOW=LOW, UNKNOWN=UNKNOWN, ERROR=ERROR,
        SIMULATE=SIMULATE, set_MODE=set_MODE,
    )

def new_sim(backend):
    c = backend['Circuit']()
    c.simulate(backend['SIMULATE'])
    return c

# ══════════════════════════════════════════════════════════════════
#  COMPLEX TOPOLOGY BUILDERS
# ══════════════════════════════════════════════════════════════════

def build_not_chain(c, backend, length, src):
    """Chain of NOT gates.  Returns final gate."""
    prev = src
    for _ in range(length):
        g = c.getcomponent(backend['NOT_ID'])
        c.connect(g, prev, 0)
        prev = g
    return prev

def build_half_adder(c, backend, a, b):
    """1-bit half adder: returns (sum_gate, carry_gate)."""
    xor_g = c.getcomponent(backend['XOR_ID'])
    and_g = c.getcomponent(backend['AND_ID'])
    c.connect(xor_g, a, 0)
    c.connect(xor_g, b, 1)
    c.connect(and_g, a, 0)
    c.connect(and_g, b, 1)
    return xor_g, and_g   # sum, carry

def build_full_adder(c, backend, a, b, cin):
    """1-bit full adder: returns (sum_gate, cout_gate)."""
    xor1 = c.getcomponent(backend['XOR_ID'])
    xor2 = c.getcomponent(backend['XOR_ID'])
    and1 = c.getcomponent(backend['AND_ID'])
    and2 = c.getcomponent(backend['AND_ID'])
    or1  = c.getcomponent(backend['OR_ID'])
    c.connect(xor1, a, 0);  c.connect(xor1, b, 1)
    c.connect(xor2, xor1, 0); c.connect(xor2, cin, 1)
    c.connect(and1, a, 0);  c.connect(and1, b, 1)
    c.connect(and2, xor1, 0); c.connect(and2, cin, 1)
    c.connect(or1, and1, 0); c.connect(or1, and2, 1)
    return xor2, or1   # sum, cout

def build_ripple_adder(c, backend, bits):
    """N-bit ripple-carry adder.  Returns (a_vars, b_vars, sum_gates, cout)."""
    a_vars = [c.getcomponent(backend['VARIABLE_ID']) for _ in range(bits)]
    b_vars = [c.getcomponent(backend['VARIABLE_ID']) for _ in range(bits)]
    # bit-0 uses half adder
    s0, carry = build_half_adder(c, backend, a_vars[0], b_vars[0])
    sums = [s0]
    for i in range(1, bits):
        s, carry = build_full_adder(c, backend, a_vars[i], b_vars[i], carry)
        sums.append(s)
    return a_vars, b_vars, sums, carry

def build_binary_tree_and(c, backend, n_inputs):
    """Binary AND-reduction tree. Returns (inputs, output_gate)."""
    leaves = [c.getcomponent(backend['VARIABLE_ID']) for _ in range(n_inputs)]
    layer = list(leaves)
    while len(layer) > 1:
        next_layer = []
        for i in range(0, len(layer) - 1, 2):
            g = c.getcomponent(backend['AND_ID'])
            c.connect(g, layer[i], 0)
            c.connect(g, layer[i+1], 1)
            next_layer.append(g)
        if len(layer) % 2 == 1:
            next_layer.append(layer[-1])
        layer = next_layer
    return leaves, layer[0]

def build_binary_tree_or(c, backend, n_inputs):
    """Binary OR-reduction tree. Returns (inputs, output_gate)."""
    leaves = [c.getcomponent(backend['VARIABLE_ID']) for _ in range(n_inputs)]
    layer = list(leaves)
    while len(layer) > 1:
        next_layer = []
        for i in range(0, len(layer) - 1, 2):
            g = c.getcomponent(backend['OR_ID'])
            c.connect(g, layer[i], 0)
            c.connect(g, layer[i+1], 1)
            next_layer.append(g)
        if len(layer) % 2 == 1:
            next_layer.append(layer[-1])
        layer = next_layer
    return leaves, layer[0]

def build_crossbar(c, backend, rows, cols):
    """
    rows×cols NAND crossbar — every row variable drives every gate
    in its column to stress fanout and book-keeping.
    Returns (row_vars, col_outputs).
    """
    row_vars = [c.getcomponent(backend['VARIABLE_ID']) for _ in range(rows)]
    col_outputs = []
    for col in range(cols):
        g = c.getcomponent(backend['NAND_ID'])
        c.setlimits(g, rows)
        for row, v in enumerate(row_vars):
            c.connect(g, v, row)
        col_outputs.append(g)
    return row_vars, col_outputs

def build_layered_and_pyramid(c, backend, width, depth):
    """
    Generates a depth-layer wide AND pyramid that converges to a single gate.
    Returns (inputs, apex_gate).
    """
    inputs = [c.getcomponent(backend['VARIABLE_ID']) for _ in range(width)]
    layer  = list(inputs)
    for _ in range(depth):
        # Each gate in next layer gets two consecutive gates from current layer
        next_layer = []
        for i in range(0, len(layer) - 1, 2):
            g = c.getcomponent(backend['AND_ID'])
            c.connect(g, layer[i], 0)
            c.connect(g, layer[i+1], 1)
            next_layer.append(g)
        if len(layer) % 2 == 1:
            next_layer.append(layer[-1])
        layer = next_layer
        if len(layer) == 1:
            break
    return inputs, layer[0]

def build_xor_parity(c, backend, n):
    """XOR chain for n-input parity.  Returns (vars, final_xor)."""
    vs = [c.getcomponent(backend['VARIABLE_ID']) for _ in range(n)]
    prev = vs[0]
    for i in range(1, n):
        g = c.getcomponent(backend['XOR_ID'])
        c.connect(g, prev, 0)
        c.connect(g, vs[i], 1)
        prev = g
    return vs, prev


# ══════════════════════════════════════════════════════════════════
#  INTEGRITY TEST SECTION
# ══════════════════════════════════════════════════════════════════

def run_integrity(backend, label):
    C   = backend['Circuit']
    HIGH, LOW, UNKNOWN, ERROR = (
        backend['HIGH'], backend['LOW'],
        backend['UNKNOWN'], backend['ERROR'])
    SIM = backend['SIMULATE']

    print(f"\n  {'─'*86}")
    print(f"  INTEGRITY TESTS — {label}")
    print(f"  {'─'*86}")

    passed = failed = 0

    def chk(cond, name):
        nonlocal passed, failed
        ok = _check(cond, name, label)
        if ok: passed += 1
        else:  failed += 1

    # ── 1. NOT chain (even/odd inversion) ────────────────────────
    c = new_sim(backend)
    v = c.getcomponent(backend['VARIABLE_ID'])
    c.toggle(v, HIGH)
    end4  = build_not_chain(c, backend, 4, v)
    end5  = build_not_chain(c, backend, 5, v)
    chk(end4.output == HIGH, "NOT chain ×4: HIGH→HIGH")
    chk(end5.output == LOW,  "NOT chain ×5: HIGH→LOW")
    c.toggle(v, LOW)
    chk(end4.output == LOW,  "NOT chain ×4 after toggle: LOW→LOW")

    # ── 2. Half adder correctness ─────────────────────────────────
    c = new_sim(backend)
    va = c.getcomponent(backend['VARIABLE_ID'])
    vb = c.getcomponent(backend['VARIABLE_ID'])
    s, carry = build_half_adder(c, backend, va, vb)
    for (a_val, b_val, exp_s, exp_c) in [
            (LOW, LOW, LOW, LOW), (HIGH, LOW, HIGH, LOW),
            (LOW, HIGH, HIGH, LOW), (HIGH, HIGH, LOW, HIGH)]:
        c.toggle(va, a_val); c.toggle(vb, b_val)
        chk(s.output == exp_s and carry.output == exp_c,
            f"Half adder {a_val}+{b_val} → sum={exp_s} carry={exp_c}")

    # ── 3. 8-bit ripple adder 170+85=255 (all bits set) ──────────
    c = new_sim(backend)
    a_vars, b_vars, sums, cout = build_ripple_adder(c, backend, 8)
    # 170 = 0b10101010, 85 = 0b01010101 → 255 = 0b11111111
    val_a, val_b = 170, 85
    for i in range(8):
        c.toggle(a_vars[i], (val_a >> i) & 1)
        c.toggle(b_vars[i], (val_b >> i) & 1)
    result = sum(sums[i].output << i for i in range(8)) + (cout.output << 8)
    chk(result == 255, f"8-bit ripple adder: 170+85 = {result} (expect 255)")

    # carry into 9th bit must be LOW (255 fits in 8 bits)
    chk(cout.output == LOW, "8-bit adder: no carry out for 170+85")

    # 200+100=300=0x12C (overflow into carry)
    c = new_sim(backend)
    a_vars, b_vars, sums, cout = build_ripple_adder(c, backend, 8)
    for i in range(8):
        c.toggle(a_vars[i], (200 >> i) & 1)
        c.toggle(b_vars[i], (100 >> i) & 1)
    low8 = sum(sums[i].output << i for i in range(8))
    chk(cout.output == HIGH, f"8-bit adder: carry out for 200+100 (300>255)")
    chk(low8 == 44, f"8-bit adder: 200+100 low-8 bits = {low8} (expect 44)")

    # ── 4. XOR parity ─────────────────────────────────────────────
    c = new_sim(backend)
    vs, parity = build_xor_parity(c, backend, 16)
    for v in vs: c.toggle(v, HIGH)   # 16 HIGH → even parity → LOW
    chk(parity.output == LOW, "16-input XOR parity: all-HIGH → even → LOW")
    c.toggle(vs[0], LOW)              # flip one → odd parity → HIGH
    chk(parity.output == HIGH, "16-input XOR parity: one LOW → odd → HIGH")

    # ── 5. Binary AND tree ─────────────────────────────────────────
    c = new_sim(backend)
    leaves, apex = build_binary_tree_and(c, backend, 32)
    for v in leaves: c.toggle(v, HIGH)
    chk(apex.output == HIGH, "AND tree 32-in: all HIGH → HIGH")
    c.toggle(leaves[17], LOW)
    chk(apex.output == LOW,  "AND tree 32-in: one LOW → LOW")

    # ── 6. Binary OR tree ─────────────────────────────────────────
    c = new_sim(backend)
    leaves, apex = build_binary_tree_or(c, backend, 32)
    for v in leaves: c.toggle(v, LOW)
    chk(apex.output == LOW,  "OR tree 32-in: all LOW → LOW")
    c.toggle(leaves[5], HIGH)
    chk(apex.output == HIGH, "OR tree 32-in: one HIGH → HIGH")

    # ── 7. Layered AND pyramid 64-wide × 6 deep ───────────────────
    c = new_sim(backend)
    inputs, apex = build_layered_and_pyramid(c, backend, 64, 6)
    for v in inputs: c.toggle(v, HIGH)
    chk(apex.output == HIGH, "AND pyramid 64×6: all-HIGH → HIGH")
    c.toggle(inputs[32], LOW)
    chk(apex.output == LOW,  "AND pyramid 64×6: one LOW → LOW")

    # ── 8. Crossbar ───────────────────────────────────────────────
    c = new_sim(backend)
    rows_v, col_out = build_crossbar(c, backend, 8, 4)
    for v in rows_v: c.toggle(v, HIGH)
    # All inputs HIGH → NAND with 8 inputs all HIGH → LOW
    chk(all(g.output == LOW for g in col_out),
        "Crossbar 8×4: all-HIGH rows → all col NAND = LOW")
    c.toggle(rows_v[0], LOW)
    # One LOW input → NAND → HIGH for all columns
    chk(all(g.output == HIGH for g in col_out),
        "Crossbar 8×4: one LOW row → all col NAND = HIGH")

    # ── 9. IC wrapping a ripple adder ─────────────────────────────
    tmp_adder = os.path.join(tempfile.gettempdir(), "_bench_adder4.json")
    # Build 4-bit adder as standalone circuit, save as IC
    c_adder = new_sim(backend)
    in_pins_a = [c_adder.getcomponent(backend['INPUT_PIN_ID']) for _ in range(4)]
    in_pins_b = [c_adder.getcomponent(backend['INPUT_PIN_ID']) for _ in range(4)]
    out_pins  = [c_adder.getcomponent(backend['OUTPUT_PIN_ID']) for _ in range(5)]  # 4 sum + 1 carry
    # half adder for bit 0
    s0, carry_g = build_half_adder(c_adder, backend, in_pins_a[0], in_pins_b[0])
    c_adder.connect(out_pins[0], s0, 0)
    prev_carry = carry_g
    for i in range(1, 4):
        si, ci = build_full_adder(c_adder, backend, in_pins_a[i], in_pins_b[i], prev_carry)
        c_adder.connect(out_pins[i], si, 0)
        prev_carry = ci
    c_adder.connect(out_pins[4], prev_carry, 0)
    c_adder.save_as_ic(tmp_adder, "RippleAdder4", "", "")

    # Load IC into a fresh circuit and verify 9+6=15
    c2 = new_sim(backend)
    ic = c2.getIC(tmp_adder)
    chk(ic is not None, "IC load: 4-bit ripple adder IC created OK")
    chk(len(ic.inputs) == 8, f"IC: has 8 input pins (got {len(ic.inputs)})")
    chk(len(ic.outputs) == 5, f"IC: has 5 output pins (got {len(ic.outputs)})")

    # Connect variables and test 9 + 6 = 15, no carry
    va_pins = ic.inputs[:4]
    vb_pins = ic.inputs[4:]
    vars_a = []; vars_b = []
    for i, pin in enumerate(va_pins):
        v = c2.getcomponent(backend['VARIABLE_ID'])
        c2.connect(pin, v, 0); vars_a.append(v)
    for i, pin in enumerate(vb_pins):
        v = c2.getcomponent(backend['VARIABLE_ID'])
        c2.connect(pin, v, 0); vars_b.append(v)

    val_a2, val_b2 = 9, 6   # 9+6=15
    for i in range(4):
        c2.toggle(vars_a[i], (val_a2 >> i) & 1)
        c2.toggle(vars_b[i], (val_b2 >> i) & 1)
    result2 = sum(ic.outputs[i].output << i for i in range(5))
    chk(result2 == 15, f"IC 4-bit adder: 9+6 = {result2} (expect 15)")
    chk(ic.outputs[4].output == LOW, "IC 4-bit adder: no carry for 9+6")

    # 10+10=20
    for i in range(4):
        c2.toggle(vars_a[i], (10 >> i) & 1)
        c2.toggle(vars_b[i], (10 >> i) & 1)
    result3 = sum(ic.outputs[i].output << i for i in range(5))
    chk(result3 == 20, f"IC 4-bit adder: 10+10 = {result3} (expect 20)")
    if os.path.exists(tmp_adder): os.remove(tmp_adder)

    # ── 10. Nested IC (IC inside IC) ──────────────────────────────
    tmp_inner = os.path.join(tempfile.gettempdir(), "_bench_inner.json")
    tmp_outer = os.path.join(tempfile.gettempdir(), "_bench_outer.json")

    # Inner IC: NOT gate
    c_inner = new_sim(backend)
    ip = c_inner.getcomponent(backend['INPUT_PIN_ID'])
    op = c_inner.getcomponent(backend['OUTPUT_PIN_ID'])
    ng = c_inner.getcomponent(backend['NOT_ID'])
    c_inner.connect(ng, ip, 0); c_inner.connect(op, ng, 0)
    c_inner.save_as_ic(tmp_inner, "InnerNOT", "", "")

    # Outer circuit wraps two inner ICs in series: NOT(NOT(x)) = x
    c_outer = new_sim(backend)
    i_pin  = c_outer.getcomponent(backend['INPUT_PIN_ID'])
    o_pin  = c_outer.getcomponent(backend['OUTPUT_PIN_ID'])
    ic_a   = c_outer.getIC(tmp_inner)
    ic_b   = c_outer.getIC(tmp_inner)
    c_outer.connect(ic_a.inputs[0], i_pin, 0)
    c_outer.connect(ic_b.inputs[0], ic_a.outputs[0], 0)
    c_outer.connect(o_pin, ic_b.outputs[0], 0)
    c_outer.save_as_ic(tmp_outer, "DoubleNOT", "", "")

    # Load and verify
    c3 = new_sim(backend)
    ic_dn = c3.getIC(tmp_outer)
    chk(ic_dn is not None, "Nested IC: double-NOT IC loaded OK")
    v3 = c3.getcomponent(backend['VARIABLE_ID'])
    c3.connect(ic_dn.inputs[0], v3, 0)
    c3.toggle(v3, HIGH)
    chk(ic_dn.outputs[0].output == HIGH, "Nested IC: NOT(NOT(HIGH)) = HIGH")
    c3.toggle(v3, LOW)
    chk(ic_dn.outputs[0].output == LOW,  "Nested IC: NOT(NOT(LOW)) = LOW")

    for fp in (tmp_inner, tmp_outer):
        if os.path.exists(fp): os.remove(fp)

    # ── 11. Error/Oscillation propagation through IC ──────────────────
    tmp_err = os.path.join(tempfile.gettempdir(), "_bench_err.json")
    c_err = new_sim(backend)
    ip_e = c_err.getcomponent(backend['INPUT_PIN_ID'])
    op_e = c_err.getcomponent(backend['OUTPUT_PIN_ID'])
    c_err.connect(op_e, ip_e, 0)
    c_err.save_as_ic(tmp_err, "Passthrough", "", "")

    c4 = new_sim(backend)
    ic_pt = c4.getIC(tmp_err)
    
    # Create a self-referential XOR (Infinite Loop)
    xor_e  = c4.getcomponent(backend['XOR_ID'])
    v_trig = c4.getcomponent(backend['VARIABLE_ID'])
    c4.connect(xor_e, v_trig, 0)
    c4.connect(xor_e, xor_e, 1)   # feedback loop
    c4.connect(ic_pt.inputs[0], xor_e, 0)
    c4.toggle(v_trig, HIGH)
    
    # Check if the infinite loop was safely caught by the async runner OR set to ERROR
    has_runner = getattr(c4, 'runner', None) is not None and not c4.runner.done()
    is_error = ic_pt.outputs[0].output == ERROR
    
    chk(has_runner or is_error, "Safety Check: IC handled infinite feedback (Oscillation/ERROR)")
    
    stop_runner(c4)  # Clean up the background task!
    if os.path.exists(tmp_err): os.remove(tmp_err)


    # ── 12. UNKNOWN propagation ────────────────────────────────────
    c5 = new_sim(backend)
    va5 = c5.getcomponent(backend['VARIABLE_ID'])
    vb5 = c5.getcomponent(backend['VARIABLE_ID'])
    and5 = c5.getcomponent(backend['AND_ID'])
    c5.connect(and5, va5, 0); c5.connect(and5, vb5, 1)
    # va5 stays UNKNOWN, vb5 = LOW → AND must be LOW (anything AND LOW = LOW)
    c5.toggle(vb5, LOW)
    chk(and5.output == LOW, "UNKNOWN prop: UNKNOWN AND LOW = LOW (absorb)")
    c5.toggle(vb5, HIGH)
    # Engine logic for AND: returns HIGH only if ALL inputs are HIGH (high == limit)
    # otherwise defaults to LOW. So UNKNOWN AND HIGH evaluates to LOW.
    chk(and5.output == LOW, "UNKNOWN prop: UNKNOWN AND HIGH = LOW (default fallback)")

    print(f"\n    Integrity total: {passed} passed, {failed} failed")
    return passed, failed


# ══════════════════════════════════════════════════════════════════
#  BENCHMARK: IC
# ══════════════════════════════════════════════════════════════════

def bench_ic_create(backend, gate_count, pin_count):
    def create():
        c = new_sim(backend)
        in_pins  = [c.getcomponent(backend['INPUT_PIN_ID'])  for _ in range(pin_count)]
        out_pins = [c.getcomponent(backend['OUTPUT_PIN_ID']) for _ in range(pin_count)]
        gpc = max(1, gate_count // pin_count)
        for p in range(pin_count):
            prev = in_pins[p]
            for _ in range(gpc):
                g = c.getcomponent(backend['NOT_ID'])
                c.connect(g, prev, 0); prev = g
            c.connect(out_pins[p], prev, 0)
        return c
    return timed(create)


def bench_complex_ic(backend, gate_count, tmp_path):
    """
    Build a richer IC using XOR/AND/OR fan-in chains, save, reload, simulate.
    Returns (create_ms, save_ms, load_ms, sim_ms).
    """
    def create():
        c = new_sim(backend)
        pins = max(2, gate_count // 50)
        pins = min(pins, 32)   # cap at 32 pins

        in_pins  = [c.getcomponent(backend['INPUT_PIN_ID'])  for _ in range(pins)]
        out_pins = [c.getcomponent(backend['OUTPUT_PIN_ID']) for _ in range(pins)]

        remaining = gate_count
        for p in range(pins):
            chain_len = max(1, remaining // (pins - p))
            remaining -= chain_len
            prev = in_pins[p]
            for idx in range(chain_len):
                kind  = [backend['NOT_ID'], backend['XOR_ID'],
                         backend['AND_ID'], backend['OR_ID'],
                         backend['NAND_ID']][idx % 5]
                g = c.getcomponent(kind)
                if kind != backend['NOT_ID']:
                    c.setlimits(g, 2)
                    # Second source: loop back to previous output-pin's gate
                    # or just connect to itself (same chain, previous gate)
                    c.connect(g, prev, 0)
                    c.connect(g, in_pins[p], 1)  # fan-in from pin
                else:
                    c.connect(g, prev, 0)
                prev = g
            c.connect(out_pins[p], prev, 0)
        return c

    create_ms, c = timed(create)

    def do_save():
        c.save_as_ic(tmp_path, "ComplexIC", "", "")
    save_ms, _ = timed(do_save)

    def do_load():
        c2 = new_sim(backend)
        return c2, c2.getIC(tmp_path)
    load_ms, (c2, ic) = timed(do_load)

    sim_ms = 0.0
    if ic and ic.inputs:
        # Connect all inputs and toggle them all
        vs = []
        for pin in ic.inputs:
            v = c2.getcomponent(backend['VARIABLE_ID'])
            c2.connect(pin, v, 0); vs.append(v)
        t0 = time.perf_counter_ns()
        for i, v in enumerate(vs):
            c2.toggle(v, i % 2)
        sim_ms = (time.perf_counter_ns() - t0) / 1_000_000
        stop_runner(c2)  # <--- Added cleanup

    return create_ms, save_ms, load_ms, sim_ms


def bench_ic_save_load(backend, circuit, tmp_path):
    def do_save():
        circuit.save_as_ic(tmp_path, "BenchIC", "", "")
    save_ms, _ = timed(do_save)

    def do_load():
        c2 = new_sim(backend)
        return c2, c2.getIC(tmp_path)
    load_ms, (c2, loaded) = timed(do_load)
    return save_ms, load_ms, c2, loaded


# ══════════════════════════════════════════════════════════════════
#  BENCHMARK: CIRCUIT
# ══════════════════════════════════════════════════════════════════

def bench_complex_circuit(backend, gate_count, tmp_path):
    """
    Multi-topology circuit:
      1/3 → NOT chain from variable
      1/3 → AND pyramid
      1/3 → XOR parity chain
    Returns (create_ms, save_ms, load_ms, sim_ms).
    """
    def create():
        c   = new_sim(backend)
        seg = max(4, gate_count // 3)

        # Segment 1: NOT chain
        v1 = c.getcomponent(backend['VARIABLE_ID'])
        build_not_chain(c, backend, seg, v1)

        # Segment 2: AND pyramid (width = nearest power-of-2 ≥ sqrt(seg))
        width = 1
        while width * width < seg: width *= 2
        width = min(width, 512)
        inputs2, _ = build_layered_and_pyramid(c, backend, width, 99)

        # Segment 3: XOR parity
        n_parity = min(seg, 1024)
        inputs3, _ = build_xor_parity(c, backend, n_parity)

        return c, v1, inputs2, inputs3

    create_ms, (c, v1, inp2, inp3) = timed(create)

    def do_save():
        c.writetojson(tmp_path)
    save_ms, _ = timed(do_save)

    def do_load():
        c2 = new_sim(backend)
        c2.readfromjson(tmp_path)
        return c2
    load_ms, c2 = timed(do_load)

    # Simulate: toggle the first variable in the loaded circuit
    sim_ms = 0.0
    loaded_vars = c2.get_variables()
    if loaded_vars:
        t0 = time.perf_counter_ns()
        c2.toggle(loaded_vars[0], backend['HIGH'])
        sim_ms = (time.perf_counter_ns() - t0) / 1_000_000
        stop_runner(c2)  # <--- Added cleanup

    return create_ms, save_ms, load_ms, sim_ms


# ══════════════════════════════════════════════════════════════════
#  RUNNER
# ══════════════════════════════════════════════════════════════════

def run_single_backend(label, use_reactor):
    print(f"\n{header(f'  {label}  ')}")

    try:
        backend = load_backend(use_reactor)
    except ImportError as e:
        print(f"  ⚠ SKIPPED — Cannot import {label}: {e}")
        return None, 0, 0

    total_passed = total_failed = 0
    results = {}
    tmp_dir = tempfile.mkdtemp()

    # ── INTEGRITY ─────────────────────────────────────────────────
    p, f = run_integrity(backend, label)
    total_passed += p; total_failed += f

    # ── COMPLEX IC BENCHMARK ──────────────────────────────────────
    print(f"\n  {'─'*86}")
    print(f"  COMPLEX IC BENCHMARK  (mixed XOR/AND/OR/NAND/NOT topologies)")
    print(f"  {'─'*86}")

    complex_ic_configs = [
        ("Micro IC",         10,    2),
        ("Small IC",        500,    4),
        ("Medium IC",     5_000,    8),
        ("Large IC",     25_000,   16),
        ("Massive IC",   75_000,   32),
        ("Colossal IC", 150_000,   64),
    ]

    print(f"  | {'Name':<14} | {'Gates':>9} | {'Pins':>5} | {'Create':>10} | {'Save':>10} | {'Load':>10} | {'Sim':>10} |")
    print(f"  |{'-'*16}+{'-'*11}+{'-'*7}+{'-'*12}+{'-'*12}+{'-'*12}+{'-'*12}|")

    for name, gc_count, pin_count in complex_ic_configs:
        gc.collect()
        tmp_path = os.path.join(tmp_dir, f"cplx_ic_{gc_count}.json")
        try:
            c_ms, s_ms, l_ms, sim_ms = bench_complex_ic(backend, gc_count, tmp_path)
            results[f'ic_create_{gc_count}'] = c_ms
            results[f'ic_save_{gc_count}']   = s_ms
            results[f'ic_load_{gc_count}']   = l_ms
            results[f'ic_sim_{gc_count}']    = sim_ms
            print(f"  | {name:<14} | {gc_count:>9,} | {pin_count:>5} "
                  f"| {format_time(c_ms):>10} | {format_time(s_ms):>10} "
                  f"| {format_time(l_ms):>10} | {format_time(sim_ms):>10} |")
        except Exception as ex:
            print(f"  | {name:<14} | {gc_count:>9,} | {'ERR':>5} | {'ERROR'*4} |  {ex}")
        finally:
            if os.path.exists(tmp_path): os.remove(tmp_path)

    # ── COMPLEX CIRCUIT BENCHMARK ─────────────────────────────────
    print(f"\n  {'─'*86}")
    print(f"  COMPLEX CIRCUIT BENCHMARK  (NOT chain + AND pyramid + XOR parity)")
    print(f"  {'─'*86}")

    complex_circ_configs = [
        ("Tiny Circ",          300),
        ("Small Circ",       3_000),
        ("Medium Circ",     30_000),
        ("Large Circ",     150_000),
        ("Massive Circ",   500_000),
        ("Colossal Circ",  900_000),
    ]

    print(f"  | {'Name':<14} | {'~Gates':>9} | {'Create':>12} | {'Save':>12} | {'Load':>12} | {'Sim':>10} |")
    print(f"  |{'-'*16}+{'-'*11}+{'-'*14}+{'-'*14}+{'-'*14}+{'-'*12}|")

    for name, g_count in complex_circ_configs:
        gc.collect()
        tmp_path = os.path.join(tmp_dir, f"cplx_circ_{g_count}.json")
        try:
            c_ms, s_ms, l_ms, sim_ms = bench_complex_circuit(backend, g_count, tmp_path)
            results[f'circ_create_{g_count}'] = c_ms
            results[f'circ_save_{g_count}']   = s_ms
            results[f'circ_load_{g_count}']   = l_ms
            results[f'circ_sim_{g_count}']    = sim_ms
            print(f"  | {name:<14} | {g_count:>9,} | {format_time(c_ms):>12} "
                  f"| {format_time(s_ms):>12} | {format_time(l_ms):>12} "
                  f"| {format_time(sim_ms):>10} |")
        except Exception as ex:
            print(f"  | {name:<14} | {g_count:>9,} | {'ERROR':<40} | {ex}")
        finally:
            if os.path.exists(tmp_path): os.remove(tmp_path)

    # ── NESTED IC STRESS ──────────────────────────────────────────
    print(f"\n  {'─'*86}")
    print(f"  NESTED IC STRESS  (chain of 10 save→load→rewrap)")
    print(f"  {'─'*86}")

    nest_files = []
    nest_ok = True
    try:
        # Level 0: simple passthrough NOT
        fp0 = os.path.join(tmp_dir, "nest_0.json")
        cn = new_sim(backend)
        ip0 = cn.getcomponent(backend['INPUT_PIN_ID'])
        op0 = cn.getcomponent(backend['OUTPUT_PIN_ID'])
        ng0 = cn.getcomponent(backend['NOT_ID'])
        cn.connect(ng0, ip0, 0); cn.connect(op0, ng0, 0)
        cn.save_as_ic(fp0, "Nest0", "", "")
        nest_files.append(fp0)

        t_nest = time.perf_counter_ns()
        for level in range(1, 10):
            prev_fp = nest_files[-1]
            new_fp  = os.path.join(tmp_dir, f"nest_{level}.json")
            cw = new_sim(backend)
            wi = cw.getcomponent(backend['INPUT_PIN_ID'])
            wo = cw.getcomponent(backend['OUTPUT_PIN_ID'])
            inner = cw.getIC(prev_fp)
            cw.connect(inner.inputs[0], wi, 0)
            cw.connect(wo, inner.outputs[0], 0)
            cw.save_as_ic(new_fp, f"Nest{level}", "", "")
            nest_files.append(new_fp)
        nest_ms = (time.perf_counter_ns() - t_nest) / 1_000_000

        # Load the deepest and verify NOT10(HIGH) = LOW
        ct = new_sim(backend)
        final_ic = ct.getIC(nest_files[-1])
        vt = ct.getcomponent(backend['VARIABLE_ID'])
        ct.connect(final_ic.inputs[0], vt, 0)
        ct.toggle(vt, backend['HIGH'])
        # 10 layers of NOT: HIGH → LOW
        exp = backend['LOW']
        result_ok = final_ic.outputs[0].output == exp
        print(f"    10× nested NOT IC built in {format_time(nest_ms)}")
        p2 = 0; f2 = 0
        def nc(cond, n):
            nonlocal p2, f2, total_passed, total_failed
            ok = _check(cond, n, label)
            if ok: p2 += 1; total_passed += 1
            else:  f2 += 1; total_failed += 1
        nc(result_ok, "10-level nested NOT IC: NOT¹⁰(HIGH) = LOW")
        ct.toggle(vt, backend['LOW'])
        nc(final_ic.outputs[0].output == backend['HIGH'],
           "10-level nested NOT IC: NOT¹⁰(LOW) = HIGH")
        stop_runner(ct)  # <--- Added cleanup

    except Exception as ex:
        print(f"    ✗ Nested IC stress CRASHED: {ex}")
        total_failed += 1
    finally:
        for fp in nest_files:
            if os.path.exists(fp): os.remove(fp)

    try:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

    print(f"\n  {'─'*86}")
    print(f"  {label} SUMMARY: {total_passed} passed, {total_failed} failed")
    print(f"  {'─'*86}")
    return results, total_passed, total_failed


# ══════════════════════════════════════════════════════════════════
#  COMPARISON TABLE
# ══════════════════════════════════════════════════════════════════

def print_comparison(e_res, r_res):
    if not e_res or not r_res:
        return
    print(f"\n{header('  HEAD-TO-HEAD COMPARISON  ')}")
    def sort_key(k):
        parts = k.rsplit('_', 1)
        return (parts[0], int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0)
    
    common = sorted(set(e_res) & set(r_res), key=sort_key)
    ic_keys   = [k for k in common if k.startswith('ic_')]
    circ_keys = [k for k in common if k.startswith('circ_')]

    for group_name, keys in [("Complex IC", ic_keys), ("Complex Circuit", circ_keys)]:
        if not keys: continue
        print(f"\n  {group_name}:")
        print(f"  | {'Benchmark':<28} | {'Engine':>13} | {'Reactor':>13} | {'Speedup':>10} |")
        print(f"  |{'-'*30}+{'-'*15}+{'-'*15}+{'-'*12}|")
        for key in keys:
            em = e_res[key]; rm = r_res[key]
            sp = em / rm if rm > 0 else float('inf')
            lbl = key.replace('_', ' ').title()
            print(f"  | {lbl:<28} | {format_time(em):>13} | {format_time(rm):>13} | {sp:>9.1f}x |")


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

class _Tee:
    def __init__(self, *s): self.streams = s
    def write(self, d):
        for s in self.streams: s.write(d)
    def flush(self):
        for s in self.streams: s.flush()


async def run_all():
    print(divider())
    print(header("  IC & CIRCUIT BENCHMARK + INTEGRITY SUITE  "))
    print(divider())
    print(f"  Platform : {platform.system()} {platform.release()}")
    print(f"  Python   : {platform.python_version()}")
    print(f"  Time     : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(divider())

    e_res, ep, ef = run_single_backend("ENGINE (Python)",  use_reactor=False)
    r_res, rp, rf = run_single_backend("REACTOR (Cython)", use_reactor=True)

    print_comparison(e_res, r_res)

    total_p = ep + rp
    total_f = ef + rf
    print(f"\n{divider()}")
    print(f"  INTEGRITY SUMMARY")
    print(f"  Engine  : {ep} passed, {ef} failed")
    print(f"  Reactor : {rp} passed, {rf} failed")
    print(f"  Total   : {total_p} passed, {total_f} failed")
    if total_f == 0:
        print(f"  {'✓ ALL INTEGRITY CHECKS PASSED':^86}")
    else:
        print(f"  {'✗ FAILURES DETECTED — see *** marks above':^86}")
    print(divider())
    print(f"  BENCHMARK COMPLETE")
    print(divider())


if __name__ == "__main__":
    from datetime import datetime
    _LOG = "ic_circuit_benchmark_results.txt"
    with open(_LOG, "a", encoding="utf-8") as _lf:
        _lf.write(f"\n{'='*70}\nRUN  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*70}\n")
        _orig = sys.stdout
        sys.stdout = _Tee(_orig, _lf)
        try:
            asyncio.run(run_all())
        except KeyboardInterrupt:
            print("\n[!] Benchmark Aborted by User.")

        finally:
            sys.stdout = _orig
    print(f"\nLog saved to: {_LOG}")

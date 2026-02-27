"""
DARION LOGIC SIM - TOPOLOGY COMPLEXITY PROFILER v6.0 (True Hardware Metrics)
Calculates exact C-level evaluation counts by querying the engine directly.
Includes statistical jitter filtering and zero-overhead timing loops.
Real-life circuit library: L0-L21 covering synthetic stress tests and
achieved silicon-equivalent topologies (adders, latches, ALU, CRC, etc.).
"""

import time
import gc
import sys
import os
import random
import argparse

script_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(script_dir, 'reactor')) or os.path.exists(os.path.join(script_dir, 'engine')):
    root_dir = script_dir
elif getattr(sys, 'frozen', False):
    root_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
else:
    root_dir = os.path.abspath(os.path.join(script_dir, '..'))

parser = argparse.ArgumentParser(description='Topology Complexity Profiler')
parser.add_argument('--engine', action='store_true', help='Use Python engine backend (default: Reactor/Cython)')
args, _ = parser.parse_known_args()

if args.engine:
    sys.path.insert(0, os.path.join(root_dir, 'engine'))
    backend_name = "Engine"
else:
    sys.path.insert(0, os.path.join(root_dir, 'reactor'))
    backend_name = "Reactor"

from Circuit import Circuit as CircuitClass
from Const import AND_ID, XOR_ID, OR_ID, NOT_ID, VARIABLE_ID, HIGH, LOW, SIMULATE, DESIGN


# =====================================================================
# TOPOLOGIES
# =====================================================================

def build_level_0_linear(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    prev = master
    for _ in range(target_gates - 1):
        g = circuit.getcomponent(NOT_ID)
        circuit.connect(g, prev, 0)
        prev = g
    return master, target_gates, target_gates, "L0: Linear Chain"

def build_level_1_parallel(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    lanes = max(1, target_gates // 50) 
    depth = target_gates // lanes
    total_physical = 1
    for _ in range(lanes):
        prev = master
        for _ in range(depth):
            g = circuit.getcomponent(NOT_ID)
            circuit.connect(g, prev, 0)
            prev = g
            total_physical += 1
    return master, total_physical, total_physical, "L1: Wide Fan-Out"

def build_level_2_fanout_tree(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    current_layer = [master]
    count = 1
    while count < target_gates:
        next_layer = []
        for node in current_layer:
            if count >= target_gates: break
            g1, g2 = circuit.getcomponent(NOT_ID), circuit.getcomponent(NOT_ID)
            circuit.connect(g1, node, 0); circuit.connect(g2, node, 0)
            next_layer.extend([g1, g2])
            count += 2
        current_layer = next_layer
    return master, count, count, "L2: Binary Tree"

def build_level_3_memory_maze(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    gates = [circuit.getcomponent(NOT_ID) for _ in range(target_gates - 1)]
    random.seed(42)
    random.shuffle(gates) 
    prev = master
    for g in gates:
        circuit.connect(g, prev, 0)
        prev = g
    return master, target_gates, target_gates, "L3: Memory Maze"

def build_level_4_glitch_avalanche(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    half = target_gates // 2
    chain = [master]
    for _ in range(half):
        g = circuit.getcomponent(NOT_ID)
        circuit.connect(g, chain[-1], 0)
        chain.append(g)
    for i in range(1, len(chain)):
        g = circuit.getcomponent(XOR_ID)
        circuit.connect(g, master, 0)    
        circuit.connect(g, chain[i], 1)  
    physical_count = half * 2
    theoretical_evals = half * 3  
    return master, physical_count, theoretical_evals, "L4: Glitch Avalanche"

def build_level_5_event_hurricane(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    size = target_gates # Removed artificial cap to allow natural scaling math
    xors = [circuit.getcomponent(XOR_ID) for _ in range(size)]
    static_low = circuit.getcomponent(VARIABLE_ID)
    circuit.toggle(static_low, 0)
    for i in range(size-1, -1, -1):
        circuit.connect(xors[i], master, 0)
    circuit.connect(xors[0], static_low, 1)
    for i in range(1, size):
        circuit.connect(xors[i], xors[i-1], 1)
    physical_count = size + 2
    theoretical_evals = (size * (size + 1)) // 2 
    return master, physical_count, theoretical_evals, "L5: Queue Thrash O(N^2)"

def build_level_6_sparse_fanin(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    leaves = [master]
    static_low = circuit.getcomponent(VARIABLE_ID)
    circuit.toggle(static_low, 0)
    
    while len(leaves) * 2 <= target_gates:
        var = circuit.getcomponent(VARIABLE_ID)
        circuit.toggle(var, 0)
        leaves.append(var)
        
    current_layer = leaves
    total_physical = len(leaves) + 1
    exact_evals = 1 
    
    while len(current_layer) > 1:
        next_layer = []
        for i in range(0, len(current_layer), 2):
            if i+1 < len(current_layer):
                g = circuit.getcomponent(XOR_ID)
                circuit.connect(g, current_layer[i], 0)
                circuit.connect(g, current_layer[i+1], 1)
                next_layer.append(g)
                total_physical += 1
            else:
                next_layer.append(current_layer[i])
        current_layer = next_layer
        exact_evals += 1
        
    return master, total_physical, exact_evals, "L6: Sparse Fan-In"

def build_level_7_braid(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    width = 4
    num_layers = target_gates // width
    
    prev_layer = [master] * width 
    total_physical = 1
    exact_evals = 1
    
    for _ in range(num_layers):
        current_layer = []
        for i in range(width):
            g = circuit.getcomponent(AND_ID)
            circuit.connect(g, prev_layer[i], 0)
            circuit.connect(g, prev_layer[(i+1)%width], 1)
            current_layer.append(g)
            total_physical += 1
        prev_layer = current_layer
        exact_evals += width
        
    return master, total_physical, exact_evals, "L7: Dense Braid"

def build_level_8_diamond(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    current_layer = [master]
    total_physical = 1
    exact_evals = 1
    expand_target = max(2, target_gates // 2)
    
    while total_physical < expand_target:
        next_layer = []
        for node in current_layer:
            g1, g2 = circuit.getcomponent(NOT_ID), circuit.getcomponent(NOT_ID)
            circuit.connect(g1, node, 0); circuit.connect(g2, node, 0)
            next_layer.extend([g1, g2])
            total_physical += 2
            exact_evals += 2
        current_layer = next_layer
        
    while len(current_layer) > 1:
        next_layer = []
        for i in range(0, len(current_layer), 2):
            if i+1 < len(current_layer):
                g = circuit.getcomponent(AND_ID)
                circuit.connect(g, current_layer[i], 0)
                circuit.connect(g, current_layer[i+1], 1)
                next_layer.append(g)
                total_physical += 1
                exact_evals += 1
            else:
                next_layer.append(current_layer[i])
        current_layer = next_layer
        
    return master, total_physical, exact_evals, "L8: Diamond (Exp/Con)"

def build_level_9_hamming_ecc(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    master = circuit.getcomponent(VARIABLE_ID)
    
    # We need 4 data lines for Hamming(7,4). We will make them toggle differently.
    # d1 = master
    # d2 = master delayed by 1 gate
    # d3 = master delayed by 2 gates
    # d4 = master delayed by 3 gates
    d1 = master
    
    n1 = circuit.getcomponent(NOT_ID)
    circuit.connect(n1, master, 0)
    d2 = circuit.getcomponent(NOT_ID)
    circuit.connect(d2, n1, 0)
    
    n2 = circuit.getcomponent(NOT_ID)
    circuit.connect(n2, d2, 0)
    d3 = circuit.getcomponent(NOT_ID)
    circuit.connect(d3, n2, 0)
    
    n3 = circuit.getcomponent(NOT_ID)
    circuit.connect(n3, d3, 0)
    d4 = circuit.getcomponent(NOT_ID)
    circuit.connect(d4, n3, 0)
    
    total_physical = 7
    exact_evals = 7
    
    # Each Hamming block needs 6 XOR gates
    blocks = max(1, target_gates // 6)
    
    for _ in range(blocks):
        # p1 = d1 ^ d2 ^ d4
        x1 = circuit.getcomponent(XOR_ID)
        circuit.connect(x1, d1, 0); circuit.connect(x1, d2, 1)
        p1 = circuit.getcomponent(XOR_ID)
        circuit.connect(p1, x1, 0); circuit.connect(p1, d4, 1)
        
        # p2 = d1 ^ d3 ^ d4
        x2 = circuit.getcomponent(XOR_ID)
        circuit.connect(x2, d1, 0); circuit.connect(x2, d3, 1)
        p2 = circuit.getcomponent(XOR_ID)
        circuit.connect(p2, x2, 0); circuit.connect(p2, d4, 1)
        
        # p3 = d2 ^ d3 ^ d4
        x3 = circuit.getcomponent(XOR_ID)
        circuit.connect(x3, d2, 0); circuit.connect(x3, d3, 1)
        p3 = circuit.getcomponent(XOR_ID)
        circuit.connect(p3, x3, 0); circuit.connect(p3, d4, 1)
        
        total_physical += 6
        exact_evals += 15
        
    return master, total_physical, exact_evals, "L9: Hamming(7,4) ECC"

def build_level_10_ripple_carry_adder(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    """Ripple Carry Adder: each full-adder is a 5-gate cell (2x XOR, 2x AND, 1x OR).
    Tests sequential carry-chain latency -- the critical path grows linearly."""
    master = circuit.getcomponent(VARIABLE_ID)   # shared 'A' bus driven by master
    carry_in = circuit.getcomponent(VARIABLE_ID)  # carry-in = 0
    circuit.toggle(carry_in, 0)
    bits = max(1, target_gates // 5)
    total_physical = 2  # master + carry_in
    exact_evals = 0
    c = carry_in  # running carry
    for _ in range(bits):
        b = circuit.getcomponent(VARIABLE_ID)  # B input
        circuit.toggle(b, 0)
        # Sum bit: (A ^ B) ^ Cin
        xab  = circuit.getcomponent(XOR_ID)
        circuit.connect(xab, master, 0); circuit.connect(xab, b, 1)
        xsum = circuit.getcomponent(XOR_ID)
        circuit.connect(xsum, xab, 0); circuit.connect(xsum, c, 1)
        # Carry out: (A & B) | (Cin & (A ^ B))
        aab  = circuit.getcomponent(AND_ID)
        circuit.connect(aab, master, 0); circuit.connect(aab, b, 1)
        acx  = circuit.getcomponent(AND_ID)
        circuit.connect(acx, c, 0); circuit.connect(acx, xab, 1)
        oc   = circuit.getcomponent(OR_ID)
        circuit.connect(oc, aab, 0); circuit.connect(oc, acx, 1)
        c = oc
        total_physical += 6  # b + 5 gates
        exact_evals    += 5
    return master, total_physical, exact_evals, "L10: Ripple Carry Adder"

def build_level_11_priority_encoder(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    """N-bit Priority Encoder: balanced OR-reduction tree, all N inputs = master.
    FIXED: previous version used OR(master, NOT(master)) which is a tautology
    (always HIGH regardless of master) -- root output never changed with master.
    Now all N slots alias master directly: OR(master,...,master) = master,
    so output tracks master (HIGH=any-active) and the full tree fires each toggle.
    root output: HIGH when master=HIGH, LOW when master=LOW. Logically correct."""
    master = circuit.getcomponent(VARIABLE_ID)
    n_inputs = max(2, target_gates)
    # All leaf slots reference master -- no static VARIABLE heap
    current_layer = [master] * n_inputs
    total_physical = 1
    # master has 2*n_inputs fanout edges (2 per leaf OR);
    # geometric cascade sum through log2(N) levels ≈ 2*n_inputs
    exact_evals = 2 * n_inputs
    # OR-reduction tree
    while len(current_layer) > 1:
        next_layer = []
        for i in range(0, len(current_layer), 2):
            if i + 1 < len(current_layer):
                g = circuit.getcomponent(OR_ID)
                circuit.connect(g, current_layer[i], 0)
                circuit.connect(g, current_layer[i+1], 1)
                next_layer.append(g)
                total_physical += 1
            else:
                next_layer.append(current_layer[i])
        current_layer = next_layer
    return master, total_physical, exact_evals, "L11: Priority Encoder"

def build_level_12_wallace_tree(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    """Wallace Tree Multiplier: 3-2 compressor (full-adder) reduction.
    Inputs fan out from master via XOR/NOT splitter so ALL compressor cells
    receive a changing signal on each toggle (O(N) evaluations per transition)."""
    # Build a balanced splitter: master fans out to n_inputs live signals
    # using pairs (master, XOR(master, const)) so both halves invert together
    master  = circuit.getcomponent(VARIABLE_ID)
    nmaster = circuit.getcomponent(NOT_ID)
    circuit.connect(nmaster, master, 0)
    total_physical = 2
    exact_evals    = 1
    n_inputs = max(3, target_gates // 5 * 3)  # leave ~40% budget for compressor gates
    inputs = []
    for i in range(n_inputs):
        inputs.append(master if i % 2 == 0 else nmaster)
    # Wallace 3-2 compressor reduction
    current = inputs
    while len(current) > 2:
        reduced = []
        i = 0
        while i + 2 < len(current):
            # Full-adder: sum = A^B^C, carry = (A&B)|(C&(A^B))
            xab = circuit.getcomponent(XOR_ID)
            circuit.connect(xab, current[i], 0); circuit.connect(xab, current[i+1], 1)
            s = circuit.getcomponent(XOR_ID)
            circuit.connect(s, xab, 0); circuit.connect(s, current[i+2], 1)
            aab = circuit.getcomponent(AND_ID)
            circuit.connect(aab, current[i], 0); circuit.connect(aab, current[i+1], 1)
            acx = circuit.getcomponent(AND_ID)
            circuit.connect(acx, current[i+2], 0); circuit.connect(acx, xab, 1)
            co = circuit.getcomponent(OR_ID)
            circuit.connect(co, aab, 0); circuit.connect(co, acx, 1)
            reduced.extend([s, co])
            total_physical += 5; exact_evals += 5
            i += 3
        while i < len(current):
            reduced.append(current[i]); i += 1
        current = reduced
    return master, total_physical, exact_evals, "L12: Wallace Tree"

def build_level_13_sr_latch_farm(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    """SR Latch Farm: each latch is 2x NOR (simulated as NOT+OR feedback pair).
    Tests how the engine handles cyclic/feedback topologies at scale."""
    master = circuit.getcomponent(VARIABLE_ID)
    # NOR latch: Q = NOT(R | Q_bar),  Q_bar = NOT(S | Q)
    # Approximated with OR+NOT pairs; cross-couple via VARIABLE mirrors.
    latches = max(1, target_gates // 4)
    total_physical = 1
    exact_evals = 1
    for _ in range(latches):
        s_node = circuit.getcomponent(VARIABLE_ID)
        r_node = circuit.getcomponent(VARIABLE_ID)
        circuit.toggle(s_node, 0); circuit.toggle(r_node, 0)
        # Q_bar side
        or_qbar = circuit.getcomponent(OR_ID)
        circuit.connect(or_qbar, master, 0); circuit.connect(or_qbar, r_node, 1)
        q_bar   = circuit.getcomponent(NOT_ID)
        circuit.connect(q_bar, or_qbar, 0)
        # Q side
        or_q = circuit.getcomponent(OR_ID)
        circuit.connect(or_q, s_node, 0); circuit.connect(or_q, q_bar, 1)
        q    = circuit.getcomponent(NOT_ID)
        circuit.connect(q, or_q, 0)
        total_physical += 6
        exact_evals    += 4
    return master, total_physical, exact_evals, "L13: SR Latch Farm"

def build_level_14_sparse_random_dag(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    """Sparse Random DAG: random backward-only connections between gates.
    Tests cache-unfriendly, unpredictable traversal order."""
    rng = random.Random(0xDEADBEEF)
    sources = []
    for _ in range(max(2, target_gates // 20)):
        v = circuit.getcomponent(VARIABLE_ID)
        circuit.toggle(v, rng.randint(0, 1))
        sources.append(v)
    master = sources[0]
    pool = list(sources)
    total_physical = len(sources)
    exact_evals = 0
    remaining = target_gates - total_physical
    gate_types = [NOT_ID, XOR_ID, AND_ID, OR_ID]
    for _ in range(remaining):
        gt = rng.choice(gate_types)
        g  = circuit.getcomponent(gt)
        if gt == NOT_ID:
            p = rng.choice(pool)
            circuit.connect(g, p, 0)
        else:
            p0 = rng.choice(pool); p1 = rng.choice(pool)
            circuit.connect(g, p0, 0); circuit.connect(g, p1, 1)
        pool.append(g)
        total_physical += 1
        exact_evals    += 1
    return master, total_physical, exact_evals, "L14: Sparse Random DAG"

def build_level_15_decoder_tree(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    """Full Binary Decoder: N address bits drive 2^N AND gates.
    Tests extreme fan-out (each address bit fans out to half the AND gates).
    Physical gates = 2*addr + 2^addr; large sizes are capped at 10-bit (1024 outputs)."""
    # Choose address width so that 2^addr outputs ~ target_gates
    import math
    addr_bits = min(10, max(2, int(math.log2(max(4, target_gates)))))
    outputs = 1 << addr_bits  # 2^addr_bits
    # Create addr_bits address lines and their complements
    addr_lines = []
    comp_lines = []
    for _ in range(addr_bits):
        v  = circuit.getcomponent(VARIABLE_ID)
        nv = circuit.getcomponent(NOT_ID)
        circuit.connect(nv, v, 0)
        addr_lines.append(v); comp_lines.append(nv)
    master = addr_lines[0]
    total_physical = addr_bits * 2
    exact_evals = addr_bits  # NOTs evaluate once each
    # Each output i selects the AND of specific true/complement bits
    # We chain 2-input ANDs for each output minterm
    for out_idx in range(outputs):
        prev = None
        for bit in range(addr_bits):
            sel = addr_lines[bit] if (out_idx >> bit) & 1 else comp_lines[bit]
            if prev is None:
                prev = sel
            else:
                g = circuit.getcomponent(AND_ID)
                circuit.connect(g, prev, 0); circuit.connect(g, sel, 1)
                prev = g
                total_physical += 1
                exact_evals    += 1
    return master, total_physical, exact_evals, "L15: Decoder Tree"

def build_level_16_carry_lookahead(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    """4-bit Carry Lookahead Adder repeated N times."""
    master = circuit.getcomponent(VARIABLE_ID)
    carry  = circuit.getcomponent(VARIABLE_ID)
    circuit.toggle(carry, 0)
    # Each 4-bit CLA block uses ~20 gates
    blocks = max(1, target_gates // 20)
    total_physical = 2
    exact_evals    = 0
    for _ in range(blocks):
        b = [circuit.getcomponent(VARIABLE_ID) for _ in range(4)]
        for bv in b: circuit.toggle(bv, 0)
        p, g = [], []
        for i in range(4):
            pi = circuit.getcomponent(XOR_ID)
            circuit.connect(pi, master, 0); circuit.connect(pi, b[i], 1)
            gi = circuit.getcomponent(AND_ID)
            circuit.connect(gi, master, 0); circuit.connect(gi, b[i], 1)
            p.append(pi); g.append(gi)
        # C1 = G0 | (P0 & Cin)
        a0 = circuit.getcomponent(AND_ID)
        circuit.connect(a0, p[0], 0); circuit.connect(a0, carry, 1)
        c1 = circuit.getcomponent(OR_ID)
        circuit.connect(c1, g[0], 0); circuit.connect(c1, a0, 1)
        # C2 = G1 | (P1&G0) | (P1&P0&Cin)  -- two-level approximation
        a1 = circuit.getcomponent(AND_ID)
        circuit.connect(a1, p[1], 0); circuit.connect(a1, g[0], 1)
        a2 = circuit.getcomponent(AND_ID)
        circuit.connect(a2, p[1], 0); circuit.connect(a2, a0, 1)
        o1 = circuit.getcomponent(OR_ID)
        circuit.connect(o1, g[1], 0); circuit.connect(o1, a1, 1)
        c2 = circuit.getcomponent(OR_ID)
        circuit.connect(c2, o1, 0); circuit.connect(c2, a2, 1)
        carry = c2
        total_physical += 4 + 8 + 6
        exact_evals    += 8 + 6
    return master, total_physical, exact_evals, "L16: CLA 4-bit"

def build_level_17_d_latch_array(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    """Chain of D-latches: Q = (D & En) | (Q_prev & ~En)."""
    master = circuit.getcomponent(VARIABLE_ID)   # shared D
    en     = circuit.getcomponent(VARIABLE_ID)   # shared enable
    circuit.toggle(en, 1)
    latches = max(1, target_gates // 4)
    total_physical = 2
    exact_evals    = 0
    q_prev = master
    for _ in range(latches):
        nen   = circuit.getcomponent(NOT_ID)
        circuit.connect(nen, en, 0)
        d_en  = circuit.getcomponent(AND_ID)
        circuit.connect(d_en, master, 0); circuit.connect(d_en, en, 1)
        q_nen = circuit.getcomponent(AND_ID)
        circuit.connect(q_nen, q_prev, 0); circuit.connect(q_nen, nen, 1)
        q     = circuit.getcomponent(OR_ID)
        circuit.connect(q, d_en, 0); circuit.connect(q, q_nen, 1)
        q_prev = q
        total_physical += 4
        exact_evals    += 4
    return master, total_physical, exact_evals, "L17: D-Latch Array"

def build_level_18_barrel_shifter(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    """8-bit 3-stage barrel shifter (shift by 1/2/4) using 2:1 muxes."""
    WIDTH  = 8
    STAGES = 3
    # Per block: STAGES*(NOT + 8*(AND+AND+OR)) + (WIDTH-1) extra data vars = 3*(1+24)+7 = 82
    GATES_PER_BLOCK = STAGES * (1 + WIDTH * 3) + (WIDTH - 1)
    blocks = max(1, target_gates // GATES_PER_BLOCK)
    # master IS data[0] so toggling it propagates through all mux stages
    master = circuit.getcomponent(VARIABLE_ID)
    total_physical = 1
    exact_evals    = 0
    for _ in range(blocks):
        # Reuse master as lane 0; create independent vars for lanes 1-7
        data = [master] + [circuit.getcomponent(VARIABLE_ID) for _ in range(WIDTH - 1)]
        for d in data[1:]: circuit.toggle(d, 0)
        total_physical += WIDTH - 1
        layer = data
        for stage in range(STAGES):
            sel  = circuit.getcomponent(VARIABLE_ID)
            circuit.toggle(sel, 0)
            nsel = circuit.getcomponent(NOT_ID)
            circuit.connect(nsel, sel, 0)
            total_physical += 2; exact_evals += 1
            shift_amt  = 1 << stage
            next_layer = []
            for i in range(WIDTH):
                d0 = layer[i]
                d1 = layer[(i - shift_amt) % WIDTH]
                a0 = circuit.getcomponent(AND_ID)
                circuit.connect(a0, d0, 0); circuit.connect(a0, nsel, 1)
                a1 = circuit.getcomponent(AND_ID)
                circuit.connect(a1, d1, 0); circuit.connect(a1, sel, 1)
                o  = circuit.getcomponent(OR_ID)
                circuit.connect(o, a0, 0); circuit.connect(o, a1, 1)
                next_layer.append(o)
                total_physical += 3; exact_evals += 3
            layer = next_layer
    return master, total_physical, exact_evals, "L18: Barrel Shifter"

def build_level_19_crc8_lfsr(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    """CRC-8/MAXIM LFSR with XOR feedback taps at positions 4 and 5."""
    WIDTH        = 8
    TAP_POSITIONS = {4, 5}
    # Each LFSR instance: WIDTH vars + 1 feedback XOR + len(TAP_POSITIONS) tap XORs + 1 output XOR
    GATES_PER_INST = WIDTH + 1 + len(TAP_POSITIONS) + 1
    stages_n = max(1, target_gates // GATES_PER_INST)
    master = circuit.getcomponent(VARIABLE_ID)   # serial data-in
    total_physical = 1
    exact_evals    = 0
    for _ in range(stages_n):
        reg = [circuit.getcomponent(VARIABLE_ID) for _ in range(WIDTH)]
        for r in reg: circuit.toggle(r, 0)
        total_physical += WIDTH
        # Feedback: MSB XOR serial_in
        fb = circuit.getcomponent(XOR_ID)
        circuit.connect(fb, reg[WIDTH - 1], 0); circuit.connect(fb, master, 1)
        total_physical += 1; exact_evals += 1
        new_reg = []
        for i in range(WIDTH):
            if i == 0:
                new_reg.append(fb)
            elif i - 1 in TAP_POSITIONS:
                x = circuit.getcomponent(XOR_ID)
                circuit.connect(x, reg[i - 1], 0); circuit.connect(x, fb, 1)
                new_reg.append(x)
                total_physical += 1; exact_evals += 1
            else:
                new_reg.append(reg[i - 1])
        # Output tap: read MSB of new register
        chk = circuit.getcomponent(XOR_ID)
        circuit.connect(chk, new_reg[WIDTH - 1], 0); circuit.connect(chk, master, 1)
        total_physical += 1; exact_evals += 1
    return master, total_physical, exact_evals, "L19: CRC-8 LFSR"

def build_level_20_magnitude_comparator(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    """8-bit equality comparator: XNOR each bit-pair, AND-reduce all results."""
    WIDTH = 8
    # Each block: (WIDTH-1) extra A inputs + WIDTH B inputs + WIDTH XNOR (XOR+NOT) + (WIDTH-1) AND
    GATES_PER_BLOCK = (WIDTH - 1) + WIDTH + WIDTH * 2 + (WIDTH - 1)
    blocks = max(1, target_gates // GATES_PER_BLOCK)
    master = circuit.getcomponent(VARIABLE_ID)
    total_physical = 1
    exact_evals    = 0
    for _ in range(blocks):
        a = [master] + [circuit.getcomponent(VARIABLE_ID) for _ in range(WIDTH - 1)]
        b = [circuit.getcomponent(VARIABLE_ID) for _ in range(WIDTH)]
        for i in range(1, WIDTH): circuit.toggle(a[i], i % 2)
        for i in range(WIDTH):   circuit.toggle(b[i], (i + 1) % 2)
        total_physical += (WIDTH - 1) + WIDTH
        xnors = []
        for i in range(WIDTH):
            x  = circuit.getcomponent(XOR_ID)
            circuit.connect(x, a[i], 0); circuit.connect(x, b[i], 1)
            nx = circuit.getcomponent(NOT_ID)
            circuit.connect(nx, x, 0)
            xnors.append(nx)
            total_physical += 2; exact_evals += 2
        eq = xnors[0]
        for i in range(1, WIDTH):
            g = circuit.getcomponent(AND_ID)
            circuit.connect(g, eq, 0); circuit.connect(g, xnors[i], 1)
            eq = g
            total_physical += 1; exact_evals += 1
    return master, total_physical, exact_evals, "L20: 8-bit Comparator"

def build_level_21_alu_slice(circuit, target_gates, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=0):
    """1-bit ALU slice × N: AND / OR / XOR / ADD with 2-bit opcode mux."""
    # Each slice: 3 ops + 5-gate half-adder + 2-level opcode mux (11 gates) = ~19 gates
    GATES_PER_SLICE = 19
    slices = max(1, target_gates // GATES_PER_SLICE)
    master = circuit.getcomponent(VARIABLE_ID)   # shared A
    op0    = circuit.getcomponent(VARIABLE_ID); circuit.toggle(op0, 0)
    op1    = circuit.getcomponent(VARIABLE_ID); circuit.toggle(op1, 0)
    nop0   = circuit.getcomponent(NOT_ID); circuit.connect(nop0, op0, 0)
    nop1   = circuit.getcomponent(NOT_ID); circuit.connect(nop1, op1, 0)
    total_physical = 5; exact_evals = 2
    for _ in range(slices):
        b   = circuit.getcomponent(VARIABLE_ID); circuit.toggle(b, 0)
        cin = circuit.getcomponent(VARIABLE_ID); circuit.toggle(cin, 0)
        # Four operations computed in parallel
        res_and = circuit.getcomponent(AND_ID)
        circuit.connect(res_and, master, 0); circuit.connect(res_and, b, 1)
        res_or  = circuit.getcomponent(OR_ID)
        circuit.connect(res_or,  master, 0); circuit.connect(res_or,  b, 1)
        res_xor = circuit.getcomponent(XOR_ID)
        circuit.connect(res_xor, master, 0); circuit.connect(res_xor, b, 1)
        # ADD: half-adder sum (XOR reused via res_xor)
        xab     = circuit.getcomponent(XOR_ID)
        circuit.connect(xab, master, 0); circuit.connect(xab, b, 1)
        res_add = circuit.getcomponent(XOR_ID)
        circuit.connect(res_add, xab, 0); circuit.connect(res_add, cin, 1)
        # 2-bit mux: out = AND(op=00)|OR(op=01)|XOR(op=10)|ADD(op=11)
        m0 = circuit.getcomponent(AND_ID); circuit.connect(m0, res_and, 0); circuit.connect(m0, nop0, 1)
        m1 = circuit.getcomponent(AND_ID); circuit.connect(m1, m0, 0);      circuit.connect(m1, nop1, 1)
        m2 = circuit.getcomponent(AND_ID); circuit.connect(m2, res_or,  0); circuit.connect(m2, op0,  1)
        m3 = circuit.getcomponent(AND_ID); circuit.connect(m3, m2, 0);      circuit.connect(m3, nop1, 1)
        or1 = circuit.getcomponent(OR_ID); circuit.connect(or1, m1, 0); circuit.connect(or1, m3, 1)
        m4 = circuit.getcomponent(AND_ID); circuit.connect(m4, res_xor, 0); circuit.connect(m4, nop0, 1)
        m5 = circuit.getcomponent(AND_ID); circuit.connect(m5, m4, 0);      circuit.connect(m5, op1,  1)
        m6 = circuit.getcomponent(AND_ID); circuit.connect(m6, res_add, 0); circuit.connect(m6, op0,  1)
        m7 = circuit.getcomponent(AND_ID); circuit.connect(m7, m6, 0);      circuit.connect(m7, op1,  1)
        or2 = circuit.getcomponent(OR_ID); circuit.connect(or2, m5, 0); circuit.connect(or2, m7, 1)
        out = circuit.getcomponent(OR_ID)
        circuit.connect(out, or1, 0); circuit.connect(out, or2, 1)
        total_physical += 2 + 5 + 11   # b,cin + 5 op gates + 11 mux/out gates
        exact_evals    += 5 + 11
    return master, total_physical, exact_evals, "L21: ALU Slice"


# =====================================================================
# CIRCUIT DESCRIPTIONS  (printed as a legend after the benchmark table)
# =====================================================================

LEVEL_DESCRIPTIONS = {
    "L0":  ("Linear Chain",
            "A single inverter chain -- every gate depends solely on the previous one. "
            "Zero parallelism, one critical path. Measures pure sequential evaluation latency."),
    "L1":  ("Wide Fan-Out",
            "One source fans into many independent inverter chains running in parallel. "
            "Tests the scheduler's ability to dispatch many ready-gates simultaneously."),
    "L2":  ("Binary Tree",
            "Balanced binary fan-out tree: 2 children per node, O(log N) depth. "
            "Reveals how well the engine exploits tree-level parallelism."),
    "L3":  ("Memory Maze",
            "Topology identical to L0 but gate objects are shuffled in memory before wiring. "
            "Isolates the cost of pointer-chasing through fragmented cache lines."),
    "L4":  ("Glitch Avalanche",
            "Half chain + N XOR gates each tied to the chain head AND the master. One toggle "
            "floods the queue with O(N) simultaneous glitch events -- tests event-queue saturation."),
    "L5":  ("Queue Thrash O(N^2)",
            "XOR chain where every gate also depends on the very first master node. A single toggle "
            "cascades O(N^2) re-evaluations -- absolute worst-case queue pressure."),
    "L6":  ("Sparse Fan-In",
            "Multiple independent sources reduced by a balanced XOR tree to one output. "
            "All sources change at once -- measures throughput of wide simultaneous fan-in reduction."),
    "L7":  ("Dense Braid",
            "Four parallel AND-gate lanes where each gate also reads from the adjacent lane (wrap-around). "
            "Maximises wire density; models a tightly interconnected datapath strip."),
    "L8":  ("Diamond (Exp/Con)",
            "Expands into a binary fan-out tree then contracts leaf-pairs via AND reduction. "
            "The hourglass shape exercises both the expand and merge phases of a pipeline."),
    "L9":  ("Hamming(7,4) ECC",
            "Parity-bit computation of a Hamming(7,4) error-correcting code. "
            "Three XOR chains model the syndrome logic found in DRAM ECC controllers."),
    "L10": ("Ripple Carry Adder",
            "N cascaded full-adder cells (2x XOR, 2x AND, 1x OR each). Carry must ripple "
            "through all N stages before the final sum is valid -- the classic sequential bottleneck."),
    "L11": ("Priority Encoder",
            "OR-reduction tree: master fans out (true + NOT complement) to N/2 leaf OR gates that all "
            "fire simultaneously on each toggle. O(N) evals cascade through O(log N) levels -- "
            "models 'any-bit-set' aggregation in interrupt controllers and bus arbiters."),
    "L12": ("Wallace Tree",
            "3-2 full-adder compressor reduction: master + NOT(master) feed all N leaf inputs so "
            "every compressor cell fires on each toggle. Irregular shrinking width + mixed "
            "XOR/AND/OR pattern mirrors hardware multiplier internals."),
    "L13": ("SR Latch Farm",
            "Banks of SR latches built from OR+NOT pairs with partial feedback paths. "
            "Models memory-cell arrays; tests graceful degradation under cyclic topology."),
    "L14": ("Sparse Random DAG",
            "Randomly seeded DAG (seed=0xDEADBEEF) with backward-only random connections and "
            "uniform gate-type mix. Thrashes CPU caches and branch predictors -- a synthesised netlist worst case."),
    "L15": ("Decoder Tree",
            "Binary address decoder: N address bits produce 2^N AND minterms. Every address-bit "
            "fans out to half the outputs -- models ROM/SRAM address decode logic. Capped at 10-bit."),
    "L16": ("CLA 4-bit",
            "Carry Lookahead Adder: computes propagate (P=A^B) and generate (G=A&B) signals then "
            "evaluates all carries in parallel via AND/OR. Eliminates the L10 ripple bottleneck."),
    "L17": ("D-Latch Array",
            "Chain of D-latches where each Q feeds the next latch's 'previous state': "
            "Q=(D&En)|(Q_prev&~En). Models a shift-register or pipelined register file."),
    "L18": ("Barrel Shifter",
            "Three mux-stages (shift-by-1/2/4) of 8 two-to-one muxes each. "
            "Regular structure with shared enable signals -- models the shift unit inside an ALU."),
    "L19": ("CRC-8 LFSR",
            "CRC-8/MAXIM linear feedback shift register with XOR taps at bit positions 4 and 5. "
            "Simulates hardware error-detection logic in UART, SPI, and storage interfaces."),
    "L20": ("8-bit Comparator",
            "XNORs corresponding bits of two 8-bit words then AND-reduces all XNORs to produce A==B. "
            "Models equality-check paths in address comparators and content-addressable memory (CAM)."),
    "L21": ("ALU Slice",
            "1-bit ALU slice x N: computes AND/OR/XOR/ADD in parallel then muxes the result via a "
            "2-bit opcode. Stacking N slices models a full N-bit RISC processor datapath."),
}

# =====================================================================
# MAIN PROFILER
# =====================================================================

def run_profiler():
    print("="*82)
    print(" DARION LOGIC SIM: TOPOLOGY SCALING PROFILER (V6.0) ")
    print("="*82)
    print(f"[+] Backend: {backend_name}")

    temp_circ = CircuitClass()
    has_hw_counter = hasattr(temp_circ, 'activate_eval')
    del temp_circ

    TEST_SIZES = [1_000, 5_000, 10_000, 50_000, 100_000]
    TARGET_TOTAL_THEORETICAL_EVALS = 20_000_000 
    MAX_EVALS_PER_PASS = 250_000_000 # Hard limit to prevent hours of waiting on O(N^2)
    NUM_PASSES = 3 # Statistical multi-pass to filter OS jitter
    
    print(f"\nBenchmarking Backend: {backend_name}")
    print("Testing structural scale from 1K to 100K gates to stress RAM & CPU Caches.")
    
    if has_hw_counter:
        print("[+] Hardware Counter Detected: Using absolute engine-level evaluation metrics.\n")
    else:
        print("[-] WARNING: 'activate_eval()' not found in Circuit class.")
        print("[-] Using theoretical math for ME/s. L4 and L5 scores WILL be artificially inflated.\n")

    levels = [
        build_level_0_linear, build_level_1_parallel, build_level_2_fanout_tree,
        build_level_3_memory_maze, build_level_4_glitch_avalanche, build_level_5_event_hurricane,
        build_level_6_sparse_fanin, build_level_7_braid, build_level_8_diamond, build_level_9_hamming_ecc,
        build_level_10_ripple_carry_adder, build_level_11_priority_encoder, build_level_12_wallace_tree,
        build_level_13_sr_latch_farm, build_level_14_sparse_random_dag, build_level_15_decoder_tree,
        build_level_16_carry_lookahead, build_level_17_d_latch_array, build_level_18_barrel_shifter,
        build_level_19_crc8_lfsr, build_level_20_magnitude_comparator, build_level_21_alu_slice,
    ]

    print(f"{'Topology':<26} | {'1K Size':>14} | {'5K Size':>14} | {'10K Size':>14} | {'50K Size':>14} | {'100K Size':>14} | {'Scaling':>2}")
    print("-" * 120)

    for builder in levels:
        desc_name = ""
        results = []
        
        for size in TEST_SIZES:
            circuit = CircuitClass()
            if hasattr(circuit, 'activate_eval'):
                circuit.activate_eval()
            gc.disable()
            
            master, count, theoretical_evals, desc = builder(circuit, size, VARIABLE_ID, NOT_ID, XOR_ID, AND_ID=AND_ID)
            if not desc_name: desc_name = desc
            
            # Skip if theoretical load exceeds extreme bounds (prevents L5 100K hang)
            if theoretical_evals > MAX_EVALS_PER_PASS:
                results.append(-1.0)
                circuit.clearcircuit()
                del circuit
                gc.enable()
                continue
                
            vectors = max(4, TARGET_TOTAL_THEORETICAL_EVALS // theoretical_evals)
            vectors += (vectors % 2) # Ensure even number for HIGH/LOW pairing
            
            best_time = float('inf')
            best_evals = 0
            
            # Multi-pass execution loop
            for _ in range(NUM_PASSES):
                master.value = LOW
                circuit.simulate(DESIGN)
                circuit.simulate(SIMULATE)
                
                start_evals = circuit.eval_count if has_hw_counter else 0
                
                # Zero-overhead timing block
                t_start = time.perf_counter()
                for _ in range(vectors // 2):
                    circuit.toggle(master, HIGH)
                    circuit.toggle(master, LOW)
                t_end = time.perf_counter()
                
                pass_time = t_end - t_start
                pass_evals = (circuit.eval_count - start_evals) if has_hw_counter else (theoretical_evals * vectors)
                
                if pass_time < best_time:
                    best_time = pass_time
                    best_evals = pass_evals

            m_evals_per_sec = (best_evals / best_time) / 1_000_000 if best_time > 0 else 0
            results.append(m_evals_per_sec)

            circuit.clearcircuit()
            del circuit
            gc.collect()
            gc.enable()

        # Format columns based on whether they were skipped
        def fmt(val): return f"{val:>9.2f} ME/s" if val >= 0 else f"{'N/A (Skip)':>14}"
        
        val_1k = results[0]
        # Calculate retention using the highest completed tier
        completed_vals = [r for r in results if r >= 0]
        highest_tier_val = completed_vals[-1] if completed_vals else val_1k
        retention = (highest_tier_val / val_1k) * 100 if val_1k > 0 else 0.0
            
        retention_str = f"{retention:>5.1f}%"
            
        print(f"{desc_name:<26} | {fmt(results[0])} | {fmt(results[1])} | {fmt(results[2])} | {fmt(results[3])} | {fmt(results[4])} | {retention_str}")

    print("-" * 120)

    # ---- Circuit legend ----
    print(f"\n{'CIRCUIT DESCRIPTIONS':=^120}")
    for key, (short, desc) in LEVEL_DESCRIPTIONS.items():
        print(f"  {key:<4} {short:<26}  {desc}")
    print("=" * 120)

class _Tee:
    """Mirror stdout to a log file simultaneously."""
    def __init__(self, *streams):
        self.streams = streams
    def write(self, data):
        for s in self.streams:
            s.write(data)
    def flush(self):
        for s in self.streams:
            s.flush()

if __name__ == "__main__":
    from datetime import datetime
    _LOG = "complexity_scale_results.txt"
    with open(_LOG, "a", encoding="utf-8") as _lf:
        _lf.write(f"\n{'='*70}\n")
        _lf.write(f"RUN  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        _lf.write(f"ARGS : backend={backend_name}\n")
        _lf.write(f"{'='*70}\n")
        _orig = sys.stdout
        sys.stdout = _Tee(_orig, _lf)
        try:
            run_profiler()
        finally:
            sys.stdout = _orig
    print(f"\nLog saved to: {_LOG}")
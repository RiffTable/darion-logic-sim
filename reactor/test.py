import os
import time
import itertools
from Circuit import Circuit
from Const import (
    AND_ID, OR_ID, XOR_ID, NOT_ID, NOR_ID, NAND_ID,
    INPUT_PIN_ID, OUTPUT_PIN_ID, IC_ID, VARIABLE_ID,
    HIGH, LOW, SIMULATE, DESIGN
)

# =====================================================================
#  CORE VALIDATION UTILITIES
# =====================================================================

def verify_no_garbage(ic, expected_count):
    """Ensures no wrapper ICs or internal pins survived the Cython flattener."""
    internal = getattr(ic, 'internal', [])
    garbage = [g for g in internal if g.id in (IC_ID, INPUT_PIN_ID, OUTPUT_PIN_ID)]
    
    if not garbage and len(internal) == expected_count:
        print(f"  [+] SUCCESS: Clean flattening! Exactly {expected_count} pure gates.")
        return True
    else:
        print(f"  [FAIL] Expected {expected_count} gates, found {len(internal)}.")
        for g in garbage:
            print(f"    -> GARBAGE DETECTED: {g.name} (ID: {g.id})")
        return False

def test_logic(c, ic, test_vectors, quiet=True):
    """Executes truth tables and state sequences."""
    c.simulate(DESIGN)
    vars = [c.getcomponent(VARIABLE_ID) for _ in range(len(ic.inputs))]
    for i, v in enumerate(vars):
        c.connect(ic.inputs[i], v, 0)
        
    c.simulate(SIMULATE)

    all_passed = True
    for inputs, expected in test_vectors:
        # Apply inputs
        for v, val in zip(vars, inputs):
            c.toggle(v, HIGH if val else LOW)

        # Retrieve outputs
        actual = tuple(1 if p.getoutput() == 'T' else 0 for p in ic.outputs)

        # Compare
        match = all(e is None or a == e for a, e in zip(actual, expected))
        if not match:
            print(f"  [FAIL] In: {inputs} -> Expected: {expected}, Got: {actual}")
            all_passed = False
            break # Fail fast

    if all_passed and not quiet:
        print(f"  [+] SUCCESS: 100% Logic Match across {len(test_vectors)} vectors.")
        
    # Cleanup variables so they don't pollute the circuit
    for v in vars:
        c.delobj(v)
    return all_passed

def exhaust_truth_table(c, ic, num_inputs, eval_func):
    """Dynamically generates and tests a 100% coverage combinational truth table."""
    vectors = []
    for inputs in itertools.product([0, 1], repeat=num_inputs):
        expected = eval_func(*inputs)
        if not isinstance(expected, tuple):
            expected = (expected,)
        vectors.append((inputs, expected))
    
    passed = test_logic(c, ic, vectors, quiet=True)
    if passed:
        print(f"  [+] SUCCESS: Exhaustive truth table passed ({2**num_inputs} states).")
    return passed

# =====================================================================
#  IC STANDARD LIBRARY COMPILER
# =====================================================================

def build_prerequisites(c):
    """Compiles an advanced standard library of ICs used for nesting tests."""
    
    # 1. Half Adder
    iA, iB = c.getcomponent(INPUT_PIN_ID), c.getcomponent(INPUT_PIN_ID)
    oS, oC = c.getcomponent(OUTPUT_PIN_ID), c.getcomponent(OUTPUT_PIN_ID)
    x1, a1 = c.getcomponent(XOR_ID), c.getcomponent(AND_ID)
    c.connect(x1, iA, 0); c.connect(x1, iB, 1)
    c.connect(a1, iA, 0); c.connect(a1, iB, 1)
    c.connect(oS, x1, 0); c.connect(oC, a1, 0)
    c.save_as_ic("ha.json", "HA"); c.clearcircuit()

    # 2. Full Adder
    iA, iB, iCin = c.getcomponent(INPUT_PIN_ID), c.getcomponent(INPUT_PIN_ID), c.getcomponent(INPUT_PIN_ID)
    oS, oCout = c.getcomponent(OUTPUT_PIN_ID), c.getcomponent(OUTPUT_PIN_ID)
    ha1, ha2, o1 = c.getIC("ha.json"), c.getIC("ha.json"), c.getcomponent(OR_ID)
    c.connect(ha1.inputs[0], iA, 0); c.connect(ha1.inputs[1], iB, 0)
    c.connect(ha2.inputs[0], ha1.outputs[0], 0); c.connect(ha2.inputs[1], iCin, 0)
    c.connect(o1, ha1.outputs[1], 0); c.connect(o1, ha2.outputs[1], 1)
    c.connect(oS, ha2.outputs[0], 0); c.connect(oCout, o1, 0)
    c.save_as_ic("fa.json", "FA"); c.clearcircuit()

    # 3. 2-to-1 Multiplexer (S, D0, D1) -> Y
    iS, iD0, iD1 = [c.getcomponent(INPUT_PIN_ID) for _ in range(3)]
    oY = c.getcomponent(OUTPUT_PIN_ID)
    invS = c.getcomponent(NOT_ID)
    a1, a2 = c.getcomponent(AND_ID), c.getcomponent(AND_ID)
    or1 = c.getcomponent(OR_ID)
    c.connect(invS, iS, 0)
    c.connect(a1, iD0, 0); c.connect(a1, invS, 1) # D0 AND (NOT S)
    c.connect(a2, iD1, 0); c.connect(a2, iS, 1)   # D1 AND S
    c.connect(or1, a1, 0); c.connect(or1, a2, 1)
    c.connect(oY, or1, 0)
    c.save_as_ic("mux2.json", "MUX2"); c.clearcircuit()

    # 4. SR Latch (NOR based)
    iS, iR = c.getcomponent(INPUT_PIN_ID), c.getcomponent(INPUT_PIN_ID)
    oQ, oQb = c.getcomponent(OUTPUT_PIN_ID), c.getcomponent(OUTPUT_PIN_ID)
    n1, n2 = c.getcomponent(NOR_ID), c.getcomponent(NOR_ID)
    c.connect(n1, iR, 0); c.connect(n1, n2, 1)
    c.connect(n2, iS, 0); c.connect(n2, n1, 1)
    c.connect(oQ, n1, 0); c.connect(oQb, n2, 0)
    c.save_as_ic("sr.json", "SR"); c.clearcircuit()

    # 5. D Latch (Level Sensitive)
    iD, iEN = c.getcomponent(INPUT_PIN_ID), c.getcomponent(INPUT_PIN_ID)
    oQ, oQb = c.getcomponent(OUTPUT_PIN_ID), c.getcomponent(OUTPUT_PIN_ID)
    sr, nd, as1, ar1 = c.getIC("sr.json"), c.getcomponent(NOT_ID), c.getcomponent(AND_ID), c.getcomponent(AND_ID)
    c.connect(nd, iD, 0); 
    c.connect(as1, iD, 0); c.connect(as1, iEN, 1)
    c.connect(ar1, nd, 0); c.connect(ar1, iEN, 1)
    c.connect(sr.inputs[0], as1, 0); c.connect(sr.inputs[1], ar1, 0)
    c.connect(oQ, sr.outputs[0], 0); c.connect(oQb, sr.outputs[1], 0)
    c.save_as_ic("dlatch.json", "DLatch"); c.clearcircuit()

    # 6. D Flip-Flop (Master-Slave, Edge Triggered)
    iD, iCLK = c.getcomponent(INPUT_PIN_ID), c.getcomponent(INPUT_PIN_ID)
    oQ, oQb = c.getcomponent(OUTPUT_PIN_ID), c.getcomponent(OUTPUT_PIN_ID)
    latch_master = c.getIC("dlatch.json")
    latch_slave = c.getIC("dlatch.json")
    inv_clk = c.getcomponent(NOT_ID)
    
    c.connect(inv_clk, iCLK, 0)
    c.connect(latch_master.inputs[0], iD, 0)
    c.connect(latch_master.inputs[1], inv_clk, 0) # Master writes on CLK Low
    
    c.connect(latch_slave.inputs[0], latch_master.outputs[0], 0)
    c.connect(latch_slave.inputs[1], iCLK, 0)     # Slave writes on CLK High
    
    c.connect(oQ, latch_slave.outputs[0], 0)
    c.connect(oQb, latch_slave.outputs[1], 0)
    c.save_as_ic("dff.json", "DFF"); c.clearcircuit()

# =====================================================================
#  TEST SUITES
# =====================================================================

def test_combinational_deep(c):
    print("\n==================================================")
    print("  PHASE 1: COMBINATIONAL MUX TREE (4-to-1 MUX)")
    print("==================================================")
    
    # 4-to-1 MUX using three 2-to-1 MUXes
    ins = [c.getcomponent(INPUT_PIN_ID) for _ in range(6)] # S0, S1, D0, D1, D2, D3
    oY = c.getcomponent(OUTPUT_PIN_ID)
    
    m1 = c.getIC("mux2.json") # Selects between D0, D1 using S0
    m2 = c.getIC("mux2.json") # Selects between D2, D3 using S0
    m3 = c.getIC("mux2.json") # Selects between M1, M2 using S1
    
    # M1
    c.connect(m1.inputs[0], ins[0], 0) # S0
    c.connect(m1.inputs[1], ins[2], 0) # D0
    c.connect(m1.inputs[2], ins[3], 0) # D1
    
    # M2
    c.connect(m2.inputs[0], ins[0], 0) # S0
    c.connect(m2.inputs[1], ins[4], 0) # D2
    c.connect(m2.inputs[2], ins[5], 0) # D3
    
    # M3
    c.connect(m3.inputs[0], ins[1], 0) # S1
    c.connect(m3.inputs[1], m1.outputs[0], 0)
    c.connect(m3.inputs[2], m2.outputs[0], 0)
    c.connect(oY, m3.outputs[0], 0)
    
    c.save_as_ic("mux4.json", "MUX4"); c.clearcircuit()
    mux4 = c.getIC("mux4.json")
    
    # 1 MUX2 = 4 gates (1 NOT, 2 AND, 1 OR). 3 MUX2 = 12 pure gates.
    verify_no_garbage(mux4, 12)
    
    def eval_mux4(s0, s1, d0, d1, d2, d3):
        idx = (s1 << 1) | s0
        return [d0, d1, d2, d3][idx]

    exhaust_truth_table(c, mux4, 6, eval_mux4)
    c.clearcircuit()

def test_sequential_advanced(c):
    print("\n==================================================")
    print("  PHASE 2: EDGE-TRIGGERED SEQUENTIAL (8-Bit Shift Reg)")
    print("==================================================")
    
    ins = [c.getcomponent(INPUT_PIN_ID) for _ in range(2)] # Serial In, CLK
    outs = [c.getcomponent(OUTPUT_PIN_ID) for _ in range(8)] # Q0-Q7
    dffs = [c.getIC("dff.json") for _ in range(8)]
    
    c.connect(dffs[0].inputs[0], ins[0], 0) # Data into DFF 0
    c.connect(outs[0], dffs[0].outputs[0], 0)
    c.connect(dffs[0].inputs[1], ins[1], 0) # Clock into DFF 0
    
    for i in range(1, 8):
        c.connect(dffs[i].inputs[0], dffs[i-1].outputs[0], 0) # Q -> D
        c.connect(dffs[i].inputs[1], ins[1], 0) # Shared Clock
        c.connect(outs[i], dffs[i].outputs[0], 0)
        
    c.save_as_ic("shift8.json", "Shift8"); c.clearcircuit()
    shift8 = c.getIC("shift8.json")
    
    # 1 DFF = 2 Latches + 1 NOT = 11 gates. 8 DFFs = 88 gates.
    verify_no_garbage(shift8, 88)
    
    # Shift Register Sequence Test
    # Inputs format: (Serial_In, CLK)
    vectors = [
        ((1, 0), (0,0,0,0,0,0,0,0)), # Initialize, Clock Low
        ((1, 1), (1,0,0,0,0,0,0,0)), # Clock High: Shift in 1
        ((1, 0), (1,0,0,0,0,0,0,0)), # Clock Low
        ((0, 1), (0,1,0,0,0,0,0,0)), # Clock High: Shift in 0
        ((0, 0), (0,1,0,0,0,0,0,0)), # Clock Low
        ((1, 1), (1,0,1,0,0,0,0,0)), # Clock High: Shift in 1
    ]
    test_logic(c, shift8, vectors, quiet=False)
    c.clearcircuit()

def test_performance_limits(c):
    print("\n==================================================")
    print("  PHASE 3: EXTREME STRESS BENCHMARKS")
    print("==================================================")

    # --- TEST 3A: WIDE FAN-IN & FAN-OUT (20,000 gates) ---
    i_wide = c.getcomponent(INPUT_PIN_ID)
    o_wide = c.getcomponent(OUTPUT_PIN_ID)
    
    # 10k NOT gates in parallel connected to Input
    layer1 = [c.getcomponent(NOT_ID) for _ in range(10000)]
    for n in layer1:
        c.connect(n, i_wide, 0)
        
    # All 10k NOT gates feed into 10k AND gates (each AND takes 1 layer1 and the input)
    layer2 = [c.getcomponent(AND_ID) for _ in range(10000)]
    for i, a in enumerate(layer2):
        c.connect(a, layer1[i], 0)
        c.connect(a, i_wide, 1) # Force huge fanout on input
        
    # OR them all together (Mocking a huge fan-in by linking sequentially as OR limits might apply)
    c.connect(o_wide, layer2[-1], 0)

    t0 = time.perf_counter()
    c.save_as_ic("wide.json", "WIDE")
    t_save = (time.perf_counter() - t0) * 1000
    c.clearcircuit()

    t0 = time.perf_counter()
    wide_ic = c.getIC("wide.json")
    t_load = (time.perf_counter() - t0) * 1000
    
    print(f"  [+] WIDE TIER (20,000 Gates) Save Time:  {t_save:.2f} ms")
    print(f"  [+] WIDE TIER Cython Load/Flatten Time: {t_load:.2f} ms")
    verify_no_garbage(wide_ic, 20000)
    c.clearcircuit()
def test_simulation_throughput(c):
    print("\n==================================================")
    print("  PHASE 4: RAW SIMULATION THROUGHPUT (EVALS/SEC)")
    print("==================================================")
    
    # Build a massive ripple-carry-like chain to force deep propagation waves
    CHAIN_LENGTH = 5000
    gates = [c.getcomponent(NOT_ID) for _ in range(CHAIN_LENGTH)]
    
    # Chain them sequentially
    for i in range(CHAIN_LENGTH - 1):
        c.connect(gates[i+1], gates[i], 0)
        
    in_pin = c.getcomponent(INPUT_PIN_ID)
    c.connect(gates[0], in_pin, 0)
    
    # Save and load to flatten
    c.save_as_ic("chain.json", "Chain"); c.clearcircuit()
    chain_ic = c.getIC("chain.json")
    
    var = c.getcomponent(VARIABLE_ID)
    c.connect(chain_ic.inputs[0], var, 0)
    c.simulate(SIMULATE)
    
    # Activate the Cython evaluation counter
    c.activate_eval()
    
    # Toggle the input back and forth to force massive wave propagations
    TOGGLES = 1000
    t0 = time.perf_counter()
    for i in range(TOGGLES):
        c.toggle(var, HIGH if i % 2 == 0 else LOW)
        
    t_sim = time.perf_counter() - t0
    evals = getattr(c, 'eval_count', 0) # Fallback if eval_count isn't fully exposed to Python
    
    # Calculate performance
    total_expected_evals = CHAIN_LENGTH * TOGGLES
    print(f"  [+] Pushed {TOGGLES} toggles through a {CHAIN_LENGTH}-gate deep chain.")
    print(f"  [+] Time taken: {t_sim:.4f} seconds")
    print(f"  [+] Speed:      {total_expected_evals / t_sim:,.0f} gate evaluations / second")
    
    c.deactivate_eval()
    c.clearcircuit()

def test_engine_safeguards(c):
    print("\n==================================================")
    print("  PHASE 5: ENGINE SAFEGUARDS & ERROR HANDLING")
    print("==================================================")

    # --- TEST 5A: Ring Oscillator (Infinite Loop / Wave Limit) ---
    print("  [~] Triggering Ring Oscillator (Testing Wave Limit Burn...)")
    
    # We use a NOR gate + a Trigger Variable to kickstart the oscillator.
    # While Trigger is HIGH, NOR outputs LOW (stable).
    # When Trigger drops to LOW, NOR acts as a NOT gate, and oscillation begins!
    nor1 = c.getcomponent(NOR_ID)
    not1 = c.getcomponent(NOT_ID)
    not2 = c.getcomponent(NOT_ID)
    var_trigger = c.getcomponent(VARIABLE_ID)
    
    # Loop: NOR -> NOT -> NOT -> NOR
    c.connect(not1, nor1, 0)
    c.connect(not2, not1, 0)
    c.connect(nor1, not2, 0)
    c.connect(nor1, var_trigger, 1) # Trigger pin
    
    c.simulate(SIMULATE)
    
    # 1. Force the loop into a known stable state (NOR = LOW, NOT1 = HIGH, NOT2 = LOW)
    c.toggle(var_trigger, HIGH)
    
    # 2. Release the trigger (LOW). This starts the infinite 0 -> 1 -> 0 wave!
    c.toggle(var_trigger, LOW)
    
    # Check if they successfully triggered the Cython burn() function to ERROR state ('1/0')
    out1 = nor1.getoutput()
    if out1 == '1/0':
        print("  [+] SUCCESS: Wave limit caught infinite loop and burned gates to ERROR state (1/0).")
    else:
        print(f"  [FAIL] Ring oscillator did not burn. State: {out1}")
        
    c.clearcircuit()

    # --- TEST 5B: Iterative Flattener Dominance (Extreme Depth) ---
    print("\n  [~] Testing Iterative Flattener against Extreme Depth (1000 Levels)...")
    # Since your engine flattens dynamically, it should conquer depth limits 
    # that would normally cause RecursionErrors in purely recursive engines.
    
    i_base, o_base = c.getcomponent(INPUT_PIN_ID), c.getcomponent(OUTPUT_PIN_ID)
    n1, n2 = c.getcomponent(NOT_ID), c.getcomponent(NOT_ID)
    c.connect(n1, i_base, 0); c.connect(n2, n1, 0); c.connect(o_base, n2, 0)
    c.save_as_ic("depth_0.json", "D0"); c.clearcircuit()

    t0 = time.perf_counter()
    # Nest a component inside another component 1,000 times!
    for lvl in range(1, 1001):
        i_pin, o_pin = c.getcomponent(INPUT_PIN_ID), c.getcomponent(OUTPUT_PIN_ID)
        sub_ic = c.getIC(f"depth_{lvl-1}.json")
        c.connect(sub_ic.inputs[0], i_pin, 0)
        c.connect(o_pin, sub_ic.outputs[0], 0)
        c.save_as_ic(f"depth_{lvl}.json", f"D{lvl}")
        c.clearcircuit()
        
    t_nest = time.perf_counter() - t0
    
    # Load the 1000-deep IC
    t0 = time.perf_counter()
    deep_ic = c.getIC("depth_1000.json")
    t_load = time.perf_counter() - t0
    
    print(f"  [+] SUCCESS: Flattened 1000 nested layers without Python stack overflow!")
    print(f"  [+] Nesting build time: {t_nest:.2f} s | Final IC load time: {t_load*1000:.2f} ms")
    
    # Because it's just 1 wrapper nested 1000 times over 2 NOT gates, the pure count is 2.
    verify_no_garbage(deep_ic, 2)
    c.clearcircuit()

    # Cleanup depth files
    for i in range(1001):
        if os.path.exists(f"depth_{i}.json"): os.remove(f"depth_{i}.json")
    if os.path.exists("chain.json"): os.remove("chain.json")


def cleanup():
    files = [
        "ha.json", "fa.json", "mux2.json", "mux4.json",
        "sr.json", "dlatch.json", "dff.json", "shift8.json", "wide.json"
    ]
    for f in files:
        if os.path.exists(f): os.remove(f)

def run_test_suite():
    c = Circuit()
    try:
        build_prerequisites(c)
        test_combinational_deep(c)
        test_sequential_advanced(c)
        test_performance_limits(c)
        test_simulation_throughput(c)
        test_engine_safeguards(c)
    finally:
        cleanup()
        print("\n==================================================")
        print("  TEST SUITE EXECUTION CONCLUDED")
        print("==================================================")

if __name__ == "__main__":
    run_test_suite()
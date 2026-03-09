import sys
import os
import time
import gc

# Ensure imports work whether run from root or inside the engine directory
if os.path.exists('engine'):
    sys.path.append('engine')
elif os.path.exists('Circuit.py'):
    sys.path.append('.')

from Circuit import Circuit
from Const import *

# ─── Utility Functions ────────────────────────────────────────────────────────

def assert_eq(actual, expected, context=""):
    if actual != expected:
        raise AssertionError(f"FAIL: Expected {expected}, got {actual}. Context: {context}")

def test_truth_table(c, vars_list, probes_list, truth_data):
    """
    Helper to test a circuit's truth table.
    truth_data is a list of tuples: ((inputs...), (expected_outputs...))
    """
    for inputs, expected in truth_data:
        for v, val in zip(vars_list, inputs):
            c.toggle(v, val)
        c.simulate(SIMULATE)
        
        for p, exp in zip(probes_list, expected):
            assert_eq(p.output, exp, f"Inputs {inputs}")

def cleanup_files(*filenames):
    """Deletes the JSON artifacts generated during testing."""
    for f in filenames:
        if os.path.exists(f):
            os.remove(f)

# ─── Test Cases ───────────────────────────────────────────────────────────────

def test_simple_circuit():
    print("Running Test 1: Simple Circuit (AND Gate) ...", end=" ")
    c = Circuit()
    v1 = c.getcomponent(VARIABLE_ID)
    v2 = c.getcomponent(VARIABLE_ID)
    and_gate = c.getcomponent(AND_ID)
    probe = c.getcomponent(PROBE_ID)

    c.connect(and_gate, v1, 0)
    c.connect(and_gate, v2, 1)
    c.connect(probe, and_gate, 0)

    # Save to IC
    c.save_as_ic("simple_and.json", "SimpleAND", "", "", None)
    
    # Reload the IC into a fresh circuit
    c2 = Circuit()
    ic = c2.getIC("simple_and.json")
    nv1 = c2.getcomponent(VARIABLE_ID)
    nv2 = c2.getcomponent(VARIABLE_ID)
    nprobe = c2.getcomponent(PROBE_ID)

    c2.connect(ic.inputs[0], nv1, 0)
    c2.connect(ic.inputs[1], nv2, 0)
    c2.connect(nprobe, ic.outputs[0], 0)

    test_truth_table(c2, [nv1, nv2], [nprobe], [
        ((0, 0), (0,)),
        ((0, 1), (0,)),
        ((1, 0), (0,)),
        ((1, 1), (1,)),
    ])
    print("PASSED")

def test_sandboxing():
    print("Running Test 2: Sandboxing (Partial IC Save) ...", end=" ")
    c = Circuit()
    v1 = c.getcomponent(VARIABLE_ID)
    v2 = c.getcomponent(VARIABLE_ID)
    v3 = c.getcomponent(VARIABLE_ID) 

    or_gate = c.getcomponent(OR_ID)
    and_gate = c.getcomponent(AND_ID) 
    
    p_or = c.getcomponent(PROBE_ID)
    p_and = c.getcomponent(PROBE_ID) 

    # Sandbox Group: v1, v2 -> OR -> p_or
    c.connect(or_gate, v1, 0)
    c.connect(or_gate, v2, 1)
    c.connect(p_or, or_gate, 0)

    # Extraneous Group: v2, v3 -> AND -> p_and
    c.connect(and_gate, v2, 0)
    c.connect(and_gate, v3, 1)
    c.connect(p_and, and_gate, 0)

    # Save ONLY the OR-gate setup as an IC
    selected_components = [v1, v2, or_gate, p_or]
    c.save_as_ic("sandbox_or.json", "SandboxOR", "", "", selected_components)

    # Verify original circuit is still intact
    c.toggle(v2, 1)
    c.toggle(v3, 1)
    c.simulate(SIMULATE)
    assert_eq(p_and.output, 1, "Original circuit was corrupted during partial save!")

    # Verify the saved partial IC
    c2 = Circuit()
    ic = c2.getIC("sandbox_or.json")
    nv1 = c2.getcomponent(VARIABLE_ID)
    nv2 = c2.getcomponent(VARIABLE_ID)
    nprobe = c2.getcomponent(PROBE_ID)

    c2.connect(ic.inputs[0], nv1, 0)
    c2.connect(ic.inputs[1], nv2, 0)
    c2.connect(nprobe, ic.outputs[0], 0)

    test_truth_table(c2, [nv1, nv2], [nprobe], [
        ((0, 0), (0,)),
        ((0, 1), (1,)),
        ((1, 0), (1,)),
        ((1, 1), (1,)),
    ])
    print("PASSED")

def test_nested_ic():
    print("Running Test 3: Complex & Nested IC (Full Adder) ...", end=" ")
    
    # 1. Build a Half Adder
    c = Circuit()
    ha_a = c.getcomponent(VARIABLE_ID)
    ha_b = c.getcomponent(VARIABLE_ID)
    ha_xor = c.getcomponent(XOR_ID)
    ha_and = c.getcomponent(AND_ID)
    ha_sum = c.getcomponent(PROBE_ID)
    ha_carry = c.getcomponent(PROBE_ID)

    c.connect(ha_xor, ha_a, 0)
    c.connect(ha_xor, ha_b, 1)
    c.connect(ha_and, ha_a, 0)
    c.connect(ha_and, ha_b, 1)
    c.connect(ha_sum, ha_xor, 0)
    c.connect(ha_carry, ha_and, 0)
    c.save_as_ic("half_adder.json", "HalfAdder", "", "", None)

    # 2. Build a Full Adder using two Half Adders
    c2 = Circuit()
    a = c2.getcomponent(VARIABLE_ID)
    b = c2.getcomponent(VARIABLE_ID)
    cin = c2.getcomponent(VARIABLE_ID)
    
    ha1 = c2.getIC("half_adder.json")
    ha2 = c2.getIC("half_adder.json")
    or_gate = c2.getcomponent(OR_ID)
    
    sum_out = c2.getcomponent(PROBE_ID)
    cout_out = c2.getcomponent(PROBE_ID)

    c2.connect(ha1.inputs[0], a, 0)
    c2.connect(ha1.inputs[1], b, 0)
    
    c2.connect(ha2.inputs[0], ha1.outputs[0], 0)
    c2.connect(ha2.inputs[1], cin, 0)
    
    c2.connect(or_gate, ha1.outputs[1], 0)
    c2.connect(or_gate, ha2.outputs[1], 1)
    
    c2.connect(sum_out, ha2.outputs[0], 0)
    c2.connect(cout_out, or_gate, 0)

    c2.save_as_ic("full_adder.json", "FullAdder", "", "", None)

    # 3. Load the Full Adder and verify Truth Table
    c3 = Circuit()
    fa_ic = c3.getIC("full_adder.json")
    t_a = c3.getcomponent(VARIABLE_ID)
    t_b = c3.getcomponent(VARIABLE_ID)
    t_cin = c3.getcomponent(VARIABLE_ID)
    t_sum = c3.getcomponent(PROBE_ID)
    t_cout = c3.getcomponent(PROBE_ID)

    c3.connect(fa_ic.inputs[0], t_a, 0)
    c3.connect(fa_ic.inputs[1], t_b, 0)
    c3.connect(fa_ic.inputs[2], t_cin, 0)
    c3.connect(t_sum, fa_ic.outputs[0], 0)
    c3.connect(t_cout, fa_ic.outputs[1], 0)

    test_truth_table(c3, [t_a, t_b, t_cin], [t_sum, t_cout], [
        ((0, 0, 0), (0, 0)),
        ((0, 0, 1), (1, 0)),
        ((0, 1, 0), (1, 0)),
        ((0, 1, 1), (0, 1)),
        ((1, 0, 0), (1, 0)),
        ((1, 0, 1), (0, 1)),
        ((1, 1, 0), (0, 1)),
        ((1, 1, 1), (1, 1)),
    ])
    print("PASSED")

def benchmark_ic_vs_raw():
    print("Running Test 4: Benchmark (Raw vs IC - 1000 NOT Gates) ...")
    GATE_COUNT = 1000
    ITERATIONS = 5000 
    WARMUP = 200

    # -- RAW BENCHMARK --
    c_raw = Circuit()
    var_raw = c_raw.getcomponent(VARIABLE_ID)
    probe_raw = c_raw.getcomponent(PROBE_ID)

    prev = var_raw
    for _ in range(GATE_COUNT):
        not_g = c_raw.getcomponent(NOT_ID)
        c_raw.connect(not_g, prev, 0)
        prev = not_g
    c_raw.connect(probe_raw, prev, 0)

    for i in range(WARMUP):
        c_raw.toggle(var_raw, i % 2)

    gc.disable() 
    start_raw = time.perf_counter()
    for i in range(ITERATIONS):
        c_raw.toggle(var_raw, i % 2)
    time_raw = time.perf_counter() - start_raw
    gc.enable()
    
    print(f"  -> Raw Chain processing time: {time_raw:.5f}s")
    c_raw.save_as_ic("bench_chain.json", "NotChain", "", "", None)

    # -- IC BENCHMARK --
    c_ic = Circuit()
    var_ic = c_ic.getcomponent(VARIABLE_ID)
    probe_ic = c_ic.getcomponent(PROBE_ID)
    ic_chip = c_ic.getIC("bench_chain.json")

    c_ic.connect(ic_chip.inputs[0], var_ic, 0)
    c_ic.connect(probe_ic, ic_chip.outputs[0], 0)

    for i in range(WARMUP):
        c_ic.toggle(var_ic, i % 2)

    gc.disable()
    start_ic = time.perf_counter()
    for i in range(ITERATIONS):
        c_ic.toggle(var_ic, i % 2)
    time_ic = time.perf_counter() - start_ic
    gc.enable()
    
    print(f"  -> Wrapped IC processing time: {time_ic:.5f}s")
    diff = abs(time_ic - time_raw) / max(time_raw, 0.0001) * 100
    print(f"  -> Performance Diff: {diff:.2f}%")
    print("PASSED (Benchmark Complete)\n")

def test_invalid_pin_exceptions():
    print("Running Test 5: Invalid Pin Exceptions (Guardrails) ...", end=" ")
    c1 = Circuit()
    v = c1.getcomponent(VARIABLE_ID)
    in_pin = c1.getcomponent(INPUT_PIN_ID)
    c1.connect(in_pin, v, 0)
    try:
        c1.save_as_ic("should_fail_in.json", "FailInIC", "", "", None)
        raise AssertionError("Failed to catch illegal Input Pin source!")
    except ValueError as e:
        assert "Input Pin has extra sources" in str(e)
        
    c2 = Circuit()
    out_pin = c2.getcomponent(OUTPUT_PIN_ID)
    probe = c2.getcomponent(PROBE_ID)
    c2.connect(probe, out_pin, 0)
    try:
        c2.save_as_ic("should_fail_out.json", "FailOutIC", "", "", None)
        raise AssertionError("Failed to catch illegal Output Pin target!")
    except ValueError as e:
        assert "Output Pin has extra targets" in str(e)
    print("PASSED")

def test_feedback_loop():
    print("Running Test 6: Stateful Feedback Loop (SR Latch) ...", end=" ")
    c = Circuit()
    s = c.getcomponent(VARIABLE_ID) # inputs[0]
    r = c.getcomponent(VARIABLE_ID) # inputs[1]
    
    nor1 = c.getcomponent(NOR_ID)
    nor2 = c.getcomponent(NOR_ID)
    q = c.getcomponent(PROBE_ID)       # outputs[0]
    not_q = c.getcomponent(PROBE_ID)   # outputs[1]

    c.connect(nor1, r, 0)
    c.connect(nor2, s, 1)
    c.connect(nor1, nor2, 1)
    c.connect(nor2, nor1, 0)
    c.connect(q, nor1, 0)
    c.connect(not_q, nor2, 0)

    c.save_as_ic("sr_latch.json", "SR_Latch", "", "", None)

    c2 = Circuit()
    ic = c2.getIC("sr_latch.json")
    t_s = c2.getcomponent(VARIABLE_ID)
    t_r = c2.getcomponent(VARIABLE_ID)
    t_q = c2.getcomponent(PROBE_ID)

    c2.connect(ic.inputs[0], t_s, 0) 
    c2.connect(ic.inputs[1], t_r, 0) 
    c2.connect(t_q, ic.outputs[0], 0)

    c2.simulate(SIMULATE)

    # Set (S=1, R=0)
    c2.toggle(t_r, 0)
    c2.toggle(t_s, 1)
    assert_eq(t_q.output, 1, "SR Latch failed to Set")

    # Hold (S=0, R=0)
    c2.toggle(t_s, 0)
    assert_eq(t_q.output, 1, "SR Latch failed to Hold memory")
    
    # Reset (S=0, R=1)
    c2.toggle(t_r, 1)
    assert_eq(t_q.output, 0, "SR Latch failed to Reset")
    print("PASSED")

def test_empty_and_floating():
    print("Running Test 7: Empty and Floating circuits (Pruning Check) ...", end=" ")
    c = Circuit()
    c.save_as_ic("empty.json", "EmptyIC", "", "", None)
    c2 = Circuit()
    ic_empty = c2.getIC("empty.json")
    assert len(ic_empty.inputs) == 0, "Empty IC should have 0 inputs"
    assert len(ic_empty.internal) == 0, "Empty IC should have 0 internal gates"
    
    c3 = Circuit()
    v = c3.getcomponent(VARIABLE_ID)
    a = c3.getcomponent(AND_ID)
    p = c3.getcomponent(PROBE_ID)
    c3.save_as_ic("floating.json", "FloatingIC", "", "", None)
    
    c4 = Circuit()
    ic_floating = c4.getIC("floating.json")
    assert len(ic_floating.inputs) == 1, "Floating Var did not become Input"
    assert len(ic_floating.outputs) == 1, "Floating Probe did not become Output"
    
    # The Darion Engine's build_ic() performs a graph traversal from Inputs/Outputs.
    # Therefore, gates with ZERO connections are completely ignored and pruned from the IC.
    assert len(ic_floating.internal) == 0, "Floating AND gate should have been pruned!"
    print("PASSED")

def test_sandbox_severed_wires():
    print("Running Test 8: Sandboxing with severed wires (Pruning aware) ...", end=" ")
    c = Circuit()
    v1 = c.getcomponent(VARIABLE_ID)
    v2 = c.getcomponent(VARIABLE_ID)
    and_gate = c.getcomponent(AND_ID)
    probe = c.getcomponent(PROBE_ID)

    c.connect(and_gate, v1, 0)
    c.connect(and_gate, v2, 1)
    c.connect(probe, and_gate, 0)

    # Sandbox v1 and the AND gate. 
    # v2 (source) and probe (target) are excluded, severing their wires.
    c.save_as_ic("severed.json", "SeveredIC", "", "", [v1, and_gate])
    
    c2 = Circuit()
    ic = c2.getIC("severed.json")
    
    # Verify the IO interface adjusted properly
    assert len(ic.inputs) == 1, "Should have 1 Input (from v1)"
    assert len(ic.outputs) == 0, "Should have 0 Outputs (probe was severed)"
    
    # Because we included v1, the engine's BFS traverses v1 -> AND gate.
    assert len(ic.internal) == 1, "AND gate should be internal"
    
    # Verify the severed wire correctly became a floating pin (None) without crashing
    internal_and = ic.internal[0]
    assert internal_and.sources[0] is not None, "Pin 0 should be connected to the Input"
    assert internal_and.sources[1] is None, "Pin 1 should be severed (None)"
    
    print("PASSED")

def test_sandbox_nested_ic():
    print("Running Test 9: Sandboxing a Nested IC ...", end=" ")
    
    # 1. Create a simple inner IC (Just a NOT gate)
    c_inner = Circuit()
    v_in = c_inner.getcomponent(VARIABLE_ID)
    not_g = c_inner.getcomponent(NOT_ID)
    p_out = c_inner.getcomponent(PROBE_ID)
    c_inner.connect(not_g, v_in, 0)
    c_inner.connect(p_out, not_g, 0)
    c_inner.save_as_ic("inner_not.json", "InnerNot", "", "", None)
    
    # 2. Build a circuit containing the Inner IC + other gates
    c = Circuit()
    v1 = c.getcomponent(VARIABLE_ID)
    v2 = c.getcomponent(VARIABLE_ID)
    inner_ic = c.getIC("inner_not.json")
    and_gate = c.getcomponent(AND_ID)
    probe = c.getcomponent(PROBE_ID)
    
    # Connections:
    # v1 -> inner_ic -> AND
    # v2 -------------> AND -> probe
    c.connect(inner_ic.inputs[0], v1, 0)
    c.connect(and_gate, inner_ic.outputs[0], 0)
    c.connect(and_gate, v2, 1)
    c.connect(probe, and_gate, 0)
    
    # FIX: We MUST include v1 and v2 so the Darion engine converts them 
    # into the Input Pins of the new IC. 
    c.save_as_ic("sandbox_nested.json", "SandboxNested", "", "", [v1, v2, inner_ic, and_gate, probe])
    
    # 3. Load the Sandbox IC
    c3 = Circuit()
    sand_ic = c3.getIC("sandbox_nested.json")
    nv1 = c3.getcomponent(VARIABLE_ID)
    nv2 = c3.getcomponent(VARIABLE_ID)
    nprobe = c3.getcomponent(PROBE_ID)
    
    # Because v1 and v2 were included, the IC correctly has 2 inputs.
    c3.connect(sand_ic.inputs[0], nv1, 0)
    c3.connect(sand_ic.inputs[1], nv2, 0)
    c3.connect(nprobe, sand_ic.outputs[0], 0)
    
    # Truth Table: Out = (NOT v1) AND v2
    test_truth_table(c3, [nv1, nv2], [nprobe], [
        ((0, 0), (0,)),
        ((0, 1), (1,)), # NOT(0) AND 1 = 1
        ((1, 0), (0,)),
        ((1, 1), (0,)), # NOT(1) AND 1 = 0
    ])
    
    print("PASSED")

def test_partially_connected_gates():
    print("Running Test 10: Partially Connected/Floating Internal Gates ...", end=" ")
    c = Circuit()
    v = c.getcomponent(VARIABLE_ID)
    and_gate = c.getcomponent(AND_ID)
    probe = c.getcomponent(PROBE_ID)
    
    c.connect(and_gate, v, 0) # Pin 1 is left floating
    c.connect(probe, and_gate, 0)
    
    c.save_as_ic("partial_and.json", "PartialAnd", "", "", None)
    
    c2 = Circuit()
    ic = c2.getIC("partial_and.json")
    tv = c2.getcomponent(VARIABLE_ID)
    tp = c2.getcomponent(PROBE_ID)
    
    c2.connect(ic.inputs[0], tv, 0)
    c2.connect(tp, ic.outputs[0], 0)
    
    c2.toggle(tv, 1)
    c2.simulate(SIMULATE)
    
    assert ic.outputs[0].output in [0, 2, 3], f"Floating AND gate output unexpected: {ic.outputs[0].output}"
    print("PASSED")


# ─── Execute Tests ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("==================================================")
    print("         CIRCUIT ENGINE IC TEST SUITE             ")
    print("==================================================\n")
    
    try:
        test_simple_circuit()
        test_sandboxing()
        test_nested_ic()
        benchmark_ic_vs_raw()
        test_invalid_pin_exceptions()
        test_feedback_loop()
        test_empty_and_floating()
        test_sandbox_severed_wires()
        test_sandbox_nested_ic()
        test_partially_connected_gates()
        
        print("\n✅ ALL 10 TESTS COMPLETED SUCCESSFULLY!")
    finally:
        # Cleanup all JSON artifacts generated during testing
        cleanup_files(
            "simple_and.json", 
            "sandbox_or.json", 
            "half_adder.json", 
            "full_adder.json", 
            "bench_chain.json",
            "should_fail_in.json",
            "should_fail_out.json",
            "sr_latch.json",
            "empty.json",
            "floating.json",
            "severed.json",
            "inner_not.json",
            "sandbox_nested.json",
            "partial_and.json"
        )
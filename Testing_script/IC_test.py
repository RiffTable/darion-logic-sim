import sys
import os
import time
import json
import tempfile
import argparse

# Parse arguments for reactor selection
parser = argparse.ArgumentParser(description='Run IC Tests')
parser.add_argument('--reactor', action='store_true', help='Use Cython reactor backend')
parser.add_argument('--engine', action='store_true', help='Use Python engine backend')
args, unknown = parser.parse_known_args()

base_dir = os.getcwd()
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)

# Add control to path
sys.path.append(os.path.join(root_dir, 'control'))

use_reactor = False

if args.reactor:
    use_reactor = True
elif args.engine:
    use_reactor = False
else:
    # Default to engine for automated testing
    use_reactor = False

if use_reactor:
    print("Using Reactor (Cython) Backend")
    sys.path.insert(0, os.path.join(root_dir, 'reactor'))
else:
    print("Using Engine (Python) Backend")
    sys.path.insert(0, os.path.join(root_dir, 'engine'))

try:
    from Circuit import Circuit
    from IC import IC
    from Const import IC_ID, INPUT_PIN_ID, OUTPUT_PIN_ID
    from Const import NOT_ID, AND_ID, NAND_ID, OR_ID, NOR_ID, XOR_ID, XNOR_ID, VARIABLE_ID
    from Const import HIGH, LOW, UNKNOWN, ERROR, SIMULATE, set_MODE
except ImportError as e:
    print(f"FATAL ERROR: Could not import backend modules: {e}")
    if args.reactor:
        print("Ensure you have built the reactor (python setup.py build_ext --inplace)")
    sys.exit(1)

from Control import Delete


class ThoroughICTest:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests_run = 0
        self.log_file = "test_ic_results.txt"
        with open(self.log_file, 'w') as f:
            f.write("IC THOROUGH TEST REPORT\n")
            f.write("=======================\n")

    def log(self, msg):
        print(msg)
        with open(self.log_file, 'a') as f:
            f.write(msg + "\n")

    def assert_true(self, condition, name):
        self.tests_run += 1
        if condition:
            self.passed += 1
            self.log(f"[PASS] {name}")
            return True
        else:
            self.failed += 1
            self.log(f"[FAIL] {name}")
            return False

    def setup_circuit(self, mode=SIMULATE):
        c = Circuit()
        c.simulate(mode)
        return c

    def run(self):
        self.log("Starting Thorough IC Tests with strict create->save->load workflow...")
        
        # Edge Cases
        self.test_empty_ic()
        self.test_unconnected_pins()
        self.test_partial_connections()
        self.test_all_gate_types_in_ic()
        
        # Signal Propagation
        self.test_error_propagation()
        self.test_unknown_propagation()
        self.test_floating_inputs()
        
        # Structure & Logic
        self.test_deep_nesting()
        self.test_feedback_loop_internal()
        
        # Lifecycle
        self.test_deletion_cleanup()
        self.test_save_load_complex()
        
        # Limits
        self.test_input_limit_handling()

        self.log(f"\nTest Summary: {self.passed} Passed, {self.failed} Failed")


    def test_empty_ic(self):
        """Test an IC with absolutely no internal components."""
        c = self.setup_circuit()
        fp = os.path.join(tempfile.gettempdir(), "empty_ic.json")
        c.save_as_ic(fp, "EmptyIC")
        
        c2 = self.setup_circuit()
        ic = c2.getIC(fp)
        
        self.assert_true(len(ic.inputs) == 0, "Empty IC has 0 inputs")
        self.assert_true(len(ic.outputs) == 0, "Empty IC has 0 outputs")
        
        try:
            c2.simulate(SIMULATE)
            safe = True
        except Exception as e:
            safe = False
            self.log(f"Empty IC crashed: {e}")
            
        self.assert_true(safe, "Empty IC safe to process/propagate")
        if os.path.exists(fp): os.remove(fp)

    def test_unconnected_pins(self):
        """Test IC pins that lead nowhere or come from nowhere."""
        c = self.setup_circuit()
        # Create pins but no internal connection
        c.getcomponent(INPUT_PIN_ID)
        c.getcomponent(OUTPUT_PIN_ID)
        
        fp = os.path.join(tempfile.gettempdir(), "unconnected_ic.json")
        c.save_as_ic(fp, "UnconnectedIC")
        
        c2 = self.setup_circuit()
        ic = c2.getIC(fp)
        
        v = c2.getcomponent(VARIABLE_ID)
        c2.connect(ic.inputs[0], v, 0)
        c2.toggle(v, HIGH)
        
        self.assert_true(ic.inputs[0].output == HIGH, "Input pin receives signal even if unconnected internally")
        self.assert_true(ic.outputs[0].output == UNKNOWN, "Unconnected output pin remains UNKNOWN")
        if os.path.exists(fp): os.remove(fp)

    def test_partial_connections(self):
        """Test broken internal chains."""
        c = self.setup_circuit()
        inp = c.getcomponent(INPUT_PIN_ID)
        out = c.getcomponent(OUTPUT_PIN_ID)
        not_g = c.getcomponent(NOT_ID)
        
        # Connect input to not_g, but NOT to output.
        c.connect(not_g, inp, 0)
        
        fp = os.path.join(tempfile.gettempdir(), "partial_ic.json")
        c.save_as_ic(fp, "PartialIC")
        
        c2 = self.setup_circuit()
        ic = c2.getIC(fp)
        
        v = c2.getcomponent(VARIABLE_ID)
        c2.connect(ic.inputs[0], v, 0)
        c2.toggle(v, HIGH)
        
        self.assert_true(ic.outputs[0].output == UNKNOWN, "Disconnected Output Pin ignores internal processing")
        internal_not = next((g for g in ic.internal if g.id == NOT_ID), None)
        if internal_not:
            self.assert_true(internal_not.output == LOW, "Internal logic works even if result not output")
        else:
            self.assert_true(False, "Could not find NOT gate in loaded IC internals")
            
        if os.path.exists(fp): os.remove(fp)

    def test_all_gate_types_in_ic(self):
        """Verify every gate type functions correctly inside an IC."""
        gates = {
            AND_ID: (1, 1, HIGH),
            OR_ID:  (0, 1, HIGH),
            NAND_ID:(1, 1, LOW),
            NOR_ID: (0, 0, HIGH),
            XOR_ID: (1, 0, HIGH),
            XNOR_ID:(1, 0, LOW)
        }
        
        results = {}
        for g_type, (in1, in2, expected) in gates.items():
            c = self.setup_circuit()
            inp1 = c.getcomponent(INPUT_PIN_ID)
            inp2 = c.getcomponent(INPUT_PIN_ID)
            out = c.getcomponent(OUTPUT_PIN_ID)
            g = c.getcomponent(g_type)
            
            if g.inputlimit < 2:
                 c.setlimits(g, 2)
                 
            c.connect(g, inp1, 0)
            c.connect(g, inp2, 1)
            c.connect(out, g, 0)
            
            fp = os.path.join(tempfile.gettempdir(), f"gate_ic_{g_type}.json")
            c.save_as_ic(fp, f"GateIC_{g_type}")
            
            c2 = self.setup_circuit()
            ic = c2.getIC(fp)
            v1 = c2.getcomponent(VARIABLE_ID)
            v2 = c2.getcomponent(VARIABLE_ID)
            
            c2.connect(ic.inputs[0], v1, 0)
            c2.connect(ic.inputs[1], v2, 0)
            
            c2.toggle(v1, in1)
            c2.toggle(v2, in2)
            
            results[g_type] = (ic.outputs[0].output == expected)
            if os.path.exists(fp): os.remove(fp)
            
        all_passed = all(results.values())
        self.assert_true(all_passed, f"All gate types work via proper IC methodology")

    def test_error_propagation(self):
        """Test that ERROR state passes into and out of IC."""
        c = self.setup_circuit()
        inp = c.getcomponent(INPUT_PIN_ID)
        out = c.getcomponent(OUTPUT_PIN_ID)
        c.connect(out, inp, 0)
        fp = os.path.join(tempfile.gettempdir(), "error_passthrough.json")
        c.save_as_ic(fp, "Passthrough")
        
        c2 = self.setup_circuit()
        ic = c2.getIC(fp)
        
        # Build logic to generate ERROR
        xor_g = c2.getcomponent(XOR_ID)
        v_trigger = c2.getcomponent(VARIABLE_ID)
        c2.connect(xor_g, v_trigger, 0)
        c2.connect(xor_g, xor_g, 1) # Paradox Loop
        
        c2.connect(ic.inputs[0], xor_g, 0)
        
        c2.simulate(SIMULATE)
        c2.toggle(v_trigger, HIGH)
        
        self.assert_true(ic.inputs[0].output == ERROR, "Input Pin accepts ERROR")
        self.assert_true(ic.outputs[0].output == ERROR, "Output Pin propagates ERROR")
        if os.path.exists(fp): os.remove(fp)

    def test_unknown_propagation(self):
        """Test UNKNOWN state propagation."""
        c = self.setup_circuit()
        inp = c.getcomponent(INPUT_PIN_ID)
        out = c.getcomponent(OUTPUT_PIN_ID)
        not_g = c.getcomponent(NOT_ID)
        c.connect(not_g, inp, 0)
        c.connect(out, not_g, 0)
        
        fp = os.path.join(tempfile.gettempdir(), "unknown_prop.json")
        c.save_as_ic(fp, "UnknownTest")
        
        c2 = self.setup_circuit()
        ic = c2.getIC(fp)
        v = c2.getcomponent(VARIABLE_ID)
        v.value = v.output = UNKNOWN
        c2.connect(ic.inputs[0], v, 0)
        c2.simulate(SIMULATE)
        
        self.assert_true(ic.outputs[0].output == UNKNOWN, "IC propagates UNKNOWN correctly")
        if os.path.exists(fp): os.remove(fp)

    def test_floating_inputs(self):
        """Test IC input pin not connected to any external source defaults appropriately."""
        c = self.setup_circuit()
        inp = c.getcomponent(INPUT_PIN_ID)
        out = c.getcomponent(OUTPUT_PIN_ID)
        c.connect(out, inp, 0)
        fp = os.path.join(tempfile.gettempdir(), "floating_test.json")
        c.save_as_ic(fp, "FloatingTest")
        
        c2 = self.setup_circuit()
        ic = c2.getIC(fp)
        
        self.assert_true(ic.outputs[0].output == UNKNOWN, "Floating input defaults to UNKNOWN")
        if os.path.exists(fp): os.remove(fp)

    def test_deep_nesting(self):
        """Test 10 levels of nesting through strict save & load IC creation."""
        c_base = self.setup_circuit()
        p_in = c_base.getcomponent(INPUT_PIN_ID)
        p_out = c_base.getcomponent(OUTPUT_PIN_ID)
        c_base.connect(p_out, p_in, 0)
        fp = os.path.join(tempfile.gettempdir(), "nest_0.json")
        c_base.save_as_ic(fp, "Level0")
        fps = [fp]
        
        for i in range(1, 10):
            c_wrap = self.setup_circuit()
            w_in = c_wrap.getcomponent(INPUT_PIN_ID)
            w_out = c_wrap.getcomponent(OUTPUT_PIN_ID)
            inner_ic = c_wrap.getIC(fps[-1])
            c_wrap.connect(inner_ic.inputs[0], w_in, 0)
            c_wrap.connect(w_out, inner_ic.outputs[0], 0)
            
            new_fp = os.path.join(tempfile.gettempdir(), f"nest_{i}.json")
            c_wrap.save_as_ic(new_fp, f"Level{i}")
            fps.append(new_fp)
            
        c_test = self.setup_circuit()
        final_ic = c_test.getIC(fps[-1])
        
        v = c_test.getcomponent(VARIABLE_ID)
        c_test.connect(final_ic.inputs[0], v, 0)
        c_test.toggle(v, HIGH)
        
        self.assert_true(final_ic.outputs[0].output == HIGH, "10-level nested passthrough works")
        
        for fp_temp in fps:
            if os.path.exists(fp_temp):
                os.remove(fp_temp)

    def test_feedback_loop_internal(self):
        """Test an internal feedback loop (Oscillator)."""
        c = self.setup_circuit()
        n1 = c.getcomponent(NOT_ID)
        n2 = c.getcomponent(NOT_ID)
        n3 = c.getcomponent(NOT_ID)
        c.connect(n2, n1, 0)
        c.connect(n3, n2, 0)
        c.connect(n1, n3, 0)
        
        fp = os.path.join(tempfile.gettempdir(), "oscillator.json")
        c.save_as_ic(fp, "OscillatorIC")
        
        c2 = self.setup_circuit(SIMULATE)
        try:
            ic = c2.getIC(fp)
            c2.simulate(SIMULATE)
            safe = True
        except Exception:
            safe = False
            
        self.assert_true(safe, "Internal feedback loop doesn't crash engine")
        if os.path.exists(fp): os.remove(fp)

    def test_deletion_cleanup(self):
        """Test strict cleanup when deleting IC."""
        c = self.setup_circuit()
        inp = c.getcomponent(INPUT_PIN_ID)
        fp = os.path.join(tempfile.gettempdir(), "delete_test.json")
        c.save_as_ic(fp, "DeleteTestIC")

        c2 = self.setup_circuit()
        ic = c2.getIC(fp)
        v = c2.getcomponent(VARIABLE_ID)
        c2.connect(ic.inputs[0], v, 0)
        
        self.assert_true(len(v.hitlist) == 1, "Variable connected to IC Pin")
        delete_cmd = Delete(c2, [ic])
        delete_cmd.execute()
        self.assert_true(len(v.hitlist) == 0, "Deleting IC clears source connections")
        
        delete_cmd.undo()
        self.assert_true(len(v.hitlist) == 1, "Renewing IC restores connections")
        if os.path.exists(fp): os.remove(fp)

    def test_save_load_complex(self):
        """Test saving/loading an IC with nested components."""
        # 1. Inner
        c_in = self.setup_circuit()
        i_in = c_in.getcomponent(INPUT_PIN_ID)
        i_out = c_in.getcomponent(OUTPUT_PIN_ID)
        c_in.connect(i_out, i_in, 0)
        fp_in = os.path.join(tempfile.gettempdir(), "inner.json")
        c_in.save_as_ic(fp_in, "InnerChip")
        
        # 2. Outer
        c_out = self.setup_circuit()
        inp = c_out.getcomponent(INPUT_PIN_ID)
        out = c_out.getcomponent(OUTPUT_PIN_ID)
        inner_ic = c_out.getIC(fp_in)
        
        c_out.connect(inner_ic.inputs[0], inp, 0)
        c_out.connect(out, inner_ic.outputs[0], 0)
        
        fp_out = os.path.join(tempfile.gettempdir(), "complex_ic_test.json")
        c_out.save_as_ic(fp_out, "SuperChip")
        
        # 3. Test
        c2 = self.setup_circuit()
        loaded_ic = c2.getIC(fp_out)
        
        self.assert_true(loaded_ic is not None, "Loaded Complex IC")
        self.assert_true(len(loaded_ic.internal) > 0, "Loaded IC has internals")
        
        has_internal_ic = any(isinstance(x, IC) for x in loaded_ic.internal)
        self.assert_true(has_internal_ic, "Internal IC preserved")
        
        if os.path.exists(fp_in): os.remove(fp_in)
        if os.path.exists(fp_out): os.remove(fp_out)

    def test_input_limit_handling(self):
        """Test that IC gates resize inputs correctly and don't default to 1."""
        c = self.setup_circuit()
        
        TARGET_INPUTS = 5
        and_g = c.getcomponent(AND_ID)
        c.setlimits(and_g, TARGET_INPUTS)
        
        pins = []
        for i in range(TARGET_INPUTS):
            p = c.getcomponent(INPUT_PIN_ID)
            c.connect(and_g, p, i)
            pins.append(p)
            
        out_pin = c.getcomponent(OUTPUT_PIN_ID)
        c.connect(out_pin, and_g, 0)
        
        fp = os.path.join(tempfile.gettempdir(), "limit_ic.json")
        c.save_as_ic(fp, "LimitIC")
        
        c2 = self.setup_circuit()
        ic = c2.getIC(fp)
        
        # Now verify functionality on loaded IC
        vars_list = []
        for i in range(TARGET_INPUTS):
            v = c2.getcomponent(VARIABLE_ID)
            c2.connect(ic.inputs[i], v, 0)
            vars_list.append(v)
            
        for v in vars_list:
            c2.toggle(v, HIGH)
            
        self.assert_true(ic.outputs[0].output == HIGH, "AND-5 Gate High with all High inside IC")
        
        c2.toggle(vars_list[-1], LOW)
        self.assert_true(ic.outputs[0].output == LOW, "AND-5 Gate Low with one Low inside IC")
        
        c2.toggle(vars_list[-1], HIGH)
        c2.toggle(vars_list[0], LOW)
        self.assert_true(ic.outputs[0].output == LOW, "AND-5 Gate Low with first Low inside IC")
        
        if os.path.exists(fp): os.remove(fp)

if __name__ == "__main__":
    test = ThoroughICTest()
    test.run()
    if test.failed > 0:
        sys.exit(1)
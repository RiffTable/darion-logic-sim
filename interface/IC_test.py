"""
DARION LOGIC SIM — THOROUGH IC TEST SUITE
Focuses exclusively on Integrated Circuits (ICs) with comprehensive coverage
of edge cases, error states, nesting, and dynamic modification.
"""

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

# Backend Selection Logic
if args.reactor:
    use_reactor = True
elif args.engine:
    use_reactor = False
else:
    # Interactive prompt (RESTORED)
    print("\nSelect Backend:")
    print("1. Engine (Python) [Default]")
    print("2. Reactor (Cython)")
    try:
        choice = input("Choice (1/2): ").strip()
        if choice == '2':
            use_reactor = True
        else:
            use_reactor = False
    except EOFError:
        # Handle cases where input is not possible (e.g., automated environments)
        use_reactor = False

# Add engine or reactor to path
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
        self.log(f"Starting Thorough IC Tests...")
        
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
        self.test_dynamic_modification()
        
        # Lifecycle
        self.test_deletion_cleanup()
        self.test_save_load_complex()
        
        # Limits
        self.test_input_limit_handling()

        self.log(f"\nTest Summary: {self.passed} Passed, {self.failed} Failed")

    def test_empty_ic(self):
        """Test an IC with absolutely no internal components."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        
        self.assert_true(len(ic.inputs) == 0, "Empty IC has 0 inputs")
        self.assert_true(len(ic.outputs) == 0, "Empty IC has 0 outputs")
        
        try:
            c.simulate(SIMULATE)
            safe = True
        except Exception as e:
            safe = False
            self.log(f"Empty IC crashed: {e}")
            
        self.assert_true(safe, "Empty IC safe to process/propagate")

    def test_unconnected_pins(self):
        """Test IC pins that lead nowhere or come from nowhere."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        
        inp = ic.getcomponent(INPUT_PIN_ID)
        out = ic.getcomponent(OUTPUT_PIN_ID)
        
        v = c.getcomponent(VARIABLE_ID)
        c.connect(inp, v, 0)
        c.toggle(v, HIGH)
        
        self.assert_true(inp.output == HIGH, "Input pin receives signal even if unconnected internally")
        self.assert_true(out.output == UNKNOWN, "Unconnected output pin remains UNKNOWN")

    def test_partial_connections(self):
        """Test broken internal chains."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        
        inp = ic.getcomponent(INPUT_PIN_ID)
        out = ic.getcomponent(OUTPUT_PIN_ID)
        not_g = ic.getcomponent(NOT_ID)
        
        c.connect(not_g, inp, 0)
        v = c.getcomponent(VARIABLE_ID)
        c.connect(inp, v, 0)
        c.toggle(v, HIGH)
        
        self.assert_true(not_g.output == LOW, "Internal logic works even if result not output")
        self.assert_true(out.output == UNKNOWN, "Disconnected Output Pin ignores internal processing")

    def test_all_gate_types_in_ic(self):
        """Verify every gate type functions correctly inside an IC."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        
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
            sub_c = self.setup_circuit()
            sub_ic = sub_c.getcomponent(IC_ID)
            
            inp1 = sub_ic.getcomponent(INPUT_PIN_ID)
            inp2 = sub_ic.getcomponent(INPUT_PIN_ID)
            out = sub_ic.getcomponent(OUTPUT_PIN_ID)
            
            g = sub_ic.getcomponent(g_type)
            # Standard gates must support at least 2 inputs
            if g.inputlimit < 2:
                 sub_c.setlimits(g, 2)

            sub_c.connect(g, inp1, 0)
            sub_c.connect(g, inp2, 1)
            sub_c.connect(out, g, 0)
            
            v1 = sub_c.getcomponent(VARIABLE_ID)
            v2 = sub_c.getcomponent(VARIABLE_ID)
            sub_c.connect(inp1, v1, 0)
            sub_c.connect(inp2, v2, 0)
            
            sub_c.toggle(v1, in1)
            sub_c.toggle(v2, in2)
            
            results[g_type] = (out.output == expected)
            
        all_passed = all(results.values())
        self.assert_true(all_passed, f"All gate types work in IC: {results}")

    def test_error_propagation(self):
        """Test that ERROR state passes into and out of IC."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        inp = ic.getcomponent(INPUT_PIN_ID)
        out = ic.getcomponent(OUTPUT_PIN_ID)
        
        c.connect(out, inp, 0)
        
        xor_g = c.getcomponent(XOR_ID)
        v_trigger = c.getcomponent(VARIABLE_ID)
        
        c.connect(xor_g, v_trigger, 0)
        c.connect(xor_g, xor_g, 1) # Paradox Loop
        
        c.connect(inp, xor_g, 0)
        
        c.simulate(SIMULATE)
        c.toggle(v_trigger, HIGH)
        
        self.assert_true(inp.output == ERROR, "Input Pin accepts ERROR")
        self.assert_true(out.output == ERROR, "Output Pin propagates ERROR")

    def test_unknown_propagation(self):
        """Test UNKNOWN state propagation."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        inp = ic.getcomponent(INPUT_PIN_ID)
        out = ic.getcomponent(OUTPUT_PIN_ID)
        
        not_g = ic.getcomponent(NOT_ID)
        c.connect(not_g, inp, 0)
        c.connect(out, not_g, 0)
        
        v = c.getcomponent(VARIABLE_ID)
        v.value=v.output=UNKNOWN
        c.connect(inp, v, 0)
        c.simulate(SIMULATE)
        
        self.assert_true(out.output == UNKNOWN, "IC propagates UNKNOWN correctly")

    def test_floating_inputs(self):
        """Test IC input pin not connected to any external source."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        inp = ic.getcomponent(INPUT_PIN_ID)
        out = ic.getcomponent(OUTPUT_PIN_ID)
        
        c.connect(out, inp, 0)
        self.assert_true(out.output == UNKNOWN, "Floating input defaults to UNKNOWN")

    def test_deep_nesting(self):
        """Test 10 levels of nesting."""
        c = self.setup_circuit()
        
        current_ic = c.getcomponent(IC_ID)
        root_inp = current_ic.getcomponent(INPUT_PIN_ID)
        root_out = current_ic.getcomponent(OUTPUT_PIN_ID)
        c.connect(root_out, root_inp, 0)
        
        # Level 0 (Inner most)
        inner = c.getcomponent(IC_ID)
        i_in = inner.getcomponent(INPUT_PIN_ID)
        i_out = inner.getcomponent(OUTPUT_PIN_ID)
        c.connect(i_out, i_in, 0)
        
        prev_ic = inner
        prev_in = i_in
        prev_out = i_out
        
        for i in range(9):
             wrapper = c.getcomponent(IC_ID)
             w_in = wrapper.getcomponent(INPUT_PIN_ID)
             w_out = wrapper.getcomponent(OUTPUT_PIN_ID)
             
             wrapper.addgate(prev_ic)
             c.canvas.remove(prev_ic)
             c.iclist.remove(prev_ic)
             c.connect(prev_in, w_in, 0)
             c.connect(w_out, prev_out, 0)
             c.counter += wrapper.counter
             
             prev_ic = wrapper
             prev_in = w_in
             prev_out = w_out
             
        v = c.getcomponent(VARIABLE_ID)
        c.connect(prev_in, v, 0)
        
        # Accumulate IC counters for propagation wave limit
        c.counter += current_ic.counter
        c.counter += inner.counter
        c.toggle(v, HIGH)
        self.assert_true(prev_out.output == HIGH, "10-level nested passthrough works")

    def test_feedback_loop_internal(self):
        """Test an internal feedback loop (Oscillator)."""
        c = self.setup_circuit(SIMULATE)
        ic = c.getcomponent(IC_ID)
        
        n1 = ic.getcomponent(NOT_ID)
        n2 = ic.getcomponent(NOT_ID)
        n3 = ic.getcomponent(NOT_ID)
        
        c.connect(n2, n1, 0)
        c.connect(n3, n2, 0)
        c.connect(n1, n3, 0)
        
        try:
            c.simulate(SIMULATE)
            safe = True
        except:
            safe = False
        
        self.assert_true(safe, "Internal feedback loop doesn't crash engine")

    def test_dynamic_modification(self):
        """Test adding components to an IC that is already live."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        inp = ic.getcomponent(INPUT_PIN_ID)
        out = ic.getcomponent(OUTPUT_PIN_ID)
        
        v = c.getcomponent(VARIABLE_ID)
        c.connect(inp, v, 0)
        c.toggle(v, HIGH)
        
        self.assert_true(out.output == UNKNOWN, "Output initially UNKNOWN")
        
        not_g = ic.getcomponent(NOT_ID)
        c.connect(not_g, inp, 0)
        c.connect(out, not_g, 0)
        c.counter += ic.counter
        
        c.toggle(v, LOW)
        c.toggle(v, HIGH)
        
        self.assert_true(out.output == LOW, "Dynamically added gate works (HIGH->NOT->LOW)")

    def test_deletion_cleanup(self):
        """Test strict cleanup when deleting IC."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        inp = ic.getcomponent(INPUT_PIN_ID)
        
        v = c.getcomponent(VARIABLE_ID)
        c.connect(inp, v, 0)
        
        self.assert_true(len(v.hitlist) == 1, "Variable connected to IC Pin")
        c.hideComponent(ic) 
        self.assert_true(len(v.hitlist) == 0, "Deleting IC clears source connections")
        
        c.renewComponent(ic)
        self.assert_true(len(v.hitlist) == 1, "Renewing IC restores connections")

    def test_save_load_complex(self):
        """Test saving/loading an IC with nested components."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        ic.custom_name = "SuperChip"
        
        inp = ic.getcomponent(INPUT_PIN_ID)
        out = ic.getcomponent(OUTPUT_PIN_ID)
        
        inner = ic.getcomponent(IC_ID)
        inner.custom_name = "InnerChip"
        i_in = inner.getcomponent(INPUT_PIN_ID)
        i_out = inner.getcomponent(OUTPUT_PIN_ID)
        c.connect(i_out, i_in, 0)
        
        c.connect(i_in, inp, 0)
        c.connect(out, i_out, 0)
        
        fp = os.path.join(tempfile.gettempdir(), "complex_ic_test.json")
        c.save_as_ic(fp, "ComplexIC")
        
        c2 = self.setup_circuit()
        loaded_ic = c2.getIC(fp)
        
        self.assert_true(loaded_ic is not None, "Loaded Complex IC")
        self.assert_true(len(loaded_ic.internal) > 0, "Loaded IC has internals")
        
        has_internal_ic = any(isinstance(x, IC) for x in loaded_ic.internal)
        self.assert_true(has_internal_ic, "Internal IC preserved")
        
        os.remove(fp)

    def test_input_limit_handling(self):
        """Test that IC gates resize inputs correctly and don't default to 1."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        
        # 1. Ensure AND gate starts with default limit >= 2
        and_g = ic.getcomponent(AND_ID)
        self.assert_true(and_g.inputlimit >= 2, "AND Gate default limit >= 2")
        
        # 2. Resize and Connect
        TARGET_INPUTS = 5
        c.setlimits(and_g, TARGET_INPUTS)
        
        # Verify limit was actually set
        self.assert_true(and_g.inputlimit == TARGET_INPUTS, f"AND Gate resized to {TARGET_INPUTS}")
        
        vars_list = []
        pins = []
        
        for i in range(TARGET_INPUTS):
            v = c.getcomponent(VARIABLE_ID)
            p = ic.getcomponent(INPUT_PIN_ID)
            
            # External Variable -> IC Pin -> AND Gate[i]
            c.connect(p, v, 0)
            c.connect(and_g, p, i)
            
            vars_list.append(v)
            pins.append(p)

        # 3. Functional Verification
        
        # Set all to HIGH
        for v in vars_list:
            c.toggle(v, HIGH)
            
        # Check Output (We need an output pin to read the result easily, or check gate directly)
        out_pin = ic.getcomponent(OUTPUT_PIN_ID)
        c.connect(out_pin, and_g, 0)
        
        self.assert_true(out_pin.output == HIGH, "AND-5 Gate High with all High")
        
        # Set one to LOW (the last one)
        c.toggle(vars_list[-1], LOW)
        self.assert_true(out_pin.output == LOW, "AND-5 Gate Low with one Low")
        
        # Set first to LOW (and reset last to HIGH)
        c.toggle(vars_list[-1], HIGH)
        c.toggle(vars_list[0], LOW)
        self.assert_true(out_pin.output == LOW, "AND-5 Gate Low with first Low")


if __name__ == "__main__":
    test = ThoroughICTest()
    test.run()
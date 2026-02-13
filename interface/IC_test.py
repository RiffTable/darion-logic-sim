
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
    # Interactive prompt
    print("\nSelect Backend:")
    print("1. Engine (Python) [Default]")
    print("2. Reactor (Cython)")
    choice = input("Choice (1/2): ").strip()
    if choice == '2':
        use_reactor = True
    else:
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
    from Const import HIGH, LOW, UNKNOWN, ERROR, SIMULATE, FLIPFLOP, set_MODE
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
        self.test_input_limit_handling()

        self.log(f"\nTest Summary: {self.passed} Passed, {self.failed} Failed")

    def test_empty_ic(self):
        """Test an IC with absolutely no internal components."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        
        # It should exist and have 0 inputs/outputs
        self.assert_true(len(ic.inputs) == 0, "Empty IC has 0 inputs")
        self.assert_true(len(ic.outputs) == 0, "Empty IC has 0 outputs")
        self.assert_true(len(ic.internal) == 0, "Empty IC has 0 internals")
        
        # Should be safe to 'simulate' even if empty
        try:
            c.simulate(SIMULATE) # Should process nothing
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
        
        # Connect external variable to input, but input connects to nothing internally
        v = c.getcomponent(VARIABLE_ID)
        inp.connect(v, 0)
        
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
        
        # Connect inp -> NOT, but NOT -> nothing (Output pin disconnected)
        not_g.connect(inp, 0)
        
        v = c.getcomponent(VARIABLE_ID)
        inp.connect(v, 0)
        
        c.toggle(v, HIGH)
        # NOT gate should work
        self.assert_true(not_g.output == LOW, "Internal logic works even if result not output")
        # Output pin should be unchanged (UNKNOWN)
        self.assert_true(out.output == UNKNOWN, "Disconnected Output Pin ignores internal processing")

    def test_all_gate_types_in_ic(self):
        """Verify every gate type functions correctly inside an IC."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        
        gates = {
            AND_ID: (1, 1, HIGH),   # AND(1,1)=1
            OR_ID:  (0, 1, HIGH),   # OR(0,1)=1
            NAND_ID:(1, 1, LOW),    # NAND(1,1)=0
            NOR_ID: (0, 0, HIGH),   # NOR(0,0)=1
            XOR_ID: (1, 0, HIGH),   # XOR(1,0)=1
            XNOR_ID:(1, 0, LOW)     # XNOR(1,0)=0
        }
        
        results = {}
        vars_map = {}
        
        for g_type, (in1, in2, expected) in gates.items():
            # Setup separate circuit for each gate to be clean
            sub_c = self.setup_circuit()
            sub_ic = sub_c.getcomponent(IC_ID)
            
            inp1 = sub_ic.getcomponent(INPUT_PIN_ID)
            inp2 = sub_ic.getcomponent(INPUT_PIN_ID)
            out = sub_ic.getcomponent(OUTPUT_PIN_ID)
            
            g = sub_ic.getcomponent(g_type)
            g.connect(inp1, 0)
            g.connect(inp2, 1)
            out.connect(g, 0)
            
            v1 = sub_c.getcomponent(VARIABLE_ID)
            v2 = sub_c.getcomponent(VARIABLE_ID)
            inp1.connect(v1, 0)
            inp2.connect(v2, 0)
            
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
        
        # Simple passthrough
        out.connect(inp, 0)
        
        # Can't easily force an ERROR from a simple Variable, so let's mock it
        # Or create an error condition (XOR loop) feeding the IC
        xor_g = c.getcomponent(XOR_ID)
        c.connect(xor_g, xor_g, 1) # Self loop causes ERROR/Oscillation
        v = c.getcomponent(VARIABLE_ID)
        c.connect(xor_g, v, 0)
        
        set_MODE(FLIPFLOP) # Allow oscillation/feedback
        c.toggle(v, 1) 
        # XOR(1, prev) -> if prev=0 -> 1 -> XOR(1,1)->0 -> XOR(1,0)->1 ... Oscillation
        # The engine usually produces ERROR for unstable loops in SIMULATE mode or just oscillates.
        # Let's try SIMULATE mode which detects unstable states better? 
        # Or just force the value.
        
        v_force = c.getcomponent(VARIABLE_ID)
        c.connect(inp, v_force, 0)
        v_force.output = ERROR # Hack: force the variable state
        v_force.propagate()
        
        self.assert_true(inp.output == ERROR, "Input Pin accepts ERROR")
        self.assert_true(out.output == ERROR, "Output Pin propagates ERROR")

    def test_unknown_propagation(self):
        """Test UNKNOWN state propagation."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        inp = ic.getcomponent(INPUT_PIN_ID)
        out = ic.getcomponent(OUTPUT_PIN_ID)
        
        # Logic: NOT(Unknown) -> Unknown? Or Logic dependant?
        # In this engine, NOT(Unknown) -> Unknown usually.
        not_g = ic.getcomponent(NOT_ID)
        not_g.connect(inp, 0)
        out.connect(not_g, 0)
        
        v = c.getcomponent(VARIABLE_ID)
        # Don't toggle V, leave it UNKNOWN (default?)
        # Actually Variables default to LOW usually? No, check Gates.pyx
        # Usually they default to LOW or are initialized. 
        # Let's force UNKNOWN.
        v.output = UNKNOWN
        inp.connect(v, 0)
        v.propagate()
        
        self.assert_true(out.output == UNKNOWN, "IC propagates UNKNOWN correctly")

    def test_floating_inputs(self):
        """Test IC input pin not connected to any external source."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        inp = ic.getcomponent(INPUT_PIN_ID)
        out = ic.getcomponent(OUTPUT_PIN_ID)
        
        # Just connect internal logic
        out.connect(inp, 0)
        
        # Ensure it works (should be UNKNOWN or LOW depending on defaults)
        self.assert_true(out.output == UNKNOWN, "Floating input defaults to UNKNOWN")

    def test_deep_nesting(self):
        """Test 10 levels of nesting (deeper than speed_test)."""
        c = self.setup_circuit()
        
        current_ic = c.getcomponent(IC_ID)
        root_inp = current_ic.getcomponent(INPUT_PIN_ID)
        root_out = current_ic.getcomponent(OUTPUT_PIN_ID)
        
        # Make a passthrough
        root_out.connect(root_inp, 0)
        
        # Now nest 9 more times
        # IC2 contains IC1, IC3 contains IC2...
        # Wait, usually nesting is "IC contains logic". 
        # To nest ICs, I need to add an IC *into* an IC.
        
        # Level 0 (Inner most)
        inner = c.getcomponent(IC_ID)
        i_in = inner.getcomponent(INPUT_PIN_ID)
        i_out = inner.getcomponent(OUTPUT_PIN_ID)
        i_out.connect(i_in, 0)
        
        prev_ic = inner
        prev_in = i_in
        prev_out = i_out
        
        # Wrap it 9 times
        for i in range(9):
             wrapper = c.getcomponent(IC_ID)
             w_in = wrapper.getcomponent(INPUT_PIN_ID)
             w_out = wrapper.getcomponent(OUTPUT_PIN_ID)
             
             # Add prev_ic to wrapper
             wrapper.addgate(prev_ic)
             
             # Connect Wrapper In -> Prev IC In
             prev_in.connect(w_in, 0)
             # Connect Prev IC Out -> Wrapper Out
             w_out.connect(prev_out, 0)
             
             prev_ic = wrapper
             prev_in = w_in
             prev_out = w_out
             
        # Connect to circuit
        v = c.getcomponent(VARIABLE_ID)
        prev_in.connect(v, 0)
        
        c.toggle(v, HIGH)
        self.assert_true(prev_out.output == HIGH, "10-level nested passthrough works")

    def test_feedback_loop_internal(self):
        """Test an internal feedback loop (Oscillator)."""
        c = self.setup_circuit(FLIPFLOP)
        ic = c.getcomponent(IC_ID)
        
        # Create Loop: NOT -> NOT -> NOT (Odd number = oscillator)
        n1 = ic.getcomponent(NOT_ID)
        n2 = ic.getcomponent(NOT_ID)
        n3 = ic.getcomponent(NOT_ID)
        
        n2.connect(n1, 0)
        n3.connect(n2, 0)
        n1.connect(n3, 0) # Loop back
        
        # Trigger it? It's self-contained.
        # Check if it crashes or reaches a stable state (which it shouldn't).
        # In FLIPFLOP mode, it might just toggle endlessly if we step it, but here it runs until stability or max steps.
        # This tests stability/crash resilience.
        
        try:
            c.simulate(FLIPFLOP)
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
        
        # Initially unconnected
        v = c.getcomponent(VARIABLE_ID)
        inp.connect(v, 0)
        c.toggle(v, HIGH)
        
        self.assert_true(out.output == UNKNOWN, "Output initially UNKNOWN")
        
        # Dynamically add a NOT gate bridging them
        not_g = ic.getcomponent(NOT_ID)
        not_g.connect(inp, 0)
        out.connect(not_g, 0)
        
        # Force update?
        c.toggle(v, LOW)
        c.toggle(v, HIGH)
        
        self.assert_true(out.output == LOW, "Dynamically added gate works (HIGH->NOT->LOW)")

    def test_deletion_cleanup(self):
        """Test strict cleanup when deleting IC."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        inp = ic.getcomponent(INPUT_PIN_ID)
        
        v = c.getcomponent(VARIABLE_ID)
        inp.connect(v, 0)
        
        self.assert_true(len(v.hitlist) == 1, "Variable connected to IC Pin")
        
        # Hide/Delete IC
        c.hideComponent(ic) # Should trigger hide() on IC
        
        # Verify clean disconnect
        # Note: Hide usually soft-disconnects (flags hidden maybe?). 
        # But IC.hide() implementation explicitly removes from source hitlists?
        # Check IC.py: hide() calls remove(profile) which modifies hitlist.
        
        # Wait, if hitlist is cleaned, len should be 0 or profile marked.
        # The IC.py hide() loop: 
        # for pin in inputs: ... remove(profile, index) ... if not profile.index: hitlist_del
        
        self.assert_true(len(v.hitlist) == 0, "Deleting IC clears source connections")
        
        # Bring it back
        c.renewComponent(ic)
        self.assert_true(len(v.hitlist) == 1, "Renewing IC restores connections")

    def test_save_load_complex(self):
        """Test saving/loading an IC with nested components."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        ic.custom_name = "SuperChip"
        
        inp = ic.getcomponent(INPUT_PIN_ID)
        out = ic.getcomponent(OUTPUT_PIN_ID)
        
        # Nested IC
        inner = ic.getcomponent(IC_ID)
        inner.custom_name = "InnerChip"
        i_in = inner.getcomponent(INPUT_PIN_ID)
        i_out = inner.getcomponent(OUTPUT_PIN_ID)
        i_out.connect(i_in, 0)
        
        i_in.connect(inp, 0)
        out.connect(i_out, 0)
        
        # Save
        fp = os.path.join(tempfile.gettempdir(), "complex_ic_test.json")
        c.save_as_ic(fp, "ComplexIC")
        
        # Load
        c2 = self.setup_circuit()
        loaded_ic = c2.getIC(fp)
        
        self.assert_true(loaded_ic is not None, "Loaded Complex IC")
        self.assert_true(len(loaded_ic.internal) > 0, "Loaded IC has internals")
        
        # Check if internal IC exists and is an IC
        has_internal_ic = any(isinstance(x, IC) for x in loaded_ic.internal)
        self.assert_true(has_internal_ic, "Internal IC preserved")
        
        os.remove(fp)

    def test_input_limit_handling(self):
        """Test that IC gates resize inputs correctly."""
        c = self.setup_circuit()
        ic = c.getcomponent(IC_ID)
        
        and_g = ic.getcomponent(AND_ID)
        # Default limit usually 2?
        
        # Connect 5 things to it
        pins = []
        for i in range(5):
            p = ic.getcomponent(INPUT_PIN_ID)
            and_g.setlimits(5) # Auto-resize or manual resize
            and_g.connect(p, i) 
            pins.append(p)
            
        self.assert_true(and_g.inputlimit >= 5, "Internal gate resized for multiple inputs")


if __name__ == "__main__":
    test = ThoroughICTest()
    test.run()

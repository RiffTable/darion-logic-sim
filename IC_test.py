
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

# Add engine to path
engine_path = os.path.join(os.getcwd(), 'engine')
if engine_path not in sys.path:
    sys.path.append(engine_path)

try:
    from Circuit import Circuit
    import Const
    from Gates import Gate, Variable, Nothing
    from Gates import NOT, AND, NAND, OR, NOR, XOR, XNOR
    from Gates import InputPin, OutputPin
    from IC import IC
except ImportError as e:
    print(f"FATAL ERROR: Could not import engine modules: {e}")
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

    def setup_circuit(self, mode=Const.SIMULATE):
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
        ic = c.getcomponent(Const.IC)
        
        # It should exist and have 0 inputs/outputs
        self.assert_true(len(ic.inputs) == 0, "Empty IC has 0 inputs")
        self.assert_true(len(ic.outputs) == 0, "Empty IC has 0 outputs")
        self.assert_true(len(ic.internal) == 0, "Empty IC has 0 internals")
        
        # Should be safe to 'simulate' even if empty
        try:
            c.simulate(Const.SIMULATE) # Should process nothing
            safe = True
        except Exception as e:
            safe = False
            self.log(f"Empty IC crashed: {e}")
            
        self.assert_true(safe, "Empty IC safe to process/propagate")

    def test_unconnected_pins(self):
        """Test IC pins that lead nowhere or come from nowhere."""
        c = self.setup_circuit()
        ic = c.getcomponent(Const.IC)
        
        inp = ic.getcomponent(Const.INPUT_PIN)
        out = ic.getcomponent(Const.OUTPUT_PIN)
        
        # Connect external variable to input, but input connects to nothing internally
        v = c.getcomponent(Const.VARIABLE)
        inp.connect(v, 0)
        
        c.toggle(v, Const.HIGH)
        
        self.assert_true(inp.output == Const.HIGH, "Input pin receives signal even if unconnected internally")
        self.assert_true(out.output == Const.UNKNOWN, "Unconnected output pin remains UNKNOWN")

    def test_partial_connections(self):
        """Test broken internal chains."""
        c = self.setup_circuit()
        ic = c.getcomponent(Const.IC)
        
        inp = ic.getcomponent(Const.INPUT_PIN)
        out = ic.getcomponent(Const.OUTPUT_PIN)
        not_g = ic.getcomponent(Const.NOT)
        
        # Connect inp -> NOT, but NOT -> nothing (Output pin disconnected)
        not_g.connect(inp, 0)
        
        v = c.getcomponent(Const.VARIABLE)
        inp.connect(v, 0)
        
        c.toggle(v, Const.HIGH)
        # NOT gate should work
        self.assert_true(not_g.output == Const.LOW, "Internal logic works even if result not output")
        # Output pin should be unchanged (UNKNOWN)
        self.assert_true(out.output == Const.UNKNOWN, "Disconnected Output Pin ignores internal processing")

    def test_all_gate_types_in_ic(self):
        """Verify every gate type functions correctly inside an IC."""
        c = self.setup_circuit()
        ic = c.getcomponent(Const.IC)
        
        gates = {
            Const.AND: (1, 1, Const.HIGH),   # AND(1,1)=1
            Const.OR:  (0, 1, Const.HIGH),   # OR(0,1)=1
            Const.NAND:(1, 1, Const.LOW),    # NAND(1,1)=0
            Const.NOR: (0, 0, Const.HIGH),   # NOR(0,0)=1
            Const.XOR: (1, 0, Const.HIGH),   # XOR(1,0)=1
            Const.XNOR:(1, 0, Const.LOW)     # XNOR(1,0)=0
        }
        
        results = {}
        vars_map = {}
        
        for g_type, (in1, in2, expected) in gates.items():
            # Setup separate circuit for each gate to be clean
            sub_c = self.setup_circuit()
            sub_ic = sub_c.getcomponent(Const.IC)
            
            inp1 = sub_ic.getcomponent(Const.INPUT_PIN)
            inp2 = sub_ic.getcomponent(Const.INPUT_PIN)
            out = sub_ic.getcomponent(Const.OUTPUT_PIN)
            
            g = sub_ic.getcomponent(g_type)
            g.connect(inp1, 0)
            g.connect(inp2, 1)
            out.connect(g, 0)
            
            v1 = sub_c.getcomponent(Const.VARIABLE)
            v2 = sub_c.getcomponent(Const.VARIABLE)
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
        ic = c.getcomponent(Const.IC)
        inp = ic.getcomponent(Const.INPUT_PIN)
        out = ic.getcomponent(Const.OUTPUT_PIN)
        
        # Simple passthrough
        out.connect(inp, 0)
        
        # Can't easily force an ERROR from a simple Variable, so let's mock it
        # Or create an error condition (XOR loop) feeding the IC
        xor_g = c.getcomponent(Const.XOR)
        c.connect(xor_g, xor_g, 1) # Self loop causes ERROR/Oscillation
        v = c.getcomponent(Const.VARIABLE)
        c.connect(xor_g, v, 0)
        
        Const.set_MODE(Const.FLIPFLOP) # Allow oscillation/feedback
        c.toggle(v, 1) 
        # XOR(1, prev) -> if prev=0 -> 1 -> XOR(1,1)->0 -> XOR(1,0)->1 ... Oscillation
        # The engine usually produces ERROR for unstable loops in SIMULATE mode or just oscillates.
        # Let's try SIMULATE mode which detects unstable states better? 
        # Or just force the value.
        
        v_force = c.getcomponent(Const.VARIABLE)
        c.connect(inp, v_force, 0)
        v_force.output = Const.ERROR # Hack: force the variable state
        v_force.propagate()
        
        self.assert_true(inp.output == Const.ERROR, "Input Pin accepts ERROR")
        self.assert_true(out.output == Const.ERROR, "Output Pin propagates ERROR")

    def test_unknown_propagation(self):
        """Test UNKNOWN state propagation."""
        c = self.setup_circuit()
        ic = c.getcomponent(Const.IC)
        inp = ic.getcomponent(Const.INPUT_PIN)
        out = ic.getcomponent(Const.OUTPUT_PIN)
        
        # Logic: NOT(Unknown) -> Unknown? Or Logic dependant?
        # In this engine, NOT(Unknown) -> Unknown usually.
        not_g = ic.getcomponent(Const.NOT)
        not_g.connect(inp, 0)
        out.connect(not_g, 0)
        
        v = c.getcomponent(Const.VARIABLE)
        # Don't toggle V, leave it UNKNOWN (default?)
        # Actually Variables default to LOW usually? No, check Gates.pyx
        # Usually they default to LOW or are initialized. 
        # Let's force UNKNOWN.
        v.output = Const.UNKNOWN
        inp.connect(v, 0)
        v.propagate()
        
        self.assert_true(out.output == Const.UNKNOWN, "IC propagates UNKNOWN correctly")

    def test_floating_inputs(self):
        """Test IC input pin not connected to any external source."""
        c = self.setup_circuit()
        ic = c.getcomponent(Const.IC)
        inp = ic.getcomponent(Const.INPUT_PIN)
        out = ic.getcomponent(Const.OUTPUT_PIN)
        
        # Just connect internal logic
        out.connect(inp, 0)
        
        # Ensure it works (should be UNKNOWN or LOW depending on defaults)
        self.assert_true(out.output == Const.UNKNOWN, "Floating input defaults to UNKNOWN")

    def test_deep_nesting(self):
        """Test 10 levels of nesting (deeper than speed_test)."""
        c = self.setup_circuit()
        
        current_ic = c.getcomponent(Const.IC)
        root_inp = current_ic.getcomponent(Const.INPUT_PIN)
        root_out = current_ic.getcomponent(Const.OUTPUT_PIN)
        
        # Make a passthrough
        root_out.connect(root_inp, 0)
        
        # Now nest 9 more times
        # IC2 contains IC1, IC3 contains IC2...
        # Wait, usually nesting is "IC contains logic". 
        # To nest ICs, I need to add an IC *into* an IC.
        
        # Level 0 (Inner most)
        inner = c.getcomponent(Const.IC)
        i_in = inner.getcomponent(Const.INPUT_PIN)
        i_out = inner.getcomponent(Const.OUTPUT_PIN)
        i_out.connect(i_in, 0)
        
        prev_ic = inner
        prev_in = i_in
        prev_out = i_out
        
        # Wrap it 9 times
        for i in range(9):
             wrapper = c.getcomponent(Const.IC)
             w_in = wrapper.getcomponent(Const.INPUT_PIN)
             w_out = wrapper.getcomponent(Const.OUTPUT_PIN)
             
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
        v = c.getcomponent(Const.VARIABLE)
        prev_in.connect(v, 0)
        
        c.toggle(v, Const.HIGH)
        self.assert_true(prev_out.output == Const.HIGH, "10-level nested passthrough works")

    def test_feedback_loop_internal(self):
        """Test an internal feedback loop (Oscillator)."""
        c = self.setup_circuit(Const.FLIPFLOP)
        ic = c.getcomponent(Const.IC)
        
        # Create Loop: NOT -> NOT -> NOT (Odd number = oscillator)
        n1 = ic.getcomponent(Const.NOT)
        n2 = ic.getcomponent(Const.NOT)
        n3 = ic.getcomponent(Const.NOT)
        
        n2.connect(n1, 0)
        n3.connect(n2, 0)
        n1.connect(n3, 0) # Loop back
        
        # Trigger it? It's self-contained.
        # Check if it crashes or reaches a stable state (which it shouldn't).
        # In FLIPFLOP mode, it might just toggle endlessly if we step it, but here it runs until stability or max steps.
        # This tests stability/crash resilience.
        
        try:
            c.simulate(Const.FLIPFLOP)
            safe = True
        except:
            safe = False
        
        self.assert_true(safe, "Internal feedback loop doesn't crash engine")

    def test_dynamic_modification(self):
        """Test adding components to an IC that is already live."""
        c = self.setup_circuit()
        ic = c.getcomponent(Const.IC)
        inp = ic.getcomponent(Const.INPUT_PIN)
        out = ic.getcomponent(Const.OUTPUT_PIN)
        
        # Initially unconnected
        v = c.getcomponent(Const.VARIABLE)
        inp.connect(v, 0)
        c.toggle(v, Const.HIGH)
        
        self.assert_true(out.output == Const.UNKNOWN, "Output initially UNKNOWN")
        
        # Dynamically add a NOT gate bridging them
        not_g = ic.getcomponent(Const.NOT)
        not_g.connect(inp, 0)
        out.connect(not_g, 0)
        
        # Force update?
        c.toggle(v, Const.LOW)
        c.toggle(v, Const.HIGH)
        
        self.assert_true(out.output == Const.LOW, "Dynamically added gate works (HIGH->NOT->LOW)")

    def test_deletion_cleanup(self):
        """Test strict cleanup when deleting IC."""
        c = self.setup_circuit()
        ic = c.getcomponent(Const.IC)
        inp = ic.getcomponent(Const.INPUT_PIN)
        
        v = c.getcomponent(Const.VARIABLE)
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
        ic = c.getcomponent(Const.IC)
        ic.custom_name = "SuperChip"
        
        inp = ic.getcomponent(Const.INPUT_PIN)
        out = ic.getcomponent(Const.OUTPUT_PIN)
        
        # Nested IC
        inner = ic.getcomponent(Const.IC)
        inner.custom_name = "InnerChip"
        i_in = inner.getcomponent(Const.INPUT_PIN)
        i_out = inner.getcomponent(Const.OUTPUT_PIN)
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
        ic = c.getcomponent(Const.IC)
        
        and_g = ic.getcomponent(Const.AND)
        # Default limit usually 2?
        
        # Connect 5 things to it
        pins = []
        for i in range(5):
            p = ic.getcomponent(Const.INPUT_PIN)
            and_g.setlimits(5) # Auto-resize or manual resize
            and_g.connect(p, i) 
            pins.append(p)
            
        self.assert_true(and_g.inputlimit >= 5, "Internal gate resized for multiple inputs")


if __name__ == "__main__":
    test = ThoroughICTest()
    test.run()

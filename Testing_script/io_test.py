import sys
import os
import time
import json
import tempfile
import argparse

# Parse arguments for reactor selection
parser = argparse.ArgumentParser(description='Run IO Tests')
parser.add_argument('--reactor', action='store_true', help='Use Cython reactor backend')
parser.add_argument('--engine', action='store_true', help='Use Python engine backend')
args, unknown = parser.parse_known_args()

base_dir = os.getcwd()
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)

use_reactor = False
if args.reactor:
    use_reactor = True
elif args.engine:
    use_reactor = False
else:
    # Default to engine if nothing specified
    use_reactor = False

if use_reactor:
    print("Using Reactor (Cython) Backend for IO tests")
    sys.path.insert(0, os.path.join(root_dir, 'reactor'))
else:
    print("Using Engine (Python) Backend for IO tests")
    sys.path.insert(0, os.path.join(root_dir, 'engine'))

try:
    from Circuit import Circuit
    from IC import IC
    from Const import IC_ID, INPUT_PIN_ID, OUTPUT_PIN_ID
    from Const import NOT_ID, AND_ID, NAND_ID, OR_ID, NOR_ID, XOR_ID, XNOR_ID, VARIABLE_ID
    from Const import HIGH, LOW, UNKNOWN, ERROR, SIMULATE, set_MODE
except ImportError as e:
    print(f"FATAL ERROR: Could not import backend modules: {e}")
    sys.exit(1)


class IOTestSuite:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests_run = 0
        self.log_file = "test_io_results.txt"
        with open(self.log_file, 'w') as f:
            f.write("IO TEST REPORT\n")
            f.write("==============\n")

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
        self.log(f"Starting IO Tests...")
        self.test_write_read_json()
        self.test_save_get_ic()
        self.test_save_ic_with_var()
        self.test_ic_save_load_complex()
        self.test_invalid_json_handling()
        self.test_load_circuit_as_ic()
        self.test_load_ic_as_circuit()
        self.test_copy_empty()
        self.test_copy_paste_basic()
        self.test_copy_paste_connected()
        self.test_copy_paste_ic()
        self.test_paste_multiple_times()
        self.test_paste_without_clipboard()
        self.test_large_io_circuit()
        self.log(f"\nTest Summary: {self.passed} Passed, {self.failed} Failed")

    def test_write_read_json(self):
        c = self.setup_circuit()
        v1 = c.getcomponent(VARIABLE_ID)
        v2 = c.getcomponent(VARIABLE_ID)
        and_g = c.getcomponent(AND_ID)
        
        c.connect(and_g, v1, 0)
        c.connect(and_g, v2, 1)
        
        fp = os.path.join(tempfile.gettempdir(), "test_circuit.json")
        c.writetojson(fp)
        
        self.assert_true(os.path.exists(fp), "writetojson created file")
        
        c2 = self.setup_circuit()
        c2.readfromjson(fp)
        
        # Verify
        self.assert_true(len(c2.get_components()) == 3, "readfromjson loaded correct number of gates")
        self.assert_true(len(c2.get_variables()) == 2, "readfromjson loaded correct number of variables")
        
        os.remove(fp)

    def test_save_get_ic(self):
        c = self.setup_circuit()
        p_in = c.getcomponent(INPUT_PIN_ID)
        p_out = c.getcomponent(OUTPUT_PIN_ID)
        not_g = c.getcomponent(NOT_ID)
        
        c.connect(not_g, p_in, 0)
        c.connect(p_out, not_g, 0)
        
        fp = os.path.join(tempfile.gettempdir(), "test_ic.json")
        c.save_as_ic(fp, "InvertIC")
        
        self.assert_true(os.path.exists(fp), "save_as_ic created file")
        
        # Note: save_as_ic clears circuit (getIC is no longer auto-called)
        self.assert_true(len(c.get_components()) == 0, "save_as_ic cleared the circuit")
        self.assert_true(len(c.get_ics()) == 0, "save_as_ic cleared iclist")
        
        c2 = self.setup_circuit()
        loaded_ic = c2.getIC(fp)
        
        self.assert_true(loaded_ic is not None, "getIC loaded an IC object")
        self.assert_true(loaded_ic.custom_name == "InvertIC", "getIC preserved name")
        self.assert_true(len(loaded_ic.inputs) == 1, "getIC preserved inputs")
        self.assert_true(len(loaded_ic.outputs) == 1, "getIC preserved outputs")
        
        os.remove(fp)

    def test_save_ic_with_var(self):
        c = self.setup_circuit()
        v = c.getcomponent(VARIABLE_ID)
        not_g = c.getcomponent(NOT_ID)
        c.connect(not_g, v, 0)
        
        fp = os.path.join(tempfile.gettempdir(), "test_ic_var.json")
        c.save_as_ic(fp, "VarIC")
        
        # It should refuse to save and not clear the circuit
        self.assert_true(not os.path.exists(fp), "save_as_ic refused to save circuit with variables")
        self.assert_true(len(c.get_variables()) == 1, "Variables still in circuit")

    def test_invalid_json_handling(self):
        fp = os.path.join(tempfile.gettempdir(), "invalid.json")
        with open(fp, "w") as f:
            f.write("{invalid_json: true, broken")
        
        c = self.setup_circuit()
        crashed1 = False
        try:
            c.readfromjson(fp)
        except Exception:
            crashed1 = True
            
        self.assert_true(crashed1, "readfromjson raises exception on invalid json")
        
        crashed2 = False
        try:
            c.getIC(fp)
        except Exception:
            crashed2 = True
            
        self.assert_true(crashed2, "getIC raises exception on invalid json")
        os.remove(fp)

    def test_load_circuit_as_ic(self):
        # Create a simple circuit
        c = self.setup_circuit()
        g = c.getcomponent(NOT_ID)
        fp = os.path.join(tempfile.gettempdir(), "simple_circuit.json")
        c.writetojson(fp)
        
        c2 = self.setup_circuit()
        crashed = False
        res = None
        try:
            # Trying to load a standard circuit array into an IC will fail or return None
            res = c2.getIC(fp)
        except Exception:
            crashed = True
            
        self.assert_true(crashed or res is None, "getIC handles/rejects normal circuit JSON appropriately")
        os.remove(fp)

    def test_load_ic_as_circuit(self):
        # Create an IC
        c = self.setup_circuit()
        g = c.getcomponent(NOT_ID)
        fp = os.path.join(tempfile.gettempdir(), "test_ic_only.json")
        c.save_as_ic(fp, "MyIC")
        
        c2 = self.setup_circuit()
        crashed = False
        try:
            # save_as_ic produces a single array/dict for the IC, readfromjson anticipates a list of gates
            c2.readfromjson(fp)
        except Exception:
            crashed = True
            
        self.assert_true(crashed or len(c2.get_components()) == 0, "readfromjson handles/rejects IC JSON appropriately")
        os.remove(fp)

    def test_copy_empty(self):
        c = self.setup_circuit()
        c.copy([])
        # It should just return, clipboard.json might not be created or might be overwritten empty,
        # but won't crash
        self.assert_true(True, "copy([]) does not crash")

    def test_paste_without_clipboard(self):
        c = self.setup_circuit()
        # Ensure clipboard.json doesn't exist
        if os.path.exists("clipboard.json"):
            os.remove("clipboard.json")
            
        crashed = False
        try:
            c.paste()
        except FileNotFoundError:
            crashed = True
            
        self.assert_true(crashed, "paste raises FileNotFoundError if clipboard.json missing")

    def test_large_io_circuit(self):
        c = self.setup_circuit()
        # Build 1000 gates
        for i in range(1000):
            c.getcomponent(NOT_ID)
        fp = os.path.join(tempfile.gettempdir(), "large_circuit.json")
        c.writetojson(fp)
        self.assert_true(os.path.exists(fp), "writetojson handles large circuits")
        
        c2 = self.setup_circuit()
        c2.readfromjson(fp)
        self.assert_true(len(c2.get_components()) == 1000, "readfromjson handles large circuits (1000 gates)")
        os.remove(fp)

    def test_ic_save_load_complex(self):
        c_sub = self.setup_circuit()
        sub_in = c_sub.getcomponent(INPUT_PIN_ID)
        sub_out = c_sub.getcomponent(OUTPUT_PIN_ID)
        sub_not = c_sub.getcomponent(NOT_ID)
        c_sub.connect(sub_not, sub_in, 0)
        c_sub.connect(sub_out, sub_not, 0)
        fp_sub = os.path.join(tempfile.gettempdir(), "sub_ic.json")
        c_sub.save_as_ic(fp_sub, "SubIC")
        
        c = self.setup_circuit()
        sub_ic = c.getIC(fp_sub)
        
        main_in = c.getcomponent(INPUT_PIN_ID)
        main_out = c.getcomponent(OUTPUT_PIN_ID)
        c.connect(sub_ic.inputs[0], main_in, 0)
        c.connect(main_out, sub_ic.outputs[0], 0)
        
        fp = os.path.join(tempfile.gettempdir(), "complex_ic.json")
        c.save_as_ic(fp, "ComplexIC")
        
        c2 = self.setup_circuit()
        l_ic = c2.getIC(fp)
        
        self.assert_true(l_ic is not None, "Loaded nested IC")
        has_sub_ic = any(isinstance(x, IC) for x in l_ic.internal)
        self.assert_true(has_sub_ic, "Loaded nested IC maintains inner IC structure")
        os.remove(fp)
        if os.path.exists(fp_sub): os.remove(fp_sub)

    def test_copy_paste_basic(self):
        c = self.setup_circuit()
        nand_g = c.getcomponent(NAND_ID)
        not_g = c.getcomponent(NOT_ID)
        
        c.copy([nand_g, not_g])
        self.assert_true(os.path.exists("clipboard.json"), "copy creates clipboard.json")
        
        pasted = c.paste()
        self.assert_true(len(pasted) == 2, "paste returns correct number of items")
        self.assert_true(pasted[0] is not nand_g, "Pasted items are new instances")
        self.assert_true(len(c.get_components()) == 4, "Total canvas contains original + pasted")

    def test_copy_paste_connected(self):
        c = self.setup_circuit()
        v1 = c.getcomponent(VARIABLE_ID)
        nand_g = c.getcomponent(NAND_ID)
        c.connect(nand_g, v1, 0)
        
        c.copy([v1, nand_g])
        pasted = c.paste()
        self.assert_true(len(pasted) == 2, "Copied connected combo")
        
        p_v = pasted[0]
        p_nand = pasted[1]
        if p_v.id != VARIABLE_ID:
            p_v, p_nand = p_nand, p_v
            
        # check connection
        # verify p_v is source of p_nand
        is_connected = False
        if isinstance(p_nand.sources, list):
            for src in p_nand.sources:
                if src is p_v:
                    is_connected = True
        self.assert_true(is_connected, "Connections are preserved after pasting")

    def test_copy_paste_ic(self):
        c_sub = self.setup_circuit()
        pin1 = c_sub.getcomponent(INPUT_PIN_ID)
        pin2 = c_sub.getcomponent(OUTPUT_PIN_ID)
        not_g = c_sub.getcomponent(NOT_ID)
        c_sub.connect(not_g, pin1, 0)
        c_sub.connect(pin2, not_g, 0)
        fp_ic = os.path.join(tempfile.gettempdir(), "cp_ic.json")
        c_sub.save_as_ic(fp_ic, "CpIC")
        
        c = self.setup_circuit()
        ic = c.getIC(fp_ic)
        
        c.copy([ic])
        pasted = c.paste()
        
        self.assert_true(len(pasted) == 1, "Pasted an IC")
        p_ic = pasted[0]
        self.assert_true(isinstance(p_ic, IC), "Pasted object is IC")
        self.assert_true(len(p_ic.inputs) == 1, "Pasted IC has correct inputs")
        self.assert_true(len(p_ic.outputs) == 1, "Pasted IC has correct outputs")
        self.assert_true(p_ic is not ic, "Pasted IC is new instance")
        if os.path.exists(fp_ic): os.remove(fp_ic)

    def test_paste_multiple_times(self):
        c = self.setup_circuit()
        v1 = c.getcomponent(VARIABLE_ID)
        c.copy([v1])
        
        p1 = c.paste()
        p2 = c.paste()
        p3 = c.paste()
        
        self.assert_true(len(c.get_components()) == 4, "Can paste multiple times correctly")
        self.assert_true(len(c.get_variables()) == 4, "Variables are registered on each paste")

if __name__ == "__main__":
    t = IOTestSuite()
    t.run()
    if t.failed > 0:
        sys.exit(1)

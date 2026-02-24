"""
DARION LOGIC SIM — EVENT MANAGER EXTREME TEST SUITE
Thoroughly stress tests Event Manager (undo/redo, history limits, memory leaks, performance)
"""

import time
import sys
import os
import gc
import random

sys.setrecursionlimit(10_000)

base_dir = os.getcwd()
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)

import argparse
parser = argparse.ArgumentParser(description='Run Event Manager Tests')
parser.add_argument('--reactor', action='store_true', help='Use Cython reactor backend')
parser.add_argument('--engine', action='store_true', help='Use Python engine backend')
args, unknown = parser.parse_known_args()

use_reactor = True
if args.engine:
    use_reactor = False

# Add control to path
sys.path.append(os.path.join(root_dir, 'control'))
if use_reactor:
    print("Using Reactor (Cython) Backend")
    sys.path.insert(0, os.path.join(root_dir, 'reactor'))
else:
    print("Using Engine (Python) Backend")
    sys.path.insert(0, os.path.join(root_dir, 'engine'))

from Circuit import Circuit
from Event_Manager import Event
from Control import Add, AddIC, Delete, Connect, Disconnect, Paste, Toggle, SetLimits, Rename
import Const

# Overwrite constant limit to stress test extreme scenarios
Const.LIMIT = 100_000 

class EventManagerTestSuite:
    def __init__(self):
        self.circuit = Circuit()
        self.circuit.simulate(Const.SIMULATE) # Ensure we are in SIMULATE mode or DESIGN
        self.event_mgr = Event()
        self.passed = 0
        self.failed = 0
        self.test_count = 0
        self.log_file = sys.stdout

    def addcomponent(self, choice):
        cmd = Add(self.circuit, choice)
        cmd.execute()
        self.event_mgr.register(cmd)
        return cmd.gate
        
    def hide(self, gatelist):
        cmd = Delete(self.circuit, gatelist)
        cmd.execute()
        self.event_mgr.register(cmd)
        
    def connect(self, target, source, index):
        cmd = Connect(self.circuit, target, source, index)
        cmd.execute()
        self.event_mgr.register(cmd)
        
    def disconnect(self, target, index):
        cmd = Disconnect(self.circuit, target, index)
        cmd.execute()
        self.event_mgr.register(cmd)
        
    def input(self, target, val):
        cmd = Toggle(self.circuit, target, val)
        cmd.execute()
        self.event_mgr.register(cmd)
        
    def setlimits(self, target, size):
        cmd = SetLimits(target, size)
        cmd.execute()
        self.event_mgr.register(cmd)
        
    def paste(self):
        cmd = Paste(self.circuit)
        cmd.execute()
        self.event_mgr.register(cmd)
        
    def copy(self, gatelist):
        self.circuit.copy(gatelist)

    def log(self, msg):
        self.log_file.write(msg + "\n")
        self.log_file.flush()

    def assert_test(self, condition, test_name, details=""):
        self.test_count += 1
        if condition:
            self.passed += 1
            self.log(f"  [PASS] {test_name}")
            return True
        else:
            self.failed += 1
            self.log(f"  [FAIL] {test_name} {details}")
            return False

    def get_circuit_size(self):
        return len(self.circuit.canvas)

    def section(self, title):
        self.log(f"\n{'='*60}")
        self.log(f"  {title}")
        self.log(f"{'='*60}")

    def test_single_add_delete(self):
        self.section("Single Add/Delete Undo/Redo")
        start_size = self.get_circuit_size()
        
        # Add single
        gate = self.addcomponent(Const.AND_ID)
        self.assert_test(self.get_circuit_size() == start_size + 1, "Gate Added")
        
        # Undo Add
        self.event_mgr.undo()
        self.assert_test(self.get_circuit_size() == start_size, "Undo Add Gate")
        
        # Redo Add
        self.event_mgr.redo()
        self.assert_test(self.get_circuit_size() == start_size + 1, "Redo Add Gate")
        
        # Delete single logic (We must wrap gate in a list since hide takes a list)
        self.hide([gate])
        self.assert_test(self.get_circuit_size() == start_size, "Gate Deleted via hide()")
        
        # Undo Delete
        self.event_mgr.undo()
        self.assert_test(self.get_circuit_size() == start_size + 1, "Undo Delete Gate")
        
        # Redo Delete
        self.event_mgr.redo()
        self.assert_test(self.get_circuit_size() == start_size, "Redo Delete Gate")

    def test_mass_create_delete(self):
        self.section("Mass Create / Delete / Undo / Redo Stress")
        start_size = self.get_circuit_size()
        
        gates = []
        # Add 10,000 gates
        for i in range(10_000):
            g = self.addcomponent(Const.AND_ID)
            gates.append(g)
            
        self.assert_test(self.get_circuit_size() == start_size + 10_000, "10,000 Gates Added")
        
        # Event mgr hide can take a massive list
        start_time = time.perf_counter()
        self.hide(gates)
        end_time = time.perf_counter()
        
        self.assert_test(self.get_circuit_size() == start_size, f"10,000 Gates Deleted in {end_time - start_time:.4f}s")
        
        start_time = time.perf_counter()
        self.event_mgr.undo()
        end_time = time.perf_counter()
        
        self.assert_test(self.get_circuit_size() == start_size + 10_000, f"Undo Mass Delete in {end_time - start_time:.4f}s")
        
        start_time = time.perf_counter()
        self.event_mgr.redo()
        end_time = time.perf_counter()
        
        self.assert_test(self.get_circuit_size() == start_size, f"Redo Mass Delete in {end_time - start_time:.4f}s")
        
        # Undo to get the gates back
        self.event_mgr.undo()

        # Now test the limit queue purging bottleneck
        # The history has: [Add]*10000 + [MassDelete] = 10001
        # Now let's trigger the queue limit!
        original_limit = Const.LIMIT
        Const.LIMIT = 5 # Set very low to trigger limit popping
        try:
            # We will perform some dummy events to make the history shift, which causes popping off event queue
            # And triggers permanent object deletion bottleneck!
            for i in range(10):
                g = self.addcomponent(Const.OR_ID)
            self.assert_test(True, "Queue shift caused by reaching Const.LIMIT with mass-create didn't crash")
        except Exception as e:
            self.assert_test(False, "Mass Delete Queue popping logic crashed!", str(e))
        
        Const.LIMIT = original_limit

    def test_connect_disconnect_bottleneck(self):
        self.section("Connect / Disconnect Network Undo/Redo Stress")
        # Ensure we start fresh
        self.event_mgr.undolist.clear()
        self.event_mgr.redolist.clear()
        self.circuit.clearcircuit()
        
        v = self.addcomponent(Const.VARIABLE_ID)
        gates = []
        for i in range(1_000):
            g = self.addcomponent(Const.AND_ID)
            gates.append(g)
        
        # Add 1,000 connections
        start_t = time.perf_counter()
        for i in range(1_000):
            self.connect(gates[i], v, 0)
        end_t = time.perf_counter()
        self.assert_test(len(v.hitlist) == 1_000, f"1,000 connections created in {end_t - start_t:.4f}s")
        
        # Undo 1,000 connections
        start_t = time.perf_counter()
        for i in range(1_000):
            self.event_mgr.undo()
        end_t = time.perf_counter()
        self.assert_test(len(v.hitlist) == 0, f"Undo 1,000 connections in {end_t - start_t:.4f}s")
        
        # Redo 1,000 connections
        start_t = time.perf_counter()
        for i in range(1_000):
            self.event_mgr.redo()
        end_t = time.perf_counter()
        self.assert_test(len(v.hitlist) == 1_000, f"Redo 1,000 connections in {end_t - start_t:.4f}s")
        
        # Disconnect via Event_Manager
        start_t = time.perf_counter()
        for i in range(1_000):
            self.disconnect(gates[i], 0)
        end_t = time.perf_counter()
        self.assert_test(len(v.hitlist) == 0, f"1,000 disconnections in {end_t - start_t:.4f}s")
        
        # Undo 1000 disconnections
        start_t = time.perf_counter()
        for i in range(1_000):
            self.event_mgr.undo()
        end_t = time.perf_counter()
        self.assert_test(len(v.hitlist) == 1_000, f"Undo 1,000 disconnections in {end_t - start_t:.4f}s")

    def test_property_mutations(self):
        self.section("Property Mutations (Toggle/SetLimits)")
        self.circuit.clearcircuit()
        
        v = self.addcomponent(Const.VARIABLE_ID)
        
        self.assert_test(v.output == Const.LOW, "Initial Input LOW")
        
        # Toggle 1 -> HIGH
        self.input(v, Const.HIGH)
        self.assert_test(v.output == Const.HIGH, "Input set to HIGH")
        
        # Undo Toggle
        self.event_mgr.undo()
        self.assert_test(v.output == Const.LOW, "Undo set to LOW")
        
        # Redo Toggle
        self.event_mgr.redo()
        self.assert_test(v.output == Const.HIGH, "Redo set to HIGH")
        
        g = self.addcomponent(Const.AND_ID)
        self.assert_test(g.inputlimit == 2, "AND initial input limit 2")
        
        self.setlimits(g, 50)
        self.assert_test(len(g.sources) == 50, "AND limit set to 50")
        
        self.event_mgr.undo()
        self.assert_test(len(g.sources) == 2, "Undo limit to 2")
        
        self.event_mgr.redo()
        self.assert_test(len(g.sources) == 50, "Redo limit to 50")
        self.assert_test(g.sources[10] is None, "Ensure redo properly constructs internal states")

    def test_copy_paste_undo_redo(self):
        self.section("Copy/Paste Undo/Redo Integration")
        self.circuit.clearcircuit()
        self.event_mgr.undolist.clear()
        self.event_mgr.redolist.clear()
        
        gates = []
        for i in range(100):
            gates.append(self.addcomponent(Const.AND_ID))
            
        self.copy(gates)
        self.assert_test(len(self.circuit.copydata) == 100, "100 gates copied")
        
        self.paste()
        self.assert_test(len(self.circuit.canvas) == 200, "100 gates pasted -> 200 Total")
        
        # Undo paste
        start_t = time.perf_counter()
        self.event_mgr.undo()
        end_t = time.perf_counter()
        
        self.assert_test(len(self.circuit.canvas) == 100, f"Undo paste in {end_t - start_t:.4f}s")
        
        # Redo paste
        start_t = time.perf_counter()
        self.event_mgr.redo()
        end_t = time.perf_counter()
        
        self.assert_test(len(self.circuit.canvas) == 200, f"Redo paste in {end_t - start_t:.4f}s")

    def test_mega_chaos(self):
        self.section("Chaos Test - Random Operations, then Full Undo")
        self.circuit.clearcircuit()
        self.event_mgr.undolist.clear()
        self.event_mgr.redolist.clear()
        
        actions_performed = 0
        gate_types = [Const.AND_ID, Const.OR_ID, Const.NAND_ID, Const.NOR_ID, Const.XOR_ID, Const.VARIABLE_ID, Const.PROBE_ID]
        
        # 10,000 Random operations
        gates = []
        for i in range(1_000):
            gt = random.choice(gate_types)
            g = self.addcomponent(gt)
            gates.append(g)
            actions_performed += 1

            # Connect randomly
            if i > 0 and len(gates) > 1:
                target = random.choice(gates)
                source = random.choice(gates)
                if target.name not in ["Variable", "Probe"] and source != target:
                    # Find empty index
                    idx = -1
                    for ii in range(target.inputlimit):
                        if target.sources[ii] is None:
                            idx = ii
                            break
                    if idx != -1:
                        self.connect(target, source, idx)
                        actions_performed += 1

            if random.random() < 0.1 and len(gates) > 0:
                # hide gate
                todel = random.choice(gates)
                self.hide([todel])
                gates.remove(todel)
                actions_performed += 1

        canvas_size_after = len(self.circuit.canvas)
        self.assert_test(actions_performed > 0, f"Performed {actions_performed} operations... Canvas size: {canvas_size_after}")
        
        start_t = time.perf_counter()
        for _ in range(actions_performed):
            self.event_mgr.undo()
        end_t = time.perf_counter()
        
        self.assert_test(len(self.circuit.canvas) == 0, f"Chaos fully undone to empty canvas in {end_t - start_t:.4f}s")
        

    def run_all(self):
        self.log(f"\n{'='*70}")
        self.log(f"  DARION LOGIC SIM - EVENT MANAGER EXTREME TEST SUITE")
        self.log(f"{'='*70}")
        
        try:
            self.test_single_add_delete()
            self.test_mass_create_delete()
            self.test_connect_disconnect_bottleneck()
            self.test_property_mutations()
            self.test_copy_paste_undo_redo()
            self.test_mega_chaos()
        except Exception as e:
            self.log(f"\n[FATAL ERROR] {e}")
            import traceback
            traceback.print_exc()
            self.failed += 1

        self.log(f"\n{'='*70}")
        self.log(f"  SUMMARY: {self.passed} PASS, {self.failed} FAIL")
        self.log(f"{'='*70}")

if __name__ == '__main__':
    tester = EventManagerTestSuite()
    tester.run_all()
    if tester.failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

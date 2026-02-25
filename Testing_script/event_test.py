import argparse
import sys
import os
parser = argparse.ArgumentParser(description='Run Speed Tests')
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

# Try importing psutil for RAM monitoring
try:
    import psutil
    process = psutil.Process(os.getpid())
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
import unittest
from Circuit import Circuit
from Const import *
from Control import Add, Delete, Connect, Disconnect, Toggle, SetLimits, Rename
from Event_Manager import Event

# ... rest of your test code ...

class TestTimeTravel(unittest.TestCase):
    def setUp(self):
        """Initialize a fresh circuit and event manager for each test."""
        self.circuit = Circuit()
        self.em = Event()
        # Ensure simulation mode is active for testing logic states
        self.circuit.simulate(SIMULATE)

    def do(self, command):
        """Helper to execute and register a command if successful."""
        if command.execute():
            self.em.register(command)
        return command

    # ==========================================
    # 1. CORE MECHANICS & EDGE CASES
    # ==========================================

    def test_empty_undo_redo(self):
        """Undoing or redoing an empty history should not crash."""
        try:
            self.em.undo()
            self.em.redo()
        except Exception as e:
            self.fail(f"Empty undo/redo raised an exception: {e}")

    def test_redo_stack_invalidation(self):
        """Performing a new action after an undo must clear the redo stack."""
        cmd1 = self.do(Add(self.circuit, AND_ID))
        gate = cmd1.gate
        
        self.em.undo()
        self.assertNotIn(gate, self.circuit.get_components())
        self.assertEqual(len(self.em.redolist), 1)

        # Do a new action (should vaporize the redo timeline)
        self.do(Add(self.circuit, OR_ID))
        self.assertEqual(len(self.em.redolist), 0)

    def test_deque_maxlen_enforcement(self):
        """Ensure the event manager never exceeds the memory limit of 250 items."""
        for _ in range(300):
            self.do(Add(self.circuit, NOT_ID))
        
        self.assertEqual(len(self.em.undolist), 250)
        self.assertEqual(len(self.circuit.get_components()), 300)

    # ==========================================
    # 2. ATOMIC COMMAND VERIFICATION
    # ==========================================

    def test_rename_and_limits(self):
        """Test metadata mutation reversibility."""
        add_cmd = self.do(Add(self.circuit, AND_ID))
        gate = add_cmd.gate

        self.do(Rename(gate, "MyCustomAND"))
        self.assertEqual(gate.custom_name, "MyCustomAND")
        
        self.em.undo()
        # Control.py saves 'old_name' as gate.name (e.g. 'AND-1'), not as an empty string.
        self.assertEqual(gate.custom_name, gate.name) 
        
        self.em.redo()
        self.assertEqual(gate.custom_name, "MyCustomAND")

        self.do(SetLimits(gate, 4))
        self.assertEqual(gate.inputlimit, 4)
        self.em.undo()
        self.assertEqual(gate.inputlimit, 2)

    def test_connect_disconnect_time_travel(self):
        """Test physical topology changes."""
        var_cmd = self.do(Add(self.circuit, VARIABLE_ID))
        not_cmd = self.do(Add(self.circuit, NOT_ID))
        
        var_gate = var_cmd.gate
        not_gate = not_cmd.gate

        # Connect Var -> NOT
        self.do(Connect(self.circuit, not_gate, var_gate, 0))
        self.assertIs(not_gate.sources[0], var_gate)
        
        # Cross-backend extraction: Engine yields Profiles, Reactor yields Gates
        targets = [getattr(p, 'target', p) for p in var_gate.hitlist]
        self.assertIn(not_gate, targets)

        # Undo Connection
        self.em.undo()
        self.assertIsNone(not_gate.sources[0])
        
        targets = [getattr(p, 'target', p) for p in var_gate.hitlist]
        self.assertNotIn(not_gate, targets)

        # Redo Connection
        self.em.redo()
        self.assertIs(not_gate.sources[0], var_gate)

        # Manual Disconnect Command
        self.do(Disconnect(self.circuit, not_gate, 0))
        self.assertIsNone(not_gate.sources[0])
        
        # Undo Disconnect Command
        self.em.undo()
        self.assertIs(not_gate.sources[0], var_gate)

    def test_deletion_and_restoration(self):
        """Test bulk deletion of components."""
        g1 = self.do(Add(self.circuit, AND_ID)).gate
        g2 = self.do(Add(self.circuit, OR_ID)).gate
        
        self.do(Delete(self.circuit, [g1, g2]))
        self.assertNotIn(g1, self.circuit.get_components())
        self.assertNotIn(g2, self.circuit.get_components())

        self.em.undo()
        self.assertIn(g1, self.circuit.get_components())
        self.assertIn(g2, self.circuit.get_components())

    # ==========================================
    # 3. COMPLEX CIRCUIT TIME TRAVEL (SR LATCH)
    # ==========================================

    def test_sr_latch_state_reversal(self):
        """
        Builds a NOR-based SR Latch and toggles states.
        Verifies that Command-based 'Undo' on a stateful circuit correctly 
        triggers the memory state based on the CURRENT electrical propagation,
        rather than restoring a magical historical snapshot.
        """
        # 1. Build components
        s_var = self.do(Add(self.circuit, VARIABLE_ID)).gate
        r_var = self.do(Add(self.circuit, VARIABLE_ID)).gate
        nor_q = self.do(Add(self.circuit, NOR_ID)).gate
        nor_not_q = self.do(Add(self.circuit, NOR_ID)).gate

        # Set variables to 0 (LOW)
        self.do(Toggle(self.circuit, s_var, LOW))
        self.do(Toggle(self.circuit, r_var, LOW))

        # 2. Wire the Latch
        self.do(Connect(self.circuit, nor_q, r_var, 0))
        self.do(Connect(self.circuit, nor_not_q, s_var, 0))
        
        # Cross-couple
        self.do(Connect(self.circuit, nor_q, nor_not_q, 1))
        self.do(Connect(self.circuit, nor_not_q, nor_q, 1))

        # Initial state upon connection
        self.assertEqual(nor_q.output, HIGH)
        self.assertEqual(nor_not_q.output, LOW)
        
        # 3. RESET the Latch (S=0, R=1)
        self.do(Toggle(self.circuit, r_var, HIGH))
        self.assertEqual(nor_q.output, LOW)
        self.assertEqual(nor_not_q.output, HIGH)

        # --- TIME TRAVEL INITIATION ---

        # Undo the RESET (This issues the inverse command: Toggle R to LOW)
        self.em.undo()
        self.assertEqual(r_var.value, LOW)
        
        # Since S=0 and R=0, the latch enters MEMORY MODE.
        # It holds its CURRENT state (Q=0), it does NOT magically revert to 
        # the historical state (Q=1). This proves the engine simulates real physics!
        self.assertEqual(nor_q.output, LOW) 
        self.assertEqual(nor_not_q.output, HIGH)

        # Redo the RESET
        self.em.redo()
        self.assertEqual(r_var.value, HIGH)
        self.assertEqual(nor_q.output, LOW)
        self.assertEqual(nor_not_q.output, HIGH)

    def test_latch_total_annihilation_undo(self):
        """Test deleting an active, charged latch and undoing the deletion."""
        s_var = self.do(Add(self.circuit, VARIABLE_ID)).gate
        r_var = self.do(Add(self.circuit, VARIABLE_ID)).gate
        nor_q = self.do(Add(self.circuit, NOR_ID)).gate
        nor_not_q = self.do(Add(self.circuit, NOR_ID)).gate

        self.do(Connect(self.circuit, nor_q, r_var, 0))
        self.do(Connect(self.circuit, nor_not_q, s_var, 0))
        self.do(Connect(self.circuit, nor_q, nor_not_q, 1))
        self.do(Connect(self.circuit, nor_not_q, nor_q, 1))

        self.do(Toggle(self.circuit, r_var, HIGH)) # Force RESET
        self.assertEqual(nor_not_q.output, HIGH)

        # Nuke the entire circuit
        self.do(Delete(self.circuit, [s_var, r_var, nor_q, nor_not_q]))
        self.assertEqual(len(self.circuit.get_components()), 0)
        
        # Book counts should be cleared on hide
        self.assertEqual(nor_q.book[HIGH], 0)

        # Restore the circuit
        self.em.undo()
        self.assertEqual(len(self.circuit.get_components()), 4)
        
        # The electrical state should fully propagate and restore!
        self.assertEqual(nor_not_q.output, HIGH)

if __name__ == '__main__':
    unittest.main(verbosity=2)
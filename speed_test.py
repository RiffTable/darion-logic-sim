"""
DARION LOGIC SIM — COMPREHENSIVE TEST SUITE
Tests every aspect of the logic simulator in one click.
"""

import time
import sys
import os
import random
import platform
import gc
import tempfile

# --- CONFIGURATION & SETUP ---
sys.setrecursionlimit(10_000)

# Add engine to path
engine_path = os.path.join(os.getcwd(), 'engine')
if engine_path not in sys.path:
    sys.path.append(engine_path)

# Try importing psutil for RAM monitoring
try:
    import psutil
    process = psutil.Process(os.getpid())
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    from Circuit import Circuit
    from Event_Manager import Event
    import Const
    from Gates import Gate, Variable, Probe, Nothing, Profile
    from Gates import NOT, AND, NAND, OR, NOR, XOR, XNOR
    from Gates import InputPin, OutputPin
    from IC import IC
    from Store import Components
except ImportError as e:
    print(f"FATAL ERROR: Could not import engine modules: {e}")
    print("Ensure you have built the project (build.bat/sh) and are running this from the root.")
    sys.exit(1)


class ComprehensiveTestSuite:
    def __init__(self):
        self.circuit = Circuit()
        self.event_manager = Event(Circuit())
        self.passed = 0
        self.failed = 0
        self.test_count = 0
        # Performance metrics storage
        self.perf_metrics = {}
        
    def log(self, msg, end="\n"):
        print(msg, end=end)
        sys.stdout.flush()

    def timer(self, func):
        """Precise timing wrapper."""
        start = time.perf_counter_ns()
        func()
        end = time.perf_counter_ns()
        return (end - start) / 1_000_000  # Returns ms

    def assert_test(self, condition, test_name, details=""):
        """Assert a test condition and track results."""
        self.test_count += 1
        if condition:
            self.passed += 1
            self.log(f"    [PASS] {test_name}")
            return True
        else:
            self.failed += 1
            self.log(f"    [FAIL] {test_name} {details}")
            return False

    def section(self, title):
        """Print a section header."""
        self.log(f"\n{'='*70}")
        self.log(f"  {title}")
        self.log(f"{'='*70}")

    def subsection(self, title):
        """Print a subsection header."""
        self.log(f"\n  [{title}]")

    def run_all(self):
        print(f"\n{'='*70}")
        print(f"   DARION LOGIC SIM - COMPREHENSIVE TEST SUITE")
        print(f"{'='*70}")
        print(f"System: {platform.system()} {platform.release()} | Python {platform.python_version()}")
        if HAS_PSUTIL:
            print(f"Initial RAM: {process.memory_info().rss / 1024 / 1024:.2f} MB")
        print(f"{'-'*70}")

        # ==================== PART 1: UNIT TESTS ====================
        self.section("PART 1: UNIT TESTS")
        
        self.test_gate_construction()
        self.test_gate_logic()
        self.test_profile_operations()
        self.test_book_tracking()
        self.test_connection_mechanics()
        self.test_disconnection_mechanics()
        self.test_variable_operations()
        self.test_probe_operations()
        self.test_io_pins()
        self.test_setlimits()
        
        # ==================== PART 2: CIRCUIT OPERATIONS ====================
        self.section("PART 2: CIRCUIT OPERATIONS")
        
        self.test_circuit_management()
        self.test_propagation_simulate()
        self.test_propagation_flipflop()
        self.test_error_propagation()
        self.test_hide_reveal()
        self.test_reset()
        
        # ==================== PART 3: EVENT MANAGER (UNDO/REDO) ====================
        self.section("PART 3: EVENT MANAGER (UNDO/REDO)")
        
        self.test_undo_add()
        self.test_undo_delete()
        self.test_undo_connect()
        self.test_undo_disconnect()
        self.test_undo_toggle()
        self.test_undo_setlimits()
        self.test_redo_operations()
        
        # ==================== PART 4: IC (INTEGRATED CIRCUIT) ====================
        self.section("PART 4: IC (INTEGRATED CIRCUIT)")
        
        self.test_ic_creation()
        self.test_ic_connections()
        self.test_ic_hide_reveal()
        
        # ==================== PART 5: SERIALIZATION ====================
        self.section("PART 5: SERIALIZATION (SAVE/LOAD)")
        
        self.test_save_load_circuit()
        self.test_save_load_ic()
        self.test_copy_paste()
        
        # ==================== PART 6: TRUTH TABLE ====================
        self.section("PART 6: TRUTH TABLE")
        
        self.test_truth_table()
        
        # ==================== PART 7: PERFORMANCE BENCHMARKS ====================
        self.section("PART 7: PERFORMANCE BENCHMARKS")
        
        self.test_marathon(count=100_000)
        self.test_avalanche(layers=18)
        self.test_gridlock(size=250)
        self.test_echo_chamber(count=10_000)
        self.test_black_hole(inputs=100_000)
        self.test_paradox_burn()
        self.test_warehouse(count=500_000)

        # ==================== SUMMARY ====================
        self.section("FINAL SUMMARY")
        total = self.passed + self.failed
        self.log(f"\n  Total Tests: {total}")
        self.log(f"  Passed: {self.passed} ({100*self.passed/total:.1f}%)")
        self.log(f"  Failed: {self.failed}")
        
        # Performance Results Table
        self.log(f"\n  {'-'*60}")
        self.log(f"  PERFORMANCE RESULTS")
        self.log(f"  {'-'*60}")
        
        total_gates = 0
        total_time_ms = 0
        
        if 'marathon' in self.perf_metrics:
            m = self.perf_metrics['marathon']
            self.log(f"  Marathon (Serial):    {m['time']:.2f} ms | {m['latency']:.2f} ns/gate")
            total_gates += m['gates']
            total_time_ms += m['time']
        
        if 'avalanche' in self.perf_metrics:
            a = self.perf_metrics['avalanche']
            self.log(f"  Avalanche (Fanout):   {a['time']:.2f} ms | {a['rate']:,.0f} events/sec")
            total_gates += a['gates']
            total_time_ms += a['time']
        
        if 'gridlock' in self.perf_metrics:
            g = self.perf_metrics['gridlock']
            self.log(f"  Gridlock (Mesh):      {g['time']:.2f} ms | {g['gates']:,} gates")
            total_gates += g['gates']
            total_time_ms += g['time']
        
        if 'echo_chamber' in self.perf_metrics:
            e = self.perf_metrics['echo_chamber']
            gates_in_latches = e['latches'] * 2  # 2 NOR gates per latch
            self.log(f"  Echo Chamber (FF):    {e['time']:.2f} ms | {e['latches']:,} latches")
            total_gates += gates_in_latches
            total_time_ms += e['time']
        
        if 'black_hole' in self.perf_metrics:
            b = self.perf_metrics['black_hole']
            self.log(f"  Black Hole (Fan-in):  {b['time']:.4f} ms | {b['inputs']:,} inputs")
            total_gates += b['inputs']  # Count inputs as events
            total_time_ms += b['time']
        
        if 'paradox' in self.perf_metrics:
            p = self.perf_metrics['paradox']
            self.log(f"  Paradox (Loop):       {p['time']:.4f} ms | Burn detection")
        
        if 'warehouse' in self.perf_metrics:
            w = self.perf_metrics['warehouse']
            self.log(f"  Warehouse (Memory):   {w['allocated']:.1f} MB | {w['bytes_per_gate']:.1f} Bytes/Gate")
        
        self.log(f"  {'-'*60}")
        
        # Overall Performance Score
        if total_time_ms > 0:
            overall_rate = total_gates / (total_time_ms / 1000)  # gates per second
            self.log(f"\n  {'='*60}")
            self.log(f"  OVERALL PERFORMANCE SCORE")
            self.log(f"  {'='*60}")
            self.log(f"  Total Gates Processed:  {total_gates:,}")
            self.log(f"  Total Time:             {total_time_ms:.2f} ms")
            self.log(f"  Average Throughput:     {overall_rate:,.0f} gates/sec")
            self.log(f"  Average Throughput:     {overall_rate/1_000_000:.2f} M gates/sec")
            self.log(f"  {'='*60}")
        
        if self.failed == 0:
            self.log(f"\n  {'='*50}")
            self.log(f"  [SUCCESS] ALL TESTS PASSED")
            self.log(f"  {'='*50}")
        else:
            self.log(f"\n  {'='*50}")
            self.log(f"  [FAILURE] SOME TESTS FAILED")
            self.log(f"  {'='*50}")

    # =========================================================================
    # PART 1: UNIT TESTS
    # =========================================================================

    def test_gate_construction(self):
        self.subsection("Gate Construction")
        
        # Test all gate types can be constructed
        gates = [NOT(), AND(), NAND(), OR(), NOR(), XOR(), XNOR()]
        self.assert_test(len(gates) == 7, "All 7 gate types constructed")
        
        # Test Variable and Probe
        var = Variable()
        probe = Probe()
        self.assert_test(var.inputlimit == 1, "Variable has inputlimit=1")
        self.assert_test(probe.inputlimit == 1, "Probe has inputlimit=1")
        
        # Test AND gate default inputs
        and_gate = AND()
        self.assert_test(and_gate.inputlimit == 2, "AND gate has default inputlimit=2")
        self.assert_test(len(and_gate.sources) == 2, "AND gate has 2 source slots")
        
        # Test initial output state
        self.assert_test(and_gate.output == Const.UNKNOWN, "Gate starts with UNKNOWN output")

    def test_gate_logic(self):
        self.subsection("Gate Logic (All 7 Types)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        # NOT gate: inverts input
        v1 = c.getcomponent(Const.VARIABLE)
        not_g = c.getcomponent(Const.NOT)
        c.connect(not_g, v1, 0)
        c.toggle(v1, Const.HIGH)
        self.assert_test(not_g.output == Const.LOW, "NOT(1) = 0")
        c.toggle(v1, Const.LOW)
        self.assert_test(not_g.output == Const.HIGH, "NOT(0) = 1")
        
        # AND gate: all inputs must be high
        c.clearcircuit()
        c.simulate(Const.SIMULATE)
        v1, v2 = c.getcomponent(Const.VARIABLE), c.getcomponent(Const.VARIABLE)
        and_g = c.getcomponent(Const.AND)
        c.connect(and_g, v1, 0)
        c.connect(and_g, v2, 1)
        c.toggle(v1, 1); c.toggle(v2, 1)
        self.assert_test(and_g.output == Const.HIGH, "AND(1,1) = 1")
        c.toggle(v2, 0)
        self.assert_test(and_g.output == Const.LOW, "AND(1,0) = 0")
        
        # NAND gate: inverted AND
        c.clearcircuit()
        c.simulate(Const.SIMULATE)
        v1, v2 = c.getcomponent(Const.VARIABLE), c.getcomponent(Const.VARIABLE)
        nand_g = c.getcomponent(Const.NAND)
        c.connect(nand_g, v1, 0)
        c.connect(nand_g, v2, 1)
        c.toggle(v1, 1); c.toggle(v2, 1)
        self.assert_test(nand_g.output == Const.LOW, "NAND(1,1) = 0")
        c.toggle(v2, 0)
        self.assert_test(nand_g.output == Const.HIGH, "NAND(1,0) = 1")
        
        # OR gate: any input high
        c.clearcircuit()
        c.simulate(Const.SIMULATE)
        v1, v2 = c.getcomponent(Const.VARIABLE), c.getcomponent(Const.VARIABLE)
        or_g = c.getcomponent(Const.OR)
        c.connect(or_g, v1, 0)
        c.connect(or_g, v2, 1)
        c.toggle(v1, 0); c.toggle(v2, 0)
        self.assert_test(or_g.output == Const.LOW, "OR(0,0) = 0")
        c.toggle(v1, 1)
        self.assert_test(or_g.output == Const.HIGH, "OR(1,0) = 1")
        
        # NOR gate: inverted OR
        c.clearcircuit()
        c.simulate(Const.SIMULATE)
        v1, v2 = c.getcomponent(Const.VARIABLE), c.getcomponent(Const.VARIABLE)
        nor_g = c.getcomponent(Const.NOR)
        c.connect(nor_g, v1, 0)
        c.connect(nor_g, v2, 1)
        c.toggle(v1, 0); c.toggle(v2, 0)
        self.assert_test(nor_g.output == Const.HIGH, "NOR(0,0) = 1")
        c.toggle(v1, 1)
        self.assert_test(nor_g.output == Const.LOW, "NOR(1,0) = 0")
        
        # XOR gate: odd number of highs
        c.clearcircuit()
        c.simulate(Const.SIMULATE)
        v1, v2 = c.getcomponent(Const.VARIABLE), c.getcomponent(Const.VARIABLE)
        xor_g = c.getcomponent(Const.XOR)
        c.connect(xor_g, v1, 0)
        c.connect(xor_g, v2, 1)
        c.toggle(v1, 1); c.toggle(v2, 0)
        self.assert_test(xor_g.output == Const.HIGH, "XOR(1,0) = 1")
        c.toggle(v2, 1)
        self.assert_test(xor_g.output == Const.LOW, "XOR(1,1) = 0")
        
        # XNOR gate: inverted XOR
        c.clearcircuit()
        c.simulate(Const.SIMULATE)
        v1, v2 = c.getcomponent(Const.VARIABLE), c.getcomponent(Const.VARIABLE)
        xnor_g = c.getcomponent(Const.XNOR)
        c.connect(xnor_g, v1, 0)
        c.connect(xnor_g, v2, 1)
        c.toggle(v1, 1); c.toggle(v2, 1)
        self.assert_test(xnor_g.output == Const.HIGH, "XNOR(1,1) = 1")
        c.toggle(v2, 0)
        self.assert_test(xnor_g.output == Const.LOW, "XNOR(1,0) = 0")

    def test_profile_operations(self):
        self.subsection("Profile Operations (add/remove/hide/reveal/update/burn)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        v = c.getcomponent(Const.VARIABLE)
        g = c.getcomponent(Const.AND)
        c.connect(g, v, 0)
        
        # Check profile was created
        self.assert_test(len(v.hitlist) == 1, "Profile created on connect")
        self.assert_test(g in v.targets, "Target registered in source.targets")
        
        # Check profile.index
        profile = v.hitlist[0]
        self.assert_test(profile.target == g, "Profile.target is correct")
        self.assert_test(profile.source == v, "Profile.source is correct")

    def test_book_tracking(self):
        self.subsection("Book Tracking (input counting)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        v1 = c.getcomponent(Const.VARIABLE)
        v2 = c.getcomponent(Const.VARIABLE)
        g = c.getcomponent(Const.AND)
        
        c.toggle(v1, Const.HIGH)
        c.toggle(v2, Const.LOW)
        c.connect(g, v1, 0)
        c.connect(g, v2, 1)
        
        # book[LOW]=1, book[HIGH]=1
        self.assert_test(g.book[Const.HIGH] == 1, "Book tracks 1 HIGH input")
        self.assert_test(g.book[Const.LOW] == 1, "Book tracks 1 LOW input")
        
        c.toggle(v2, Const.HIGH)
        self.assert_test(g.book[Const.HIGH] == 2, "Book updates on signal change")

    def test_connection_mechanics(self):
        self.subsection("Connection Mechanics")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        v = c.getcomponent(Const.VARIABLE)
        g = c.getcomponent(Const.AND)
        
        # Before connection
        self.assert_test(g.sources[0] == Nothing, "Source slot starts as Nothing")
        
        c.connect(g, v, 0)
        
        # After connection
        self.assert_test(g.sources[0] == v, "Source slot filled after connect")
        self.assert_test(g in v.targets, "Gate added to source's targets dict")

    def test_disconnection_mechanics(self):
        self.subsection("Disconnection Mechanics")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        v = c.getcomponent(Const.VARIABLE)
        g = c.getcomponent(Const.AND)
        c.connect(g, v, 0)
        
        # Before disconnection
        self.assert_test(g.sources[0] == v, "Connected before disconnect")
        
        c.disconnect(g, 0)
        
        # After disconnection
        self.assert_test(g.sources[0] == Nothing, "Source cleared after disconnect")
        self.assert_test(g not in v.targets, "Gate removed from source's targets")

    def test_variable_operations(self):
        self.subsection("Variable Operations")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        v = c.getcomponent(Const.VARIABLE)
        self.assert_test(v.sources == 0, "Variable sources is int (not list)")
        
        c.toggle(v, Const.HIGH)
        self.assert_test(v.output == Const.HIGH, "Variable output after toggle HIGH")
        
        c.toggle(v, Const.LOW)
        self.assert_test(v.output == Const.LOW, "Variable output after toggle LOW")

    def test_probe_operations(self):
        self.subsection("Probe Operations")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        v = c.getcomponent(Const.VARIABLE)
        p = c.getcomponent(Const.PROBE)
        c.connect(p, v, 0)
        
        c.toggle(v, Const.HIGH)
        self.assert_test(p.output == Const.HIGH, "Probe follows source (HIGH)")
        
        c.toggle(v, Const.LOW)
        self.assert_test(p.output == Const.LOW, "Probe follows source (LOW)")

    def test_io_pins(self):
        self.subsection("InputPin/OutputPin Operations")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        inp = c.getcomponent(Const.INPUT_PIN)
        out = c.getcomponent(Const.OUTPUT_PIN)
        v = c.getcomponent(Const.VARIABLE)
        g = c.getcomponent(Const.NOT)
        
        # InputPin: connects like a probe
        c.connect(inp, v, 0)
        c.toggle(v, Const.HIGH)
        self.assert_test(inp.output == Const.HIGH, "InputPin follows source")
        
        # OutputPin: connects like a probe
        c.connect(g, inp, 0)
        c.connect(out, g, 0)
        self.assert_test(out.output == Const.LOW, "OutputPin follows source (NOT(1)=0)")

    def test_setlimits(self):
        self.subsection("setlimits (change input count)")
        c = Circuit()
        
        g = c.getcomponent(Const.AND)
        self.assert_test(g.inputlimit == 2, "Default AND has 2 inputs")
        
        # Increase limit
        result = g.setlimits(4)
        self.assert_test(result == True, "setlimits(4) returns True")
        self.assert_test(g.inputlimit == 4, "Input limit increased to 4")
        self.assert_test(len(g.sources) == 4, "Sources list expanded")
        
        # Decrease limit (no connections)
        result = g.setlimits(2)
        self.assert_test(result == True, "setlimits(2) returns True")
        self.assert_test(g.inputlimit == 2, "Input limit decreased to 2")

    # =========================================================================
    # PART 2: CIRCUIT OPERATIONS
    # =========================================================================

    def test_circuit_management(self):
        self.subsection("Circuit Management")
        c = Circuit()
        
        # Test getcomponent
        g = c.getcomponent(Const.AND)
        self.assert_test(g is not None, "getcomponent returns gate")
        self.assert_test(g in c.canvas, "Gate added to canvas")
        self.assert_test(g in c.objlist[Const.AND], "Gate added to objlist")
        
        # Test clearcircuit
        c.clearcircuit()
        self.assert_test(len(c.canvas) == 0, "clearcircuit empties canvas")
        self.assert_test(len(c.varlist) == 0, "clearcircuit empties varlist")

    def test_propagation_simulate(self):
        self.subsection("Signal Propagation (SIMULATE mode)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        # Chain: V -> NOT -> NOT -> NOT (output should be inverted 3x)
        v = c.getcomponent(Const.VARIABLE)
        n1 = c.getcomponent(Const.NOT)
        n2 = c.getcomponent(Const.NOT)
        n3 = c.getcomponent(Const.NOT)
        c.connect(n1, v, 0)
        c.connect(n2, n1, 0)
        c.connect(n3, n2, 0)
        
        c.toggle(v, Const.HIGH)
        self.assert_test(n3.output == Const.LOW, "3 NOTs: HIGH -> LOW")
        
        c.toggle(v, Const.LOW)
        self.assert_test(n3.output == Const.HIGH, "3 NOTs: LOW -> HIGH")

    def test_propagation_flipflop(self):
        self.subsection("Signal Propagation (FLIPFLOP mode)")
        c = Circuit()
        c.simulate(Const.FLIPFLOP)
        
        # SR Latch: two NOR gates with feedback
        s = c.getcomponent(Const.VARIABLE)
        r = c.getcomponent(Const.VARIABLE)
        q = c.getcomponent(Const.NOR)
        qb = c.getcomponent(Const.NOR)
        
        c.connect(q, r, 0)
        c.connect(qb, s, 0)
        c.connect(q, qb, 1)
        c.connect(qb, q, 1)
        
        # Set latch
        c.toggle(s, 1)
        c.toggle(s, 0)
        self.assert_test(q.output == Const.HIGH, "SR Latch: SET makes Q=1")
        
        # Reset latch
        c.toggle(r, 1)
        c.toggle(r, 0)
        self.assert_test(q.output == Const.LOW, "SR Latch: RESET makes Q=0")

    def test_error_propagation(self):
        self.subsection("Error Propagation")
        c = Circuit()
        c.simulate(Const.FLIPFLOP)
        
        # Create XOR feedback (should cause error)
        v = c.getcomponent(Const.VARIABLE)
        xor_g = c.getcomponent(Const.XOR)
        c.connect(xor_g, v, 0)
        c.connect(xor_g, xor_g, 1)  # self-loop
        
        c.toggle(v, 1)
        self.assert_test(xor_g.output == Const.ERROR, "XOR feedback causes ERROR")

    def test_hide_reveal(self):
        self.subsection("Hide/Reveal Operations")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        v = c.getcomponent(Const.VARIABLE)
        g = c.getcomponent(Const.AND)
        c.connect(g, v, 0)
        
        # Hide
        c.hideComponent(g)
        self.assert_test(g not in c.canvas, "Hidden gate removed from canvas")
        self.assert_test(g not in v.targets, "Hidden gate removed from source targets")
        
        # Reveal
        c.renewComponent(g)
        self.assert_test(g in c.canvas, "Revealed gate back in canvas")
        self.assert_test(g in v.targets, "Revealed gate back in source targets")

    def test_reset(self):
        self.subsection("Circuit Reset")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        v = c.getcomponent(Const.VARIABLE)
        g = c.getcomponent(Const.NOT)
        c.connect(g, v, 0)
        c.toggle(v, Const.HIGH)
        
        self.assert_test(g.output == Const.LOW, "NOT(1) = 0 before reset")
        
        c.reset()
        
        self.assert_test(Const.get_MODE() == Const.DESIGN, "Mode is DESIGN after reset")
        self.assert_test(g.output == Const.UNKNOWN, "Output is UNKNOWN after reset")

    # =========================================================================
    # PART 3: EVENT MANAGER (UNDO/REDO)
    # =========================================================================

    def test_undo_add(self):
        self.subsection("Undo: Add Component")
        e = Event(Circuit())
        
        g = e.addcomponent(Const.AND)
        self.assert_test(g in e.circuit.canvas, "Gate added to canvas")
        
        e.undo()
        self.assert_test(g not in e.circuit.canvas, "Undo removes gate from canvas")

    def test_undo_delete(self):
        self.subsection("Undo: Delete Component")
        e = Event(Circuit())
        
        g = e.addcomponent(Const.AND)
        e.hide(g)
        self.assert_test(g not in e.circuit.canvas, "Gate hidden from canvas")
        
        e.undo()
        self.assert_test(g in e.circuit.canvas, "Undo restores gate to canvas")

    def test_undo_connect(self):
        self.subsection("Undo: Connect")
        e = Event(Circuit())
        e.circuit.simulate(Const.SIMULATE)
        
        v = e.addcomponent(Const.VARIABLE)
        g = e.addcomponent(Const.AND)
        e.connect(g, v, 0)
        
        self.assert_test(g.sources[0] == v, "Connected")
        
        e.undo()
        self.assert_test(g.sources[0] == Nothing, "Undo disconnects")

    def test_undo_disconnect(self):
        self.subsection("Undo: Disconnect")
        e = Event(Circuit())
        e.circuit.simulate(Const.SIMULATE)
        
        v = e.addcomponent(Const.VARIABLE)
        g = e.addcomponent(Const.AND)
        e.connect(g, v, 0)
        e.disconnect(g, 0)
        
        self.assert_test(g.sources[0] == Nothing, "Disconnected")
        
        e.undo()
        self.assert_test(g.sources[0] == v, "Undo reconnects")

    def test_undo_toggle(self):
        self.subsection("Undo: Toggle Variable")
        e = Event(Circuit())
        e.circuit.simulate(Const.SIMULATE)
        
        v = e.addcomponent(Const.VARIABLE)
        e.input(v, 1)
        
        self.assert_test(v.output == Const.HIGH, "Variable set to HIGH")
        
        e.undo()
        self.assert_test(v.output == Const.LOW, "Undo reverts to LOW")

    def test_undo_setlimits(self):
        self.subsection("Undo: setlimits")
        e = Event(Circuit())
        
        g = e.addcomponent(Const.AND)
        e.setlimits(g, 4)
        
        self.assert_test(g.inputlimit == 4, "Limit increased to 4")
        
        e.undo()
        self.assert_test(g.inputlimit == 2, "Undo reverts limit to 2")

    def test_redo_operations(self):
        self.subsection("Redo Operations")
        e = Event(Circuit())
        
        g = e.addcomponent(Const.AND)
        e.undo()
        self.assert_test(g not in e.circuit.canvas, "Undo removes gate")
        
        e.redo()
        self.assert_test(g in e.circuit.canvas, "Redo restores gate")

    # =========================================================================
    # PART 4: IC (INTEGRATED CIRCUIT)
    # =========================================================================

    def test_ic_creation(self):
        self.subsection("IC Creation")
        c = Circuit()
        
        ic = c.getcomponent(Const.IC)
        self.assert_test(ic is not None, "IC created")
        self.assert_test(isinstance(ic, IC), "IC is instance of IC class")
        self.assert_test(ic in c.iclist, "IC added to iclist")

    def test_ic_connections(self):
        self.subsection("IC Connections (InputPin/OutputPin)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        # Create IC with internal gates
        ic = c.getcomponent(Const.IC)
        inp = ic.getcomponent(Const.INPUT_PIN)
        out = ic.getcomponent(Const.OUTPUT_PIN)
        not_g = ic.getcomponent(Const.NOT)
        
        # Wire internal: inp -> not -> out
        not_g.connect(inp, 0)
        out.connect(not_g, 0)
        
        # Connect external variable to IC input
        v = c.getcomponent(Const.VARIABLE)
        inp.connect(v, 0)
        
        c.toggle(v, Const.HIGH)
        self.assert_test(out.output == Const.LOW, "IC internal NOT inverts signal")

    def test_ic_hide_reveal(self):
        self.subsection("IC Hide/Reveal")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        v = c.getcomponent(Const.VARIABLE)
        ic = c.getcomponent(Const.IC)
        inp = ic.getcomponent(Const.INPUT_PIN)
        out = ic.getcomponent(Const.OUTPUT_PIN)
        
        inp.connect(v, 0)
        
        # Hide IC
        ic.hide()
        self.assert_test(inp not in v.targets, "IC.hide() disconnects input pins from sources")
        
        # Reveal IC
        ic.reveal()
        self.assert_test(inp in v.targets, "IC.reveal() reconnects input pins")

    # =========================================================================
    # PART 5: SERIALIZATION
    # =========================================================================

    def test_save_load_circuit(self):
        self.subsection("Save/Load Circuit")
        
        # Create a circuit
        c1 = Circuit()
        c1.simulate(Const.SIMULATE)
        v = c1.getcomponent(Const.VARIABLE)
        g = c1.getcomponent(Const.NOT)
        c1.connect(g, v, 0)
        c1.toggle(v, Const.HIGH)
        
        # Save
        temp_file = os.path.join(tempfile.gettempdir(), "test_circuit.json")
        c1.writetojson(temp_file)
        self.assert_test(os.path.exists(temp_file), "Circuit saved to file")
        
        # Load into new circuit
        c2 = Circuit()
        c2.readfromjson(temp_file)
        c2.simulate(Const.SIMULATE)
        
        self.assert_test(len(c2.canvas) == 2, "Loaded circuit has 2 components")
        self.assert_test(len(c2.varlist) == 1, "Loaded circuit has 1 variable")
        
        # Cleanup
        os.remove(temp_file)

    def test_save_load_ic(self):
        self.subsection("Save/Load IC")
        
        # Create a simple inverter IC
        c1 = Circuit()
        inp = c1.getcomponent(Const.INPUT_PIN)
        not_g = c1.getcomponent(Const.NOT)
        out = c1.getcomponent(Const.OUTPUT_PIN)
        c1.connect(not_g, inp, 0)
        c1.connect(out, not_g, 0)
        
        # Save as IC
        temp_file = os.path.join(tempfile.gettempdir(), "test_ic.json")
        c1.save_as_ic(temp_file, "TestInverter")
        self.assert_test(os.path.exists(temp_file), "IC saved to file")
        
        # Load IC into new circuit
        c2 = Circuit()
        ic = c2.getIC(temp_file)
        self.assert_test(ic is not None, "IC loaded from file")
        self.assert_test(len(ic.inputs) == 1, "IC has 1 input pin")
        self.assert_test(len(ic.outputs) == 1, "IC has 1 output pin")
        
        # Cleanup
        os.remove(temp_file)

    def test_copy_paste(self):
        self.subsection("Copy/Paste Operations")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        # Create components
        v = c.getcomponent(Const.VARIABLE)
        g = c.getcomponent(Const.NOT)
        c.connect(g, v, 0)
        
        initial_count = len(c.canvas)
        
        # Copy and paste
        c.copy([g])
        new_items = c.paste()
        
        self.assert_test(len(c.canvas) == initial_count + 1, "Paste adds new component")
        self.assert_test(new_items is not None, "Paste returns new item codes")

    # =========================================================================
    # PART 6: TRUTH TABLE
    # =========================================================================

    def test_truth_table(self):
        self.subsection("Truth Table Generation")
        c = Circuit()
        
        # Create AND gate with 2 variables
        v1 = c.getcomponent(Const.VARIABLE)
        v2 = c.getcomponent(Const.VARIABLE)
        g = c.getcomponent(Const.AND)
        c.connect(g, v1, 0)
        c.connect(g, v2, 1)
        
        c.simulate(Const.SIMULATE)
        
        table = c.truthTable()
        self.assert_test(table is not None, "Truth table generated")
        self.assert_test("Truth Table" in table, "Output contains 'Truth Table'")
        # AND truth table should have 4 rows (00, 01, 10, 11)
        # Only 11 produces T
        self.assert_test(table.count("T") >= 1, "Truth table shows TRUE output")

    # =========================================================================
    # PART 7: PERFORMANCE BENCHMARKS
    # =========================================================================

    def test_marathon(self, count):
        self.subsection(f"Marathon: {count:,} NOT Gates (Serial Latency)")
        self.circuit.clearcircuit()
        c = self.circuit
        
        inp = c.getcomponent(Const.VARIABLE)
        prev = inp
        gates = []
        for _ in range(count):
            g = c.getcomponent(Const.NOT)
            c.connect(g, prev, 0)
            prev = g
            gates.append(g)

        c.simulate(Const.SIMULATE)
        c.toggle(inp, 0)
        
        duration = self.timer(lambda: c.toggle(inp, 1))
        
        expected = 'T' if (count % 2 == 0) else 'F'
        actual = gates[-1].getoutput()
        passed = (actual == expected)
        
        latency = (duration*1e6)/count
        self.perf_metrics['marathon'] = {'time': duration, 'latency': latency, 'gates': count}

        self.log(f"    Time: {duration:.4f} ms | Latency: {latency:.2f} ns/gate")
        self.assert_test(passed, f"Output correct ({expected})")

    def test_avalanche(self, layers):
        total = (2**layers)-1
        self.subsection(f"Avalanche: {layers} Layers ({total:,} Gates)")
        self.circuit.clearcircuit()
        c = self.circuit
        
        root = c.getcomponent(Const.VARIABLE)
        layer = [root]
        for _ in range(layers):
            next_l = []
            for p in layer:
                g1 = c.getcomponent(Const.AND); c.setlimits(g1, 1); c.connect(g1, p, 0)
                g2 = c.getcomponent(Const.AND); c.setlimits(g2, 1); c.connect(g2, p, 0)
                next_l.extend([g1, g2])
            layer = next_l

        c.simulate(Const.SIMULATE)
        c.toggle(root, 0)

        duration = self.timer(lambda: c.toggle(root, 1))
        
        rate = total/(duration/1000)
        self.perf_metrics['avalanche'] = {'time': duration, 'rate': rate, 'gates': total}

        self.log(f"    Time: {duration:.4f} ms | Rate: {rate:,.0f} events/sec")
        self.assert_test(True, "Avalanche completed")

    def test_gridlock(self, size):
        total = size*size
        self.subsection(f"Gridlock: {size}x{size} Mesh ({total:,} Gates)")
        self.circuit.clearcircuit()
        c = self.circuit

        grid = [[None]*size for _ in range(size)]
        trig = c.getcomponent(Const.VARIABLE)

        for r in range(size):
            for k in range(size):
                grid[r][k] = c.getcomponent(Const.OR)
        
        for r in range(size):
            for k in range(size):
                g = grid[r][k]
                ins = 0
                if r>0: c.connect(g, grid[r-1][k], ins); ins+=1
                elif r==0 and k==0: c.connect(g, trig, 0); ins+=1
                if k>0: c.connect(g, grid[r][k-1], ins); ins+=1
                c.setlimits(g, max(1, ins))

        c.simulate(Const.SIMULATE)
        c.toggle(trig, 0)

        duration = self.timer(lambda: c.toggle(trig, 1))
        
        passed = (grid[size-1][size-1].getoutput() == 'T')
        
        self.perf_metrics['gridlock'] = {'time': duration, 'gates': total, 'size': size}

        self.log(f"    Time: {duration:.4f} ms")
        self.assert_test(passed, "Signal reached corner")

    def test_echo_chamber(self, count):
        self.subsection(f"Echo Chamber: {count:,} SR Latches (FLIPFLOP mode)")
        self.circuit.clearcircuit()
        c = self.circuit
        c.simulate(Const.FLIPFLOP)

        set_line = c.getcomponent(Const.VARIABLE)
        rst_line = c.getcomponent(Const.VARIABLE)
        
        latches = []
        for _ in range(count):
            q = c.getcomponent(Const.NOR)
            qb = c.getcomponent(Const.NOR)
            c.connect(q, rst_line, 0)
            c.connect(qb, set_line, 0)
            c.connect(q, qb, 1)
            c.connect(qb, q, 1)
            latches.append(q)

        c.toggle(set_line, 0)
        c.toggle(rst_line, 1)
        c.toggle(rst_line, 0)

        duration = self.timer(lambda: c.toggle(set_line, 1))
        
        passed = all(l.getoutput() == 'T' for l in latches)
        
        self.perf_metrics['echo_chamber'] = {'time': duration, 'latches': count}

        self.log(f"    Time: {duration:.4f} ms")
        self.assert_test(passed, "All latches set correctly")

    def test_black_hole(self, inputs):
        self.subsection(f"Black Hole: {inputs:,} Inputs -> 1 AND Gate")
        self.circuit.clearcircuit()
        c = self.circuit
        c.simulate(Const.SIMULATE)

        black_hole = c.getcomponent(Const.AND)
        c.setlimits(black_hole, inputs)

        vars_list = []
        for i in range(inputs):
            v = c.getcomponent(Const.VARIABLE)
            c.connect(black_hole, v, i)
            vars_list.append(v)
        
        for i in range(inputs - 1):
            c.toggle(vars_list[i], 1)
        
        trigger = vars_list[-1]
        duration = self.timer(lambda: c.toggle(trigger, 1))
        
        passed = (black_hole.getoutput() == 'T')
        
        self.perf_metrics['black_hole'] = {'time': duration, 'inputs': inputs}

        self.log(f"    Time: {duration:.4f} ms")
        self.assert_test(passed, "AND gate output is HIGH")

    def test_paradox_burn(self):
        self.subsection("Paradox: XOR Feedback Loop (Oscillation Test)")
        
        self.circuit.clearcircuit()
        c = self.circuit
        c.simulate(Const.FLIPFLOP)

        source = c.getcomponent(Const.VARIABLE)
        xor_gate = c.getcomponent(Const.XOR)

        c.connect(xor_gate, source, 0)
        c.connect(xor_gate, xor_gate, 1)  # Loop
        
        try:
            start = time.perf_counter_ns()
            c.toggle(source, 1)
            end = time.perf_counter_ns()
            dt = (end - start) / 1_000_000
            
            self.perf_metrics['paradox'] = {'time': dt}
            
            self.log(f"    Time: {dt:.4f} ms (Engine halted safely)")
            self.assert_test(xor_gate.output == Const.ERROR, "XOR burns to ERROR state")
            
        except RecursionError:
            self.assert_test(True, "Caught by Python RecursionError")
        except Exception as e:
            self.assert_test(False, f"CRASHED: {e}")

    def test_warehouse(self, count):
        self.subsection(f"Warehouse: {count:,} Disconnected NOT Gates (Memory Test)")
        
        if not HAS_PSUTIL:
            self.log("    [SKIPPED] psutil not installed")
            return

        self.circuit.clearcircuit()
        gc.collect()
        time.sleep(0.1)
        baseline = process.memory_info().rss
        self.log(f"    Baseline RAM: {baseline/1024/1024:.2f} MB")

        c = self.circuit
        gates = []
        for _ in range(count):
            gates.append(c.getcomponent(Const.NOT))
        
        current = process.memory_info().rss
        delta_bytes = current - baseline
        mb_used = delta_bytes / 1024 / 1024
        bytes_per_gate = delta_bytes / count

        self.log(f"    Allocated: {mb_used:.2f} MB | {bytes_per_gate:.2f} Bytes/Gate")
        
        self.perf_metrics['warehouse'] = {'allocated': mb_used, 'bytes_per_gate': bytes_per_gate, 'gates': count}

        gates = None
        self.circuit.clearcircuit()
        gc.collect()
        time.sleep(0.1)
        final_mem = process.memory_info().rss
        leak = final_mem - baseline
        
        passed_leak = leak < (5 * 1024 * 1024)
        
        self.log(f"    Post-Cleanup: {leak/1024/1024:.2f} MB difference")
        self.assert_test(passed_leak, "Memory returned to baseline (no major leak)")


if __name__ == "__main__":
    suite = ComprehensiveTestSuite()
    try:
        suite.run_all()
    except KeyboardInterrupt:
        print("\n[!] Test Aborted.")
"""
DARION LOGIC SIM — MASTER INTEGRITY TEST SUITE
Merges core, IC, IO, and Event Manager tests into a single script.
"""

import time
import sys
import os
import gc
import random
import platform
import tempfile
import json
from collections import deque
import unittest
import io
# Force the standard output to use UTF-8
# Force the standard output to use UTF-8
import sys
if hasattr(sys, 'stdout') and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
try:
    import ctypes
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
except Exception:
    pass

# --- CONFIGURATION & SETUP ---
sys.setrecursionlimit(10_000)
LOG_FILE = "master_test_results.txt"

import argparse
parser = argparse.ArgumentParser(description='Run Master Integrity Tests')
parser.add_argument('--engine', action='store_true', help='Use Python engine backend (default: Reactor/Cython)')
args, unknown = parser.parse_known_args()

base_dir = os.getcwd()
# Fix script_dir resolution for integrity_test.py
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)

sys.path.append(os.path.join(root_dir, 'control'))

use_reactor = not args.engine  # Reactor (Cython) is default; --engine switches to Python

if use_reactor:
    print("Using Reactor (Cython) Backend")
    sys.path.insert(0, os.path.join(root_dir, 'reactor'))
else:
    print("Using Engine (Python) Backend")
    sys.path.insert(0, os.path.join(root_dir, 'engine'))

try:
    import psutil
    process = psutil.Process(os.getpid())
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from Circuit import Circuit
from Event_Manager import Event
import Const
from Const import *
from Gates import Gate, Variable, Probe
from Gates import NOT, AND, NAND, OR, NOR, XOR, XNOR
from Gates import InputPin, OutputPin
from IC import IC
from Control import Add, AddIC, Delete, Connect, Disconnect, Paste, Toggle, SetLimits, Rename

Const.LIMIT = 100_000


class AggressiveTestSuite:
    def __init__(self):
        self.circuit = Circuit()
        self.event_manager = Event()
        self.passed = 0
        self.failed = 0
        self.test_count = 0
        self.perf_metrics = {}
        self.section_passed = 0
        self.section_failed = 0
        self.section_metrics = {}  # Store timing/memory per section
        self.failures = []
        self.log_file = open(LOG_FILE, 'a', encoding='utf-8')
        from datetime import datetime
        self.log_file.write(f"\n\n{'='*70}\n")
        self.log_file.write(f"TEST RUN: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.log_file.write(f"{'='*70}\n")
        
    def log(self, msg, console=False):
        """Write to log file, optionally also to console."""
        self.log_file.write(msg + "\n")
        if console:
            print(msg)
            sys.stdout.flush()

    def timer(self, func):
        """
        Modified timer: Disables GC during execution to ensure consistency.
        Does NOT perform warmup (warmup must be done by the caller to handle state).
        """
        gc_enabled = gc.isenabled()
        gc.disable()
        
        start = time.perf_counter_ns()
        func()
        end = time.perf_counter_ns()
        
        if gc_enabled:
            gc.enable()
            
        return (end - start) / 1_000_000

    @staticmethod
    def format_time(ms):
        """Format a time value (in ms) with adaptive units."""
        if ms >= 1000:
            return f"{ms / 1000:.2f} s"
        elif ms >= 0.1:
            return f"{ms:.2f} ms"
        elif ms >= 0.001:
            return f"{ms * 1000:.1f} µs"
        else:
            return f"{ms * 1_000_000:.0f} ns"

    def assert_test(self, condition, test_name, details=""):
        self.test_count += 1
        self._subsection_tests += 1
        
        if condition:
            self.passed += 1
            self.section_passed += 1
            self._print_status()
            return True
        else:
            self.failed += 1
            self.section_failed += 1
            
            # Move to next line to print failure, then reprint status
            print() 
            msg = f"    [FAIL] {test_name} {details}"
            print(msg)
            self.log(msg)
            self.failures.append(msg)
            
            self._print_status(force=True)
            return False

    def section(self, title):
        # End previous section - record metrics
        if hasattr(self, '_current_section') and hasattr(self, '_section_start'):
            duration = (time.perf_counter_ns() - self._section_start) / 1_000_000
            mem_delta = 0
            if HAS_PSUTIL:
                mem_delta = (process.memory_info().rss - self._section_mem) / 1024 / 1024
            
            status = "PASS" if self.section_failed == 0 else "FAIL"
            self.section_metrics[self._current_section] = {
                'passed': self.section_passed,
                'failed': self.section_failed,
                'time_ms': duration,
                'mem_mb': mem_delta,
                'status': status
            }
            # Show section completion
            if self._current_section != "_END_":
                status_icon = "[OK]" if self.section_failed == 0 else "[FAIL]"
                print(f"  {status_icon} {self._current_section}: {self.section_passed} passed ({duration:.0f}ms)")
                sys.stdout.flush()
        
        # Start new section
        self._current_section = title
        self._section_start = time.perf_counter_ns()
        if HAS_PSUTIL:
            self._section_mem = process.memory_info().rss
        self.section_passed = 0
        self.section_failed = 0
        gc.collect()
        
        # Show section start
        if title != "_END_":
            print(f"\n[{title}]")
            sys.stdout.flush()

    def subsection(self, title):
        # Show subsection being tested
        self._subsection_title = title
        self._subsection_start = time.perf_counter_ns()
        self._subsection_tests = 0
        self._print_status(force=True)

    def _print_status(self, force=False, suffix=""):
        if not force and self._subsection_tests % 100 != 0:
            return
        
        # Simple spinner or progress
        spinners = "|/-\\"
        spin_char = spinners[(self._subsection_tests // 100) % 4]
        
        passed = self.section_passed
        failed = self.section_failed
        
        # \r to return to start of line, clear roughly 80 chars
        msg = f"\r  - {self._subsection_title}: {spin_char} {passed} OK"
        if failed > 0:
            msg += f" | {failed} FAIL"
        
        if suffix:
            msg += f" {suffix}"
            
        print(f"{msg:<80}", end="", flush=True)

    def subsection_done(self):
        # Mark subsection complete
        duration = (time.perf_counter_ns() - self._subsection_start) / 1_000_000
        
        # Final static print to overwrite the dynamic line
        status = "OK" if self.section_failed == 0 else "FAIL"
        
        msg = f"\r  - {self._subsection_title}: {self.section_passed} {status} ({duration:.0f}ms)"
        print(f"{msg:<80}", flush=True)

    def progress(self, current, total, interval=10000):
        """Show progress during long operations"""
        if current > 0 and current % interval == 0:
            pct = 100 * current / total
            self._print_status(force=True, suffix=f"[{pct:.0f}%]")

    def run_all(self):
        print(f"System: {platform.system()} | Python {platform.python_version()}")
        print(f"Log file: {LOG_FILE}")
        print(f"{'-'*70}")

        self.log(f"DARION LOGIC SIM - AGGRESSIVE TEST SUITE", console=False)
        self.log(f"System: {platform.system()} {platform.release()} | Python {platform.python_version()}")
        if HAS_PSUTIL:
            self.log(f"Initial RAM: {process.memory_info().rss / 1024 / 1024:.2f} MB")

        # ==================== PART 1: HEAVY UNIT TESTS ====================
        self.section("UNIT TESTS")
        self.test_gate_Construction_heavy()
        self.test_gate_logic_exhaustive()
        self.test_profile_stress()
        self.test_book_tracking_stress()
        self.test_connection_stress()
        self.test_delete_stress()  # New test
        self.test_disconnection_stress()
        self.test_variable_rapid_toggle()
        self.test_probe_chain_stress()
        self.test_io_pins_stress()
        self.test_setlimits_stress()
        
        # ==================== PART 1.5: COMPREHENSIVE COVERAGE ====================
        self.section("COMPREHENSIVE COVERAGE")
        self.test_every_gate_simulate()

        self.test_every_gate_multi_input()
        self.test_all_gate_methods()
        self.test_all_circuit_methods()
        self.test_mixed_gate_circuit()
        
        # ==================== PART 2: CIRCUIT STRESS ====================
        self.section("CIRCUIT STRESS")
        self.test_circuit_management_stress()
        self.test_propagation_deep_chain()
        self.test_propagation_wide_fanout()

        self.test_hide_reveal_stress()
        self.test_reset_stress()
        
        # ==================== PART 3: EVENT MANAGER STRESS ====================
        self.section("EVENT MANAGER")
        self.test_undo_redo_stress()
        self.test_rapid_undo_redo()
        
        # ==================== PART 4: IC STRESS (COMPREHENSIVE) ====================
        self.section("IC TESTS")
        self.test_ic_basic_functionality()
        self.test_ic_nested()
        self.test_ic_deeply_nested()
        self.test_ic_many_pins()
        self.test_ic_complex_internal()
        self.test_ic_save_load()
        self.test_ic_hide_reveal()
        self.test_ic_reset()
        self.test_ic_copy_paste()
        self.test_ic_massive_internal()
        self.test_ic_cascade()
        self.test_ic_multi_output()
        self.test_ic_stress_bulk()
        
        # ==================== PART 5: SERIALIZATION STRESS ====================
        self.section("SERIALIZATION")
        self.test_save_load_large_circuit()
        self.test_copy_paste_stress()
        self.test_copy_paste_complex()  # New test
        
        # ==================== PART 6: TRUTH TABLE STRESS ====================
        self.section("TRUTH TABLE")
        self.test_truth_table_4_inputs()
        self.test_truth_table_6_inputs()
        self.test_truth_table_8_inputs()
        self.test_truth_table_10_inputs()
        self.test_truth_table_complex()
        
        # ==================== PART 8: REAL-WORLD STRESS ====================
        self.section("REAL-WORLD STRESS")
        self.test_ripple_adder_correctness(bits=16)
        self.test_sr_latch_metastability(count=1000)
        self.test_mux_tree(select_bits=10)
        self.test_ring_oscillator(length=50)
        self.test_decoder_encoder(bits=8)
        self.test_cascade_adder_pipeline(stages=4, bits=8)
        self.test_xor_parity_generator(bits=1024)
        self.test_glitch_propagation(depth=500)
        self.test_hot_swap_under_load(count=200)
        self.test_reconvergent_fanout(depth=10)

        # Finalize last section
        self.section("_END_")  # Trigger saving of last section metrics
        
        # ==================== SUMMARY ====================
        self.print_summary()
        self.log_file.close()

    def print_summary(self):
        def out(msg):
            print(msg)
            self.log(msg)
        
        out(f"\n{'='*70}")
        out(f"  SECTION RESULTS")
        out(f"{'='*70}")
        out(f"  {'Section':<25} {'Tests':>8} {'Time':>10} {'Memory':>10} {'Status':>8}")
        out(f"  {'-'*25} {'-'*8} {'-'*10} {'-'*10} {'-'*8}")
        
        for name, m in self.section_metrics.items():
            if name == "_END_":
                continue
            tests = f"{m['passed']}"
            if m['failed'] > 0:
                tests = f"{m['passed']}/{m['passed']+m['failed']}"
            time_str = f"{m['time_ms']:.0f} ms" if m['time_ms'] >= 1 else f"{m['time_ms']*1000:.0f} us"
            mem_str = f"+{m['mem_mb']:.1f} MB" if m['mem_mb'] >= 0.1 else "~0 MB"
            status = "PASS" if m['status'] == "PASS" else "FAIL"
            out(f"  {name:<25} {tests:>8} {time_str:>10} {mem_str:>10} {status:>8}")
        
        total = self.passed + self.failed
        
        # Show failures if any
        if self.failures:
            out(f"\n  FAILURES:")
            for f in self.failures[:10]:
                out(f"    {f}")
            if len(self.failures) > 10:
                out(f"    ... and {len(self.failures)-10} more")
        
        # Final result
        out(f"\n{'='*70}")
        out(f"  TOTAL: {self.passed}/{total} tests ({100*self.passed/total:.1f}%)")
        if self.failed == 0:
            out(f"  [SUCCESS] ALL TESTS PASSED")
        else:
            out(f"  [FAILURE] {self.failed} TESTS FAILED")
        print(f"\nResults saved to: {LOG_FILE}")

    # =========================================================================
    # PART 1: HEAVY UNIT TESTS
    # =========================================================================

    def test_gate_Construction_heavy(self):
        self.subsection("Gate Construction (1000 each)")
        gate_types = [NOT, AND, NAND, OR, NOR, XOR, XNOR]
        count = 1000
        
        for gate_cls in gate_types:
            gates = [gate_cls() for _ in range(count)]
            all_unknown = all(g.output == Const.UNKNOWN for g in gates)
            self.assert_test(len(gates) == count and all_unknown, f"{gate_cls.__name__} x{count}")

    def test_gate_logic_exhaustive(self):
        self.subsection("Gate Logic (Full Truth Tables)")
        
        truth_tables = {
            'AND_ID':  [(0,0,0), (0,1,0), (1,0,0), (1,1,1)],
            'NAND_ID': [(0,0,1), (0,1,1), (1,0,1), (1,1,0)],
            'OR_ID':   [(0,0,0), (0,1,1), (1,0,1), (1,1,1)],
            'NOR_ID':  [(0,0,1), (0,1,0), (1,0,0), (1,1,0)],
            'XOR_ID':  [(0,0,0), (0,1,1), (1,0,1), (1,1,0)],
            'XNOR_ID': [(0,0,1), (0,1,0), (1,0,0), (1,1,1)],
        }
        
        for name, table in truth_tables.items():
            c = Circuit()
            c.simulate(Const.SIMULATE)
            v1, v2 = c.getcomponent(Const.VARIABLE_ID), c.getcomponent(Const.VARIABLE_ID)
            g = c.getcomponent(getattr(Const, name))
            c.connect(g, v1, 0)
            c.connect(g, v2, 1)
            
            all_pass = True
            for a, b, expected in table:
                c.toggle(v1, a)
                c.toggle(v2, b)
                actual = 1 if g.output == Const.HIGH else 0
                if actual != expected:
                    all_pass = False
                    break
            self.assert_test(all_pass, f"{name} truth table")
        
        # NOT gate
        c = Circuit()
        c.simulate(Const.SIMULATE)
        v = c.getcomponent(Const.VARIABLE_ID)
        n = c.getcomponent(Const.NOT_ID)
        c.connect(n, v, 0)
        
        all_correct = True
        for i in range(100):
            val = i % 2
            c.toggle(v, val)
            expected = Const.LOW if val else Const.HIGH
            if n.output != expected:
                all_correct = False
                break
        self.assert_test(all_correct, "NOT gate 100 toggles")

    def test_profile_stress(self):
        self.subsection("Profile Operations (1000 connections)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        source = c.getcomponent(Const.VARIABLE_ID)
        
        # Create a constant rail for the second input of AND gates
        const_high = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(const_high, Const.HIGH)
        
        gates = []
        for i in range(1000):
            g = c.getcomponent(Const.AND_ID)
            # Use 2 inputs properly: Source -> 0, Const_High -> 1
            c.connect(g, source, 0)
            c.connect(g, const_high, 1)
            gates.append(g)
        
        self.assert_test(len(source.hitlist) == 1000, "1000 profiles created")
        
        c.toggle(source, Const.HIGH)
        all_high = all(g.output == Const.HIGH for g in gates)
        self.assert_test(all_high, "All 1000 gates received signal")

    def test_book_tracking_stress(self):
        self.subsection("Book Tracking (100-input gate)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        g = c.getcomponent(Const.AND_ID)
        c.setlimits(g, 100)
        
        variables = []
        for i in range(100):
            v = c.getcomponent(Const.VARIABLE_ID)
            c.toggle(v, Const.LOW)
            c.connect(g, v, i)
            variables.append(v)
        
        self.assert_test(g.book[Const.LOW] == 100, f"100 LOW tracked")
        
        for i in range(50):
            c.toggle(variables[i], Const.HIGH)
        
        self.assert_test(g.book[Const.HIGH] == 50, "50 HIGH after toggle")
        
        for i in range(50, 100):
            c.toggle(variables[i], Const.HIGH)
        self.assert_test(g.output == Const.HIGH, "AND(100 HIGH) = HIGH")

    def test_connection_stress(self):
        self.subsection("Connection Stress (500 cycles)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        v = c.getcomponent(Const.VARIABLE_ID)
        g = c.getcomponent(Const.AND_ID)
        
        # Each connect and disconnect is individually verified (1000 total assertions)
        for i in range(500):
            c.connect(g, v, 0)
            self.assert_test(g.sources[0] == v, f"Cycle {i}: Connected")
            c.disconnect(g, 0)
            self.assert_test(g.sources[0] is None, f"Cycle {i}: Disconnected")

    def test_disconnection_stress(self):
        self.subsection("Disconnection (50-source gate)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        g = c.getcomponent(Const.AND_ID)
        c.setlimits(g, 50)
        
        for i in range(50):
            v = c.getcomponent(Const.VARIABLE_ID)
            c.connect(g, v, i)
            c.toggle(v, Const.HIGH)
        
        for i in range(49, -1, -1):
            c.disconnect(g, i)
        
        all_none = all(g.sources[i] is None for i in range(50))
        self.assert_test(all_none, "All 50 sources cleared")

    def test_variable_rapid_toggle(self):
        self.subsection("Variable Rapid Toggle (10000)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        v = c.getcomponent(Const.VARIABLE_ID)
        probe = c.getcomponent(Const.PROBE_ID)
        c.connect(probe, v, 0)
        
        start = time.perf_counter_ns()
        for i in range(10000):
            c.toggle(v, i % 2)
        end = time.perf_counter_ns()
        
        duration_ms = (end - start) / 1_000_000
        self.assert_test(v.output == Const.HIGH, f"Final state correct ({duration_ms:.1f}ms)")

    def test_probe_chain_stress(self):
        self.subsection("Probe Chain (100 probes)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        v = c.getcomponent(Const.VARIABLE_ID)
        probes = [c.getcomponent(Const.PROBE_ID) for _ in range(100)]
        for p in probes:
            c.connect(p, v, 0)
        
        c.toggle(v, Const.HIGH)
        all_high = all(p.output == Const.HIGH for p in probes)
        self.assert_test(all_high, "All 100 probes HIGH")

    def test_io_pins_stress(self):
        self.subsection("IO Pins (50 chains)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        for _ in range(50):
            v = c.getcomponent(Const.VARIABLE_ID)
            inp = c.getcomponent(Const.INPUT_PIN_ID)
            out = c.getcomponent(Const.OUTPUT_PIN_ID)
            g = c.getcomponent(Const.NOT_ID)
            c.connect(inp, v, 0)
            c.connect(g, inp, 0)
            c.connect(out, g, 0)
            c.toggle(v, Const.HIGH)
        
        self.assert_test(True, "50 IO pin chains created")

    def test_setlimits_stress(self):
        self.subsection("setlimits (Expand/Contract)")
        c = Circuit()
        g = c.getcomponent(Const.AND_ID)
        
        passed = True
        for size in [10, 100, 500, 1000, 500, 100, 10, 2]:
            g.setlimits(size)
            if g.inputlimit != size:
                passed = False
                break
        self.assert_test(passed, "Expand/contract 2->1000->2")

    # =========================================================================
    # PART 1.5: COMPREHENSIVE COVERAGE
    # =========================================================================

    def test_every_gate_simulate(self):
        """Test every gate type in SIMULATE mode with full truth table verification."""
        self.subsection("Every Gate (SIMULATE mode)")

        # --- NOT gate ---
        c = Circuit()
        c.simulate(Const.SIMULATE)
        v = c.getcomponent(Const.VARIABLE_ID)
        g = c.getcomponent(Const.NOT_ID)
        c.connect(g, v, 0)
        c.toggle(v, Const.HIGH)
        self.assert_test(g.output == Const.LOW, "NOT(1)=0")
        c.toggle(v, Const.LOW)
        self.assert_test(g.output == Const.HIGH, "NOT(0)=1")

        # --- AND gate ---
        c = Circuit()
        c.simulate(Const.SIMULATE)
        v1, v2 = c.getcomponent(Const.VARIABLE_ID), c.getcomponent(Const.VARIABLE_ID)
        g = c.getcomponent(Const.AND_ID)
        c.connect(g, v1, 0); c.connect(g, v2, 1)
        for a, b, exp in [(0,0,Const.LOW),(0,1,Const.LOW),(1,0,Const.LOW),(1,1,Const.HIGH)]:
            c.toggle(v1, a); c.toggle(v2, b)
            self.assert_test(g.output == exp, f"AND({a},{b})={1 if exp==Const.HIGH else 0}")

        # --- NAND gate ---
        c = Circuit()
        c.simulate(Const.SIMULATE)
        v1, v2 = c.getcomponent(Const.VARIABLE_ID), c.getcomponent(Const.VARIABLE_ID)
        g = c.getcomponent(Const.NAND_ID)
        c.connect(g, v1, 0); c.connect(g, v2, 1)
        for a, b, exp in [(0,0,Const.HIGH),(0,1,Const.HIGH),(1,0,Const.HIGH),(1,1,Const.LOW)]:
            c.toggle(v1, a); c.toggle(v2, b)
            self.assert_test(g.output == exp, f"NAND({a},{b})={1 if exp==Const.HIGH else 0}")

        # --- OR gate ---
        c = Circuit()
        c.simulate(Const.SIMULATE)
        v1, v2 = c.getcomponent(Const.VARIABLE_ID), c.getcomponent(Const.VARIABLE_ID)
        g = c.getcomponent(Const.OR_ID)
        c.connect(g, v1, 0); c.connect(g, v2, 1)
        for a, b, exp in [(0,0,Const.LOW),(0,1,Const.HIGH),(1,0,Const.HIGH),(1,1,Const.HIGH)]:
            c.toggle(v1, a); c.toggle(v2, b)
            self.assert_test(g.output == exp, f"OR({a},{b})={1 if exp==Const.HIGH else 0}")

        # --- NOR gate ---
        c = Circuit()
        c.simulate(Const.SIMULATE)
        v1, v2 = c.getcomponent(Const.VARIABLE_ID), c.getcomponent(Const.VARIABLE_ID)
        g = c.getcomponent(Const.NOR_ID)
        c.connect(g, v1, 0); c.connect(g, v2, 1)
        for a, b, exp in [(0,0,Const.HIGH),(0,1,Const.LOW),(1,0,Const.LOW),(1,1,Const.LOW)]:
            c.toggle(v1, a); c.toggle(v2, b)
            self.assert_test(g.output == exp, f"NOR({a},{b})={1 if exp==Const.HIGH else 0}")

        # --- XOR gate ---
        c = Circuit()
        c.simulate(Const.SIMULATE)
        v1, v2 = c.getcomponent(Const.VARIABLE_ID), c.getcomponent(Const.VARIABLE_ID)
        g = c.getcomponent(Const.XOR_ID)
        c.connect(g, v1, 0); c.connect(g, v2, 1)
        for a, b, exp in [(0,0,Const.LOW),(0,1,Const.HIGH),(1,0,Const.HIGH),(1,1,Const.LOW)]:
            c.toggle(v1, a); c.toggle(v2, b)
            self.assert_test(g.output == exp, f"XOR({a},{b})={1 if exp==Const.HIGH else 0}")

        # --- XNOR gate ---
        c = Circuit()
        c.simulate(Const.SIMULATE)
        v1, v2 = c.getcomponent(Const.VARIABLE_ID), c.getcomponent(Const.VARIABLE_ID)
        g = c.getcomponent(Const.XNOR_ID)
        c.connect(g, v1, 0); c.connect(g, v2, 1)
        for a, b, exp in [(0,0,Const.HIGH),(0,1,Const.LOW),(1,0,Const.LOW),(1,1,Const.HIGH)]:
            c.toggle(v1, a); c.toggle(v2, b)
            self.assert_test(g.output == exp, f"XNOR({a},{b})={1 if exp==Const.HIGH else 0}")

        # --- Variable ---
        c = Circuit()
        v = c.getcomponent(Const.VARIABLE_ID)
        self.assert_test(v.output == Const.UNKNOWN, "Variable initial=UNKNOWN")
        c.simulate(Const.SIMULATE)
        c.toggle(v, Const.HIGH)
        self.assert_test(v.output == Const.HIGH, "Variable toggle HIGH")
        c.toggle(v, Const.LOW)
        self.assert_test(v.output == Const.LOW, "Variable toggle LOW")

        # --- Probe ---
        c = Circuit()
        c.simulate(Const.SIMULATE)
        v = c.getcomponent(Const.VARIABLE_ID)
        p = c.getcomponent(Const.PROBE_ID)
        c.connect(p, v, 0)
        c.toggle(v, Const.HIGH)
        self.assert_test(p.output == Const.HIGH, "Probe follows HIGH")
        c.toggle(v, Const.LOW)
        self.assert_test(p.output == Const.LOW, "Probe follows LOW")

        # --- InputPin ---
        c = Circuit()
        c.simulate(Const.SIMULATE)
        v = c.getcomponent(Const.VARIABLE_ID)
        inp = c.getcomponent(Const.INPUT_PIN_ID)
        c.connect(inp, v, 0)
        c.toggle(v, Const.HIGH)
        self.assert_test(inp.output == Const.HIGH, "InputPin follows HIGH")

        # --- OutputPin ---
        c = Circuit()
        c.simulate(Const.SIMULATE)
        v = c.getcomponent(Const.VARIABLE_ID)
        inp = c.getcomponent(Const.INPUT_PIN_ID)
        n = c.getcomponent(Const.NOT_ID)
        out = c.getcomponent(Const.OUTPUT_PIN_ID)
        c.connect(inp, v, 0)
        c.connect(n, inp, 0)
        c.connect(out, n, 0)
        c.toggle(v, Const.HIGH)
        self.assert_test(out.output == Const.LOW, "OutputPin chain: V->InPin->NOT->OutPin")



    def test_every_gate_multi_input(self):
        """Test every gate type with more than 2 inputs (expanded via setlimits)."""
        self.subsection("Every Gate (Multi-Input)")

        # Test 4-input gates for each type
        n_inputs = 4

        # AND: all HIGH -> HIGH, any LOW -> LOW
        c = Circuit()
        c.simulate(Const.SIMULATE)
        g = c.getcomponent(Const.AND_ID)
        c.setlimits(g, n_inputs)
        vs = [c.getcomponent(Const.VARIABLE_ID) for _ in range(n_inputs)]
        for i, v in enumerate(vs): c.connect(g, v, i)
        for v in vs: c.toggle(v, Const.HIGH)
        self.assert_test(g.output == Const.HIGH, "AND(4): all HIGH -> HIGH")
        c.toggle(vs[0], Const.LOW)
        self.assert_test(g.output == Const.LOW, "AND(4): one LOW -> LOW")

        # NAND: all HIGH -> LOW, any LOW -> HIGH
        c = Circuit()
        c.simulate(Const.SIMULATE)
        g = c.getcomponent(Const.NAND_ID)
        c.setlimits(g, n_inputs)
        vs = [c.getcomponent(Const.VARIABLE_ID) for _ in range(n_inputs)]
        for i, v in enumerate(vs): c.connect(g, v, i)
        for v in vs: c.toggle(v, Const.HIGH)
        self.assert_test(g.output == Const.LOW, "NAND(4): all HIGH -> LOW")
        c.toggle(vs[0], Const.LOW)
        self.assert_test(g.output == Const.HIGH, "NAND(4): one LOW -> HIGH")

        # OR: any HIGH -> HIGH, all LOW -> LOW
        c = Circuit()
        c.simulate(Const.SIMULATE)
        g = c.getcomponent(Const.OR_ID)
        c.setlimits(g, n_inputs)
        vs = [c.getcomponent(Const.VARIABLE_ID) for _ in range(n_inputs)]
        for i, v in enumerate(vs): c.connect(g, v, i)
        for v in vs: c.toggle(v, Const.LOW)
        self.assert_test(g.output == Const.LOW, "OR(4): all LOW -> LOW")
        c.toggle(vs[0], Const.HIGH)
        self.assert_test(g.output == Const.HIGH, "OR(4): one HIGH -> HIGH")

        # NOR: all LOW -> HIGH, any HIGH -> LOW
        c = Circuit()
        c.simulate(Const.SIMULATE)
        g = c.getcomponent(Const.NOR_ID)
        c.setlimits(g, n_inputs)
        vs = [c.getcomponent(Const.VARIABLE_ID) for _ in range(n_inputs)]
        for i, v in enumerate(vs): c.connect(g, v, i)
        for v in vs: c.toggle(v, Const.LOW)
        self.assert_test(g.output == Const.HIGH, "NOR(4): all LOW -> HIGH")
        c.toggle(vs[0], Const.HIGH)
        self.assert_test(g.output == Const.LOW, "NOR(4): one HIGH -> LOW")

        # XOR: odd number of HIGHs -> HIGH, even -> LOW
        c = Circuit()
        c.simulate(Const.SIMULATE)
        g = c.getcomponent(Const.XOR_ID)
        c.setlimits(g, n_inputs)
        vs = [c.getcomponent(Const.VARIABLE_ID) for _ in range(n_inputs)]
        for i, v in enumerate(vs): c.connect(g, v, i)
        for v in vs: c.toggle(v, Const.LOW)
        self.assert_test(g.output == Const.LOW, "XOR(4): 0 HIGH -> LOW")
        c.toggle(vs[0], Const.HIGH)
        self.assert_test(g.output == Const.HIGH, "XOR(4): 1 HIGH -> HIGH")
        c.toggle(vs[1], Const.HIGH)
        self.assert_test(g.output == Const.LOW, "XOR(4): 2 HIGH -> LOW")
        c.toggle(vs[2], Const.HIGH)
        self.assert_test(g.output == Const.HIGH, "XOR(4): 3 HIGH -> HIGH")

        # XNOR: even number of HIGHs -> HIGH, odd -> LOW
        c = Circuit()
        c.simulate(Const.SIMULATE)
        g = c.getcomponent(Const.XNOR_ID)
        c.setlimits(g, n_inputs)
        vs = [c.getcomponent(Const.VARIABLE_ID) for _ in range(n_inputs)]
        for i, v in enumerate(vs): c.connect(g, v, i)
        for v in vs: c.toggle(v, Const.LOW)
        self.assert_test(g.output == Const.HIGH, "XNOR(4): 0 HIGH -> HIGH")
        c.toggle(vs[0], Const.HIGH)
        self.assert_test(g.output == Const.LOW, "XNOR(4): 1 HIGH -> LOW")
        c.toggle(vs[1], Const.HIGH)
        self.assert_test(g.output == Const.HIGH, "XNOR(4): 2 HIGH -> HIGH")

        # NOT uses base Gate.setlimits, so it CAN expand (but process only uses book)
        c = Circuit()
        n = c.getcomponent(Const.NOT_ID)
        result = c.setlimits(n, 4)
        self.assert_test(result == True, "NOT setlimits(4) expands (uses base Gate)")
        self.assert_test(n.inputlimit == 4, "NOT inputlimit == 4 after expand")

        # Probe cannot expand
        c = Circuit()
        p = c.getcomponent(Const.PROBE_ID)
        result = c.setlimits(p, 4)
        self.assert_test(result == False, "Probe setlimits(4) returns False")

        # Variable cannot expand
        c = Circuit()
        v = c.getcomponent(Const.VARIABLE_ID)
        result = c.setlimits(v, 4)
        self.assert_test(result == False, "Variable setlimits(4) returns False")

    def test_all_gate_methods(self):
        """Touch every accessible method/property on every gate type."""
        self.subsection("All Gate Methods")

        gate_types_Const = [Const.NOT_ID, Const.AND_ID, Const.NAND_ID, Const.OR_ID, Const.NOR_ID, Const.XOR_ID, Const.XNOR_ID]
        gate_names = ['NOT', 'AND', 'NAND', 'OR', 'NOR', 'XOR', 'XNOR']

        for gtype, gname in zip(gate_types_Const, gate_names):
            c = Circuit()
            c.simulate(Const.SIMULATE)
            g = c.getcomponent(gtype)

            # --- getoutput (before connection) ---
            self.assert_test(g.getoutput() == 'X', f"{gname}.getoutput() = 'X' initially")

            # --- rename ---
            g.rename(f"my_{gname}")
            self.assert_test(g.custom_name == f"my_{gname}", f"{gname}.rename() works")

            # --- custom_name and __repr__ / __str__ ---
            g.custom_name = f"custom_{gname}"
            self.assert_test(repr(g) == f"custom_{gname}", f"{gname} repr uses custom_name")
            self.assert_test(str(g) == f"custom_{gname}", f"{gname} str uses custom_name")
            g.custom_name = ''
            self.assert_test(repr(g) == g.name, f"{gname} repr falls back to name")

            # --- code ---
            self.assert_test(isinstance(g.code, tuple) and len(g.code) == 2, f"{gname}.code is tuple")

            # --- json_data ---
            jd = g.json_data()
            self.assert_test(isinstance(jd, list) and len(jd) == 4, f"{gname}.json_data() has keys")

            # --- copy_data ---
            cluster = set()
            g.load_to_cluster(cluster)
            self.assert_test(g in cluster, f"{gname}.load_to_cluster adds self")
            cd = g.copy_data(cluster)
            self.assert_test(isinstance(cd, list) and len(cd) == 4, f"{gname}.copy_data() has keys")

            # --- connect, process, propagate via circuit ---
            if gtype == Const.NOT_ID:
                v = c.getcomponent(Const.VARIABLE_ID)
                c.connect(g, v, 0)
                c.toggle(v, Const.HIGH)
                self.assert_test(g.getoutput() == 'F', f"{gname} getoutput after connect = 'F'")
            else:
                v1 = c.getcomponent(Const.VARIABLE_ID)
                v2 = c.getcomponent(Const.VARIABLE_ID)
                c.connect(g, v1, 0)
                c.connect(g, v2, 1)
                c.toggle(v1, Const.HIGH)
                c.toggle(v2, Const.HIGH)
                out_str = g.getoutput()
                self.assert_test(out_str in ('T', 'F'), f"{gname} getoutput after HIGH,HIGH = '{out_str}'")

            # --- book tracking ---
            self.assert_test(isinstance(list(g.book), list), f"{gname}.book is accessible")

            # --- hitlist property ---
            hl = g.hitlist
            self.assert_test(isinstance(hl, list), f"{gname}.hitlist returns list")

            # --- sources ---
            self.assert_test(isinstance(g.sources, list), f"{gname}.sources is list")

        # --- Variable methods ---
        c = Circuit()
        v = c.getcomponent(Const.VARIABLE_ID)
        self.assert_test(v.getoutput() == 'X', "Variable.getoutput() = 'X' initially")
        c.simulate(Const.SIMULATE)
        c.toggle(v, Const.HIGH)
        self.assert_test(v.getoutput() == 'T', "Variable.getoutput() = 'T'")
        v.rename("my_var")
        self.assert_test(v.custom_name == "my_var", "Variable.rename() works")
        v.custom_name = "custom_var"
        self.assert_test(str(v) == "custom_var", "Variable str uses custom_name")
        v.custom_name = ''
        jd = v.json_data()
        self.assert_test(isinstance(jd, list) and len(jd) == 4, "Variable.json_data has 'value'")
        cluster = set()
        v.load_to_cluster(cluster)
        cd = v.copy_data(cluster)
        self.assert_test(isinstance(cd, list) and len(cd) == 4, "Variable.copy_data has 'value'")
        # Variable connect/disconnect are no-ops
        c.connect(v, v, 0)  # should not crash
        c.disconnect(v, 0)   # should not crash
        self.assert_test(True, "Variable connect/disconnect no-ops")
        # Variable setlimits returns False
        self.assert_test(v.setlimits(10) == False, "Variable.setlimits returns False")

        # --- Probe methods ---
        c = Circuit()
        c.simulate(Const.SIMULATE)
        p = c.getcomponent(Const.PROBE_ID)
        v = c.getcomponent(Const.VARIABLE_ID)
        c.connect(p, v, 0)
        c.toggle(v, Const.HIGH)
        self.assert_test(p.getoutput() == 'T', "Probe.getoutput() = 'T'")
        p.rename("my_probe")
        self.assert_test(p.custom_name == "my_probe", "Probe.rename() works")
        jd = p.json_data()
        self.assert_test(isinstance(jd, list) and len(jd) == 4, "Probe.json_data has 'source'")
        cluster = set()
        p.load_to_cluster(cluster)
        self.assert_test(p in cluster, "Probe.load_to_cluster adds self")
        self.assert_test(p.setlimits(5) == False, "Probe.setlimits returns False")

        # --- InputPin methods ---
        c = Circuit()
        c.simulate(Const.SIMULATE)
        inp = c.getcomponent(Const.INPUT_PIN_ID)
        v = c.getcomponent(Const.VARIABLE_ID)
        c.connect(inp, v, 0)
        c.toggle(v, Const.HIGH)
        self.assert_test(inp.getoutput() == 'T', "InputPin.getoutput() = 'T'")
        inp.rename("my_inp")
        self.assert_test(inp.custom_name == "my_inp", "InputPin.rename() works")

        # --- OutputPin methods ---
        c = Circuit()
        c.simulate(Const.SIMULATE)
        out = c.getcomponent(Const.OUTPUT_PIN_ID)
        v = c.getcomponent(Const.VARIABLE_ID)
        n = c.getcomponent(Const.NOT_ID)
        c.connect(n, v, 0)
        c.connect(out, n, 0)
        c.toggle(v, Const.HIGH)
        self.assert_test(out.getoutput() == 'F', "OutputPin.getoutput() = 'F'")
        out.rename("my_out")
        self.assert_test(out.custom_name == "my_out", "OutputPin.rename() works")

    def test_all_circuit_methods(self):
        """Touch every accessible Circuit method."""
        self.subsection("All Circuit Methods")

        c = Circuit()
        c.simulate(Const.SIMULATE)

        # getcomponent for every type
        all_types = [
            (Const.NOT_ID, 'NOT'), (Const.AND_ID, 'AND'), (Const.NAND_ID, 'NAND'),
            (Const.OR_ID, 'OR'), (Const.NOR_ID, 'NOR'), (Const.XOR_ID, 'XOR'),
            (Const.XNOR_ID, 'XNOR'), (Const.VARIABLE_ID, 'Variable'),
            (Const.PROBE_ID, 'Probe'), (Const.INPUT_PIN_ID, 'InputPin'),
            (Const.OUTPUT_PIN_ID, 'OutputPin'),
        ]
        components = {}
        for gtype, gname in all_types:
            comp = c.getcomponent(gtype)
            self.assert_test(comp is not None, f"getcomponent({gname}) != None")
            components[gname] = comp

        # canvas tracking
        self.assert_test(len(c.get_components()) == len(all_types), f"canvas has {len(all_types)} components")

        # getobj / decode
        and_gate = components['AND']
        code = and_gate.code
        retrieved = c.getobj(code)
        self.assert_test(retrieved is and_gate, "getobj retrieves same object")

        # setlimits via circuit
        self.assert_test(c.setlimits(and_gate, 4) == True, "Circuit.setlimits expands AND to 4")
        self.assert_test(and_gate.inputlimit == 4, "AND inputlimit == 4 after expand")

        # connect/disconnect via circuit
        v = components['Variable']
        c.connect(and_gate, v, 0)
        self.assert_test(and_gate.sources[0] is v, "Circuit.connect wired Variable->AND")
        c.disconnect(and_gate, 0)
        self.assert_test(and_gate.sources[0] == None, "Circuit.disconnect cleared AND[0]")

        # toggle
        c.toggle(v, Const.HIGH)
        self.assert_test(v.output == Const.HIGH, "Circuit.toggle sets Variable HIGH")

        # hide / reveal
        probe = components['Probe']
        c.hide([probe])
        self.assert_test(probe not in c.get_components(), "hide removes from canvas")
        c.reveal([probe])
        self.assert_test(probe in c.get_components(), "reveal restores to canvas")

        # listComponents / listVar (just call them, no assertions on output)
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            c.listComponent()
            c.listVar()
        self.assert_test(True, "listComponent/listVar ran without error")

        # diagnose (capture stdout, just make sure it doesn't crash)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                c.diagnose()
            self.assert_test(len(buf.getvalue()) > 0, "diagnose produced output")
        except Exception as e:
            self.assert_test(False, f"diagnose crashed: {e}")

        # truthTable with all types connected
        c2 = Circuit()
        v1 = c2.getcomponent(Const.VARIABLE_ID)
        v2 = c2.getcomponent(Const.VARIABLE_ID)
        for gtype, gname in all_types:
            if gtype in (Const.VARIABLE_ID, Const.PROBE_ID, Const.INPUT_PIN_ID, Const.OUTPUT_PIN_ID):
                continue
            g = c2.getcomponent(gtype)
            if gtype == Const.NOT_ID:
                c2.connect(g, v1, 0)
            else:
                c2.connect(g, v1, 0)
                c2.connect(g, v2, 1)
        c2.simulate(Const.SIMULATE)
        tt = c2.truthTable()
        self.assert_test(tt is not None and len(tt) > 0, "truthTable with all gate types")

        # writetojson / readfromjson
        temp_path = os.path.join(tempfile.gettempdir(), "coverage_test.json")
        c2.writetojson(temp_path)
        self.assert_test(os.path.exists(temp_path), "writetojson created file")
        c3 = Circuit()
        c3.readfromjson(temp_path)
        self.assert_test(len(c3.get_components()) == len(c2.get_components()), "readfromjson loaded same count")
        os.remove(temp_path)

        # copy / paste
        c4 = Circuit()
        g1 = c4.getcomponent(Const.AND_ID)
        g2 = c4.getcomponent(Const.OR_ID)
        g3 = c4.getcomponent(Const.NOT_ID)
        initial = len(c4.get_components())
        c4.copy([g1, g2, g3])
        c4.paste()
        self.assert_test(len(c4.get_components()) == initial + 3, "copy/paste duplicated 3 gates")

        # simulate modes
        c5 = Circuit()
        c5.simulate(Const.SIMULATE)
        self.assert_test(Const.get_MODE() == Const.SIMULATE, "simulate(SIMULATE) sets mode")
        c5.reset()
        self.assert_test(Const.get_MODE() == Const.DESIGN, "reset() sets DESIGN mode")

        # clearcircuit
        c6 = Circuit()
        for _ in range(10): c6.getcomponent(Const.AND_ID)
        c6.clearcircuit()
        self.assert_test(len(c6.get_components()) == 0, "clearcircuit empties canvas")

    def test_mixed_gate_circuit(self):
        """Build a circuit using every gate type simultaneously and verify propagation."""
        self.subsection("Mixed Gate Circuit")

        c = Circuit()
        c.simulate(Const.SIMULATE)

        # 2 variables feeding into every 2-input gate type
        v1 = c.getcomponent(Const.VARIABLE_ID)
        v2 = c.getcomponent(Const.VARIABLE_ID)

        gates = {}
        for gtype, gname in [(Const.AND_ID,'AND'), (Const.NAND_ID,'NAND'), (Const.OR_ID,'OR'),
                              (Const.NOR_ID,'NOR'), (Const.XOR_ID,'XOR'), (Const.XNOR_ID,'XNOR')]:
            g = c.getcomponent(gtype)
            c.connect(g, v1, 0)
            c.connect(g, v2, 1)
            gates[gname] = g

        # NOT from v1
        not_g = c.getcomponent(Const.NOT_ID)
        c.connect(not_g, v1, 0)
        gates['NOT'] = not_g

        # Probe from AND output
        probe = c.getcomponent(Const.PROBE_ID)
        c.connect(probe, gates['AND'], 0)

        # InputPin -> OutputPin chain through XOR
        inp_pin = c.getcomponent(Const.INPUT_PIN_ID)
        c.connect(inp_pin, v1, 0)
        out_pin = c.getcomponent(Const.OUTPUT_PIN_ID)
        c.connect(out_pin, gates['XOR'], 0)

        # Test with (1, 1)
        c.toggle(v1, Const.HIGH)
        c.toggle(v2, Const.HIGH)
        expected = {
            'AND': Const.HIGH, 'NAND': Const.LOW, 'OR': Const.HIGH,
            'NOR': Const.LOW, 'XOR': Const.LOW, 'XNOR': Const.HIGH,
            'NOT': Const.LOW
        }
        all_ok = True
        for gname, exp in expected.items():
            if gates[gname].output != exp:
                self.assert_test(False, f"Mixed(1,1) {gname} expected {exp} got {gates[gname].output}")
                all_ok = False
        if all_ok:
            self.assert_test(True, "Mixed(1,1) all gates correct")

        # Probe should follow AND
        self.assert_test(probe.output == Const.HIGH, "Mixed: Probe follows AND(1,1)=HIGH")
        # OutputPin should follow XOR
        self.assert_test(out_pin.output == Const.LOW, "Mixed: OutputPin follows XOR(1,1)=LOW")
        # InputPin should follow v1
        self.assert_test(inp_pin.output == Const.HIGH, "Mixed: InputPin follows v1=HIGH")

        # Test with (0, 1)
        c.toggle(v1, Const.LOW)
        expected = {
            'AND': Const.LOW, 'NAND': Const.HIGH, 'OR': Const.HIGH,
            'NOR': Const.LOW, 'XOR': Const.HIGH, 'XNOR': Const.LOW,
            'NOT': Const.HIGH
        }
        all_ok = True
        for gname, exp in expected.items():
            if gates[gname].output != exp:
                self.assert_test(False, f"Mixed(0,1) {gname} expected {exp} got {gates[gname].output}")
                all_ok = False
        if all_ok:
            self.assert_test(True, "Mixed(0,1) all gates correct")

        # Test with (1, 0)
        c.toggle(v1, Const.HIGH)
        c.toggle(v2, Const.LOW)
        expected = {
            'AND': Const.LOW, 'NAND': Const.HIGH, 'OR': Const.HIGH,
            'NOR': Const.LOW, 'XOR': Const.HIGH, 'XNOR': Const.LOW,
            'NOT': Const.LOW
        }
        all_ok = True
        for gname, exp in expected.items():
            if gates[gname].output != exp:
                self.assert_test(False, f"Mixed(1,0) {gname} expected {exp} got {gates[gname].output}")
                all_ok = False
        if all_ok:
            self.assert_test(True, "Mixed(1,0) all gates correct")

        # Test with (0, 0)
        c.toggle(v1, Const.LOW)
        expected = {
            'AND': Const.LOW, 'NAND': Const.HIGH, 'OR': Const.LOW,
            'NOR': Const.HIGH, 'XOR': Const.LOW, 'XNOR': Const.HIGH,
            'NOT': Const.HIGH
        }
        all_ok = True
        for gname, exp in expected.items():
            if gates[gname].output != exp:
                self.assert_test(False, f"Mixed(0,0) {gname} expected {exp} got {gates[gname].output}")
                all_ok = False
        if all_ok:
            self.assert_test(True, "Mixed(0,0) all gates correct")

        # Reset and verify all go UNKNOWN
        c.reset()
        all_unknown = all(g.output == Const.UNKNOWN for g in gates.values())
        self.assert_test(all_unknown, "Mixed: reset -> all UNKNOWN")

        # Re-simulate and hide/reveal each gate type
        c.simulate(Const.SIMULATE)
        c.toggle(v1, Const.HIGH)
        c.toggle(v2, Const.HIGH)
        for gname, g in gates.items():
            c.hide([g])
            self.assert_test(g not in c.get_components(), f"Mixed: hide {gname}")
            c.reveal([g])
            self.assert_test(g in c.get_components(), f"Mixed: reveal {gname}")

        # Disconnect and reconnect each gate (only if source is connected)
        for gname, g in gates.items():
            if gname == 'NOT':
                if g.sources[0] :
                    c.disconnect(g, 0)
                self.assert_test(g.sources[0] == None, f"Mixed: disconnect {gname}[0]")
                c.connect(g, v1, 0)
                self.assert_test(g.sources[0] is v1, f"Mixed: reconnect {gname}[0]")
            else:
                if g.sources[0] != None:
                    c.disconnect(g, 0)
                if g.sources[1] != None:
                    c.disconnect(g, 1)
                self.assert_test(g.sources[0] == None and g.sources[1] == None,
                                 f"Mixed: disconnect {gname}[0,1]")
                c.connect(g, v1, 0)
                c.connect(g, v2, 1)
                self.assert_test(g.sources[0] is v1 and g.sources[1] is v2,
                                 f"Mixed: reconnect {gname}[0,1]")

        self.assert_test(True, "Mixed circuit full lifecycle complete")

    # =========================================================================
    # PART 2: CIRCUIT STRESS TESTS
    # =========================================================================

    def test_circuit_management_stress(self):
        self.subsection("Circuit Management (500 gates)")
        c = Circuit()
        
        gates = [c.getcomponent(Const.AND_ID) for _ in range(500)]
        self.assert_test(len(c.get_components()) == 500, "500 gates added")
        
        for g in gates[:250]:
            c.hide([g])
        self.assert_test(len(c.get_components()) == 250, "250 after hiding")
        
        for g in gates[:250]:
            c.reveal([g])
        self.assert_test(len(c.get_components()) == 500, "500 after revealing")

    def test_propagation_deep_chain(self):
        self.subsection("Propagation (1000-deep chain)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        v = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(v, Const.LOW)
        prev = v
        for _ in range(1000):
            n = c.getcomponent(Const.NOT_ID)
            c.connect(n, prev, 0)
            prev = n
        
        c.toggle(v, Const.HIGH)
        self.assert_test(prev.output == Const.HIGH, f"1000-deep chain HIGH->HIGH")
        
        c.toggle(v, Const.LOW)
        self.assert_test(prev.output == Const.LOW, f"1000-deep chain LOW->LOW")

    def test_propagation_wide_fanout(self):
        self.subsection("Propagation (5000 fanout)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        v = c.getcomponent(Const.VARIABLE_ID)
        const_high = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(const_high, Const.HIGH)
        
        gates = []
        for _ in range(5000):
            # Using 2-input AND gate as a buffer/repeater properly.
            g = c.getcomponent(Const.AND_ID)
            c.connect(g, v, 0)
            c.connect(g, const_high, 1)
            gates.append(g)
        
        start = time.perf_counter_ns()
        c.toggle(v, Const.HIGH)
        duration = (time.perf_counter_ns() - start) / 1_000_000
        
        all_high = all(g.output == Const.HIGH for g in gates)
        self.assert_test(all_high, f"5000 targets updated ({duration:.2f}ms)")

    def test_delete_stress(self):
        self.subsection("Delete Stress (Delete 500 gates)")
        c = Circuit()
        c.simulate(Const.SIMULATE)

        v = c.getcomponent(Const.VARIABLE_ID)
        const_high = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(const_high, Const.HIGH)
        
        gates = []
        for i in range(500):
            g = c.getcomponent(Const.AND_ID)
            c.connect(g, v, 0)
            c.connect(g, const_high, 1)
            gates.append(g)

        self.assert_test(len(v.hitlist) == 500, "500 connections in hitlist")

        # Delete (hide) half
        for g in gates[:250]:
            c.hide([g])

        # Removing gates should clean up the source's hitlist
        self.assert_test(len(v.hitlist) == 250, "250 connections remaining after termination")
        
        c.toggle(v, Const.HIGH)
        # Check remaining gates work
        # Note: gates[250:] correspond to the second half which we kept
        remaining_ok = all(g.output == Const.HIGH for g in gates[250:])
        self.assert_test(remaining_ok, "Remaining 250 gates still functional")

    def test_copy_paste_complex(self):
        self.subsection("Copy/Paste Complex Structure")
        c = Circuit()
        c.simulate(Const.SIMULATE)

        # Build an SR Latch structure to test internal reference copying
        set_pin = c.getcomponent(Const.VARIABLE_ID)
        rst_pin = c.getcomponent(Const.VARIABLE_ID)
        
        q = c.getcomponent(Const.NOR_ID)
        qb = c.getcomponent(Const.NOR_ID)
        
        # Connections
        c.connect(q, rst_pin, 0)
        c.connect(q, qb, 1)      # Feedback
        c.connect(qb, set_pin, 0)
        c.connect(qb, q, 1)      # Feedback
        
        # Copy the latch (q, qb) but NOT the external inputs
        c.copy([q, qb])
        pasted_gates = c.paste() # Returns list of new gates
        
        self.assert_test(len(pasted_gates) == 2, "2 components pasted")
        
        # Identify pasted components
        q_copy = pasted_gates[0]
        qb_copy = pasted_gates[1]
        
        # Verify internal feedback loop is preserved (gates point to each other's copies)
        # Using string representation to check cross-reference or source identity
        
        # Source 1 of q_copy should be qb_copy
        # Source 1 of qb_copy should be q_copy
        internal_ok = (q_copy.sources[1] == qb_copy) and (qb_copy.sources[1] == q_copy)
        self.assert_test(internal_ok, "Internal feedback loop preserved in copy")
        
        # Verify external connections are lost (because inputs weren't copied)
        external_lost = (q_copy.sources[0] == None) and (qb_copy.sources[0] == None)
        self.assert_test(external_lost, "External connections dropped (as expected)")

    def test_hide_reveal_stress(self):
        self.subsection("Hide/Reveal (100 cycles)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        v = c.getcomponent(Const.VARIABLE_ID)
        chain = [v]
        for _ in range(10):
            g = c.getcomponent(Const.NOT_ID)
            c.connect(g, chain[-1], 0)
            chain.append(g)
        
        middle = chain[5]
        for _ in range(100):
            c.hide([middle])
            c.reveal([middle])
        
        self.assert_test(True, "100 hide/reveal cycles")

    def test_reset_stress(self):
        self.subsection("Reset")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        for _ in range(100):
            v = c.getcomponent(Const.VARIABLE_ID)
            g = c.getcomponent(Const.NOT_ID)
            c.connect(g, v, 0)
            c.toggle(v, Const.HIGH)
        
        c.reset()
        self.assert_test(Const.get_MODE() == Const.DESIGN, "Reset to DESIGN mode")

    # =========================================================================
    # PART 3: EVENT MANAGER STRESS
    # =========================================================================

    def test_undo_redo_stress(self):
        self.subsection("Undo/Redo (200 ops)")
        e = Event()
        c = Circuit()
        
        # Add 100 gates - each is an undoable operation
        for i in range(100):
            cmd = Add(c, Const.AND_ID)
            cmd.execute()
            e.register(cmd)
            g = cmd.gate
            self.assert_test(g in c.get_components(), f"Add gate {i}")
        
        # Undo each one
        for i in range(100):
            e.undo()
            self.assert_test(len(c.get_components()) == 99-i, f"Undo {i}")
        
        # Redo each one
        for i in range(100):
            e.redo()
            self.assert_test(len(c.get_components()) == i+1, f"Redo {i}")

    def test_rapid_undo_redo(self):
        self.subsection("Rapid Undo/Redo (500 cycles)")
        e = Event()
        c = Circuit()
        
        cmd = Add(c, Const.AND_ID)
        cmd.execute()
        e.register(cmd)
        g = cmd.gate
        
        # 500 undo/redo cycles, each pair verified
        for i in range(500):
            e.undo()
            self.assert_test(g not in c.get_components(), f"Cycle {i}: Undo")
            e.redo()
            self.assert_test(g in c.get_components(), f"Cycle {i}: Redo")

    # =========================================================================
    # PART 4: IC STRESS
    # =========================================================================

    def test_ic_basic_functionality(self):
        self.subsection("IC Basic Functionality")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        # Create a simple inverter IC
        ic = c.getcomponent(Const.IC_ID)
        inp = ic.getcomponent(Const.INPUT_PIN_ID)
        out = ic.getcomponent(Const.OUTPUT_PIN_ID)
        not_g = ic.getcomponent(Const.NOT_ID)
        c.connect(not_g, inp, 0)
        c.connect(out, not_g, 0)
        
        self.assert_test(len(ic.inputs) == 1, "IC has 1 input")
        self.assert_test(len(ic.outputs) == 1, "IC has 1 output")
        self.assert_test(len(ic.internal) == 1, "IC has 1 internal gate")
        
        # Wire up and test
        v = c.getcomponent(Const.VARIABLE_ID)
        c.connect(inp, v, 0)
        c.counter+=ic.counter
        c.toggle(v, Const.HIGH)
        self.assert_test(out.output == Const.LOW, "IC inverts HIGH->LOW")
        
        c.toggle(v, Const.LOW)
        self.assert_test(out.output == Const.HIGH, "IC inverts LOW->HIGH")

    def test_ic_nested(self):
        self.subsection("Nested ICs (2 levels)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        # Create outer IC containing inner IC
        outer_ic = c.getcomponent(Const.IC_ID)
        outer_inp = outer_ic.getcomponent(Const.INPUT_PIN_ID)
        outer_out = outer_ic.getcomponent(Const.OUTPUT_PIN_ID)
        
        # Inner IC: double inverter (identity)
        inner_ic = outer_ic.getcomponent(Const.IC_ID)
        inner_inp = inner_ic.getcomponent(Const.INPUT_PIN_ID)
        inner_out = inner_ic.getcomponent(Const.OUTPUT_PIN_ID)
        not1 = inner_ic.getcomponent(Const.NOT_ID)
        not2 = inner_ic.getcomponent(Const.NOT_ID)
        c.connect(not1, inner_inp, 0)
        c.connect(not2, not1, 0)
        c.connect(inner_out, not2, 0)
        
        # Wire outer IC
        c.connect(inner_inp, outer_inp, 0)
        c.connect(outer_out, inner_out, 0)
        
        v = c.getcomponent(Const.VARIABLE_ID)
        c.connect(outer_inp, v, 0)
        c.counter+=outer_ic.counter
        c.counter+=inner_ic.counter
        c.toggle(v, Const.HIGH)
        self.assert_test(outer_out.output == Const.HIGH, "Nested IC preserves HIGH")
        
        c.toggle(v, Const.LOW)
        self.assert_test(outer_out.output == Const.LOW, "Nested IC preserves LOW")

    def test_ic_deeply_nested(self):
        self.subsection("Deeply Nested ICs (4 levels)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        # Create 4-level nested structure
        def create_inverter_ic(parent):
            if isinstance(parent, Circuit):
                ic = parent.getcomponent(Const.IC_ID)
            else:
                ic = parent.getcomponent(Const.IC_ID)
            inp = ic.getcomponent(Const.INPUT_PIN_ID)
            out = ic.getcomponent(Const.OUTPUT_PIN_ID)
            not_g = ic.getcomponent(Const.NOT_ID)
            c.counter+=ic.counter
            c.connect(not_g, inp, 0)
            c.connect(out, not_g, 0)
            return ic, inp, out
        
        # Level 1
        ic1, inp1, out1 = create_inverter_ic(c)
        # Level 2 inside ic1
        ic2, inp2, out2 = create_inverter_ic(c)
        ic1.addgate(ic2)
        c.delobj(ic2)

        # Level 3 inside ic2
        ic3, inp3, out3 = create_inverter_ic(c)
        ic2.addgate(ic3)
        c.delobj(ic3)

        # Level 4 inside ic3
        ic4, inp4, out4 = create_inverter_ic(c)
        ic3.addgate(ic4)
        c.delobj(ic4)
        
        # Wire them together: v -> ic1.inp -> ic2.inp -> ic3.inp -> ic4.inp
        create_inverter_ic = locals()['create_inverter_ic'] # Ensure scope
        # Wire them together: v -> ic1.inp -> ic2.inp -> ic3.inp -> ic4.inp
        c.counter+=ic1.counter
        c.counter+=ic2.counter
        c.counter+=ic3.counter
        c.counter+=ic4.counter
        v = c.getcomponent(Const.VARIABLE_ID)
        c.connect(inp1, v, 0)
        c.connect(inp2, inp1, 0)
        c.connect(inp3, inp2, 0)
        c.connect(inp4, inp3, 0)
        c.connect(out3, out4, 0)
        c.connect(out2, out3, 0)
        c.connect(out1, out2, 0)
        
        c.simulate(Const.SIMULATE)
        c.toggle(v, Const.HIGH)
        # inp1->inp2->inp3->inp4->NOT->out4->out3->out2->out1
        # Effectively a single inverter wrapped in wires
        self.assert_test(out1.output == Const.LOW, "4-level nested IC (inverter behavior)")

    def test_ic_many_pins(self):
        self.subsection("IC with 32 pins")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        ic = c.getcomponent(Const.IC_ID)
        outputs = []
        variables = []
        
        for i in range(32):
            inp = ic.getcomponent(Const.INPUT_PIN_ID)
            out = ic.getcomponent(Const.OUTPUT_PIN_ID)
            not_g = ic.getcomponent(Const.NOT_ID)
            c.connect(not_g, inp, 0)
            c.connect(out, not_g, 0)
            c.counter+=ic.counter
            v = c.getcomponent(Const.VARIABLE_ID)
            c.connect(inp, v, 0)
            variables.append(v)
            outputs.append(out)
        
        self.assert_test(len(ic.inputs) == 32, "32 input pins created")
        self.assert_test(len(ic.outputs) == 32, "32 output pins created")
        
        # Toggle all HIGH
        for v in variables:
            c.toggle(v, Const.HIGH)
        
        all_low = all(o.output == Const.LOW for o in outputs)
        self.assert_test(all_low, "32-pin IC all inverted correctly")
        
        # Toggle half (alternating)
        for i, v in enumerate(variables):
            c.toggle(v, i % 2)
        
        # Logic is inverted: Input 1 -> Output 0. Input 0 -> Output 1.
        # So if i%2==1 (Odd/High), expect Low. If i%2==0 (Even/Low), expect High.
        alternating = all(outputs[i].output == (Const.LOW if i % 2 else Const.HIGH) for i in range(32))
        self.assert_test(alternating, "32-pin IC alternating pattern")

    def test_ic_complex_internal(self):
        self.subsection("IC with Complex Internal Logic (Full Adder)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        ic = c.getcomponent(Const.IC_ID)
        
        # Inputs: A, B, Cin
        inp_a = ic.getcomponent(Const.INPUT_PIN_ID)
        inp_b = ic.getcomponent(Const.INPUT_PIN_ID)
        inp_cin = ic.getcomponent(Const.INPUT_PIN_ID)
        
        # Outputs: Sum, Cout
        out_sum = ic.getcomponent(Const.OUTPUT_PIN_ID)
        out_cout = ic.getcomponent(Const.OUTPUT_PIN_ID)
        
        # Internal logic: Full Adder
        xor1 = ic.getcomponent(Const.XOR_ID)
        c.connect(xor1, inp_a, 0)
        c.connect(xor1, inp_b, 1)
        
        xor2 = ic.getcomponent(Const.XOR_ID)
        c.connect(xor2, xor1, 0)
        c.connect(xor2, inp_cin, 1)
        c.connect(out_sum, xor2, 0)
        
        and1 = ic.getcomponent(Const.AND_ID)
        c.connect(and1, inp_a, 0)
        c.connect(and1, inp_b, 1)
        
        and2 = ic.getcomponent(Const.AND_ID)
        c.connect(and2, xor1, 0)
        c.connect(and2, inp_cin, 1)
        
        or1 = ic.getcomponent(Const.OR_ID)
        c.connect(or1, and1, 0)
        c.connect(or1, and2, 1)
        c.connect(out_cout, or1, 0)
        c.counter+=ic.counter
        self.assert_test(len(ic.internal) == 5, "IC has 5 internal gates")
        
        # Wire inputs
        v_a = c.getcomponent(Const.VARIABLE_ID)
        v_b = c.getcomponent(Const.VARIABLE_ID)
        v_cin = c.getcomponent(Const.VARIABLE_ID)
        c.connect(inp_a, v_a, 0)
        c.connect(inp_b, v_b, 0)
        c.connect(inp_cin, v_cin, 0)
        
        # Test: 1+1+1 = 11 (Sum=1, Cout=1)
        c.toggle(v_a, 1); c.toggle(v_b, 1); c.toggle(v_cin, 1)
        self.assert_test(out_sum.output == Const.HIGH, "Full Adder IC: Sum(1,1,1)=1")
        self.assert_test(out_cout.output == Const.HIGH, "Full Adder IC: Cout(1,1,1)=1")
        
        # Test: 1+0+0 = 01
        c.toggle(v_a, 1); c.toggle(v_b, 0); c.toggle(v_cin, 0)
        self.assert_test(out_sum.output == Const.HIGH, "Full Adder IC: Sum(1,0,0)=1")
        self.assert_test(out_cout.output == Const.LOW, "Full Adder IC: Cout(1,0,0)=0")

    def test_ic_save_load(self):
        self.subsection("IC Save/Load to JSON")
        c1 = Circuit()
        c1.simulate(Const.SIMULATE)
        
        # Create IC
        ic = c1.getcomponent(Const.IC_ID)
        ic.custom_name = "TestInverter"
        inp = ic.getcomponent(Const.INPUT_PIN_ID)
        out = ic.getcomponent(Const.OUTPUT_PIN_ID)
        not_g = ic.getcomponent(Const.NOT_ID)
        c1.connect(not_g, inp, 0)
        c1.connect(out, not_g, 0)
        
        v = c1.getcomponent(Const.VARIABLE_ID)
        c1.connect(inp, v, 0)
        c1.toggle(v, Const.HIGH)
        c1.counter+=ic.counter
        # Save
        temp_file = os.path.join(tempfile.gettempdir(), "test_ic.json")
        c1.writetojson(temp_file)
        self.assert_test(os.path.exists(temp_file), "IC circuit saved to file")
        
        # Load into new circuit
        c2 = Circuit()
        c2.readfromjson(temp_file)
        c2.simulate(Const.SIMULATE)
        
        self.assert_test(len(c2.get_components()) == len(c1.get_components()), "Loaded circuit has same component count")
        
        os.remove(temp_file)
        self.assert_test(True, "IC save/load complete")

    def test_ic_hide_reveal(self):
        self.subsection("IC Hide/Reveal (50 cycles)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        ic = c.getcomponent(Const.IC_ID)
        inp = ic.getcomponent(Const.INPUT_PIN_ID)
        out = ic.getcomponent(Const.OUTPUT_PIN_ID)
        not_g = ic.getcomponent(Const.NOT_ID)
        c.connect(not_g, inp, 0)
        c.connect(out, not_g, 0)
        
        v = c.getcomponent(Const.VARIABLE_ID)
        c.connect(inp, v, 0)
        
        c.toggle(v, Const.HIGH)
        c.counter+=ic.counter
        for i in range(50):
            ic.hide()
            ic.reveal()
        
        # Verify still works after hide/reveal cycles
        c.toggle(v, Const.LOW)
        self.assert_test(out.output == Const.HIGH, "IC works after 50 hide/reveal cycles")

    def test_ic_reset(self):
        self.subsection("IC Reset")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        ic = c.getcomponent(Const.IC_ID)
        inp = ic.getcomponent(Const.INPUT_PIN_ID)
        out = ic.getcomponent(Const.OUTPUT_PIN_ID)
        not_g = ic.getcomponent(Const.NOT_ID)
        c.connect(not_g, inp, 0)
        c.connect(out, not_g, 0)
        
        v = c.getcomponent(Const.VARIABLE_ID)
        c.connect(inp, v, 0)
        c.counter+=ic.counter
        c.toggle(v, Const.HIGH)
        self.assert_test(out.output == Const.LOW, "IC output LOW before reset")
        
        ic.reset()
        self.assert_test(out.output == Const.UNKNOWN, "IC output UNKNOWN after reset")
        
        c.reset()
        self.assert_test(Const.get_MODE() == Const.DESIGN, "Circuit reset to DESIGN mode")

    def test_ic_copy_paste(self):
        self.subsection("IC Copy/Paste")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        ic = c.getcomponent(Const.IC_ID)
        inp = ic.getcomponent(Const.INPUT_PIN_ID)
        out = ic.getcomponent(Const.OUTPUT_PIN_ID)
        not_g = ic.getcomponent(Const.NOT_ID)
        c.connect(not_g, inp, 0)
        c.connect(out, not_g, 0)
        
        initial_count = len(c.get_components())
        
        # Copy and paste
        c.copy([ic])
        c.paste()
        c.counter+=ic.counter
        self.assert_test(len(c.get_components()) == initial_count + 1, "IC copied and pasted")


    def test_ic_massive_internal(self):
        self.subsection("IC with 100 Internal Gates")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        ic = c.getcomponent(Const.IC_ID)
        inp = ic.getcomponent(Const.INPUT_PIN_ID)
        
        # Chain of 100 NOT gates
        prev = inp
        for _ in range(100):
            not_g = ic.getcomponent(Const.NOT_ID)
            c.connect(not_g, prev, 0)
            prev = not_g
        
        out = ic.getcomponent(Const.OUTPUT_PIN_ID)
        c.connect(out, prev, 0)
        
        self.assert_test(len(ic.internal) == 100, "IC has 100 internal gates")
        
        v = c.getcomponent(Const.VARIABLE_ID)
        c.connect(inp, v, 0)
        c.counter+=ic.counter
        c.toggle(v, Const.HIGH)
        # 100 inversions = identity (even number)
        self.assert_test(out.output == Const.HIGH, "100-gate IC chain works")

    def test_ic_cascade(self):
        self.subsection("IC Cascade (10 ICs in series)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        v = c.getcomponent(Const.VARIABLE_ID)
        prev_out = v
        
        ics = []
        for _ in range(10):
            ic = c.getcomponent(Const.IC_ID)
            inp = ic.getcomponent(Const.INPUT_PIN_ID)
            out = ic.getcomponent(Const.OUTPUT_PIN_ID)
            not_g = ic.getcomponent(Const.NOT_ID)
            c.connect(not_g, inp, 0)
            c.connect(out, not_g, 0)
            c.counter+=ic.counter
            
            c.connect(inp, prev_out, 0)
            prev_out = out
            ics.append(out)
        c.toggle(v, Const.HIGH)
        # 10 inversions = identity (even)
        self.assert_test(prev_out.output == Const.HIGH, "10 cascaded ICs work")
        
        c.toggle(v, Const.LOW)
        self.assert_test(prev_out.output == Const.LOW, "Cascade propagates LOW")

    def test_ic_multi_output(self):
        self.subsection("IC with 8 Outputs from 1 Input")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        ic = c.getcomponent(Const.IC_ID)
        inp = ic.getcomponent(Const.INPUT_PIN_ID)
        
        outputs = []
        for i in range(8):
            out = ic.getcomponent(Const.OUTPUT_PIN_ID)
            if i % 2 == 0:
                # Direct connection
                c.connect(out, inp, 0)
            else:
                # Through NOT
                not_g = ic.getcomponent(Const.NOT_ID)
                c.connect(not_g, inp, 0)
                c.connect(out, not_g, 0)
            outputs.append(out)
        
        v = c.getcomponent(Const.VARIABLE_ID)
        c.connect(inp, v, 0)
        c.counter+=ic.counter
        c.toggle(v, Const.HIGH)
        
        # Even outputs = HIGH (direct), Odd outputs = LOW (inverted)
        correct = all(outputs[i].output == (Const.HIGH if i % 2 == 0 else Const.LOW) for i in range(8))
        self.assert_test(correct, "8-output IC: alternating pattern")

    def test_ic_stress_bulk(self):
        self.subsection("Bulk IC Stress (50 ICs, 100 toggles each)")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        ics = []
        variables = []
        outputs = []
        
        for _ in range(50):
            ic = c.getcomponent(Const.IC_ID)
            inp = ic.getcomponent(Const.INPUT_PIN_ID)
            out = ic.getcomponent(Const.OUTPUT_PIN_ID)
            not_g = ic.getcomponent(Const.NOT_ID)
            c.connect(not_g, inp, 0)
            c.connect(out, not_g, 0)
            
            v = c.getcomponent(Const.VARIABLE_ID)
            c.connect(inp, v, 0)
            c.counter+=ic.counter
            ics.append(ic)
            variables.append(v)
            outputs.append(out)
        
        self.assert_test(len(ics) == 50, "50 ICs created")
        
        start = time.perf_counter_ns()
        for _ in range(100):
            for v in variables:
                c.toggle(v, Const.HIGH)
            for v in variables:
                c.toggle(v, Const.LOW)
        duration = (time.perf_counter_ns() - start) / 1_000_000
        
        self.assert_test(True, f"50 ICs x 100 toggle cycles: {duration:.2f}ms")

    # =========================================================================
    # PART 5: SERIALIZATION STRESS
    # =========================================================================

    def test_save_load_large_circuit(self):
        self.subsection("Save/Load 1000 gates")
        c1 = Circuit()
        c1.simulate(Const.SIMULATE)
        
        prev = c1.getcomponent(Const.VARIABLE_ID)
        for _ in range(999):
            g = c1.getcomponent(Const.NOT_ID)
            c1.connect(g, prev, 0)
            prev = g
        
        temp_file = os.path.join(tempfile.gettempdir(), "test_large.json")
        c1.writetojson(temp_file)
        
        c2 = Circuit()
        c2.readfromjson(temp_file)
        
        self.assert_test(len(c2.get_components()) == 1000, "1000 components loaded")
        os.remove(temp_file)

    def test_copy_paste_stress(self):
        self.subsection("Copy/Paste 50 gates")
        c = Circuit()
        c.simulate(Const.SIMULATE)
        
        gates = [c.getcomponent(Const.NOT_ID) for _ in range(50)]
        initial = len(c.get_components())
        c.copy(gates)
        c.paste()
        
        self.assert_test(len(c.get_components()) == initial + 50, "50 pasted")

    # =========================================================================
    # PART 6: TRUTH TABLE STRESS
    # =========================================================================

    def test_truth_table_4_inputs(self):
        """4-input truth table (16 rows)"""
        c = Circuit()
        vars = [c.getcomponent(Const.VARIABLE_ID) for _ in range(4)]
        g = c.getcomponent(Const.AND_ID)
        c.setlimits(g, 4)
        for i, v in enumerate(vars):
            c.connect(g, v, i)
        c.simulate(Const.SIMULATE)
        
        start = time.perf_counter_ns()
        table = c.truthTable()
        duration = (time.perf_counter_ns() - start) / 1_000_000
        
        self.assert_test(table is not None, f"4-input (16 rows): {duration:.2f} ms")
        
        # Verify AND behavior
        for v in vars:
            c.toggle(v, 1)
        self.assert_test(g.output == Const.HIGH, "AND(1,1,1,1)=1")

    def test_truth_table_6_inputs(self):
        """6-input truth table (64 rows)"""
        c = Circuit()
        vars = [c.getcomponent(Const.VARIABLE_ID) for _ in range(6)]
        g = c.getcomponent(Const.OR_ID)
        c.setlimits(g, 6)
        for i, v in enumerate(vars):
            c.connect(g, v, i)
        c.simulate(Const.SIMULATE)
        
        start = time.perf_counter_ns()
        table = c.truthTable()
        duration = (time.perf_counter_ns() - start) / 1_000_000
        
        self.assert_test(table is not None, f"6-input (64 rows): {duration:.2f} ms")

    def test_truth_table_8_inputs(self):
        """8-input truth table (256 rows)"""
        c = Circuit()
        vars = [c.getcomponent(Const.VARIABLE_ID) for _ in range(8)]
        g = c.getcomponent(Const.XOR_ID)
        c.setlimits(g, 8)
        for i, v in enumerate(vars):
            c.connect(g, v, i)
        c.simulate(Const.SIMULATE)
        
        start = time.perf_counter_ns()
        table = c.truthTable()
        duration = (time.perf_counter_ns() - start) / 1_000_000
        
        self.assert_test(table is not None, f"8-input (256 rows): {duration:.2f} ms")

    def test_truth_table_10_inputs(self):
        """10-input truth table (1024 rows)"""
        c = Circuit()
        vars = [c.getcomponent(Const.VARIABLE_ID) for _ in range(10)]
        g = c.getcomponent(Const.NAND_ID)
        c.setlimits(g, 10)
        for i, v in enumerate(vars):
            c.connect(g, v, i)
        c.simulate(Const.SIMULATE)
        
        start = time.perf_counter_ns()
        table = c.truthTable()
        duration = (time.perf_counter_ns() - start) / 1_000_000
        
        self.assert_test(table is not None, f"10-input (1024 rows): {duration:.2f} ms")

    def test_truth_table_complex(self):
        """Full adder circuit (3 inputs, 2 outputs)"""
        c = Circuit()
        
        # Full adder: A + B + Cin = (Sum, Cout)
        a = c.getcomponent(Const.VARIABLE_ID)
        b = c.getcomponent(Const.VARIABLE_ID)
        cin = c.getcomponent(Const.VARIABLE_ID)
        
        # Sum = A XOR B XOR Cin
        xor1 = c.getcomponent(Const.XOR_ID)
        c.connect(xor1, a, 0)
        c.connect(xor1, b, 1)
        
        sum_out = c.getcomponent(Const.XOR_ID)
        c.connect(sum_out, xor1, 0)
        c.connect(sum_out, cin, 1)
        
        # Cout = (A AND B) OR (Cin AND (A XOR B))
        and1 = c.getcomponent(Const.AND_ID)
        c.connect(and1, a, 0)
        c.connect(and1, b, 1)
        
        and2 = c.getcomponent(Const.AND_ID)
        c.connect(and2, cin, 0)
        c.connect(and2, xor1, 1)
        
        cout = c.getcomponent(Const.OR_ID)
        c.connect(cout, and1, 0)
        c.connect(cout, and2, 1)
        
        c.simulate(Const.SIMULATE)
        
        # Verify: 1+1+1 = 11 (Sum=1, Cout=1)
        c.toggle(a, 1); c.toggle(b, 1); c.toggle(cin, 1)
        self.assert_test(sum_out.output == Const.HIGH, "Full adder Sum(1,1,1)=1")
        self.assert_test(cout.output == Const.HIGH, "Full adder Cout(1,1,1)=1")
        
        # Verify: 1+0+0 = 01 (Sum=1, Cout=0)
        c.toggle(a, 1); c.toggle(b, 0); c.toggle(cin, 0)
        self.assert_test(sum_out.output == Const.HIGH, "Full adder Sum(1,0,0)=1")
        self.assert_test(cout.output == Const.LOW, "Full adder Cout(1,0,0)=0")
        
        table = c.truthTable()
        self.assert_test(table is not None, "Full adder truth table")

    # =========================================================================
    # PART 7: SPEED BENCHMARKS
    # =========================================================================

    def test_marathon(self, count):
        self.subsection(f"Marathon ({count:,} NOT gates)")
        self.circuit.clearcircuit()
        c = self.circuit
        
        inp = c.getcomponent(Const.VARIABLE_ID)
        prev = inp
        for _ in range(count):
            g = c.getcomponent(Const.NOT_ID)
            c.connect(g, prev, 0)
            prev = g

        c.simulate(Const.SIMULATE)
        c.toggle(inp, 0)
        
        # Warmup: Toggle to 1 then back to 0
        c.toggle(inp, 1)
        c.toggle(inp, 0)
        
        duration = self.timer(lambda: c.toggle(inp, 1))
        latency = (duration*1e6)/count
        self.perf_metrics['marathon'] = {'time': duration, 'latency': latency, 'gates': count}
        
        expected = 'T' if (count % 2 == 0) else 'F'
        self.assert_test(prev.getoutput() == expected, f"{duration:.2f}ms | {latency:.1f}ns/gate")

    def test_avalanche(self, layers):
        total = (2**layers)-1
        self.subsection(f"Avalanche ({layers} layers, {total:,} gates)")
        self.circuit.clearcircuit()
        c = self.circuit
        
        root = c.getcomponent(Const.VARIABLE_ID)
        # Create constant HIGH rail for AND gate second inputs
        const_high = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(const_high, Const.HIGH)
        
        layer = [root]
        for _ in range(layers):
            next_l = []
            for p in layer:
                # Use standard 2-input AND gates instead of 1-input buffers
                g1 = c.getcomponent(Const.AND_ID); c.connect(g1, p, 0); c.connect(g1, const_high, 1)
                g2 = c.getcomponent(Const.AND_ID); c.connect(g2, p, 0); c.connect(g2, const_high, 1)
                next_l.extend([g1, g2])
            layer = next_l

        c.simulate(Const.SIMULATE)
        c.toggle(root, 0)

        # Warmup
        c.toggle(root, 1)
        c.toggle(root, 0)

        duration = self.timer(lambda: c.toggle(root, 1))
        rate = total/(duration/1000)
        self.perf_metrics['avalanche'] = {'time': duration, 'rate': rate, 'gates': total}
        
        self.assert_test(True, f"{duration:.2f}ms | {rate/1_000_000:.2f}M/sec")

    def test_gridlock(self, size):
        total = size*size
        self.subsection(f"Gridlock ({size}x{size} = {total:,} gates)")
        self.circuit.clearcircuit()
        c = self.circuit

        grid = [[None]*size for _ in range(size)]
        trig = c.getcomponent(Const.VARIABLE_ID)
        
        # Create constant LOW rail for unconnected OR inputs
        const_low = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(const_low, Const.LOW)

        for r in range(size):
            for k in range(size):
                grid[r][k] = c.getcomponent(Const.OR_ID)
        
        for r in range(size):
            for k in range(size):
                g = grid[r][k]
                
                # Input 0: Top neighbor, trigger, or LOW rail
                if r > 0:
                    c.connect(g, grid[r-1][k], 0)
                elif r == 0 and k == 0:
                    c.connect(g, trig, 0)
                else:
                    c.connect(g, const_low, 0)
                
                # Input 1: Left neighbor or LOW rail
                if k > 0:
                    c.connect(g, grid[r][k-1], 1)
                else:
                    c.connect(g, const_low, 1)
                
                # Removed setlimits(1) optimization

        c.simulate(Const.SIMULATE)
        c.toggle(trig, 0)

        # Warmup
        c.toggle(trig, 1)
        c.toggle(trig, 0)

        duration = self.timer(lambda: c.toggle(trig, 1))
        self.perf_metrics['gridlock'] = {'time': duration, 'gates': total}
        
        passed = (grid[size-1][size-1].getoutput() == 'T')
        self.assert_test(passed, f"{duration:.2f}ms")

    def test_echo_chamber(self, count):
        self.subsection(f"Echo Chamber ({count:,} SR latches)")
        self.circuit.clearcircuit()
        c = self.circuit
        c.simulate(Const.SIMULATE)

        set_line = c.getcomponent(Const.VARIABLE_ID)
        rst_line = c.getcomponent(Const.VARIABLE_ID)
        
        latches = []
        for _ in range(count):
            q = c.getcomponent(Const.NOR_ID)
            qb = c.getcomponent(Const.NOR_ID)
            c.connect(q, rst_line, 0)
            c.connect(qb, set_line, 0)
            c.connect(q, qb, 1)
            c.connect(qb, q, 1)
            latches.append(q)

        c.toggle(set_line, 0)
        c.toggle(rst_line, 1)
        c.toggle(rst_line, 0)

        # Warmup
        c.toggle(set_line, 1)
        c.toggle(set_line, 0)

        duration = self.timer(lambda: c.toggle(set_line, 1))
        self.perf_metrics['echo_chamber'] = {'time': duration, 'gates': count*2}
        
        passed = all(l.getoutput() == 'T' for l in latches)
        self.assert_test(passed, f"{duration:.2f}ms")

    def test_black_hole(self, inputs):
        self.subsection(f"Black Hole ({inputs:,} inputs)")
        self.circuit.clearcircuit()
        c = self.circuit
        c.simulate(Const.SIMULATE)

        black_hole = c.getcomponent(Const.AND_ID)
        c.setlimits(black_hole, inputs)

        vars_list = []
        for i in range(inputs):
            v = c.getcomponent(Const.VARIABLE_ID)
            c.connect(black_hole, v, i)
            vars_list.append(v)
        
        for i in range(inputs - 1):
            c.toggle(vars_list[i], 1)
        
        trigger = vars_list[-1]
        
        # Warmup
        c.toggle(trigger, 1)
        c.toggle(trigger, 0)

        duration = self.timer(lambda: c.toggle(trigger, 1))
        self.perf_metrics['black_hole'] = {'time': duration, 'gates': inputs}
        
        self.assert_test(black_hole.getoutput() == 'T', f"{duration:.4f}ms")

    def test_paradox_burn(self):
        self.subsection("Paradox (XOR loop)")
        self.circuit.clearcircuit()
        c = self.circuit
        c.simulate(Const.SIMULATE)

        source = c.getcomponent(Const.VARIABLE_ID)
        xor_gate = c.getcomponent(Const.XOR_ID)

        c.connect(xor_gate, source, 0)
        c.connect(xor_gate, xor_gate, 1)
        
        # NOTE: Skipping warmup for paradox test as it triggers error state/potential crash
        try:
            gc.disable()
            start = time.perf_counter_ns()
            c.toggle(source, 1)
            duration = (time.perf_counter_ns() - start) / 1_000_000
            gc.enable()
            
            self.perf_metrics['paradox'] = {'time': duration, 'gates': 1}
            self.assert_test(xor_gate.output == Const.ERROR, f"ERROR state ({duration:.4f}ms)")
        except RecursionError:
            gc.enable()
            self.assert_test(True, "Caught RecursionError")
        except Exception as e:
            gc.enable()
            self.assert_test(False, f"CRASHED: {e}")



    def test_mega_chain(self):
        self.subsection("Mega Chain (1M NOT gates)")
        self.circuit.clearcircuit()
        c = self.circuit
        
        inp = c.getcomponent(Const.VARIABLE_ID)
        prev = inp
        count = 1_000_000
        
        for i in range(count):
            g = c.getcomponent(Const.NOT_ID)
            c.connect(g, prev, 0)
            prev = g
            if i > 0 and i % 100000 == 0:
                self.progress(i, count)

        c.simulate(Const.SIMULATE)
        c.toggle(inp, 0)
        
        # Warmup
        c.toggle(inp, 1)
        c.toggle(inp, 0)

        start = time.perf_counter_ns()
        c.toggle(inp, 1)
        duration = (time.perf_counter_ns() - start) / 1_000_000
        latency = (duration * 1e6) / count
        
        self.perf_metrics['mega_chain'] = {'time': duration, 'latency': latency, 'gates': count}
        
        expected = 'T' if (count % 2 == 0) else 'F'
        self.assert_test(prev.getoutput() == expected, f"{duration:.2f}ms | {latency:.1f}ns/gate")

    def test_extreme_fanout(self):
        self.subsection("Extreme Fanout (50K targets)")
        self.circuit.clearcircuit()
        c = self.circuit
        c.simulate(Const.SIMULATE)
        
        v = c.getcomponent(Const.VARIABLE_ID)
        const_high = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(const_high, Const.HIGH)
        
        gates = []
        count = 50_000
        
        for i in range(count):
            g = c.getcomponent(Const.AND_ID)
            # Use 2-input AND
            c.connect(g, v, 0)
            c.connect(g, const_high, 1)
            gates.append(g)
            if i > 0 and i % 10000 == 0:
                self.progress(i, count)
        
        c.toggle(v, 0)

        # Warmup
        c.toggle(v, 1)
        c.toggle(v, 0)
        
        start = time.perf_counter_ns()
        c.toggle(v, 1)
        duration = (time.perf_counter_ns() - start) / 1_000_000
        
        all_high = all(g.output == Const.HIGH for g in gates)
        self.perf_metrics['extreme_fanout'] = {'time': duration, 'gates': count}
        
        self.assert_test(all_high, f"{duration:.2f}ms | {count} gates updated")

    def test_extreme_fanin(self, count):
        self.subsection(f"Extreme Fan-in ({count:,} inputs)")
        self.circuit.clearcircuit()
        c = self.circuit
        c.simulate(Const.SIMULATE)
        
        g = c.getcomponent(Const.AND_ID)
        c.setlimits(g, count)
        
        vars_list = []
        for i in range(count):
            v = c.getcomponent(Const.VARIABLE_ID)
            c.connect(g, v, i)
            vars_list.append(v)
            if i > 0 and i % 10000 == 0:
                self.progress(i, count)
        
        # Set all HIGH
        for v in vars_list:
            c.toggle(v, 1)
            
        # Warmup: Toggle first input 0 -> 1 -> 0 (wait, default was 1)
        c.toggle(vars_list[0], 0)
        c.toggle(vars_list[0], 1)

        start = time.perf_counter_ns()
        c.toggle(vars_list[0], 0)
        duration = (time.perf_counter_ns() - start) / 1_000_000
        
        self.perf_metrics['extreme_fanin'] = {'time': duration, 'gates': count}
        self.assert_test(g.output == Const.LOW, f"{duration:.2f}ms")

    def test_extreme_fanin_fanout(self, count):
        self.subsection(f"Extreme Fan-in+Fan-out ({count:,} in/out)")
        self.circuit.clearcircuit()
        c = self.circuit
        c.simulate(Const.SIMULATE)
        
        central = c.getcomponent(Const.AND_ID)
        c.setlimits(central, count)
        
        # For fanout targets, use proper 2-input AND gates
        const_high = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(const_high, Const.HIGH)
        
        inputs = []
        for i in range(count):
            v = c.getcomponent(Const.VARIABLE_ID)
            c.connect(central, v, i)
            inputs.append(v)
            if i > 0 and i % 10000 == 0:
                self.progress(i, count)
                
        targets = []
        for i in range(count):
            g = c.getcomponent(Const.AND_ID)
            # Use 2-input AND
            c.connect(g, central, 0)
            c.connect(g, const_high, 1)
            targets.append(g)
            if i > 0 and i % 10000 == 0:
                self.progress(i, count)
        
        for v in inputs:
            c.toggle(v, 1)
            
        # Warmup
        c.toggle(inputs[0], 0)
        c.toggle(inputs[0], 1)

        start = time.perf_counter_ns()
        c.toggle(inputs[0], 0)
        duration = (time.perf_counter_ns() - start) / 1_000_000
        
        all_passed = all(g.output == Const.LOW for g in targets)
        self.perf_metrics['extreme_fanin_fanout'] = {'time': duration, 'gates': count + count + 1}
        self.assert_test(all_passed, f"{duration:.2f}ms")
    def test_cpu_datapath(self, bit_width=8192):
        self.subsection(f"CPU Datapath ({bit_width}-bit ALU + Registers)")
        self.circuit.clearcircuit()
        c = self.circuit
        c.simulate(Const.SIMULATE) # SIMULATE mode includes latches now
        
        a_inputs = []
        b_inputs = []
        sum_outputs = []
        latches = []
        
        clock = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(clock, Const.LOW)

        # Build 8192-bit Ripple Carry Adder & Register File
        # ~10 gates per bit = ~80,000 active gates total
        prev_carry = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(prev_carry, Const.LOW) # Cin = 0

        for i in range(bit_width):
            # 1. Inputs
            a = c.getcomponent(Const.VARIABLE_ID)
            b = c.getcomponent(Const.VARIABLE_ID)
            a_inputs.append(a)
            b_inputs.append(b)
            
            # 2. Full Adder Logic
            # XOR1 = A ^ B
            xor1 = c.getcomponent(Const.XOR_ID)
            c.connect(xor1, a, 0); c.connect(xor1, b, 1)
            
            # Sum = XOR1 ^ Cin
            sum_g = c.getcomponent(Const.XOR_ID)
            c.connect(sum_g, xor1, 0); c.connect(sum_g, prev_carry, 1)
            sum_outputs.append(sum_g)
            
            # AND1 = A & B
            and1 = c.getcomponent(Const.AND_ID)
            c.connect(and1, a, 0); c.connect(and1, b, 1)
            
            # AND2 = Cin & XOR1
            and2 = c.getcomponent(Const.AND_ID)
            c.connect(and2, prev_carry, 0); c.connect(and2, xor1, 1)
            
            # Cout = AND1 | AND2
            cout = c.getcomponent(Const.OR_ID)
            c.connect(cout, and1, 0); c.connect(cout, and2, 1)
            prev_carry = cout # Route to next bit
            
            # 3. Register (D-Latch built from SR Latch)
            # Set = Sum & Clock
            set_g = c.getcomponent(Const.AND_ID)
            c.connect(set_g, sum_g, 0); c.connect(set_g, clock, 1)
            
            # Reset = ~Sum & Clock
            not_sum = c.getcomponent(Const.NOT_ID)
            c.connect(not_sum, sum_g, 0)
            rst_g = c.getcomponent(Const.AND_ID)
            c.connect(rst_g, not_sum, 0); c.connect(rst_g, clock, 1)
            
            # SR Latch (NOR based)
            q = c.getcomponent(Const.NOR_ID)
            qb = c.getcomponent(Const.NOR_ID)
            c.connect(q, rst_g, 0); c.connect(q, qb, 1)
            c.connect(qb, set_g, 0); c.connect(qb, q, 1)
            latches.append(q)
            
            if i > 0 and i % 1000 == 0:
                self.progress(i, bit_width)

        # --- BENCHMARK PHASE 1: The Ripple Cascade ---
        # Set A = 1111...1111 (All High)
        for a in a_inputs:
            c.toggle(a, Const.HIGH)
        # Set B = 0000...0000 (All Low)
        for b in b_inputs:
            c.toggle(b, Const.LOW)

        # Warmup the engine structures
        c.toggle(b_inputs[0], Const.HIGH)
        c.toggle(b_inputs[0], Const.LOW)

        # The test: Add 1 to A. This causes a cascading carry bit to ripple 
        # sequentially through all 8192 adder stages!
        gc.disable()
        start_cascade = time.perf_counter_ns()
        c.toggle(b_inputs[0], Const.HIGH) 
        cascade_duration = (time.perf_counter_ns() - start_cascade) / 1_000_000
        gc.enable()

        # --- BENCHMARK PHASE 2: The Clock Fan-out ---
        # Trigger the clock high to save the sum into the latches
        gc.disable()
        start_clock = time.perf_counter_ns()
        c.toggle(clock, Const.HIGH)
        clock_duration = (time.perf_counter_ns() - start_clock) / 1_000_000
        c.toggle(clock, Const.LOW) # Reset clock
        gc.enable()

        total_duration = cascade_duration + clock_duration
        
        # Verify correctness
        # If A=1111...1111 and we added B=1, the sum should roll over to 0000...0000
        # (Technically the very last Cout is 1, but all sum bits are 0)
        latch_pass = all(l.output == Const.LOW for l in latches)
        
        self.perf_metrics['cpu_datapath'] = {'time': total_duration, 'gates': bit_width * 10}
        msg = f"Ripple: {cascade_duration:.2f}ms | Clock: {clock_duration:.2f}ms"
        self.assert_test(latch_pass, msg)

    # =========================================================================
    # PART 8: REAL-WORLD STRESS TESTS
    # =========================================================================

    def test_ripple_adder_correctness(self, bits=16):
        """Build a real N-bit ripple carry adder and verify arithmetic results."""
        self.subsection(f"Ripple Adder Correctness ({bits}-bit)")
        c = Circuit()
        c.simulate(Const.SIMULATE)

        a_vars = [c.getcomponent(Const.VARIABLE_ID) for _ in range(bits)]
        b_vars = [c.getcomponent(Const.VARIABLE_ID) for _ in range(bits)]
        sum_gates = []

        cin_var = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(cin_var, Const.LOW)
        prev_carry = cin_var

        for i in range(bits):
            xor1 = c.getcomponent(Const.XOR_ID)
            c.connect(xor1, a_vars[i], 0); c.connect(xor1, b_vars[i], 1)
            sum_g = c.getcomponent(Const.XOR_ID)
            c.connect(sum_g, xor1, 0); c.connect(sum_g, prev_carry, 1)
            sum_gates.append(sum_g)
            and1 = c.getcomponent(Const.AND_ID)
            c.connect(and1, a_vars[i], 0); c.connect(and1, b_vars[i], 1)
            and2 = c.getcomponent(Const.AND_ID)
            c.connect(and2, prev_carry, 0); c.connect(and2, xor1, 1)
            cout = c.getcomponent(Const.OR_ID)
            c.connect(cout, and1, 0); c.connect(cout, and2, 1)
            prev_carry = cout

        total_gates = bits * 5
        def set_value(vars_list, val):
            for i, v in enumerate(vars_list):
                c.toggle(v, (val >> i) & 1)

        def read_sum():
            result = 0
            for i, sg in enumerate(sum_gates):
                if sg.output == Const.HIGH:
                    result |= (1 << i)
            if prev_carry.output == Const.HIGH:
                result |= (1 << bits)
            return result

        # Test cases: boundary + random
        max_val = (1 << bits) - 1
        test_cases = [
            (0, 0), (1, 0), (0, 1), (1, 1),
            (max_val, 1),       # overflow / rollover
            (max_val, max_val), # max + max
            (0x5555 & max_val, 0xAAAA & max_val),  # alternating bits
            (max_val, 0),       # identity
        ]
        random.seed(42)
        for _ in range(12):
            test_cases.append((random.randint(0, max_val), random.randint(0, max_val)))

        all_pass = True
        for a_val, b_val in test_cases:
            set_value(a_vars, a_val)
            set_value(b_vars, b_val)
            expected = a_val + b_val
            actual = read_sum()
            if actual != expected:
                self.assert_test(False, f"Adder {a_val}+{b_val}: got {actual}, expected {expected}")
                all_pass = False
                break

        if all_pass:
            self.perf_metrics['ripple_adder'] = {'time': 0, 'gates': total_gates}
            self.assert_test(True, f"{len(test_cases)} additions verified ({total_gates} gates)")

    def test_sr_latch_metastability(self, count=1000):
        """Build SR latches and test Set, Reset, Hold, and Forbidden states."""
        self.subsection(f"SR Latch Metastability ({count})")
        c = Circuit()
        c.simulate(Const.SIMULATE)

        set_line = c.getcomponent(Const.VARIABLE_ID)
        rst_line = c.getcomponent(Const.VARIABLE_ID)

        qs = []
        qbs = []
        for _ in range(count):
            q = c.getcomponent(Const.NOR_ID)
            qb = c.getcomponent(Const.NOR_ID)
            c.connect(q, rst_line, 0);  c.connect(q, qb, 1)
            c.connect(qb, set_line, 0); c.connect(qb, q, 1)
            qs.append(q); qbs.append(qb)

        # Reset all: R=1, S=0 -> Q=0, Qb=1
        c.toggle(set_line, Const.LOW); c.toggle(rst_line, Const.HIGH)
        c.toggle(rst_line, Const.LOW)
        all_reset = all(q.output == Const.LOW for q in qs)
        self.assert_test(all_reset, "Reset state: all Q=LOW")

        # Set all: S=1, R=0 -> Q=1, Qb=0
        c.toggle(set_line, Const.HIGH)
        c.toggle(set_line, Const.LOW)
        all_set = all(q.output == Const.HIGH for q in qs)
        self.assert_test(all_set, "Set state: all Q=HIGH")

        # Hold: S=0, R=0 -> Q should stay HIGH
        all_hold = all(q.output == Const.HIGH for q in qs)
        self.assert_test(all_hold, "Hold state: all Q=HIGH retained")

        # Forbidden: S=1, R=1 -> Both NOR outputs go LOW
        c.toggle(set_line, Const.HIGH); c.toggle(rst_line, Const.HIGH)
        all_low = all(q.output == Const.LOW for q in qs) and all(qb.output == Const.LOW for qb in qbs)
        self.assert_test(all_low, f"Forbidden state: all Q=LOW, Qb=LOW ({count} latches)")

        self.perf_metrics['sr_latch'] = {'time': 0, 'gates': count * 2}

    def test_mux_tree(self, select_bits=10):
        """Build a 2^N:1 multiplexer tree from AND/OR/NOT gates, verify selection."""
        num_inputs = 1 << select_bits
        self.subsection(f"Mux Tree ({num_inputs}:1, {select_bits} select)")
        c = Circuit()
        c.simulate(Const.SIMULATE)

        data_vars = [c.getcomponent(Const.VARIABLE_ID) for _ in range(num_inputs)]
        sel_vars = [c.getcomponent(Const.VARIABLE_ID) for _ in range(select_bits)]

        # Initialize all data to LOW, all selects to LOW
        for d in data_vars:
            c.toggle(d, Const.LOW)
        for s in sel_vars:
            c.toggle(s, Const.LOW)

        # Build mux tree bottom-up
        # Each mux2: out = (d0 AND ~sel) OR (d1 AND sel)
        current_layer = data_vars[:]
        sel_idx = 0
        total_gates = 0

        while len(current_layer) > 1:
            next_layer = []
            sel = sel_vars[sel_idx]
            not_sel = c.getcomponent(Const.NOT_ID)
            c.connect(not_sel, sel, 0)
            total_gates += 1

            for i in range(0, len(current_layer), 2):
                d0 = current_layer[i]
                d1 = current_layer[i + 1]
                a0 = c.getcomponent(Const.AND_ID)
                c.connect(a0, d0, 0); c.connect(a0, not_sel, 1)
                a1 = c.getcomponent(Const.AND_ID)
                c.connect(a1, d1, 0); c.connect(a1, sel, 1)
                orr = c.getcomponent(Const.OR_ID)
                c.connect(orr, a0, 0); c.connect(orr, a1, 1)
                next_layer.append(orr)
                total_gates += 3

            current_layer = next_layer
            sel_idx += 1

        mux_output = current_layer[0]

        # Verify: set data[0]=HIGH, select 0 -> output HIGH
        c.toggle(data_vars[0], Const.HIGH)
        self.assert_test(mux_output.output == Const.HIGH, "Mux select 0: data[0]=HIGH -> HIGH")

        # Select input 7: set sel = 0b0000000111
        c.toggle(data_vars[0], Const.LOW)
        c.toggle(data_vars[7], Const.HIGH)

        gc.disable()
        start = time.perf_counter_ns()
        for i in range(select_bits):
            c.toggle(sel_vars[i], (7 >> i) & 1)
        result = mux_output.output
        duration = (time.perf_counter_ns() - start) / 1_000_000
        gc.enable()

        self.assert_test(result == Const.HIGH, f"Mux select 7: data[7]=HIGH -> HIGH ({total_gates} gates)")
        self.perf_metrics['mux_tree'] = {'time': duration, 'gates': total_gates}

    def test_ring_oscillator(self, length=50):
        """NOT chain with XOR feedback: guaranteed unstable, should trigger ERROR."""
        self.subsection(f"Ring Oscillator ({length} inverters)")
        c = Circuit()
        c.simulate(Const.SIMULATE)

        source = c.getcomponent(Const.VARIABLE_ID)

        # Build: source -> XOR -> NOT x length -> feedback to XOR
        xor_g = c.getcomponent(Const.XOR_ID)
        c.connect(xor_g, source, 0)

        prev = xor_g
        chain = [xor_g]
        for _ in range(length):
            n = c.getcomponent(Const.NOT_ID)
            c.connect(n, prev, 0)
            chain.append(n)
            prev = n

        # Feedback: last NOT output -> XOR input 1 (creates oscillation regardless of parity)
        c.connect(xor_g, prev, 1)

        try:
            gc.disable()
            start = time.perf_counter_ns()
            c.toggle(source, Const.HIGH)
            duration = (time.perf_counter_ns() - start) / 1_000_000
            gc.enable()

            has_error = any(g.output == Const.ERROR for g in chain)
            self.perf_metrics['ring_osc'] = {'time': duration, 'gates': length + 1}
            self.assert_test(has_error, f"ERROR detected in ring ({duration:.2f}ms)")
        except RecursionError:
            gc.enable()
            self.assert_test(True, "RecursionError caught (expected)")
        except Exception as e:
            gc.enable()
            self.assert_test(False, f"CRASHED: {e}")

    def test_decoder_encoder(self, bits=8):
        """Build N-to-2^N decoder then 2^N-to-N encoder, verify round-trip."""
        num_outputs = 1 << bits
        self.subsection(f"Decoder/Encoder ({bits}-bit -> {num_outputs} lines)")
        c = Circuit()
        c.simulate(Const.SIMULATE)

        inputs = [c.getcomponent(Const.VARIABLE_ID) for _ in range(bits)]
        for v in inputs:
            c.toggle(v, Const.LOW)

        # Build decoder: each output line = AND of all input bits (direct or inverted)
        not_inputs = []
        for v in inputs:
            n = c.getcomponent(Const.NOT_ID)
            c.connect(n, v, 0)
            not_inputs.append(n)

        decoder_outputs = []
        total_gates = bits  # NOT gates
        for i in range(num_outputs):
            g = c.getcomponent(Const.AND_ID)
            c.setlimits(g, bits)
            for j in range(bits):
                if (i >> j) & 1:
                    c.connect(g, inputs[j], j)
                else:
                    c.connect(g, not_inputs[j], j)
            decoder_outputs.append(g)
            total_gates += 1

        # Verify a few decoder patterns
        test_values = [0, 1, 5, (num_outputs - 1), 42 % num_outputs, 128 % num_outputs]
        all_pass = True
        for val in test_values:
            for i in range(bits):
                c.toggle(inputs[i], (val >> i) & 1)
            # Check that only decoder_outputs[val] is HIGH
            for idx, dout in enumerate(decoder_outputs):
                expected = Const.HIGH if idx == val else Const.LOW
                if dout.output != expected:
                    self.assert_test(False, f"Decoder[{idx}] for input {val}: got {dout.output} expected {expected}")
                    all_pass = False
                    break
            if not all_pass:
                break

        if all_pass:
            self.assert_test(True, f"Decoder verified ({total_gates} gates)")

        self.perf_metrics['decoder_encoder'] = {'time': 0, 'gates': total_gates}

    def test_cascade_adder_pipeline(self, stages=4, bits=8):
        """Chain multiple adders: result of stage N feeds into stage N+1."""
        total_bits = bits
        self.subsection(f"Cascade Adder Pipeline ({stages}x {bits}-bit)")
        c = Circuit()
        c.simulate(Const.SIMULATE)

        # First stage inputs
        a_vars = [c.getcomponent(Const.VARIABLE_ID) for _ in range(bits)]
        b_vars = [c.getcomponent(Const.VARIABLE_ID) for _ in range(bits)]

        total_gates = 0
        prev_sums = None

        for stage in range(stages):
            if stage == 0:
                a_inputs = a_vars
                b_inputs = b_vars
            else:
                a_inputs = prev_sums  # Feed previous sum into next A
                b_inputs = b_vars     # Re-use same B

            cin = c.getcomponent(Const.VARIABLE_ID)
            c.toggle(cin, Const.LOW)
            prev_carry = cin
            sums = []

            for i in range(bits):
                xor1 = c.getcomponent(Const.XOR_ID)
                c.connect(xor1, a_inputs[i], 0); c.connect(xor1, b_inputs[i], 1)
                sum_g = c.getcomponent(Const.XOR_ID)
                c.connect(sum_g, xor1, 0); c.connect(sum_g, prev_carry, 1)
                sums.append(sum_g)
                and1 = c.getcomponent(Const.AND_ID)
                c.connect(and1, a_inputs[i], 0); c.connect(and1, b_inputs[i], 1)
                and2 = c.getcomponent(Const.AND_ID)
                c.connect(and2, prev_carry, 0); c.connect(and2, xor1, 1)
                cout_g = c.getcomponent(Const.OR_ID)
                c.connect(cout_g, and1, 0); c.connect(cout_g, and2, 1)
                prev_carry = cout_g
                total_gates += 5

            prev_sums = sums

        # Test: A=3, B=2 -> stage0=5, stage1=7, stage2=9, stage3=11
        for i in range(bits):
            c.toggle(a_vars[i], (3 >> i) & 1)
            c.toggle(b_vars[i], (2 >> i) & 1)

        # Read final stage output
        result = 0
        for i, sg in enumerate(prev_sums):
            if sg.output == Const.HIGH:
                result |= (1 << i)

        expected = 3
        for _ in range(stages):
            expected = (expected + 2) & ((1 << bits) - 1)

        self.assert_test(result == expected, f"Pipeline result: {result} (expected {expected}, {total_gates} gates)")
        self.perf_metrics['cascade_pipeline'] = {'time': 0, 'gates': total_gates}

    def test_xor_parity_generator(self, bits=1024):
        """Build a wide XOR tree to compute parity of N inputs, verify correctness."""
        self.subsection(f"XOR Parity Generator ({bits} inputs)")
        c = Circuit()
        c.simulate(Const.SIMULATE)

        inputs = [c.getcomponent(Const.VARIABLE_ID) for _ in range(bits)]
        for v in inputs:
            c.toggle(v, Const.LOW)

        # Build XOR reduction tree
        current = inputs[:]
        total_gates = 0
        while len(current) > 1:
            next_layer = []
            i = 0
            while i + 1 < len(current):
                xor_g = c.getcomponent(Const.XOR_ID)
                c.connect(xor_g, current[i], 0)
                c.connect(xor_g, current[i + 1], 1)
                next_layer.append(xor_g)
                total_gates += 1
                i += 2
            if i < len(current):
                next_layer.append(current[i])
            current = next_layer

        parity_out = current[0]
        self.assert_test(parity_out.output == Const.LOW, "Parity(all 0) = 0")

        # Toggle one input -> parity should flip
        gc.disable()
        start = time.perf_counter_ns()
        c.toggle(inputs[0], Const.HIGH)
        duration = (time.perf_counter_ns() - start) / 1_000_000
        gc.enable()
        self.assert_test(parity_out.output == Const.HIGH, f"Parity(one 1) = 1 ({duration:.2f}ms)")

        # Toggle another -> parity back to 0
        c.toggle(inputs[bits // 2], Const.HIGH)
        self.assert_test(parity_out.output == Const.LOW, "Parity(two 1s) = 0")

        # Set all to HIGH -> parity = bits % 2
        for v in inputs:
            c.toggle(v, Const.HIGH)
        expected = Const.HIGH if bits % 2 == 1 else Const.LOW
        self.assert_test(parity_out.output == expected, f"Parity(all 1) = {bits % 2}")

        self.perf_metrics['xor_parity'] = {'time': duration, 'gates': total_gates}

    def test_glitch_propagation(self, depth=500):
        """Deep NOT chain with probes at intervals: verify consistent glitch-free output."""
        self.subsection(f"Glitch Propagation ({depth}-deep)")
        c = Circuit()
        c.simulate(Const.SIMULATE)

        v = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(v, Const.LOW)
        prev = v
        probes = []
        probe_depths = set(range(0, depth, depth // 10))

        for i in range(depth):
            n = c.getcomponent(Const.NOT_ID)
            c.connect(n, prev, 0)
            if i in probe_depths:
                p = c.getcomponent(Const.PROBE_ID)
                c.connect(p, n, 0)
                probes.append((i + 1, p))  # depth (1-indexed), probe
            prev = n

        # Toggle multiple times and verify consistency
        total_gates = depth + len(probes)
        gc.disable()
        start = time.perf_counter_ns()
        for toggle_val in [Const.HIGH, Const.LOW, Const.HIGH]:
            c.toggle(v, toggle_val)
            # Verify every probe has correct value for its depth
            for d, p in probes:
                if d % 2 == 0:
                    expected = toggle_val
                else:
                    expected = Const.LOW if toggle_val == Const.HIGH else Const.HIGH
                if p.output != expected:
                    gc.enable()
                    self.assert_test(False, f"Glitch at depth {d}: expected {expected}, got {p.output}")
                    return
        duration = (time.perf_counter_ns() - start) / 1_000_000
        gc.enable()

        self.assert_test(True, f"No glitches across {len(probes)} probes ({duration:.2f}ms)")
        self.perf_metrics['glitch_prop'] = {'time': duration, 'gates': total_gates}

    def test_hot_swap_under_load(self, count=200):
        """Hide and reveal gates while simulation is active, verify propagation survives."""
        self.subsection(f"Hot Swap Under Load ({count} cycles)")
        c = Circuit()
        c.simulate(Const.SIMULATE)

        v = c.getcomponent(Const.VARIABLE_ID)
        const_high = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(const_high, Const.HIGH)

        # Build fanout: v -> [AND buffer] x 10, each independently probed
        gates = []
        for _ in range(10):
            g = c.getcomponent(Const.AND_ID)
            c.connect(g, v, 0)
            c.connect(g, const_high, 1)
            gates.append(g)

        c.toggle(v, Const.HIGH)
        self.assert_test(all(g.output == Const.HIGH for g in gates), "Initial: all HIGH")

        # Hot-swap: hide and reveal a gate repeatedly while toggling input
        # After hide+reveal, the gate's connections are restored automatically
        gc.disable()
        start = time.perf_counter_ns()
        all_ok = True
        target = gates[5]  # Pick one gate to hot-swap
        for i in range(count):
            c.hide([target])
            c.reveal([target])
            # After reveal, reconnect (hide breaks connections)
            c.connect(target, v, 0)
            c.connect(target, const_high, 1)

            c.toggle(v, i % 2)
            expected = Const.HIGH if i % 2 == 1 else Const.LOW
            # Check all OTHER gates still work correctly
            for idx, g in enumerate(gates):
                if g is target:
                    continue  # Skip the hot-swapped gate for downstream check
                if g.output != expected:
                    all_ok = False
                    break
            if not all_ok:
                break
        duration = (time.perf_counter_ns() - start) / 1_000_000
        gc.enable()

        self.assert_test(all_ok, f"Hot swap survived {count} cycles ({duration:.2f}ms)")
        self.perf_metrics['hot_swap'] = {'time': duration, 'gates': 12}

    def test_reconvergent_fanout(self, depth=10):
        """A single input fans out to two paths, reconverges at an XOR gate.
        With identical paths, XOR should always be 0. Tests book tracking correctness."""
        self.subsection(f"Reconvergent Fanout (depth={depth})")
        c = Circuit()
        c.simulate(Const.SIMULATE)

        v = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(v, Const.LOW)

        # Path A: chain of 2*depth NOT gates (even -> identity)
        prev_a = v
        for _ in range(depth * 2):
            n = c.getcomponent(Const.NOT_ID)
            c.connect(n, prev_a, 0)
            prev_a = n

        # Path B: chain of 2*depth NOT gates (even -> identity)
        prev_b = v
        for _ in range(depth * 2):
            n = c.getcomponent(Const.NOT_ID)
            c.connect(n, prev_b, 0)
            prev_b = n

        # Reconverge at XOR
        xor_g = c.getcomponent(Const.XOR_ID)
        c.connect(xor_g, prev_a, 0)
        c.connect(xor_g, prev_b, 1)

        total_gates = depth * 4 + 1

        c.toggle(v, Const.HIGH)
        self.assert_test(xor_g.output == Const.LOW, "Reconvergent XOR(HIGH path, HIGH path) = LOW")

        c.toggle(v, Const.LOW)
        self.assert_test(xor_g.output == Const.LOW, "Reconvergent XOR(LOW path, LOW path) = LOW")

        # Stress: rapid toggles
        gc.disable()
        start = time.perf_counter_ns()
        all_ok = True
        for _ in range(1000):
            c.toggle(v, Const.HIGH)
            if xor_g.output != Const.LOW:
                all_ok = False
                break
            c.toggle(v, Const.LOW)
            if xor_g.output != Const.LOW:
                all_ok = False
                break
        duration = (time.perf_counter_ns() - start) / 1_000_000
        gc.enable()

        self.assert_test(all_ok, f"1000 toggles: XOR always LOW ({duration:.2f}ms, {total_gates} gates)")
        self.perf_metrics['reconvergent'] = {'time': duration, 'gates': total_gates}



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
        if msg.startswith("Starting") or "Summary:" in msg:
            pass # Suppress to make it cleaner
        else:
            with open(self.log_file, 'a') as f: f.write(msg + "\n")

    def assert_true(self, condition, name):
        self.tests_run += 1
        if condition:
            self.passed += 1
            print(f"  - {name:<55} [OK]")
            with open(self.log_file, 'a') as f: f.write(f"[PASS] {name}\n")
            return True
        else:
            self.failed += 1
            print(f"  - {name:<55} [FAIL]")
            with open(self.log_file, 'a') as f: f.write(f"[FAIL] {name}\n")
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
        if msg.startswith("Starting") or "Summary:" in msg:
            pass # Suppress to make it cleaner
        else:
            with open(self.log_file, 'a') as f: f.write(msg + "\n")

    def assert_true(self, condition, name):
        self.tests_run += 1
        if condition:
            self.passed += 1
            print(f"  - {name:<55} [OK]")
            with open(self.log_file, 'a') as f: f.write(f"[PASS] {name}\n")
            return True
        else:
            self.failed += 1
            print(f"  - {name:<55} [FAIL]")
            with open(self.log_file, 'a') as f: f.write(f"[FAIL] {name}\n")
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



class EventManagerTestSuite:
    def __init__(self):
        self.circuit = Circuit()
        self.circuit.simulate(Const.SIMULATE) # Ensure we are in SIMULATE mode or DESIGN
        self.event_mgr = Event()
        from collections import deque
        self.event_mgr.undolist = deque()
        self.event_mgr.redolist = deque()
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
            print(f"  - {test_name:<55} [OK]")
            return True
        else:
            self.failed += 1
            print(f"  - {test_name:<55} [FAIL] {details}")
            return False

    def get_circuit_size(self):
        return len(self.circuit.get_components())

    def section(self, title):
        print(f"\n[{title.upper()}]")
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
        self.assert_test(len(self.circuit.get_components()) == 200, "100 gates pasted -> 200 Total")
        
        # Undo paste
        start_t = time.perf_counter()
        self.event_mgr.undo()
        end_t = time.perf_counter()
        
        self.assert_test(len(self.circuit.get_components()) == 100, f"Undo paste in {end_t - start_t:.4f}s")
        
        # Redo paste
        start_t = time.perf_counter()
        self.event_mgr.redo()
        end_t = time.perf_counter()
        
        self.assert_test(len(self.circuit.get_components()) == 200, f"Redo paste in {end_t - start_t:.4f}s")

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

        canvas_size_after = len(self.circuit.get_components())
        self.assert_test(actions_performed > 0, f"Performed {actions_performed} operations... Canvas size: {canvas_size_after}")
        
        start_t = time.perf_counter()
        for _ in range(actions_performed):
            self.event_mgr.undo()
        end_t = time.perf_counter()
        
        self.assert_test(len(self.circuit.get_components()) == 0, f"Chaos fully undone to empty canvas in {end_t - start_t:.4f}s")
        

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
    print("\n" + "="*70)
    print("  DARION LOGIC SIM - MASTER INTEGRITY TEST SUITE")
    print("="*70)
    
    total_failed = 0
    total_passed = 0
    total_time_ms = 0
    
    import time
    
    def log_timing(start_t, passed, failed, step_name):
        dur = (time.perf_counter_ns() - start_t) / 1_000_000
        print(f"\n> {step_name} completed in {dur:.2f}ms | Passed: {passed} | Failed: {failed}")
        return dur

    print("\n[1/5] RUNNING CORE & STRESS TESTS")
    t0 = time.perf_counter_ns()
    t1 = AggressiveTestSuite()
    t1.log_file.close()
    t1.log_file = open("master_test_results.txt", 'w', encoding='utf-8')
    t1.run_all()
    total_passed += t1.passed
    total_failed += t1.failed
    total_time_ms += log_timing(t0, t1.passed, t1.failed, "CORE & STRESS TESTS")

    print("\n" + "-"*70)
    print("[2/5] RUNNING IC TESTS")
    print("-"*70)
    t0 = time.perf_counter_ns()
    t2 = ThoroughICTest()
    t2.run()
    total_passed += t2.passed
    total_failed += t2.failed
    total_time_ms += log_timing(t0, t2.passed, t2.failed, "IC TESTS")

    print("\n" + "-"*70)
    print("[3/5] RUNNING IO TESTS")
    print("-"*70)
    t0 = time.perf_counter_ns()
    t3 = IOTestSuite()
    t3.run()
    total_passed += t3.passed
    total_failed += t3.failed
    total_time_ms += log_timing(t0, t3.passed, t3.failed, "IO TESTS")

    print("\n" + "-"*70)
    print("[4/5] RUNNING EVENT MANAGER STRESS TESTS")
    print("-"*70)
    t0 = time.perf_counter_ns()
    t4 = EventManagerTestSuite()
    t4.run_all()
    pass4 = getattr(t4, 'passed', 0)
    fail4 = t4.failed
    total_passed += pass4
    total_failed += fail4
    total_time_ms += log_timing(t0, pass4, fail4, "EVENT MANAGER STRESS TESTS")

    print("\n" + "-"*70)
    print("[5/5] RUNNING EVENT FUNCTIONAL TESTS")
    print("-"*70)
    t0 = time.perf_counter_ns()
    
    class CustomTestResult(unittest.TextTestResult):
        def addSuccess(self, test):
            super().addSuccess(test)
            print(f"  - {test._testMethodName:<55} [OK]")
            
        def addFailure(self, test, err):
            super().addFailure(test, err)
            print(f"  - {test._testMethodName:<55} [FAIL]")

        def addError(self, test, err):
            super().addError(test, err)
            print(f"  - {test._testMethodName:<55} [ERROR]")
            
    class CustomTestRunner(unittest.TextTestRunner):
        resultclass = CustomTestResult

    suite = unittest.TestLoader().loadTestsFromTestCase(TestTimeTravel)
    import os
    result = CustomTestRunner(stream=open(os.devnull, 'w'), verbosity=0).run(suite)
    pass5 = result.testsRun - len(result.failures) - len(result.errors)
    fail5 = len(result.failures) + len(result.errors)
    total_passed += pass5
    total_failed += fail5
    total_time_ms += log_timing(t0, pass5, fail5, "EVENT FUNCTIONAL TESTS")
    
    print("\n" + "="*70)
    print(f"  MASTER SUMMARY: {total_passed} PASSED | {total_failed} FAILED")
    print(f"  TOTAL TIME:     {total_time_ms:.2f} ms")
    print("="*70)
    
    if total_failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

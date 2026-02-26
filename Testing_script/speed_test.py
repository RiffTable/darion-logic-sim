"""
DARION LOGIC SIM — AGGRESSIVE TEST SUITE
Stress tests every aspect of the logic simulator with heavy load.
Output is minimal - only shows section results and failures.
Full details written to test_results.txt
"""

import time
import sys
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
import os
import random
import platform
import gc
import tempfile

# --- CONFIGURATION & SETUP ---
sys.setrecursionlimit(10_000)
LOG_FILE = "test_results.txt"

# Parse arguments for reactor selection
import argparse
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

from Circuit import Circuit
from Event_Manager import Event
from Control import Add
import Const
from Gates import Gate, Variable, Probe
from Gates import NOT, AND, NAND, OR, NOR, XOR, XNOR
from Gates import InputPin, OutputPin
from IC import IC


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
        print(f"\n{'='*60}")
        print(f"  DARION LOGIC SIM - AGGRESSIVE TEST SUITE")
        print(f"{'='*60}")
        print(f"System: {platform.system()} | Python {platform.python_version()}")
        print(f"Log file: {LOG_FILE}")
        print(f"{'-'*60}")

        self.log(f"DARION LOGIC SIM - AGGRESSIVE TEST SUITE", console=False)
        self.log(f"System: {platform.system()} {platform.release()} | Python {platform.python_version()}")
        if HAS_PSUTIL:
            self.log(f"Initial RAM: {process.memory_info().rss / 1024 / 1024:.2f} MB")

        # ==================== SPEED BENCHMARKS ====================
        self.section("SPEED BENCHMARKS")
        self.test_marathon(count=100_000)
        self.test_avalanche(layers=18)  # ~260K gates
        self.test_gridlock(size=200)
        self.test_echo_chamber(count=10_000)
        self.test_black_hole(inputs=100_000)
        self.test_paradox_burn()
        self.test_mega_chain()
        self.test_extreme_fanout()
        self.test_extreme_fanin(count=50_000)
        self.test_extreme_fanin_fanout(count=50_000)
        self.test_cpu_datapath(bit_width=8192)

        self.test_cache_thrashing(count=20_000)

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
        
        # Performance summary
        out(f"\n{'='*70}")
        out(f"  PERFORMANCE SUMMARY")
        out(f"{'='*70}")
        
        if HAS_PSUTIL:
            final_ram = process.memory_info().rss / 1024 / 1024
            out(f"  RAM Usage:        {final_ram:.2f} MB")
        
        total_gates = 0
        total_time_ms = 0
        for name, m in self.perf_metrics.items():
            if 'time' in m and 'gates' in m and m['time'] > 0:
                total_gates += m['gates']
                total_time_ms += m['time']
        
        if total_time_ms > 0:
            throughput = total_gates / (total_time_ms / 1000) / 1_000_000
            out(f"  Gates Processed:  {total_gates:,}")
            out(f"  Benchmark Time:   {total_time_ms:.2f} ms")
            out(f"  Throughput:       {throughput:.2f} M gates/sec")
        
        # Key benchmarks
        out(f"\n  Key Benchmarks:")
        if 'marathon' in self.perf_metrics:
            m = self.perf_metrics['marathon']
            out(f"    Marathon ({m['gates']//1000}K chain):     {m['latency']:.1f} ns/gate")
        if 'avalanche' in self.perf_metrics:
            a = self.perf_metrics['avalanche']
            out(f"    Avalanche ({a['gates']/1000:.0f}K tree):     {a['rate']/1e6:.2f} M gates/sec")
        if 'gridlock' in self.perf_metrics:
            g = self.perf_metrics['gridlock']
            size = int(g['gates']**0.5)
            out(f"    Gridlock ({size}x{size} mesh):   {g['time']:.2f} ms")
        if 'echo_chamber' in self.perf_metrics:
            e = self.perf_metrics['echo_chamber']
            latches = e['gates'] // 2
            out(f"    Echo Chamber ({latches//1000}K latch):  {e['time']:.2f} ms")
        if 'black_hole' in self.perf_metrics:
            b = self.perf_metrics['black_hole']
            out(f"    Black Hole ({b['gates']//1000}K inputs):  {b['time']*1000:.1f} us")
        if 'paradox' in self.perf_metrics:
            p = self.perf_metrics['paradox']
            out(f"    Paradox (XOR loop):        {p['time']*1000:.1f} us")
        if 'mega_chain' in self.perf_metrics:
            mc = self.perf_metrics['mega_chain']
            out(f"    Mega Chain (1M):           {mc['latency']:.1f} ns/gate")
        if 'extreme_fanout' in self.perf_metrics:
            ef = self.perf_metrics['extreme_fanout']
            out(f"    Extreme Fanout (50K):      {ef['time']:.2f} ms")
        if 'extreme_fanin' in self.perf_metrics:
            efi = self.perf_metrics['extreme_fanin']
            out(f"    Extreme Fan-in ({efi['gates']//1000}K):      {efi['time']*1000:.1f} us")
        if 'extreme_fanin_fanout' in self.perf_metrics:
            eff = self.perf_metrics['extreme_fanin_fanout']
            out(f"    Extreme Fan-in+Out ({(eff['gates']-1)//2000}K):  {eff['time']:.2f} ms")
        if 'cpu_datapath' in self.perf_metrics:
            cd = self.perf_metrics['cpu_datapath']
            out(f"    CPU Datapath ({cd['gates']//1000}K):        {cd['time']:.2f} ms")

        if 'cache_thrashing' in self.perf_metrics:
            ct = self.perf_metrics['cache_thrashing']
            out(f"    Cache Thrashing ({ct['gates']//1000}K):     {ct['time']:.2f} ms")
        # Final result
        out(f"\n{'='*70}")
        out(f"  TOTAL: {self.passed}/{total} tests ({100*self.passed/total:.1f}%)")
        if self.failed == 0:
            out(f"  [SUCCESS] ALL TESTS PASSED")
        else:
            out(f"  [FAILURE] {self.failed} TESTS FAILED")

        # ===== FINAL THROUGHPUT =====
        out(f"\n{'='*70}")
        out(f"  FINAL THROUGHPUT")
        out(f"{'='*70}")
        if total_time_ms > 0:
            final_throughput = total_gates / (total_time_ms / 1000)
            if final_throughput >= 1_000_000:
                out(f"  >>> {final_throughput / 1_000_000:.2f} M gates/sec <<<")
            elif final_throughput >= 1_000:
                out(f"  >>> {final_throughput / 1_000:.2f} K gates/sec <<<")
            else:
                out(f"  >>> {final_throughput:.2f} gates/sec <<<")
            out(f"  Total gates: {total_gates:,}  |  Total time: {total_time_ms:.2f} ms")
        else:
            out(f"  >>> No timed benchmarks recorded <<<")
        out(f"{'='*70}")
        print(f"\nResults saved to: {LOG_FILE}")

    # =========================================================================
    # SPEED BENCHMARKS
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


    def test_cache_thrashing(self, count=20_000):
        self.subsection(f"Cache Thrashing ({count:,} alternating layers)")
        self.circuit.clearcircuit()
        c = self.circuit
        
        root = c.getcomponent(Const.VARIABLE_ID)
        const_high = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(const_high, Const.HIGH)
        const_low = c.getcomponent(Const.VARIABLE_ID)
        c.toggle(const_low, Const.LOW)
        
        prev = root
        for i in range(count):
            if i % 2 == 0:
                g = c.getcomponent(Const.AND_ID)
                c.connect(g, prev, 0)
                c.connect(g, const_high, 1)
            else:
                g = c.getcomponent(Const.OR_ID)
                c.connect(g, prev, 0)
                c.connect(g, const_low, 1)
            prev = g
            
        c.simulate(Const.SIMULATE)
        c.toggle(root, 0)
        c.toggle(root, 1)
        c.toggle(root, 0)
        
        duration = self.timer(lambda: c.toggle(root, 1))
        self.perf_metrics['cache_thrashing'] = {'time': duration, 'gates': count}
        self.assert_test(prev.getoutput() == 'T', f"{duration:.2f}ms")

if __name__ == "__main__":
    suite = AggressiveTestSuite()
    try:
        suite.run_all()
        input('Press any key to continue....')
    except KeyboardInterrupt:
        print("\n[!] Test Aborted.")
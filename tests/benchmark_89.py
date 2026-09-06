"""
unified_iscas_benchmark_89.py  (v1 — 3-Engine Comparison: Python, Cython, Icarus)
===========================================================================================
Unified benchmark runner comparing three simulation engines on ISCAS89 sequential datasets:
  1. Pure Python Engine  (SIMULATE mode)
  2. Cython Reactor Propagate  (SIMULATE mode / BFS Wavefront)
  3. Cython Reactor Sweep      (COMPILE  mode / Topological Forward-Pass)
  4. Icarus Verilog     (iverilog + vvp + optional VPI inner-loop timer)

Sequential circuit methodology
-------------------------------
- DFF instances are loaded via DFF.json (an IC file defining CLK/D/Q pins).
- Each logical test vector is split into two physical vectors:
    setup   : data inputs randomised, clock = 0  (data settles into gates)
    trigger : same data inputs, clock = 1        (rising edge captures DFFs)
- 50 warmup cycles (inputs = 0, clock alternates) are driven BEFORE the timed
  window to flush DFF states from an unknown reset condition.
- Sweep mode uses asyncio.run() to drain the task_manager time_queue after
  each batch_toggle() — required for correct DFF feedback resolution.
- Speedup baseline: Icarus Verilog VPI sim time.
"""

import os
import re
import sys
import time
import datetime
import json
import random
import argparse
import gc
import subprocess
import shutil
import asyncio
import math
from pathlib import Path

_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

sys.path.insert(0, _SCRIPT_DIR)

def send_perf_ctrl(cmd):
    try:
        if os.path.exists("/tmp/rx_perf_ctrl"):
            flags = os.O_WRONLY
            if hasattr(os, 'O_NONBLOCK'):
                flags |= os.O_NONBLOCK
            fd = os.open("/tmp/rx_perf_ctrl", flags)
            os.write(fd, (cmd + "\n").encode())
            os.close(fd)
    except Exception:
        pass

try:
    from iscas89_sequential_harness import (
        run_icarus_harness_89,
        parse_verilog_ports_89,
        _find_clock_idx,
        _VPI_DIR,
        _VPI_TIMER_VPI,
    )
except ImportError:
    try:
        from tests.iscas89_sequential_harness import (
            run_icarus_harness_89,
            parse_verilog_ports_89,
            _find_clock_idx,
            _VPI_DIR,
            _VPI_TIMER_VPI,
        )
    except ImportError:
        run_icarus_harness_89  = None
        parse_verilog_ports_89 = None
        _find_clock_idx        = None
        _VPI_DIR               = ""
        _VPI_TIMER_VPI         = ""


# ===========================================================================
# 2. INTERNAL WORKER — SequentialVerilogRunner (Engine / Reactor)
# ===========================================================================

class SequentialVerilogRunner:
    """
    Parses an ISCAS89 sequential Verilog netlist and benchmarks it using
    either the Python Engine or the Cython Reactor.

    DFF instances are loaded via DFF.json as an IC (same pattern as the
    VerilogStateRunner used by the verifier).  The clock-paired vector
    generation ensures DFF capture semantics are correctly exercised.
    """

    def __init__(self, v_file_path, circuit_cls, const_mod, is_reactor=True, is_oop=False, mode="engine"):
        self.filepath = v_file_path
        self.mode = mode
        self.Circuit = circuit_cls
        self.const   = const_mod
        self.circuit = self.Circuit()
        self.circuit.simulate(self.const.DESIGN)
        self.is_reactor = is_reactor
        self.is_oop = is_oop

        self.nodes = {}
        self.outputs = []
        self.input_vars = []
        self.dff_connections = []
        self.dff_crct = None

        # Load DFF.json from common locations
        for p in [
            os.path.join(_SCRIPT_DIR, "DFF.json"),
            os.path.join(_PROJECT_ROOT, "DFF.json"),
            "DFF.json",
        ]:
            if os.path.exists(p):
                try:
                    self.dff_crct = self.circuit.get_ic(p)
                    break
                except Exception:
                    pass

        self.VERILOG_GATE_MAP = {
            'and':  self.const.AND_ID,
            'nand': self.const.NAND_ID,
            'or':   self.const.OR_ID,
            'nor':  self.const.NOR_ID,
            'xor':  self.const.XOR_ID,
            'xnor': self.const.XNOR_ID,
            'not':  self.const.NOT_ID,
            'buf':  self.const.BUFFER_ID,
        }

        self._parse_verilog(v_file_path)
        self.output_objects = [self.nodes[p] for p in self.outputs if p in self.nodes]

    def _parse_verilog(self, filepath):
        json_path = filepath.replace('.v', '.json')
        
        if os.path.exists(json_path) and hasattr(self.circuit, 'readfromjson'):
            self.circuit.readfromjson(json_path)
            _, inputs, outputs = parse_verilog_ports_89(filepath)
            var_list = self.circuit.get_variables() if hasattr(self.circuit, 'get_variables') else self.circuit.get_components()
            var_dict = {}
            for v in var_list:
                name_str = getattr(v, 'custom_name', None) or getattr(v, 'codename', None) or str(v)
                var_dict[name_str] = v
                
            for inp in inputs:
                port_name = inp.split()[-1]
                expected_name = f"IN_{port_name}"
                if expected_name in var_dict:
                    self.input_vars.append(var_dict[expected_name])
                else:
                    found = False
                    for k, v in var_dict.items():
                        if port_name in k:
                            self.input_vars.append(v)
                            found = True
                            break
                    if not found:
                        print(f"Warning: Could not map pin {port_name} from JSON.")
            
            for outp in outputs:
                port_name = outp.split()[-1]
                self.outputs.append(port_name)

            for gate in self.circuit.get_components() if hasattr(self.circuit, 'get_components') else self.circuit.components:
                name_str = getattr(gate, 'custom_name', None) or getattr(gate, 'codename', None) or str(gate)
                if name_str.startswith("G_"):
                    self.nodes[name_str[2:]] = gate
                elif name_str.startswith("IN_"):
                    self.nodes[name_str[3:]] = gate
                elif name_str == "CONST_1":
                    self.nodes["1'b1"] = gate
                elif name_str == "CONST_0":
                    self.nodes["1'b0"] = gate
                else:
                    self.nodes[name_str] = gate
            if not self.is_reactor:
                self.circuit.simulate(self.const.COMPILE)
            return

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'//.*', '', content)

        module_body = content
        for m in re.finditer(r'\bmodule\s+([a-zA-Z0-9_]+)(.*?)\bendmodule\b',
                              content, flags=re.DOTALL):
            if m.group(1).lower() != 'dff':
                module_body = m.group(0)
                break

        statements  = [s.strip() for s in module_body.split(';') if s.strip()]
        connections = []

        for stmt in statements:
            if stmt.startswith('input '):
                ports = stmt.replace('input', '').strip().split(',')
                for p in ports:
                    p = p.strip()
                    if p:
                        var_node = self.circuit.getcomponent(self.const.VARIABLE_ID)
                        var_node.rename(f"IN_{p}")
                        self.nodes[p] = var_node
                        self.input_vars.append(var_node)
            elif stmt.startswith('output '):
                ports = stmt.replace('output', '').strip().split(',')
                for p in ports:
                    p = p.strip()
                    if p:
                        out_node = self.circuit.getcomponent(self.const.IC_OUTPUT_PIN_ID)
                        out_node.rename(f"OUT_{p}")
                        self.nodes[p + "_OUTPIN"] = out_node
                        self.outputs.append(p)
                        connections.append((p + "_OUTPIN", [p]))
            elif stmt.startswith(('wire ', 'module ', 'endmodule', 'reg ')):
                continue
            else:
                match = re.match(
                    r'^([a-zA-Z_]\w*)\s+([a-zA-Z_0-9]+)?\s*\((.*)\)$',
                    stmt, flags=re.DOTALL)
                if not match:
                    continue

                gate_type = match.group(1).lower()
                ports_str = match.group(3)

                if gate_type.startswith('dff'):
                    if not self.dff_crct:
                        raise RuntimeError(
                            "DFF.json is required for ISCAS89 sequential circuits "
                            "but was not found.")

                    wires = {}
                    if '.' in ports_str:
                        for pm in re.finditer(
                                r'\.\s*([a-zA-Z0-9_]+)\s*\(\s*([a-zA-Z0-9_]+)\s*\)',
                                ports_str):
                            wires[pm.group(1).upper()] = pm.group(2)
                        d_wire   = wires.get('D')
                        clk_wire = wires.get('CK', wires.get('CLK', wires.get('C')))
                        q_wire   = wires.get('Q')
                    else:
                        pts = [p.strip() for p in ports_str.split(',')]
                        # Positional: (CK, Q, D)
                        clk_wire = pts[0] if len(pts) > 0 else None
                        q_wire   = pts[1] if len(pts) > 1 else None
                        d_wire   = pts[2] if len(pts) > 2 else None

                    dff_inst  = self.circuit.load_ic(self.dff_crct)
                    inst_name = match.group(2) or f"inst_{len(self.dff_connections)}"
                    if hasattr(dff_inst, 'rename'):
                        dff_inst.rename(f"DFF_{inst_name}")
                    else:
                        dff_inst.custom_name = f"DFF_{inst_name}"

                    if q_wire:
                        self.nodes[q_wire] = dff_inst.outputs[0]

                    self.dff_connections.append((dff_inst, d_wire, clk_wire))
                    continue

                if gate_type in self.VERILOG_GATE_MAP:
                    ports = [p.strip() for p in ports_str.split(',')]
                    out_wire = ports[0]
                    in_wires = ports[1:]
                    gate_id  = self.VERILOG_GATE_MAP[gate_type]
                    gate     = self.circuit.getcomponent(gate_id)
                    gate.rename(f"G_{out_wire}")
                    if gate_id < self.const.VARIABLE_ID and hasattr(self.circuit, 'setlimits'):
                        self.circuit.setlimits(gate, len(in_wires))
                    self.nodes[out_wire] = gate
                    connections.append((out_wire, in_wires))

        # Wire combinational connections
        for target_id, source_ids in connections:
            target_gate = self.nodes.get(target_id)
            if not target_gate:
                continue
            for pin_index, source_id in enumerate(source_ids):
                source_gate = self.nodes.get(source_id)
                if source_gate:
                    self.circuit.connect(target_gate, source_gate, pin_index)

        # Wire DFF connections
        # DFF.json layout: inputs[0] = CLK, inputs[1] = D
        for dff_inst, d_wire, clk_wire in self.dff_connections:
            if clk_wire:
                clk_gate = self.nodes.get(clk_wire)
                if clk_gate and len(dff_inst.inputs) > 0:
                    self.circuit.connect(dff_inst.inputs[0], clk_gate, 0)
            if d_wire:
                d_gate = self.nodes.get(d_wire)
                if d_gate and len(dff_inst.inputs) > 1:
                    self.circuit.connect(dff_inst.inputs[1], d_gate, 0)

        self.circuit.simulate(self.const.SIMULATE)

    def _get_current_state(self) -> list:
        return [g.output for g in self.output_objects]

    async def _run_benchmark_async(self, vectors: int, warmup: int,
                                   use_optimize: bool, rx_prop: bool = True, rx_sweep: bool = True,
                                   use_perf: bool = False, perf_events: str = ""):
        """
        Async benchmark core — required because DFF feedback loops are resolved
        via the task_manager time_queue, which is an asyncio-based mechanism.
        We must await circuit.runner after each batch_toggle() to let DFF state
        propagate correctly before reading outputs.

        Returns: (propagate_result_dict, sweep_result_dict_or_None)
        """
        # ── Detect clock variable ──────────────────────────────────────────────
        clock_var = None
        for var in self.input_vars:
            name = getattr(var, 'custom_name', '') or getattr(var, 'codename', '')
            if isinstance(name, bytes):
                name = name.decode('utf-8', errors='ignore')
            if any(c in name.lower() for c in ('ck', 'clk', 'clock', 'g0')):
                clock_var = var
                break

        if use_optimize and hasattr(self.circuit, 'optimize'):
            self.circuit.optimize()

        # ── Build physical vector batches (clock-paired) ───────────────────────
        logical_count = max(vectors - warmup, 1)
        logical_warmup = warmup

        _rng = random.Random(42)

        def _make_batches(n_logical):
            batches = []
            for _ in range(n_logical):
                base = []
                for var in self.input_vars:
                    val = self.const.HIGH if _rng.randint(0, 1) else self.const.LOW
                    if self.is_oop:
                        base.append((var, val))
                    else:
                        base.append((var.location, val))

                if clock_var is not None:
                    # setup: clock = LOW
                    setup = [(item, self.const.LOW if (item == clock_var if self.is_oop else item == clock_var.location) else val)
                             for item, val in base]
                    # trigger: clock = HIGH
                    trigger = [(item, self.const.HIGH if (item == clock_var if self.is_oop else item == clock_var.location) else val)
                               for item, val in base]
                    batches.append(setup)
                    batches.append(trigger)
                else:
                    batches.append(base)
            return batches

        warmup_batches   = _make_batches(logical_warmup)
        measured_batches = _make_batches(logical_count)

        # ──────────────────────────────────────────────────────────────────────
        # PASS 1: propagate (SIMULATE / BFS wavefront)
        # ──────────────────────────────────────────────────────────────────────
        if rx_prop:
            self.circuit.simulate(self.const.SIMULATE)
            self.const.set_MODE(self.const.SIMULATE)
    
            flat_warmup_batches = [item for sublist in warmup_batches for item in sublist]
            flat_measured_batches = [item for sublist in measured_batches for item in sublist]
            batch_size = len(self.input_vars)
    
            # Warmup (untimed)
            if flat_warmup_batches:
                self.circuit.batch_toggle(flat_warmup_batches, batch_size)
    
            gc.collect()
            self.circuit.eval_count = 0
            gc.disable()
    
            perf_proc = None
            if use_perf:
                fifo_path = "/tmp/rx_perf_ctrl"
                if not os.path.exists(fifo_path):
                    try: os.mkfifo(fifo_path)
                    except Exception: pass
                perf_data = f"perf_{self.mode}_prop_{os.path.basename(self.filepath)}.data"
                perf_txt = f"perf_{self.mode}_prop_{os.path.basename(self.filepath)}.txt"
                cmd = ["perf", "record", "-D", "-1", "--control=fifo:/tmp/rx_perf_ctrl", "-p", str(os.getpid()), "-o", perf_data]
                if perf_events:
                    cmd.extend(["-e", perf_events])
                perf_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                await asyncio.sleep(0.5)

            send_perf_ctrl("enable")
            propagate_ms = self.circuit.batch_toggle(flat_measured_batches, batch_size) if flat_measured_batches else 0.0
            send_perf_ctrl("disable")
            
            if use_perf and perf_proc:
                perf_proc.terminate()
                perf_proc.wait()
                with open(perf_txt, "w") as f:
                    subprocess.run(["perf", "report", "-i", perf_data], stdout=f, stderr=subprocess.DEVNULL)
                if os.path.exists(perf_data):
                    os.remove(perf_data)
    
            gc.enable()
            propagate_evals = getattr(self.circuit, 'eval_count',
                                      len(measured_batches) * len(self.nodes))
            propagate_meps  = (
                (propagate_evals / (propagate_ms / 1000.0)) / 1_000_000.0
                if propagate_ms > 0 else 0.0
            )
    
            result = {
                "nodes":            len(self.nodes),
                "time_ms":          propagate_ms,
                "propagate_ms":     propagate_ms,
                "measured_vectors": len(measured_batches),
                "total_evals":      propagate_evals,
                "meps":             propagate_meps,
            }
        else:
            flat_warmup_batches = [item for sublist in warmup_batches for item in sublist]
            flat_measured_batches = [item for sublist in measured_batches for item in sublist]
            batch_size = len(self.input_vars)
            result = {
                "nodes":            len(self.nodes),
                "time_ms":          0.0,
                "propagate_ms":     0.0,
                "measured_vectors": len(measured_batches),
                "total_evals":      0,
                "meps":             0.0,
            }

        # ──────────────────────────────────────────────────────────────────────
        # PASS 2: sweep (COMPILE mode / linear forward-pass)
        # ──────────────────────────────────────────────────────────────────────
        has_sweep = (
            self.is_reactor
            and hasattr(self.const, 'COMPILE')
            and hasattr(self.const, 'set_MODE')
            and hasattr(self.circuit, 'simulate')
        )
        if has_sweep and rx_sweep:
            try:
                self.circuit.simulate(self.const.COMPILE)
                self.const.set_MODE(self.const.COMPILE)

                # Warmup (untimed, sweep mode)
                if flat_warmup_batches:
                    self.circuit.batch_toggle(flat_warmup_batches, batch_size)

                gc.collect()
                self.circuit.eval_count = 0
                gc.disable()
                
                perf_proc = None
                if use_perf:
                    fifo_path = "/tmp/rx_perf_ctrl"
                    if not os.path.exists(fifo_path):
                        try: os.mkfifo(fifo_path)
                        except Exception: pass
                    perf_data = f"perf_{self.mode}_sweep_{os.path.basename(self.filepath)}.data"
                    perf_txt = f"perf_{self.mode}_sweep_{os.path.basename(self.filepath)}.txt"
                    cmd = ["perf", "record", "-D", "-1", "--control=fifo:/tmp/rx_perf_ctrl", "-p", str(os.getpid()), "-o", perf_data]
                    if perf_events:
                        cmd.extend(["-e", perf_events])
                    perf_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    await asyncio.sleep(0.5)

                send_perf_ctrl("enable")
                sweep_ms = self.circuit.batch_toggle(flat_measured_batches, batch_size) if flat_measured_batches else 0.0
                send_perf_ctrl("disable")

                if use_perf and perf_proc:
                    perf_proc.terminate()
                    perf_proc.wait()
                    with open(perf_txt, "w") as f:
                        subprocess.run(["perf", "report", "-i", perf_data], stdout=f, stderr=subprocess.DEVNULL)
                    if os.path.exists(perf_data):
                        os.remove(perf_data)

                gc.enable()

                self.const.set_MODE(self.const.SIMULATE)
                sweep_evals = getattr(self.circuit, 'eval_count',
                                      len(measured_batches) * len(self.nodes))
                sweep_meps  = (
                    (sweep_evals / (sweep_ms / 1000.0)) / 1_000_000.0
                    if sweep_ms > 0 else 0.0
                )
                result["sweep_ms"]    = sweep_ms
                result["sweep_evals"] = sweep_evals
                result["sweep_meps"]  = sweep_meps
            except Exception as exc:
                self.const.set_MODE(self.const.SIMULATE)
                result["sweep_error"] = str(exc)

        return result

    def run_benchmark(self, vectors: int = 10000, warmup: int = 5000,
                      use_optimize: bool = True, rx_prop: bool = True, rx_sweep: bool = True,
                      use_perf: bool = False, perf_events: str = "") -> dict:
        """Synchronous wrapper — instantiates the asyncio loop for DFF drain."""
        return asyncio.run(
            self._run_benchmark_async(vectors, warmup, use_optimize, rx_prop, rx_sweep, use_perf, perf_events)
        )


# ===========================================================================
# 3. ISOLATED SUBPROCESS RUNNER (Engine / Reactor)
# ===========================================================================

def run_python_backend_process_89(filepath: str, mode: str,
                                   vectors: int, warmup: int,
                                   optimize: bool, rx_prop: bool = True, rx_sweep: bool = True,
                                   use_perf: bool = False, perf_events: str = "") -> dict:
    """
    Run SequentialVerilogRunner in an isolated subprocess to prevent module
    state pollution between Engine and Reactor passes.
    """
    cmd = [
        sys.executable, os.path.abspath(__file__),
        "--internal-worker", filepath,
        "--mode", mode,
        "--vectors", str(vectors),
        "--warmup",  str(warmup),
    ]
    if optimize:
        cmd.append("--optimize")
    if not rx_prop:
        cmd.append("--no-rx-prop")
    if not rx_sweep:
        cmd.append("--no-rx-sweep")
    if use_perf:
        cmd.append("--perf")
        if perf_events:
            cmd.extend(["--perf-events", perf_events])

    try:
        t0 = time.perf_counter_ns()
        res = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        t1 = time.perf_counter_ns()
        total_ms = (t1 - t0) / 1_000_000.0

        if res.returncode == 0:
            for line in reversed(res.stdout.strip().split('\n')):
                if line.startswith('{'):
                    data = json.loads(line)
                    data["load_ms"] = data.get("parse_ms", 0.0)
                    return data
            return {"error": "No JSON found in worker stdout: " + res.stdout.strip()[:100]}
        else:
            return {"error": res.stderr.strip() or "Worker process failed"}
    except Exception as e:
        return {"error": str(e)}


def internal_worker_main(filepath: str, mode: str, vectors: int,
                          warmup: int, optimize: bool, rx_prop: bool = True, rx_sweep: bool = True,
                          use_perf: bool = False, perf_events: str = ""):
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    target_path  = os.path.join(script_dir, mode)
    if not os.path.exists(target_path):
        target_path = os.path.join(project_root, mode)

    sys.path.insert(0, project_root)
    sys.path.insert(0, target_path)
    import Circuit
    import Const

    is_reactor = (mode in ('reactor', 'reactor_oop'))
    is_oop = (mode == 'reactor_oop')
    try:
        t0 = time.perf_counter_ns()
        runner = SequentialVerilogRunner(
            filepath, Circuit.Circuit, Const, is_reactor=is_reactor, is_oop=is_oop, mode=mode
        )
        t1 = time.perf_counter_ns()
        stats = runner.run_benchmark(
            vectors=vectors, warmup=warmup, use_optimize=optimize, rx_prop=rx_prop, rx_sweep=rx_sweep,
            use_perf=use_perf, perf_events=perf_events
        )
        stats['parse_ms'] = (t1 - t0) / 1_000_000.0
        print(json.dumps(stats))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


# ===========================================================================
# 4. FILE DISCOVERY
# ===========================================================================

def get_v_files(target):
    if os.path.isfile(target) and target.endswith('.v'):
        return [target]
    v_files = []
    for root, _, files in os.walk(target):
        for f in files:
            if f.endswith('.v') and not f.endswith('_base_tb.v') and not f.endswith('_89bench_tb.v'):
                v_files.append(os.path.join(root, f))
    return sorted(v_files, key=os.path.getsize)


# ===========================================================================
# 5. REPORTING — Console, JSON, TXT
# ===========================================================================

def _print_speedup_report(all_results: list, md_lines: list = None):
    import math

    W = 150
    print()

    # ── Icarus fallback baseline ───────────────────────
    print("=" * W)
    print("  SPEEDUP vs ICARUS VERILOG BASELINE  (Icarus VPI sim time = 1x)")
    print("  Reactor modes: prop = BFS wavefront (SIMULATE)  |  sweep = linear fwd-pass (COMPILE)")
    print("=" * W)
    if md_lines is not None:
        md_lines.append("## Speedup vs Icarus Verilog Baseline")
        md_lines.append("*Icarus VPI sim time = 1x*")
        md_lines.append("*Reactor modes: prop = BFS wavefront (SIMULATE)  |  sweep = linear fwd-pass (COMPILE)*")
        md_lines.append("")

    hdr = (
        f"{'Circuit':<16} | "
        f"{'Icarus(ms)':<10} | "
        f"{'Engine(ms)':<10} | {'Eng-eval':<10} | {'Eng-spd':<8} | "
        f"{'Rx-prop(ms)':<11} | {'Rx-p-eval':<10} | {'Rx-prop-spd':<11} | "
        f"{'Rx-sweep(ms)':<12} | {'Rx-s-eval':<10} | {'Rx-swp-spd':<10} | "
        f"{'Rx-oop(ms)':<10} | {'Rx-o-eval':<10} | {'Rx-o-spd':<8}"
    )
    print(hdr)
    print("-" * W)
    if md_lines is not None:
        md_lines.append(f"| {hdr} |")
        md_lines.append(f"|{'-'*18}|{'-'*12}|{'-'*12}|{'-'*12}|{'-'*10}|{'-'*13}|{'-'*12}|{'-'*13}|{'-'*14}|{'-'*12}|{'-'*12}|{'-'*12}|{'-'*12}|{'-'*10}|")

    engine_speedups        = []
    reactor_prop_speedups  = []
    reactor_sweep_speedups = []
    reactor_oop_speedups   = []

    for filename, e_res, r_res, ro_res, i_res in all_results:
        if any('error' in res for res in (e_res, r_res, ro_res, i_res)):
            continue

        i_ms  = i_res['time_ms']
        e_ms  = e_res['time_ms']
        r_ms  = r_res['time_ms']
        rs_ms = r_res.get('sweep_ms', None)
        ro_ms = ro_res['time_ms']

        e_spd  = i_ms / e_ms  if e_ms  > 0 else float('inf')
        r_spd  = i_ms / r_ms  if r_ms  > 0 else float('inf')
        rs_spd = i_ms / rs_ms if rs_ms and rs_ms > 0 else None

        ro_spd = i_ms / ro_ms if ro_ms > 0 else float('inf')

        engine_speedups.append(e_spd)
        reactor_prop_speedups.append(r_spd)
        reactor_oop_speedups.append(ro_spd)
        if rs_spd is not None: reactor_sweep_speedups.append(rs_spd)

        rs_ms_str  = f"{rs_ms:.1f}"   if rs_ms  is not None else "N/A"
        rs_spd_str = f"{rs_spd:.1f}x" if rs_spd is not None else "N/A"

        e_ev_str   = f"{e_res.get('total_evals', 0):,}" if 'error' not in e_res else "N/A"
        r_ev_str   = f"{r_res.get('total_evals', 0):,}" if 'error' not in r_res else "N/A"
        rs_ev_str  = (f"{r_res['sweep_evals']:,}"       if 'sweep_evals' in r_res
                      else ("N/A" if 'sweep_error' in r_res else "N/A"))
        ro_ev_str  = f"{ro_res.get('total_evals', 0):,}" if 'error' not in ro_res else "N/A"

        row = (
            f"{filename:<16} | "
            f"{i_ms:>10.2f} | "
            f"{e_ms:>10.1f} | {e_ev_str:>10} | {e_spd:>7.1f}x | "
            f"{r_ms:>11.1f} | {r_ev_str:>10} | {r_spd:>10.1f}x | "
            f"{rs_ms_str:>12} | {rs_ev_str:>10} | {rs_spd_str:>10} | "
            f"{ro_ms:>10.1f} | {ro_ev_str:>10} | {ro_spd:>8.1f}x"
        )
        print(row)
        if md_lines is not None:
            md_lines.append(f"| {row} |")

    if engine_speedups:
        geo_mean = lambda xs: math.exp(sum(math.log(x) for x in xs) / len(xs))
        g_e  = geo_mean(engine_speedups)
        g_r  = geo_mean(reactor_prop_speedups)
        g_rs = geo_mean(reactor_sweep_speedups) if reactor_sweep_speedups else None
        g_ro = geo_mean(reactor_oop_speedups)
        print("-" * W)
        g_rs_str = f"{g_rs:.1f}x" if g_rs is not None else "N/A"
        summary = (
            f"{'Geo-mean speedup':<16} | {'(baseline)':<10} | "
            f"{'':<10} | {'':<10} | {g_e:>7.1f}x | "
            f"{'':<11} | {'':<10} | {g_r:>10.1f}x | "
            f"{'':<12} | {'':<10} | {g_rs_str:>10} | "
            f"{'':<10} | {'':<10} | {g_ro:>8.1f}x"
        )
        print(summary)
        print("=" * W)
        if md_lines is not None:
            md_summary = (
                f"| **Geo-mean speedup** | **(baseline)** | "
                f"{'':<10} | {'':<10} | {g_e:>7.1f}x | "
                f"{'':<11} | {'':<10} | {g_r:>10.1f}x | "
                f"{'':<12} | {'':<10} | {g_rs_str:>10} | "
                f"{'':<10} | {'':<10} | {g_ro:>8.1f}x |"
            )
            md_lines.append(md_summary)

    else:
        # ── Icarus fallback baseline ───────────────────────
        print("=" * W)
        print("  SPEEDUP vs ICARUS VERILOG BASELINE  (Icarus VPI sim time = 1x)")
        print("  Reactor modes: prop = BFS wavefront (SIMULATE)  |  sweep = linear fwd-pass (COMPILE)")
        print("=" * W)
        hdr = (
            f"{'Circuit':<16} | "
            f"{'Icarus-sim(ms)':<14} | {'Engine(ms)':<10} | {'Eng-spd':<8} | "
            f"{'Rx-prop(ms)':<11} | {'Rx-prop-spd':<11} | {'Rx-sweep(ms)':<12} | {'Rx-swp-spd':<10}"
        )
        print(hdr)
        print("-" * W)

        engine_speedups        = []
        reactor_prop_speedups  = []
        reactor_sweep_speedups = []




def _save_results_89(all_results: list, args):
    """Save JSON + human-readable TXT results."""
    import datetime
    import math
    import json

    base      = args.output
    json_path = base if base.endswith('.json') else base + '.json'
    txt_path  = (base[:-5] if base.endswith('.json') else base) + '.txt'

    measured = args.vectors - args.warmup
    ts       = datetime.datetime.now(datetime.timezone.utc).isoformat()

    circuits_data = []
    for filename, e_res, r_res, ro_res, i_res in all_results:
        circuits_data.append({
            "circuit": filename,
            "engine":  e_res,
            "reactor": r_res,
            "reactor_oop": ro_res,
            "icarus":  i_res,
        })

    speedup_summary = None
    geo_mean = lambda xs: math.exp(sum(math.log(x) for x in xs) / len(xs))
    valid_i = [
        (fn, e, r, ro, i) for fn, e, r, ro, i in all_results
        if 'error' not in i and i.get('time_ms', 0) > 0
    ]
    if valid_i:
        e_spds  = [i['time_ms'] / e['time_ms']  for _, e, _, _, i in valid_i
                    if 'error' not in e and e.get('time_ms', 0) > 0]
        r_spds  = [i['time_ms'] / r['time_ms']  for _, _, r, _, i in valid_i
                    if 'error' not in r and r.get('time_ms', 0) > 0]
        rs_spds = [i['time_ms'] / r.get('sweep_ms', 0)
                    for _, _, r, _, i in valid_i
                    if 'error' not in r and r.get('sweep_ms', 0) > 0]
        ro_spds = [i['time_ms'] / ro['time_ms']  for _, _, _, ro, i in valid_i
                    if 'error' not in ro and ro.get('time_ms', 0) > 0]

        speedup_summary = {
            "baseline":                           "Icarus Verilog VPI sim time",
            "valid_circuits":                     len(valid_i),
            "engine_geo_mean_speedup":            round(geo_mean(e_spds),  3) if e_spds  else None,
            "reactor_propagate_geo_mean_speedup": round(geo_mean(r_spds),  3) if r_spds  else None,
            "reactor_sweep_geo_mean_speedup":     round(geo_mean(rs_spds), 3) if rs_spds else None,
            "reactor_oop_geo_mean_speedup":       round(geo_mean(ro_spds), 3) if ro_spds else None,
        }

    payload = {
        "meta": {
            "timestamp":        ts,
            "target":           args.target,
            "total_vectors":    args.vectors,
            "warmup_vectors":   args.warmup,
            "measured_vectors": measured,
            "optimize":         args.optimize,
            "benchmark_type":   "ISCAS89_sequential",
        },
        "circuits":        circuits_data,
        "speedup_summary": speedup_summary,
    }

    # with open(json_path, 'w', encoding='utf-8') as f:
    #     json.dump(payload, f, indent=2)
    # print(f"\n[+] Full results saved -> {json_path}")

    # ── Human-readable TXT ────────────────────────────────────────────────────
    W = 180
    txt_lines = []
    txt_lines.append("=" * W)
    txt_lines.append("  UNIFIED ISCAS89 SEQUENTIAL LOGIC SIMULATOR BENCHMARK")
    txt_lines.append(f"  Timestamp      : {ts}")
    txt_lines.append(f"  Target         : {args.target}")
    txt_lines.append(f"  Total vectors  : {args.vectors:,}  |  Warmup: {args.warmup:,}  |  Measured: {measured:,}")
    txt_lines.append(f"  Circuits       : {len(all_results)}")
    txt_lines.append(f"  Optimize       : {args.optimize}")
    txt_lines.append("  Reactor modes  : propagate = BFS wavefront (SIMULATE mode)")
    txt_lines.append("                   sweep     = linear fwd-pass (COMPILE mode, requires optimize())")
    txt_lines.append("  Speedup baseline: Icarus Verilog VPI")
    txt_lines.append("=" * W)

    hdr = (
        f"{'Circuit':<16} | "
        f"{'Engine(ms)':<10} | {'Rx-prop(ms)':<11} | {'Rx-sweep(ms)':<12} | {'Rx-oop(ms)':<10} | "
        f"{'Icarus-sim(ms)':<14}"
    )
    txt_lines.append(hdr)
    txt_lines.append("-" * W)

    for filename, e_res, r_res, ro_res, i_res in all_results:
        e_str    = f"{e_res['time_ms']:.1f}"   if 'error' not in e_res else "ERR"
        r_str    = f"{r_res['time_ms']:.1f}"   if 'error' not in r_res else "ERR"
        rs_str   = (f"{r_res['sweep_ms']:.1f}" if 'sweep_ms'    in r_res
                    else ("ERR" if 'sweep_error' in r_res else "N/A"))
        ro_str   = f"{ro_res['time_ms']:.1f}"   if 'error' not in ro_res else "ERR"
        i_s_str  = f"{i_res['time_ms']:.2f}"   if 'error' not in i_res else "ERR"
        txt_lines.append(
            f"{filename:<16} | "
            f"{e_str:>10} | {r_str:>11} | {rs_str:>12} | {ro_str:>10} | "
            f"{i_s_str:>14}"
        )
    txt_lines.append("=" * W)


    # Speedup table vs baseline
    valid_i_txt = [
        (fn, e, r, ro, i) for fn, e, r, ro, i in all_results
        if 'error' not in i and i.get('time_ms', 0) > 0
    ]
    if valid_i_txt:
        txt_lines.append("")
        txt_lines.append("=" * W)
        txt_lines.append("  SPEEDUP ANALYSIS vs ICARUS VERILOG BASELINE  (Icarus = 1.00x)")
        txt_lines.append("=" * W)
        spd_hdr = (
            f"{'Circuit':<16} | "
            f"{'Icarus-sim(ms)':<14} | {'Engine(ms)':<10} | {'Eng-spd':<8} | "
            f"{'Rx-prop(ms)':<11} | {'Rx-prop-spd':<11} | "
            f"{'Rx-sweep(ms)':<12} | {'Rx-swp-spd':<10} | "
            f"{'Rx-oop(ms)':<10} | {'Rx-oop-spd':<10}"
        )
        txt_lines.append(spd_hdr)
        txt_lines.append("-" * W)

        g_e_spds  = []
        g_r_spds  = []
        g_rs_spds = []
        g_ro_spds = []

        for fn, e, r, ro, i in valid_i_txt:
            i_ms  = i['time_ms']
            e_ms  = e.get('time_ms') if 'error' not in e else None
            r_ms  = r.get('time_ms') if 'error' not in r else None
            rs_ms = r.get('sweep_ms')if 'error' not in r else None
            ro_ms = ro.get('time_ms') if 'error' not in ro else None

            e_spd  = i_ms / e_ms  if e_ms  and e_ms  > 0 else None
            r_spd  = i_ms / r_ms  if r_ms  and r_ms  > 0 else None
            rs_spd = i_ms / rs_ms if rs_ms and rs_ms > 0 else None
            ro_spd = i_ms / ro_ms if ro_ms and ro_ms > 0 else None

            if e_spd  is not None: g_e_spds.append(e_spd)
            if r_spd  is not None: g_r_spds.append(r_spd)
            if rs_spd is not None: g_rs_spds.append(rs_spd)

            def _fmt_ms(v):  return f"{v:.1f}"  if v is not None else "N/A"
            def _fmt_spd(v): return f"{v:.1f}x" if v is not None else "N/A"

            txt_lines.append(
                f"{fn:<16} | "
                f"{i_ms:>14.2f} | {_fmt_ms(e_ms):>10} | {_fmt_spd(e_spd):>8} | "
                f"{_fmt_ms(r_ms):>11} | {_fmt_spd(r_spd):>11} | "
                f"{_fmt_ms(rs_ms):>12} | {_fmt_spd(rs_spd):>10}"
            )

        g_e  = geo_mean(g_e_spds)  if g_e_spds  else None
        g_r  = geo_mean(g_r_spds)  if g_r_spds  else None
        g_rs = geo_mean(g_rs_spds) if g_rs_spds else None

        def _fmt_spd(v): return f"{v:.1f}x" if v is not None else "N/A"

        txt_lines.append("-" * W)
        txt_lines.append(
            f"{'Geo-mean speedup':<16} | {'(baseline)':<14} | "
            f"{'':<10} | {_fmt_spd(g_e):>8} | "
            f"{'':<11} | {_fmt_spd(g_r):>11} | {'':<12} | {_fmt_spd(g_rs):>10}"
        )
        txt_lines.append("=" * W)

        # MEPS table
    meps_valid = [(fn, e, r, ro, i) for fn, e, r, ro, i in all_results
                  if 'error' not in e and 'error' not in r]
    if meps_valid:
        txt_lines.append("")
        txt_lines.append("=" * W)
        txt_lines.append("  THROUGHPUT & EVALUATION COUNTS  (MEPS = Mega Gate-Evaluations Per Second)")
        txt_lines.append("=" * W)
        meps_hdr = (
            f"{'Circuit':<16} | "
            f"{'Eng-evals':<16} | {'Eng-MEPS':<9} | "
            f"{'Rx-prop-evals':<16} | {'Rx-p-MEPS':<9} | "
            f"{'Rx-swp-evals':<16} | {'Rx-s-MEPS':<9}"
        )
        txt_lines.append(meps_hdr)
        txt_lines.append("-" * W)
        for fn, e, r, ro, i in meps_valid:
            e_ev    = f"{e.get('total_evals', 0):,}"   if 'error' not in e else "ERR"
            e_meps  = f"{e.get('meps', 0):.2f}"        if 'error' not in e else "ERR"
            r_ev    = f"{r.get('total_evals', 0):,}"   if 'error' not in r else "ERR"
            r_meps  = f"{r.get('meps', 0):.2f}"        if 'error' not in r else "ERR"
            rs_ev   = (f"{r.get('sweep_evals', 0):,}"  if 'sweep_evals'  in r
                       else ("ERR" if 'sweep_error' in r else "N/A"))
            rs_meps = (f"{r.get('sweep_meps', 0):.2f}" if 'sweep_meps'   in r
                       else ("ERR" if 'sweep_error' in r else "N/A"))
            txt_lines.append(
                f"{fn:<16} | "
                f"{e_ev:>16} | {e_meps:>9} | "
                f"{r_ev:>16} | {r_meps:>9} | "
                f"{rs_ev:>16} | {rs_meps:>9}"
            )
        txt_lines.append("=" * W)

    # Summary
    txt_lines.append("")
    txt_lines.append("=" * W)
    txt_lines.append("  BENCHMARK SUMMARY")
    txt_lines.append("=" * W)
    total_circuits = len(all_results)
    ok_e  = sum(1 for _, e, r, ro, i in all_results if 'error' not in e)
    ok_r  = sum(1 for _, e, r, ro, i in all_results if 'error' not in r)
    ok_rs = sum(1 for _, e, r, ro, i in all_results if 'sweep_ms' in r)
    ok_i  = sum(1 for _, e, r, ro, i in all_results if 'error' not in i)
    txt_lines.append(f"  Circuits tested       : {total_circuits}")
    txt_lines.append(f"  Engine results OK     : {ok_e}/{total_circuits}")
    txt_lines.append(f"  Reactor (prop) OK     : {ok_r}/{total_circuits}")
    txt_lines.append(f"  Reactor (sweep) OK    : {ok_rs}/{total_circuits}")
    txt_lines.append(f"  Icarus results OK     : {ok_i}/{total_circuits}")
    txt_lines.append("")
    if speedup_summary:
        ss = speedup_summary
        e_geo  = ss.get('engine_geo_mean_speedup')
        rp_geo = ss.get('reactor_propagate_geo_mean_speedup')
        rs_geo = ss.get('reactor_sweep_geo_mean_speedup')
        txt_lines.append("  Geo-mean speedup over Icarus Verilog baseline:")
        txt_lines.append(f"    Engine (propagate)   : {e_geo:.2f}x"  if e_geo  else "    Engine              : N/A")
        txt_lines.append(f"    Reactor (propagate)  : {rp_geo:.2f}x" if rp_geo else "    Reactor (propagate) : N/A")
        txt_lines.append(f"    Reactor (sweep)      : {rs_geo:.2f}x" if rs_geo else "    Reactor (sweep)     : N/A")
        txt_lines.append("")
        if rp_geo and rs_geo:
            ratio = rs_geo / rp_geo
            txt_lines.append(f"  Reactor sweep vs propagate speedup ratio : {ratio:.2f}x  ({'sweep faster' if ratio > 1 else 'propagate faster'})")
            txt_lines.append("")
    txt_lines.append("  Methodology:")
    txt_lines.append("    - ISCAS89 sequential circuits with D flip-flops.")
    txt_lines.append("    - DFFs loaded via DFF.json IC; CLK/D pins wired from parsed netlist.")
    txt_lines.append("    - Each logical vector → 2 physical vectors (CLK=0 setup, CLK=1 trigger).")
    txt_lines.append("    - 50 warmup cycles (inputs=0, clock alternates) flush DFF initial state.")
    txt_lines.append("    - Engine/Reactor: warmup run untimed; GC disabled during measurement.")
    txt_lines.append("    - Sweep mode: asyncio.run() drains task_manager time_queue after each toggle.")
    txt_lines.append("    - Icarus: VPI inner-loop timer excludes warmup, $readmemb, and teardown.")
    txt_lines.append("    - Speedup baseline: Icarus Verilog VPI sim time (external reference).")
    txt_lines.append("=" * W)

    txt_lines.append("")
    txt_lines.append("=" * W)
    txt_lines.append("  BENCHMARK SUMMARY")
    txt_lines.append("=" * W)
    total_circuits = len(all_results)
    ok_e  = sum(1 for _, e, r, ro, i in all_results if 'error' not in e)
    ok_r  = sum(1 for _, e, r, ro, i in all_results if 'error' not in r)
    ok_rs = sum(1 for _, e, r, ro, i in all_results if 'sweep_ms' in r)
    ok_i  = sum(1 for _, e, r, ro, i in all_results if 'error' not in i)
    txt_lines.append(f"  Circuits tested       : {total_circuits}")
    txt_lines.append(f"  Engine results OK     : {ok_e}/{total_circuits}")
    txt_lines.append(f"  Reactor (prop) OK     : {ok_r}/{total_circuits}")
    txt_lines.append(f"  Reactor (sweep) OK    : {ok_rs}/{total_circuits}")
    txt_lines.append(f"  Icarus results OK     : {ok_i}/{total_circuits}")
    txt_lines.append("=" * W)

    # with open(txt_path, 'w', encoding='utf-8') as f:
    #     f.write('\n'.join(txt_lines) + '\n')
    # print(f"[+] Human-readable results saved -> {txt_path}")


# ===========================================================================
# 6. MAIN ENTRY POINT
# ===========================================================================

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="Unified 4-Engine ISCAS89 Sequential Logic Simulator Benchmark"
    )
    parser.add_argument('target', nargs='?', type=str,
                        help="Path to .v file or directory of ISCAS89 circuits")
    parser.add_argument('--vectors', type=int, default=50000,
                        help="Total logical vectors per circuit (warmup + measured)")
    parser.add_argument('--warmup',  type=int, default=5000,
                        help="Untimed warmup logical vectors")
    parser.add_argument('--optimize', action='store_true',
                        help="Enable topological optimization in Engine/Reactor")
    parser.add_argument('--output',  type=str, default="iscas89_results",
                        help="Base path for output files")
    parser.add_argument('--dump', action='store_true',
                        help='Only generate final data to stdout')
    parser.add_argument('--json', action='store_true',
                        help='Only generate JSON to stdout')
    parser.add_argument('--plot', action='store_true',
                        help='Generate plots (future feature)')
                        
    parser.add_argument('--no-engine', dest='engine', action='store_false',
                        help='Skip the pure Python Engine benchmark')
    parser.set_defaults(engine=True)
    parser.add_argument('--no-rx-prop', dest='rx_prop', action='store_false',
                        help='Skip Reactor BFS propagate (SIMULATE mode) benchmark')
    parser.set_defaults(rx_prop=True)
    parser.add_argument('--no-rx-sweep', dest='rx_sweep', action='store_false',
                        help='Skip Reactor sweep (COMPILE mode) benchmark')
    parser.set_defaults(rx_sweep=True)
    parser.add_argument('--no-icarus', dest='icarus', action='store_false',
                        help='Skip Icarus Verilog benchmark')
    parser.set_defaults(icarus=True)

    parser.add_argument('--perf', action='store_true',
                        help='Run perf for each python backend and generate individual reports')
    parser.add_argument('--perf-events', type=str, default="",
                        help='Comma separated list of perf events to trace')

    parser.add_argument('--internal-worker', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('--mode', type=str, choices=['engine', 'reactor', 'reactor_oop'],
                        help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.internal_worker:
        internal_worker_main(
            args.target, args.mode, args.vectors, args.warmup, args.optimize, args.rx_prop, args.rx_sweep,
            getattr(args, 'perf', False), getattr(args, 'perf_events', '')
        )
        sys.exit(0)

    if not args.target:
        print("[-] Error: No target path specified.")
        sys.exit(1)

    if getattr(args, 'dump', False):
        dump_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'test_result', 'benchmark_89', 'datas'
        )
        os.makedirs(dump_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = os.path.join(
            dump_dir, f"unified_iscas_benchmark_89_{timestamp}"
        )

    measured   = args.vectors - args.warmup
    if measured <= 0:
        print(f"[-] Error: --warmup ({args.warmup}) must be < --vectors ({args.vectors})")
        sys.exit(1)

    v_files = get_v_files(args.target)
    if not v_files:
        print("[-] Error: No .v files found.")
        sys.exit(1)

    # Check VPI timer availability
    vpi_status = (
        "enabled (inner-loop VPI timer)"
        if os.path.exists(_VPI_TIMER_VPI)
        else "disabled (fallback to vvp wall time)"
    )

    W = 150
    print("=" * W)
    print("  UNIFIED ISCAS89 SEQUENTIAL LOGIC SIMULATOR BENCHMARK")
    print(f"  Total vectors  : {args.vectors:,}  |  Warmup (untimed): {args.warmup:,}  |  Measured: {measured:,}")
    print(f"  Circuits       : {len(v_files)}")
    print(f"  Icarus VPI     : {vpi_status}")
    print("  Reactor modes  : propagate (BFS wavefront, SIMULATE) | sweep (linear fwd-pass, COMPILE)")
    print("  DFF support    : DFF.json IC")
    cols1 = (
        f"| {'Circuit':<16} "
        f"| {'Engine':^10} "
        f"| {'Reactor':^11} | {'':<12} "
        f"| {'ReactorOOP':^12} "
        f"| {'Icarus':^14} |"
    )
    sep = (
        f"|{'-'*18}"
        f"|{'-'*12}"
        f"|{'-'*13}|{'-'*14}"
        f"|{'-'*14}"
        f"|{'-'*16}|"
    )
    cols2 = (
        f"| {'':<16} "
        f"| {'Time(ms)':>10} "
        f"| {'prop(ms)':>11} | {'sweep(ms)':>12} "
        f"| {'prop(ms)':>12} "
        f"| {'sim(ms)':>14} |"
    )
    print(cols1)
    print(sep)
    print(cols2)

    all_results = []
    md_lines = []
    md_lines.append("# Unified ISCAS89 Logic Simulator Benchmark")
    md_lines.append("")
    md_lines.append(f"- **Total vectors**: {args.vectors:,} (Warmup: {args.warmup:,}, Measured: {measured:,})")
    md_lines.append(f"- **Circuits**: {len(v_files)}")
    md_lines.append(f"- **Icarus VPI**: {vpi_status}")
    md_lines.append("")
    md_lines.append(cols1)
    md_lines.append(sep)
    md_lines.append(cols2)

    for filepath in v_files:
        filename = os.path.basename(filepath)

        # Run Engine and Reactor in isolated subprocesses
        if args.engine:
            e_res = run_python_backend_process_89(
                filepath, 'engine',  args.vectors, args.warmup, args.optimize, args.rx_prop, args.rx_sweep,
                getattr(args, 'perf', False), getattr(args, 'perf_events', '')
            )
        else:
            e_res = {"engine": "Engine", "file": filename, "error": "disabled"}
            
        if args.rx_prop or args.rx_sweep:
            r_res = run_python_backend_process_89(
                filepath, 'reactor', args.vectors, args.warmup, args.optimize, args.rx_prop, args.rx_sweep,
                getattr(args, 'perf', False), getattr(args, 'perf_events', '')
            )
            ro_res = run_python_backend_process_89(
                filepath, 'reactor_oop', args.vectors, args.warmup, args.optimize, True, False,
                getattr(args, 'perf', False), getattr(args, 'perf_events', '')
            )
        else:
            r_res = {"engine": "Reactor", "file": filename, "error": "disabled"}
            ro_res = {"engine": "ReactorOOP", "file": filename, "error": "disabled"}
            
        # Run Icarus harness
        if args.icarus:
            i_res = run_icarus_harness_89(
                filepath, args.vectors, args.warmup,
                getattr(args, 'perf', False), getattr(args, 'perf_events', '')
            )
        else:
            i_res = {"engine": "Icarus", "file": filename, "error": "disabled"}

        e_str    = f"{e_res['time_ms']:.1f}"   if 'error' not in e_res else "ERR"
        r_str    = f"{r_res['time_ms']:.1f}"   if 'error' not in r_res else "ERR"
        rs_str   = (f"{r_res['sweep_ms']:.1f}" if 'sweep_ms'   in r_res
                    else ("ERR" if 'sweep_error' in r_res else "N/A"))
        ro_str   = f"{ro_res['time_ms']:.1f}"   if 'error' not in ro_res else "ERR"
        i_sim_str= f"{i_res['time_ms']:.2f}"   if 'error' not in i_res else "ERR"

        # Eval sub-lines
        e_ev  = f"{e_res.get('total_evals', 0):>10,}" if 'error' not in e_res else f"{'ERR':>10}"
        r_ev  = f"{r_res.get('total_evals', 0):>11,}" if 'error' not in r_res else f"{'ERR':>11}"
        rs_ev = (f"{r_res['sweep_evals']:>12,}"        if 'sweep_evals' in r_res
                 else (f"{'ERR':>12}" if 'sweep_error' in r_res else f"{'N/A':>12}"))
        ro_ev = f"{ro_res.get('total_evals', 0):>12,}" if 'error' not in ro_res else f"{'ERR':>12}"

        row_str = (
            f"| {filename:<16} | "
            f"{e_str:>10} | {r_str:>11} | {rs_str:>12} | "
            f"{ro_str:>12} | "
            f"{i_sim_str:>14} |"
        )
        md_lines.append(row_str)

        if not getattr(args, 'json', False):
            print(row_str)
            print(f"| {'evals':<16} | {e_ev} | {r_ev} | {rs_ev} | {ro_ev} | {'-':>14} |")
            sys.stdout.flush()

        all_results.append((filename, e_res, r_res, ro_res, i_res))

    if getattr(args, 'json', False):
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        circuits_data = [{"circuit": fn, "engine": e, "reactor": r, "reactor_oop": ro, "icarus": i} for fn, e, r, ro, i in all_results]
        payload = {
            "meta": {"timestamp": ts, "target": args.target, "total_vectors": args.vectors, "warmup_vectors": args.warmup, "measured_vectors": measured, "optimize": args.optimize},
            "circuits": circuits_data
        }
        print(json.dumps(payload, indent=4), file=sys.__stdout__)
        
    if not getattr(args, 'json', False):
        print("=" * W)
        md_lines = [
            "# Unified ISCAS89 Logic Simulator Benchmark", "",
            f"- **Total vectors**: {args.vectors:,} (Warmup: {args.warmup:,}, Measured: {measured:,})",
            f"- **Circuits**: {len(v_files)}",
            f"- **Icarus VPI**: {vpi_status}", ""
        ]
        _print_speedup_report(all_results, md_lines)
        _save_results_89(all_results, args)

    if getattr(args, 'dump', False):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dump_dir = os.path.join(script_dir, 'test_result', 'benchmark_89')
        os.makedirs(dump_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_path = os.path.join(dump_dir, f"unified_iscas_benchmark_89_{timestamp}.md")
        with open(dump_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(md_lines) + "\n")
        print(f"\n[+] Markdown dump saved to -> {dump_path}")


# ===========================================================================
# OUTPUT REDIRECTION
# ===========================================================================

if __name__ == '__main__':
    _orig = sys.stdout

    if '--json' in sys.argv:
        import os
        sys.stdout = open(os.devnull, 'w')

    try:
        main()
    finally:
        if sys.stdout is not _orig:
            sys.stdout.close()
        sys.stdout = _orig


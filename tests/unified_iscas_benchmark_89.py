"""
unified_iscas_benchmark_89.py  (v1 — 4-Engine Comparison: Python, Cython, Logisim, Icarus)
===========================================================================================
Unified benchmark runner comparing four simulation engines on ISCAS89 sequential datasets:
  1. Pure Python Engine  (SIMULATE mode)
  2. Cython Reactor Propagate  (SIMULATE mode / BFS Wavefront)
  3. Cython Reactor Sweep      (COMPILE  mode / Topological Forward-Pass)
  4. Logisim-Evolution  (Java harness, uses updated D Flip-Flop support in verilog_to_circ)
  5. Icarus Verilog     (iverilog + vvp + optional VPI inner-loop timer)

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
- Speedup baseline: Icarus Verilog VPI sim time (consistent with how the
  combinational benchmark uses Logisim as the external reference).
"""

import os
import re
import sys
import time
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
try:
    from verilog_to_circ import convert_file, vector_file_path
except ImportError:
    try:
        from tests.verilog_to_circ import convert_file, vector_file_path
    except ImportError:
        convert_file = None
        vector_file_path = None

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
# 1. LOGISIM HARNESS RUNNER (sequential — uses updated verilog_to_circ)
# ===========================================================================

def run_logisim_harness_89(v_file: str, harness_cp: str,
                            vectors: int, warmup: int) -> dict:
    """
    Run the custom Java benchmark harness for Logisim-Evolution on an ISCAS89
    sequential circuit.

    The updated verilog_to_circ.py now maps DFF instances to Logisim's built-in
    D Flip-Flop component (Memory library) and generates clock-paired vectors.
    """
    if convert_file is None or vector_file_path is None:
        return {"engine": "Logisim", "file": os.path.basename(v_file),
                "error": "verilog_to_circ not available"}

    filename  = os.path.basename(v_file)
    circ_file = os.path.splitext(v_file)[0] + "_89bench_converted.circ"
    vec_file  = vector_file_path(circ_file)

    try:
        gate_count = convert_file(v_file, circ_file, max_ticks=vectors)

        if not os.path.exists(vec_file):
            return {"engine": "Logisim", "file": filename,
                    "error": f"Vector file missing: {vec_file}"}
        if not os.path.exists(circ_file):
            return {"engine": "Logisim", "file": filename,
                    "error": f"Circuit file missing: {circ_file}"}

        cmd = [
            "java", "-cp", harness_cp, "LogisimBenchmarkHarness",
            circ_file, vec_file, str(vectors), str(warmup)
        ]
        try:
            res = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=1200
            )
        except subprocess.TimeoutExpired:
            return {"engine": "Logisim", "file": filename,
                    "error": "Logisim benchmark timed out (limit: 1200s)"}

        if res.returncode != 0:
            err = (res.stderr or res.stdout).strip()
            return {"engine": "Logisim", "file": filename,
                    "error": err or f"Exit code {res.returncode}"}

        parts = res.stdout.strip().split("\t")
        if len(parts) < 2:
            return {"engine": "Logisim", "file": filename,
                    "error": f"Unexpected harness output: {res.stdout.strip()!r}"}

        net_ms           = float(parts[0])
        measured_vectors = int(parts[1])
        total_evals      = gate_count * measured_vectors
        meps = (total_evals / (net_ms / 1000.0)) / 1_000_000.0 if net_ms > 0 else 0.0

        return {
            "engine":           "Logisim",
            "file":             filename,
            "gates":            gate_count,
            "time_ms":          net_ms,
            "measured_vectors": measured_vectors,
            "total_evals":      total_evals,
            "meps":             meps,
        }
    except Exception as e:
        return {"engine": "Logisim", "file": filename, "error": str(e)}
    finally:
        for path in (circ_file, vec_file):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


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

    def __init__(self, v_file_path, circuit_cls, const_mod, is_reactor=True):
        self.Circuit = circuit_cls
        self.const   = const_mod
        self.circuit = self.Circuit()
        self.is_reactor = is_reactor

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
            'buf':  self.const.INPUT_PIN_ID,
        }

        self._parse_verilog(v_file_path)
        self.output_objects = [self.nodes[p] for p in self.outputs if p in self.nodes]

    def _parse_verilog(self, filepath):
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
                        self.outputs.append(p)
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

    def _get_current_state(self) -> list:
        return [g.output for g in self.output_objects]

    async def _run_benchmark_async(self, vectors: int, warmup: int,
                                   use_optimize: bool):
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
            name = getattr(var, 'codename', '') or getattr(var, 'custom_name', '')
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
                    base.append((var.location, val))

                if clock_var is not None:
                    # setup: clock = LOW
                    setup = [(loc, self.const.LOW if loc == clock_var.location else val)
                             for loc, val in base]
                    # trigger: clock = HIGH
                    trigger = [(loc, self.const.HIGH if loc == clock_var.location else val)
                               for loc, val in base]
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

        propagate_ms = self.circuit.batch_toggle(flat_measured_batches, batch_size) if flat_measured_batches else 0.0

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

        # ──────────────────────────────────────────────────────────────────────
        # PASS 2: sweep (COMPILE mode / linear forward-pass)
        # ──────────────────────────────────────────────────────────────────────
        has_sweep = (
            self.is_reactor
            and hasattr(self.const, 'COMPILE')
            and hasattr(self.const, 'set_MODE')
            and hasattr(self.circuit, 'simulate')
        )
        if has_sweep:
            try:
                self.circuit.simulate(self.const.COMPILE)
                self.const.set_MODE(self.const.COMPILE)

                # Warmup (untimed, sweep mode)
                if flat_warmup_batches:
                    self.circuit.batch_toggle(flat_warmup_batches, batch_size)

                gc.collect()
                self.circuit.eval_count = 0
                gc.disable()
                
                sweep_ms = self.circuit.batch_toggle(flat_measured_batches, batch_size) if flat_measured_batches else 0.0

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
                      use_optimize: bool = True) -> dict:
        """Synchronous wrapper — instantiates the asyncio loop for DFF drain."""
        return asyncio.run(
            self._run_benchmark_async(vectors, warmup, use_optimize)
        )


# ===========================================================================
# 3. ISOLATED SUBPROCESS RUNNER (Engine / Reactor)
# ===========================================================================

def run_python_backend_process_89(filepath: str, mode: str,
                                   vectors: int, warmup: int,
                                   optimize: bool) -> dict:
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

    try:
        res = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if res.returncode == 0:
            return json.loads(res.stdout)
        else:
            return {"error": res.stderr.strip() or "Worker process failed"}
    except Exception as e:
        return {"error": str(e)}


def internal_worker_main(filepath: str, mode: str, vectors: int,
                          warmup: int, optimize: bool):
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    target_path  = os.path.join(script_dir, mode)
    if not os.path.exists(target_path):
        target_path = os.path.join(project_root, mode)

    sys.path.insert(0, project_root)
    sys.path.insert(0, target_path)
    import Circuit
    import Const

    is_reactor = (mode == 'reactor')
    try:
        runner = SequentialVerilogRunner(
            filepath, Circuit.Circuit, Const, is_reactor=is_reactor
        )
        stats = runner.run_benchmark(
            vectors=vectors, warmup=warmup, use_optimize=optimize
        )
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

def _print_speedup_report(all_results: list):
    import math

    W = 175
    print()

    # Auto-select baseline: Logisim when available, Icarus when --no-logisim
    logisim_available = any('error' not in l for _, _, _, l, _ in all_results)

    if logisim_available:
        # ── Logisim baseline (normal mode) ─────────────────────────────────────
        print("=" * W)
        print("  SPEEDUP vs LOGISIM BASELINE  (Logisim timed-only window = 1x)")
        print("  Reactor modes: prop = BFS wavefront (SIMULATE)  |  sweep = linear fwd-pass (COMPILE)")
        print("=" * W)
        hdr = (
            f"{'Circuit':<16} | "
            f"{'Logisim(ms)':<11} | {'Engine(ms)':<10} | {'Eng-spd':<8} | "
            f"{'Rx-prop(ms)':<11} | {'Rx-prop-spd':<11} | {'Rx-sweep(ms)':<12} | {'Rx-swp-spd':<10} | "
            f"{'Icarus-sim(ms)':<14} | {'Icar-spd':<8}"
        )
        print(hdr)
        print("-" * W)

        engine_speedups        = []
        reactor_prop_speedups  = []
        reactor_sweep_speedups = []
        icarus_speedups        = []

        for filename, e_res, r_res, l_res, i_res in all_results:
            if any('error' in res for res in (e_res, r_res, l_res)):
                continue

            l_ms  = l_res['time_ms']
            e_ms  = e_res['time_ms']
            r_ms  = r_res['time_ms']
            rs_ms = r_res.get('sweep_ms', None)
            i_ms  = i_res.get('time_ms', 0) if 'error' not in i_res else None

            e_spd  = l_ms / e_ms  if e_ms  > 0 else float('inf')
            r_spd  = l_ms / r_ms  if r_ms  > 0 else float('inf')
            rs_spd = l_ms / rs_ms if rs_ms and rs_ms > 0 else None
            i_spd  = l_ms / i_ms  if i_ms  and i_ms  > 0 else None

            engine_speedups.append(e_spd)
            reactor_prop_speedups.append(r_spd)
            if rs_spd is not None: reactor_sweep_speedups.append(rs_spd)
            if i_spd:              icarus_speedups.append(i_spd)

            rs_ms_str  = f"{rs_ms:.1f}"   if rs_ms  is not None else "N/A"
            rs_spd_str = f"{rs_spd:.1f}x" if rs_spd is not None else "N/A"
            i_ms_str   = f"{i_ms:.1f}"    if i_ms   is not None else "N/A"
            i_spd_str  = f"{i_spd:.1f}x"  if i_spd  is not None else "N/A"

            print(
                f"{filename:<16} | "
                f"{l_ms:>11.1f} | "
                f"{e_ms:>10.1f} | {e_spd:>7.1f}x | "
                f"{r_ms:>11.1f} | {r_spd:>10.1f}x | {rs_ms_str:>12} | {rs_spd_str:>10} | "
                f"{i_ms_str:>14} | {i_spd_str:>8}"
            )

        if engine_speedups:
            geo_mean = lambda xs: math.exp(sum(math.log(x) for x in xs) / len(xs))
            g_e  = geo_mean(engine_speedups)
            g_r  = geo_mean(reactor_prop_speedups)
            g_rs = geo_mean(reactor_sweep_speedups) if reactor_sweep_speedups else None
            g_i  = geo_mean(icarus_speedups)        if icarus_speedups        else None
            print("-" * W)
            g_rs_str = f"{g_rs:.1f}x" if g_rs is not None else "N/A"
            g_i_str  = f"{g_i:.1f}x"  if g_i  is not None else "N/A"
            print(
                f"{'Geo-mean speedup':<16} | {'(baseline)':<11} | "
                f"{'':<10} | {g_e:>7.1f}x | "
                f"{'':<11} | {g_r:>10.1f}x | {'':<12} | {g_rs_str:>10} | "
                f"{'':<14} | {g_i_str:>8}"
            )
            print("=" * W)

    else:
        # ── Icarus fallback baseline (--no-logisim mode) ───────────────────────
        print("=" * W)
        print("  SPEEDUP vs ICARUS VERILOG BASELINE  (Icarus VPI sim time = 1x)  [Logisim disabled]")
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

        for filename, e_res, r_res, l_res, i_res in all_results:
            if any('error' in res for res in (e_res, r_res, i_res)):
                continue

            i_ms  = i_res['time_ms']
            e_ms  = e_res['time_ms']
            r_ms  = r_res['time_ms']
            rs_ms = r_res.get('sweep_ms', None)

            e_spd  = i_ms / e_ms  if e_ms  > 0 else float('inf')
            r_spd  = i_ms / r_ms  if r_ms  > 0 else float('inf')
            rs_spd = i_ms / rs_ms if rs_ms and rs_ms > 0 else None

            engine_speedups.append(e_spd)
            reactor_prop_speedups.append(r_spd)
            if rs_spd is not None: reactor_sweep_speedups.append(rs_spd)

            rs_ms_str  = f"{rs_ms:.1f}"   if rs_ms  is not None else "N/A"
            rs_spd_str = f"{rs_spd:.1f}x" if rs_spd is not None else "N/A"

            print(
                f"{filename:<16} | "
                f"{i_ms:>14.2f} | "
                f"{e_ms:>10.1f} | {e_spd:>7.1f}x | "
                f"{r_ms:>11.1f} | {r_spd:>10.1f}x | {rs_ms_str:>12} | {rs_spd_str:>10}"
            )

        if engine_speedups:
            geo_mean = lambda xs: math.exp(sum(math.log(x) for x in xs) / len(xs))
            g_e  = geo_mean(engine_speedups)
            g_r  = geo_mean(reactor_prop_speedups)
            g_rs = geo_mean(reactor_sweep_speedups) if reactor_sweep_speedups else None
            print("-" * W)
            g_rs_str = f"{g_rs:.1f}x" if g_rs is not None else "N/A"
            print(
                f"{'Geo-mean speedup':<16} | {'(baseline)':<14} | "
                f"{'':<10} | {g_e:>7.1f}x | "
                f"{'':<11} | {g_r:>10.1f}x | {'':<12} | {g_rs_str:>10}"
            )
            print("=" * W)


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
    for filename, e_res, r_res, l_res, i_res in all_results:
        circuits_data.append({
            "circuit": filename,
            "engine":  e_res,
            "reactor": r_res,
            "logisim": l_res,
            "icarus":  i_res,
        })

    # Speedup summary vs Logisim baseline (or Icarus if Logisim unavailable)
    logisim_available = any('error' not in l for _, _, _, l, _ in all_results)
    speedup_summary = None

    geo_mean = lambda xs: math.exp(sum(math.log(x) for x in xs) / len(xs))

    if logisim_available:
        valid_l = [
            (fn, e, r, l, i) for fn, e, r, l, i in all_results
            if 'error' not in l and l.get('time_ms', 0) > 0
        ]
        if valid_l:
            e_spds  = [l['time_ms'] / e['time_ms']  for _, e, _, l, _ in valid_l
                       if 'error' not in e and e.get('time_ms', 0) > 0]
            r_spds  = [l['time_ms'] / r['time_ms']  for _, _, r, l, _ in valid_l
                       if 'error' not in r and r.get('time_ms', 0) > 0]
            rs_spds = [l['time_ms'] / r.get('sweep_ms', 0)
                       for _, _, r, l, _ in valid_l
                       if 'error' not in r and r.get('sweep_ms', 0) > 0]
            i_spds  = [l['time_ms'] / i['time_ms']  for _, _, _, l, i in valid_l
                       if 'error' not in i and i.get('time_ms', 0) > 0]

            speedup_summary = {
                "baseline":                           "Logisim",
                "valid_circuits":                     len(valid_l),
                "engine_geo_mean_speedup":            round(geo_mean(e_spds),  3) if e_spds  else None,
                "reactor_propagate_geo_mean_speedup": round(geo_mean(r_spds),  3) if r_spds  else None,
                "reactor_sweep_geo_mean_speedup":     round(geo_mean(rs_spds), 3) if rs_spds else None,
                "icarus_geo_mean_speedup":            round(geo_mean(i_spds),  3) if i_spds  else None,
            }
    else:
        valid_i = [
            (fn, e, r, l, i) for fn, e, r, l, i in all_results
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

            speedup_summary = {
                "baseline":                           "Icarus Verilog VPI sim time",
                "valid_circuits":                     len(valid_i),
                "engine_geo_mean_speedup":            round(geo_mean(e_spds),  3) if e_spds  else None,
                "reactor_propagate_geo_mean_speedup": round(geo_mean(r_spds),  3) if r_spds  else None,
                "reactor_sweep_geo_mean_speedup":     round(geo_mean(rs_spds), 3) if rs_spds else None,
            }

    payload = {
        "meta": {
            "timestamp":        ts,
            "target":           args.target,
            "total_vectors":    args.vectors,
            "warmup_vectors":   args.warmup,
            "measured_vectors": measured,
            "optimize":         args.optimize,
            "harness":          args.harness,
            "jar":              args.jar,
            "benchmark_type":   "ISCAS89_sequential",
        },
        "circuits":        circuits_data,
        "speedup_summary": speedup_summary,
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
    print(f"\n[+] Full results saved -> {json_path}")

    # ── Human-readable TXT ────────────────────────────────────────────────────
    W = 180
    txt_lines = []
    txt_lines.append("=" * W)
    txt_lines.append("  UNIFIED 4-ENGINE ISCAS89 SEQUENTIAL LOGIC SIMULATOR BENCHMARK")
    txt_lines.append(f"  Timestamp      : {ts}")
    txt_lines.append(f"  Target         : {args.target}")
    txt_lines.append(f"  Total vectors  : {args.vectors:,}  |  Warmup: {args.warmup:,}  |  Measured: {measured:,}")
    txt_lines.append(f"  Circuits       : {len(all_results)}")
    txt_lines.append(f"  Optimize       : {args.optimize}")
    txt_lines.append("  Reactor modes  : propagate = BFS wavefront (SIMULATE mode)")
    txt_lines.append("                   sweep     = linear fwd-pass (COMPILE mode, requires optimize())")
    txt_lines.append("  Speedup baseline: Logisim timed-only window (Fallback: Icarus Verilog VPI)")
    txt_lines.append("=" * W)

    hdr = (
        f"{'Circuit':<16} | "
        f"{'Engine(ms)':<10} | {'Rx-prop(ms)':<11} | {'Rx-sweep(ms)':<12} | "
        f"{'Logisim(ms)':<11} | {'Icarus-sim(ms)':<14}"
    )
    txt_lines.append(hdr)
    txt_lines.append("-" * W)

    for filename, e_res, r_res, l_res, i_res in all_results:
        e_str    = f"{e_res['time_ms']:.1f}"   if 'error' not in e_res else "ERR"
        r_str    = f"{r_res['time_ms']:.1f}"   if 'error' not in r_res else "ERR"
        rs_str   = (f"{r_res['sweep_ms']:.1f}" if 'sweep_ms'    in r_res
                    else ("ERR" if 'sweep_error' in r_res else "N/A"))
        l_str    = f"{l_res['time_ms']:.1f}"   if 'error' not in l_res else "ERR"
        i_s_str  = f"{i_res['time_ms']:.2f}"   if 'error' not in i_res else "ERR"
        txt_lines.append(
            f"{filename:<16} | "
            f"{e_str:>10} | {r_str:>11} | {rs_str:>12} | "
            f"{l_str:>11} | {i_s_str:>14}"
        )
    txt_lines.append("=" * W)

    # Speedup table vs baseline
    if logisim_available:
        valid_l_txt = [
            (fn, e, r, l, i) for fn, e, r, l, i in all_results
            if 'error' not in l and l.get('time_ms', 0) > 0
        ]
        if valid_l_txt:
            txt_lines.append("")
            txt_lines.append("=" * W)
            txt_lines.append("  SPEEDUP ANALYSIS vs LOGISIM BASELINE  (Logisim = 1.00x)")
            txt_lines.append("=" * W)
            spd_hdr = (
                f"{'Circuit':<16} | "
                f"{'Logisim(ms)':<11} | {'Engine(ms)':<10} | {'Eng-spd':<8} | "
                f"{'Rx-prop(ms)':<11} | {'Rx-prop-spd':<11} | "
                f"{'Rx-sweep(ms)':<12} | {'Rx-swp-spd':<10} | "
                f"{'Icarus(ms)':<11} | {'Icarus-spd':<10}"
            )
            txt_lines.append(spd_hdr)
            txt_lines.append("-" * W)

            g_e_spds  = []
            g_r_spds  = []
            g_rs_spds = []
            g_i_spds  = []

            for fn, e, r, l, i in valid_l_txt:
                l_ms  = l['time_ms']
                e_ms  = e.get('time_ms') if 'error' not in e else None
                r_ms  = r.get('time_ms') if 'error' not in r else None
                rs_ms = r.get('sweep_ms')if 'error' not in r else None
                i_ms  = i.get('time_ms') if 'error' not in i else None

                e_spd  = l_ms / e_ms  if e_ms  and e_ms  > 0 else None
                r_spd  = l_ms / r_ms  if r_ms  and r_ms  > 0 else None
                rs_spd = l_ms / rs_ms if rs_ms and rs_ms > 0 else None
                i_spd  = l_ms / i_ms  if i_ms  and i_ms  > 0 else None

                if e_spd  is not None: g_e_spds.append(e_spd)
                if r_spd  is not None: g_r_spds.append(r_spd)
                if rs_spd is not None: g_rs_spds.append(rs_spd)
                if i_spd  is not None: g_i_spds.append(i_spd)

                def _fmt_ms(v):  return f"{v:.1f}"  if v is not None else "N/A"
                def _fmt_spd(v): return f"{v:.1f}x" if v is not None else "N/A"

                txt_lines.append(
                    f"{fn:<16} | "
                    f"{l_ms:>11.1f} | {_fmt_ms(e_ms):>10} | {_fmt_spd(e_spd):>8} | "
                    f"{_fmt_ms(r_ms):>11} | {_fmt_spd(r_spd):>11} | "
                    f"{_fmt_ms(rs_ms):>12} | {_fmt_spd(rs_spd):>10} | "
                    f"{_fmt_ms(i_ms):>11} | {_fmt_spd(i_spd):>10}"
                )

            g_e  = geo_mean(g_e_spds)  if g_e_spds  else None
            g_r  = geo_mean(g_r_spds)  if g_r_spds  else None
            g_rs = geo_mean(g_rs_spds) if g_rs_spds else None
            g_i  = geo_mean(g_i_spds)  if g_i_spds  else None

            def _fmt_spd(v): return f"{v:.1f}x" if v is not None else "N/A"

            txt_lines.append("-" * W)
            txt_lines.append(
                f"{'Geo-mean speedup':<16} | {'(baseline)':<11} | "
                f"{'':<10} | {_fmt_spd(g_e):>8} | "
                f"{'':<11} | {_fmt_spd(g_r):>11} | {'':<12} | {_fmt_spd(g_rs):>10} | "
                f"{'':<11} | {_fmt_spd(g_i):>10}"
            )
            txt_lines.append("=" * W)

    else:
        valid_i_txt = [
            (fn, e, r, l, i) for fn, e, r, l, i in all_results
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
                f"{'Rx-sweep(ms)':<12} | {'Rx-swp-spd':<10}"
            )
            txt_lines.append(spd_hdr)
            txt_lines.append("-" * W)

            g_e_spds  = []
            g_r_spds  = []
            g_rs_spds = []

            for fn, e, r, l, i in valid_i_txt:
                i_ms  = i['time_ms']
                e_ms  = e.get('time_ms') if 'error' not in e else None
                r_ms  = r.get('time_ms') if 'error' not in r else None
                rs_ms = r.get('sweep_ms')if 'error' not in r else None

                e_spd  = i_ms / e_ms  if e_ms  and e_ms  > 0 else None
                r_spd  = i_ms / r_ms  if r_ms  and r_ms  > 0 else None
                rs_spd = i_ms / rs_ms if rs_ms and rs_ms > 0 else None

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
    meps_valid = [(fn, e, r, l, i) for fn, e, r, l, i in all_results
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
            f"{'Rx-swp-evals':<16} | {'Rx-s-MEPS':<9} | "
            f"{'Lsim-evals':<14} | {'Lsim-MEPS':<9}"
        )
        txt_lines.append(meps_hdr)
        txt_lines.append("-" * W)
        for fn, e, r, l, i in meps_valid:
            e_ev    = f"{e.get('total_evals', 0):,}"   if 'error' not in e else "ERR"
            e_meps  = f"{e.get('meps', 0):.2f}"        if 'error' not in e else "ERR"
            r_ev    = f"{r.get('total_evals', 0):,}"   if 'error' not in r else "ERR"
            r_meps  = f"{r.get('meps', 0):.2f}"        if 'error' not in r else "ERR"
            rs_ev   = (f"{r.get('sweep_evals', 0):,}"  if 'sweep_evals'  in r
                       else ("ERR" if 'sweep_error' in r else "N/A"))
            rs_meps = (f"{r.get('sweep_meps', 0):.2f}" if 'sweep_meps'   in r
                       else ("ERR" if 'sweep_error' in r else "N/A"))
            l_ev    = f"{l.get('total_evals', 0):,}"   if 'error' not in l else "ERR"
            l_meps  = f"{l.get('meps', 0):.2f}"        if 'error' not in l else "ERR"
            txt_lines.append(
                f"{fn:<16} | "
                f"{e_ev:>16} | {e_meps:>9} | "
                f"{r_ev:>16} | {r_meps:>9} | "
                f"{rs_ev:>16} | {rs_meps:>9} | "
                f"{l_ev:>14} | {l_meps:>9}"
            )
        txt_lines.append("=" * W)

    # Summary
    txt_lines.append("")
    txt_lines.append("=" * W)
    txt_lines.append("  BENCHMARK SUMMARY")
    txt_lines.append("=" * W)
    total_circuits = len(all_results)
    ok_e  = sum(1 for _, e, r, l, i in all_results if 'error' not in e)
    ok_r  = sum(1 for _, e, r, l, i in all_results if 'error' not in r)
    ok_rs = sum(1 for _, e, r, l, i in all_results if 'sweep_ms' in r)
    ok_l  = sum(1 for _, e, r, l, i in all_results if 'error' not in l)
    ok_i  = sum(1 for _, e, r, l, i in all_results if 'error' not in i)
    txt_lines.append(f"  Circuits tested       : {total_circuits}")
    txt_lines.append(f"  Engine results OK     : {ok_e}/{total_circuits}")
    txt_lines.append(f"  Reactor (prop) OK     : {ok_r}/{total_circuits}")
    txt_lines.append(f"  Reactor (sweep) OK    : {ok_rs}/{total_circuits}")
    txt_lines.append(f"  Logisim results OK    : {ok_l}/{total_circuits}")
    txt_lines.append(f"  Icarus results OK     : {ok_i}/{total_circuits}")
    txt_lines.append("")
    if speedup_summary:
        ss = speedup_summary
        e_geo  = ss.get('engine_geo_mean_speedup')
        rp_geo = ss.get('reactor_propagate_geo_mean_speedup')
        rs_geo = ss.get('reactor_sweep_geo_mean_speedup')
        l_geo  = ss.get('logisim_geo_mean_speedup')
        txt_lines.append("  Geo-mean speedup over Icarus Verilog baseline:")
        txt_lines.append(f"    Engine (propagate)   : {e_geo:.2f}x"  if e_geo  else "    Engine              : N/A")
        txt_lines.append(f"    Reactor (propagate)  : {rp_geo:.2f}x" if rp_geo else "    Reactor (propagate) : N/A")
        txt_lines.append(f"    Reactor (sweep)      : {rs_geo:.2f}x" if rs_geo else "    Reactor (sweep)     : N/A")
        txt_lines.append(f"    Logisim              : {l_geo:.2f}x"  if l_geo  else "    Logisim             : N/A")
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
    txt_lines.append("    - Logisim: Java harness with D Flip-Flop components (Memory library).")
    txt_lines.append("    - Icarus: VPI inner-loop timer excludes warmup, $readmemb, and teardown.")
    txt_lines.append("    - Speedup baseline: Icarus Verilog VPI sim time (external reference).")
    txt_lines.append("=" * W)

    txt_lines.append("")
    txt_lines.append("=" * W)
    txt_lines.append("  BENCHMARK SUMMARY")
    txt_lines.append("=" * W)
    total_circuits = len(all_results)
    ok_e  = sum(1 for _, e, r, l, i in all_results if 'error' not in e)
    ok_r  = sum(1 for _, e, r, l, i in all_results if 'error' not in r)
    ok_rs = sum(1 for _, e, r, l, i in all_results if 'sweep_ms' in r)
    ok_l  = sum(1 for _, e, r, l, i in all_results if 'error' not in l)
    ok_i  = sum(1 for _, e, r, l, i in all_results if 'error' not in i)
    txt_lines.append(f"  Circuits tested       : {total_circuits}")
    txt_lines.append(f"  Engine results OK     : {ok_e}/{total_circuits}")
    txt_lines.append(f"  Reactor (prop) OK     : {ok_r}/{total_circuits}")
    txt_lines.append(f"  Reactor (sweep) OK    : {ok_rs}/{total_circuits}")
    txt_lines.append(f"  Logisim results OK    : {ok_l}/{total_circuits}")
    txt_lines.append(f"  Icarus results OK     : {ok_i}/{total_circuits}")
    txt_lines.append("=" * W)

    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(txt_lines) + '\n')
    print(f"[+] Human-readable results saved -> {txt_path}")


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
    parser.add_argument('--jar',     type=str, default="logisim-evolution.jar",
                        help="Path to logisim-evolution JAR")
    parser.add_argument('--harness', type=str, default="harness_build",
                        help="Directory containing LogisimBenchmarkHarness.class")
    parser.add_argument('--vectors', type=int, default=50000,
                        help="Total logical vectors per circuit (warmup + measured)")
    parser.add_argument('--warmup',  type=int, default=5000,
                        help="Untimed warmup logical vectors")
    parser.add_argument('--optimize', action='store_true',
                        help="Enable topological optimization in Engine/Reactor")
    parser.add_argument('--output',  type=str, default="iscas89_results",
                        help="Base path for output files")
    parser.add_argument('--dump', action='store_true',
                        help='Dump output to time-stamped file in test_results')
    parser.add_argument('--no-logisim', dest='logisim', action='store_false',
                        help='Skip the Logisim-Evolution benchmark engine')
    parser.set_defaults(logisim=True)
    parser.add_argument('--plot', action='store_true',
                        help='Generate plots (future feature)')

    parser.add_argument('--internal-worker', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('--mode', type=str, choices=['engine', 'reactor'],
                        help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.internal_worker:
        internal_worker_main(
            args.target, args.mode, args.vectors, args.warmup, args.optimize
        )
        sys.exit(0)

    if not args.target:
        print("[-] Error: No target path specified.")
        sys.exit(1)

    if getattr(args, 'dump', False):
        import datetime
        dump_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'test_results', 'unified_iscas_benchmark_89', 'datas'
        )
        os.makedirs(dump_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = os.path.join(
            dump_dir, f"unified_iscas_benchmark_89_{timestamp}"
        )

    harness_dir = os.path.abspath(args.harness)
    if not os.path.exists(harness_dir) and not os.path.isabs(args.harness):
        alt = os.path.join(_PROJECT_ROOT, args.harness)
        if os.path.exists(alt):
            harness_dir = alt

    jar_path = os.path.abspath(args.jar)
    if not os.path.exists(jar_path) and not os.path.isabs(args.jar):
        for _search in (_SCRIPT_DIR, _PROJECT_ROOT):
            alt = os.path.join(_search, args.jar)
            if os.path.exists(alt):
                jar_path = alt
                break

    harness_cp = jar_path + os.pathsep + harness_dir
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

    W = 180
    print("=" * W)
    print("  UNIFIED 4-ENGINE ISCAS89 SEQUENTIAL LOGIC SIMULATOR BENCHMARK")
    print(f"  Total vectors  : {args.vectors:,}  |  Warmup (untimed): {args.warmup:,}  |  Measured: {measured:,}")
    print(f"  Circuits       : {len(v_files)}")
    print(f"  Harness class  : {os.path.join(harness_dir, 'LogisimBenchmarkHarness.class')}")
    print(f"  Icarus VPI     : {vpi_status}")
    print("  Reactor modes  : propagate (BFS wavefront, SIMULATE) | sweep (linear fwd-pass, COMPILE)")
    print("  DFF support    : DFF.json IC + Logisim D Flip-Flop (Memory lib)")
    print("  Speedup base   : Icarus Verilog VPI sim time")
    print("=" * W)

    header = (
        f"{'Circuit':<16} | "
        f"{'Engine(ms)':<10} | {'Rx-prop(ms)':<11} | {'Rx-sweep(ms)':<12} | "
        f"{'Logisim(ms)':<11} | {'Icarus-sim(ms)':<14}"
    )
    print(header)
    print("-" * W)

    all_results = []

    for filepath in v_files:
        filename = os.path.basename(filepath)

        # Run Engine and Reactor in isolated subprocesses
        e_res = run_python_backend_process_89(
            filepath, 'engine',  args.vectors, args.warmup, args.optimize
        )
        r_res = run_python_backend_process_89(
            filepath, 'reactor', args.vectors, args.warmup, args.optimize
        )
        # Run Logisim harness (can be skipped with --no-logisim)
        if args.logisim:
            l_res = run_logisim_harness_89(filepath, harness_cp, args.vectors, args.warmup)
        else:
            l_res = {"engine": "Logisim", "file": filename, "error": "disabled"}
        # Run Icarus harness
        i_res = run_icarus_harness_89(filepath, args.vectors, args.warmup)

        e_str    = f"{e_res['time_ms']:.1f}"   if 'error' not in e_res else "ERR"
        r_str    = f"{r_res['time_ms']:.1f}"   if 'error' not in r_res else "ERR"
        rs_str   = (f"{r_res['sweep_ms']:.1f}" if 'sweep_ms'   in r_res
                    else ("ERR" if 'sweep_error' in r_res else "N/A"))
        l_str    = f"{l_res['time_ms']:.1f}"   if 'error' not in l_res else "ERR"
        i_sim_str= f"{i_res['time_ms']:.2f}"   if 'error' not in i_res else "ERR"

        # Eval sub-lines
        e_ev  = f"{e_res.get('total_evals', 0):>10,}" if 'error' not in e_res else f"{'ERR':>10}"
        r_ev  = f"{r_res.get('total_evals', 0):>11,}" if 'error' not in r_res else f"{'ERR':>11}"
        rs_ev = (f"{r_res['sweep_evals']:>12,}"        if 'sweep_evals' in r_res
                 else (f"{'ERR':>12}" if 'sweep_error' in r_res else f"{'N/A':>12}"))

        print(
            f"{filename:<16} | "
            f"{e_str:>10} | {r_str:>11} | {rs_str:>12} | "
            f"{l_str:>11} | {i_sim_str:>14}"
        )
        print(f"  {'evals':<14} | {e_ev} | {r_ev} | {rs_ev}")
        sys.stdout.flush()

        all_results.append((filename, e_res, r_res, l_res, i_res))

    print("=" * W)
    _print_speedup_report(all_results)
    _save_results_89(all_results, args)


# ===========================================================================
# OUTPUT TEE (--dump flag)
# ===========================================================================

class _Tee:
    def __init__(self, *streams):
        self.streams = streams
    def write(self, data):
        for s in self.streams:
            s.write(data)
    def flush(self):
        for s in self.streams:
            s.flush()


if __name__ == '__main__':
    _orig = sys.stdout
    _lf   = None

    if '--dump' in sys.argv:
        import datetime
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dump_dir = os.path.join(
            script_dir, 'test_results', 'unified_iscas_benchmark_89', 'datas'
        )
        os.makedirs(dump_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        _LOG = os.path.join(dump_dir, f"unified_iscas_benchmark_89_stdout_{timestamp}.txt")
        _lf  = open(_LOG, "a", encoding="utf-8")
        sys.stdout = _Tee(_orig, _lf)

    try:
        main()
    finally:
        sys.stdout = _orig
        if _lf:
            _lf.close()


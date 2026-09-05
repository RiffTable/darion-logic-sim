"""
unified_iscas_benchmark.py  (v5 — 3-Engine Comparison: Python, Cython, Icarus Verilog)
========================================================================================
Unified combinational benchmark runner comparing three simulation engines on ISCAS85:
  1. Pure Python Engine
  2. Cython Reactor
  3. Icarus Verilog (using VPI for inner-loop timing)

Methodology:
  - All engines are fed an identical pre-generated PRNG toggle sequence (seed=42).
  - Engine / Reactor: identical warmup_vectors run untimed via batch_toggle
    before the timed window. GC is disabled during measurement. Timing covers
    only the core simulation loop, making all engines directly comparable.
  - Icarus Verilog: Python generates the identical random vectors (seed=42,
    skipping warmup), writes them to a file loaded via $readmemb in the
    testbench. A custom VPI module (vpi_timer.c / vpi_timer.vpi) injects
    $start_timer() / $stop_timer() system tasks using Windows
    QueryPerformanceCounter directly inside the simulation. The timer fires
    AFTER $readmemb completes (disk I/O excluded) and stops AFTER the loop
    (before $finish / process teardown). This isolates Icarus's pure
    simulation throughput, matching the measurement window of Engine/Reactor.
    Reports: Compile Time (iverilog), VPI Sim Time (inner loop only),
             VPI Run Time (total vvp process), and Compile+VPI Total.
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
from pathlib import Path

_SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT  = os.path.dirname(_SCRIPT_DIR)

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


# ===========================================================================
# 1. ICARUS VERILOG HARNESS RUNNER
# ===========================================================================

_VPI_DIR       = os.path.join(_SCRIPT_DIR, "harness_build") if os.path.exists(os.path.join(_SCRIPT_DIR, "harness_build")) else os.path.join(_PROJECT_ROOT, "harness_build")
_VPI_TIMER_C   = os.path.join(_VPI_DIR, "vpi_timer.c")
_VPI_TIMER_VPI = os.path.join(_VPI_DIR, "vpi_timer.vpi")


def build_vpi_timer() -> bool:
    """Compile vpi_timer.c -> vpi_timer.vpi using iverilog-vpi if not already built."""
    if os.path.exists(_VPI_TIMER_VPI):
        return True
    if not os.path.exists(_VPI_TIMER_C):
        return False
    if not shutil.which("iverilog-vpi"):
        return False
    try:
        res = subprocess.run(
            ["iverilog-vpi", "vpi_timer.c"],
            cwd=_VPI_DIR,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return res.returncode == 0 and os.path.exists(_VPI_TIMER_VPI)
    except Exception:
        return False

def parse_verilog_ports(v_file: str):
    """Extract module name, input ports, and output ports from an ISCAS Verilog file."""
    with open(v_file, 'r', encoding='utf-8') as f:
        content = f.read()

    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'//.*', '', content)

    mod_match = re.search(r'\bmodule\s+([a-zA-Z0-9_]+)', content)
    module_name = mod_match.group(1) if mod_match else "circuit"

    def extract_ports(keyword):
        ports = []
        for m in re.finditer(r'\b' + keyword + r'\s+([^;]+);', content):
            decl = m.group(1).strip()
            range_match = re.search(r'(\[[^\]]+\])', decl)
            bus_range = range_match.group(1) + " " if range_match else ""
            cleaned = re.sub(r'(\[[^\]]+\]|\bwire\b|\breg\b|\blogic\b|\bsigned\b|\bunsigned\b)', '', decl).strip()
            for p in cleaned.split(','):
                p = p.strip()
                if p:
                    ports.append(f"{bus_range}{p}")
        return ports

    inputs = extract_ports('input')
    outputs = extract_ports('output')

    return module_name, inputs, outputs


def generate_icarus_tb(v_file: str, tb_file: str, vectors: int, warmup: int,
                       vector_file: str, use_vpi_timer: bool = True):
    """
    Generates a Verilog testbench that reads identical Python-generated vectors.

    When use_vpi_timer=True the testbench calls $start_timer() *after* $readmemb
    (all disk I/O done) and $stop_timer() *after* the simulation loop, so only
    the pure propagation work is measured — matching the Cython reactor window.
    """
    module_name, inputs, outputs = parse_verilog_ports(v_file)
    measured = max(vectors - warmup, 1)

    tb = []
    tb.append("`timescale 1ns/1ps\n")
    tb.append(f"module tb_{module_name};\n")

    # Define inputs and outputs
    for inp in inputs:
        tb.append(f"    reg {inp};\n")
    for outp in outputs:
        tb.append(f"    wire {outp};\n")

    # Packed vector store loaded from file
    total_inputs = len(inputs)
    tb.append(f"    reg [{total_inputs-1}:0] test_vectors [0:{measured-1}];\n")
    tb.append("    integer i;\n\n")

    # Instantiate UUT
    tb.append(f"    {module_name} uut (\n")
    conn = [f"        .{p.split()[-1]}({p.split()[-1]})" for p in inputs + outputs]
    tb.append(",\n".join(conn))
    tb.append("\n    );\n\n")

    v_path_str = str(vector_file).replace("\\", "/")

    tb.append("    initial begin\n")
    # Load identical vectors (disk I/O happens here, before the timer starts)
    tb.append(f"        $readmemb(\"{v_path_str}\", test_vectors);\n")

    # --- VPI inner-loop timer: starts AFTER $readmemb, BEFORE the sim loop ---
    if use_vpi_timer:
        tb.append("        $start_timer();\n")

    tb.append(f"        for (i = 0; i < {measured}; i = i + 1) begin\n")
    for idx, inp in enumerate(inputs):
        port_name = inp.split()[-1]
        tb.append(f"            {port_name} = test_vectors[i][{idx}];\n")
    tb.append("            #1;\n")
    tb.append("        end\n")

    # --- VPI inner-loop timer: stops AFTER the loop, BEFORE $finish ---
    if use_vpi_timer:
        tb.append("        $stop_timer();\n")

    tb.append("        $finish;\n")
    tb.append("    end\n")
    tb.append("endmodule\n")

    with open(tb_file, 'w', encoding='utf-8') as f:
        f.write("".join(tb))

    return module_name


def run_icarus_harness(v_file: str, vectors: int, warmup: int) -> dict:
    """
    Compile and run a circuit with Icarus Verilog (iverilog + vvp).

    Timing strategy:
      - compile_ms  : iverilog compilation wall time (process-level)
      - sim_ms      : VPI inner-loop time (QueryPerformanceCounter inside vvp),
                      measured AFTER $readmemb and BEFORE $finish — excludes
                      OS spawn, disk I/O, and teardown.  This is the fair
                      apples-to-apples number vs. Engine/Reactor.
      - run_ms      : total vvp process wall time (includes sim_ms overhead)
      - total_ms    : compile_ms + run_ms
    """
    filename    = os.path.basename(v_file)
    base_path   = os.path.splitext(v_file)[0]
    tb_file     = base_path + "_tb.v"
    vvp_file    = base_path + ".vvp"
    vector_file = base_path + "_icarus_vectors.txt"

    if not shutil.which("iverilog") or not shutil.which("vvp"):
        return {
            "engine": "Icarus",
            "file": filename,
            "error": "iverilog or vvp command not found in PATH"
        }

    # Build VPI timer if needed (one-time, cached in harness_build/)
    use_vpi = build_vpi_timer()

    try:
        t_start_total = time.perf_counter_ns()
        module_name, inputs, outputs = parse_verilog_ports(v_file)
        measured = max(vectors - warmup, 1)

        # 1. Generate identical vector dataset using Python's PRNG (seed=42)
        rng = random.Random(42)
        all_vecs = [[rng.randint(0, 1) for _ in range(len(inputs))] for _ in range(vectors)]
        measured_vecs = all_vecs[warmup:warmup + measured]

        # 2. Write measured (post-warmup) vectors as packed binary strings
        with open(vector_file, 'w', encoding='utf-8') as f:
            for vec in measured_vecs:
                # Rightmost bit = inputs[0]; leftmost bit = inputs[-1]
                bin_str = "".join(str(v) for v in reversed(vec))
                f.write(bin_str + "\n")

        # 3. Generate testbench — injects VPI $start_timer/$stop_timer when available
        generate_icarus_tb(v_file, tb_file, vectors, warmup, vector_file,
                           use_vpi_timer=use_vpi)

        # 4. Compilation (iverilog)
        t_comp_start = time.perf_counter_ns()
        comp_cmd = ["iverilog", "-o", vvp_file, v_file, tb_file]
        comp_res = subprocess.run(comp_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        t_comp_end = time.perf_counter_ns()
        compile_ms = (t_comp_end - t_comp_start) / 1_000_000.0

        if comp_res.returncode != 0:
            return {"engine": "Icarus", "file": filename,
                    "error": f"Compile failure: {comp_res.stderr.strip()}"}

        # 5. Execution (vvp) — load VPI module if available
        if use_vpi:
            run_cmd = ["vvp", "-M", _VPI_DIR, "-mvpi_timer", vvp_file]
        else:
            run_cmd = ["vvp", vvp_file]

        t_run_start = time.perf_counter_ns()
        run_res = subprocess.run(run_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        t_run_end = time.perf_counter_ns()
        run_ms = (t_run_end - t_run_start) / 1_000_000.0

        t_end_total = time.perf_counter_ns()
        total_ms_overall = (t_end_total - t_start_total) / 1_000_000.0

        if run_res.returncode != 0:
            return {"engine": "Icarus", "file": filename,
                    "error": f"Run failure: {run_res.stderr.strip()}"}

        # 6. Parse VPI inner-loop time from stdout ($ELAPSED_NS:<value>)
        sim_ms = None
        if use_vpi:
            for line in run_res.stdout.splitlines():
                if line.startswith("$ELAPSED_NS:"):
                    try:
                        elapsed_ns = int(line.split(":", 1)[1].strip())
                        sim_ms = elapsed_ns / 1_000_000.0
                    except ValueError:
                        pass
                    break

        result = {
            "engine":      "Icarus",
            "file":        filename,
            "compile_ms":  compile_ms,
            "run_ms":      run_ms,          # total vvp wall time
            "total_ms":    compile_ms + run_ms,
            "vpi_timer":   use_vpi,
        }
        if sim_ms is not None:
            # Authentic apples-to-apples number: pure simulation loop only
            result["time_ms"] = sim_ms
        else:
            # Fallback: vvp wall time (includes spawn + $readmemb overhead)
            result["time_ms"] = run_ms
            
        result["load_ms"] = compile_ms

        return result

    except Exception as e:
        return {"engine": "Icarus", "file": filename, "error": str(e)}
    finally:
        for p in (tb_file, vvp_file, vector_file):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


# ===========================================================================
# 3. INTERNAL WORKER FOR ENGINE / REACTOR ISOLATED RUNS
# ===========================================================================

class VerilogRunner:
    def __init__(self, v_file_path, circuit_cls, const_mod, is_reactor=True, use_optimize=True, mode="engine"):
        self.Circuit = circuit_cls
        self.const = const_mod
        self.use_optimize = use_optimize
        self.circuit = self.Circuit()
        self.circuit.simulate(self.const.DESIGN)
        self.is_reactor = is_reactor
        self.mode = mode
        self.nodes = {}
        self.outputs = []

        self.VERILOG_GATE_MAP = {
            'and': self.const.AND_ID, 'nand': self.const.NAND_ID, 'or': self.const.OR_ID,
            'nor': self.const.NOR_ID, 'xor': self.const.XOR_ID, 'xnor': self.const.XNOR_ID, 'not': self.const.NOT_ID,
        }

        self.input_vars = []

        self._parse_verilog(v_file_path)

    def _parse_verilog(self, filepath):
        json_path = filepath.replace('.v', '.json')
        
        if os.path.exists(json_path) and hasattr(self.circuit, 'readfromjson'):
            self.circuit.readfromjson(json_path)
            _, inputs, _ = parse_verilog_ports(filepath)
            var_list = self.circuit.get_variables()
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
            
            for gate in self.circuit.get_components():
                name_str = getattr(gate, 'custom_name', None) or getattr(gate, 'codename', None) or str(gate)
                if name_str.startswith("G_"):
                    self.nodes[name_str[2:]] = gate
                elif name_str.startswith("IN_"):
                    self.nodes[name_str[3:]] = gate
                elif name_str == "CONST_1":
                    self.const_1_node = gate
                    self.nodes["1'b1"] = gate
                elif name_str == "CONST_0":
                    self.const_0_node = gate
                    self.nodes["1'b0"] = gate
                else:
                    self.nodes[name_str] = gate
            if not self.is_reactor:
                if self.use_optimize:
                    self.circuit.optimize()
                self.circuit.simulate(self.const.COMPILE)
            return

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'//.*', '', content)
        statements = [s.strip() for s in content.split(';') if s.strip()]
        connections = []

        self.const_1_node = None
        self.const_0_node = None

        def get_const_node(val_str):
            if val_str == "1'b1":
                if not getattr(self, 'const_1_node', None):
                    self.const_1_node = self.circuit.getcomponent(self.const.VARIABLE_ID)
                    self.const_1_node.rename("CONST_1")
                    self.nodes["1'b1"] = self.const_1_node
                return self.const_1_node
            elif val_str == "1'b0":
                if not getattr(self, 'const_0_node', None):
                    self.const_0_node = self.circuit.getcomponent(self.const.VARIABLE_ID)
                    self.const_0_node.rename("CONST_0")
                    self.nodes["1'b0"] = self.const_0_node
                return self.const_0_node
            return None

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
                match = re.match(r'^([a-zA-Z_]\w*)\s+([a-zA-Z_0-9]+)?\s*\((.*)\)$', stmt)
                if match:
                    gate_type = match.group(1).lower()
                    ports_str = match.group(3)
                    if gate_type in self.VERILOG_GATE_MAP:
                        ports = [p.strip() for p in ports_str.split(',')]
                        out_wire = ports[0]
                        in_wires = ports[1:]
                        gate_id = self.VERILOG_GATE_MAP[gate_type]
                        gate = self.circuit.getcomponent(gate_id)
                        gate.rename(f"G_{out_wire}")
                        
                        for w in in_wires:
                            get_const_node(w)

                        if gate_id != self.const.NOT_ID and hasattr(self.circuit, 'setlimits'):
                            self.circuit.setlimits(gate, len(in_wires))
                        self.nodes[out_wire] = gate
                        connections.append((out_wire, in_wires))

        for target_id, source_ids in connections:
            target_gate = self.nodes.get(target_id)
            if not target_gate: continue
            for pin_index, source_id in enumerate(source_ids):
                source_gate = self.nodes.get(source_id)
                if source_gate:
                    self.circuit.connect(target_gate, source_gate, pin_index)
        if self.use_optimize:
            self.circuit.optimize()
        self.circuit.simulate(self.const.COMPILE)

    def run_benchmark(self, vectors=10000, warmup=5000, use_optimize=True, rx_prop=True, rx_sweep=True):
        """Run the simulation benchmark with symmetric warmup.

        Measures two paths for reactor, one for engine:
          - propagate_ms  : BFS wavefront (SIMULATE mode), the existing path.
          - sweep_ms      : Linear forward-pass (COMPILE mode) — reactor only.
            sweep() is triggered via simulate(COMPILE) + batch_toggle() when
            MODE==COMPILE.  Requires a topologically sorted gate_infolist
            (i.e. optimize() must have been called first) to be meaningful.
            For the engine, which has no sweep() implementation, sweep_ms is
            omitted from the result dict.
        """
        measured = max(vectors - warmup, 1)

        # temporarily turn off optimize for rx_prop
        if use_optimize:
            if hasattr(self.circuit, 'optimize'):
                self.circuit.optimize()

        # ── Shared vector set (identical across both passes) ─────────────────
        total_needed = warmup + measured
        _rng = random.Random(42)
        all_instructions = []
        for _ in range(total_needed):
            batch = []
            for var_node in self.input_vars:
                val = self.const.HIGH if _rng.randint(0, 1) else self.const.LOW
                if self.mode == "reactor_oop":
                    batch.append((var_node, val))
                else:
                    batch.append((var_node.location, val))
            
            if getattr(self, 'const_1_node', None):
                if self.mode == "reactor_oop":
                    batch.append((self.const_1_node, self.const.HIGH))
                else:
                    batch.append((self.const_1_node.location, self.const.HIGH))
            if getattr(self, 'const_0_node', None):
                if self.mode == "reactor_oop":
                    batch.append((self.const_0_node, self.const.LOW))
                else:
                    batch.append((self.const_0_node.location, self.const.LOW))
                
            all_instructions.append(batch)
        warmup_batches   = all_instructions[:warmup]
        measured_batches = all_instructions[warmup:]

        flat_warmup_batches = [item for sublist in warmup_batches for item in sublist]
        flat_measured_batches = [item for sublist in measured_batches for item in sublist]
        batch_size = len(self.input_vars) + (1 if getattr(self, 'const_1_node', None) else 0) + (1 if getattr(self, 'const_0_node', None) else 0)

        if rx_prop:
            # ── PASS 1: propagate (SIMULATE / BFS wavefront) ─────────────────────
            self.circuit.simulate(self.const.SIMULATE)

            if flat_warmup_batches:
                self.circuit.batch_toggle(flat_warmup_batches, batch_size)

            gc.collect()
            self.circuit.eval_count = 0
            gc.disable()
            
            send_perf_ctrl("enable")
            propagate_ms = self.circuit.batch_toggle(flat_measured_batches, batch_size) if flat_measured_batches else 0.0
            send_perf_ctrl("disable")

            gc.enable()
            propagate_evals = getattr(self.circuit, 'eval_count', measured * len(self.nodes))
            propagate_meps  = (
                (propagate_evals / (propagate_ms / 1000.0)) / 1_000_000.0
                if propagate_ms > 0 else 0.0
            )

            result = {
                "nodes":            len(self.nodes),
                "time_ms":          propagate_ms,   # canonical field (backward-compat)
                "propagate_ms":     propagate_ms,
                "measured_vectors": measured,
                "total_evals":      propagate_evals,
                "meps":             propagate_meps,
            }
        else:
            result = {
                "nodes":            len(self.nodes),
                "time_ms":          0.0,
                "propagate_ms":     0.0,
                "measured_vectors": measured,
                "total_evals":      0,
                "meps":             0.0,
            }

        # ── PASS 2: sweep (COMPILE mode / linear forward-pass) ───────────────
        # sweep() exists only on the reactor (cdef nogil method on Circuit.pyx).
        # batch_toggle() dispatches to sweep() when MODE==COMPILE.
        #
        # IMPORTANT: simulate(COMPILE) internally calls set_MODE(SIMULATE), not
        # set_MODE(COMPILE).  It runs sweep(0) as the *initial* full-pass setup
        # but leaves MODE=SIMULATE for subsequent calls.  To make batch_toggle()
        # route to sweep() rather than propagate(), we must call set_MODE(COMPILE)
        # ourselves before the timed loop, then restore SIMULATE afterwards.
        # set_MODE is a cpdef exposed on the Const module.
        has_sweep = (
            self.is_reactor
            and hasattr(self.const, 'COMPILE')
            and hasattr(self.const, 'set_MODE')
            and hasattr(self.circuit, 'simulate')
        )
        if has_sweep and rx_sweep:
            try:
                if use_optimize:
                    if hasattr(self.circuit, 'optimize'):
                        self.circuit.optimize()
                
                # Initial full sweep to seed all gate outputs from current values.
                # After this, MODE == SIMULATE (simulate() always sets it to SIMULATE).
                self.circuit.simulate(self.const.COMPILE)

                # Switch to COMPILE so batch_toggle() calls sweep() not propagate().
                self.const.set_MODE(self.const.COMPILE)

                if flat_warmup_batches:
                    self.circuit.batch_toggle(flat_warmup_batches, batch_size)

                gc.collect()
                self.circuit.eval_count = 0
                gc.disable()
                
                send_perf_ctrl("enable")
                sweep_ms = self.circuit.batch_toggle(flat_measured_batches, batch_size) if flat_measured_batches else 0.0
                send_perf_ctrl("disable")

                gc.enable()

                # Restore SIMULATE mode so the circuit is in a sane state.
                self.const.set_MODE(self.const.SIMULATE)
                sweep_evals = getattr(self.circuit, 'eval_count', measured * len(self.nodes))
                sweep_meps  = (
                    (sweep_evals / (sweep_ms / 1000.0)) / 1_000_000.0
                    if sweep_ms > 0 else 0.0
                )
                result["sweep_ms"]    = sweep_ms
                result["sweep_evals"] = sweep_evals
                result["sweep_meps"]  = sweep_meps
            except Exception as exc:
                result["sweep_error"] = str(exc)

        return result


def run_python_backend_process(filepath: str, mode: str, vectors: int, warmup: int, optimize: bool, rx_prop: bool, rx_sweep: bool) -> dict:
    cmd = [
        sys.executable, os.path.abspath(__file__),
        "--internal-worker", filepath,
        "--mode", mode,
        "--vectors", str(vectors),
        "--warmup", str(warmup),
    ]
    if optimize:
        cmd.append("--optimize")
    if not rx_prop:
        cmd.append("--no-rx-prop")
    if not rx_sweep:
        cmd.append("--no-rx-sweep")

    try:
        t0 = time.perf_counter_ns()
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        t1 = time.perf_counter_ns()
        total_ms = (t1 - t0) / 1_000_000.0

        if res.returncode == 0:
            data = json.loads(res.stdout)
            data["load_ms"] = data.get("parse_ms", 0.0)
            return data
        else:
            return {"error": res.stderr.strip() or "Worker process failed"}
    except Exception as e:
        return {"error": str(e)}


def internal_worker_main(filepath: str, mode: str, vectors: int, warmup: int, optimize: bool, rx_prop: bool, rx_sweep: bool):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    target_path = os.path.join(script_dir, mode)
    if not os.path.exists(target_path):
        target_path = os.path.join(project_root, mode)

    sys.path.insert(0, project_root)
    sys.path.insert(0, target_path)
    import Circuit
    import Const

    is_reactor = (mode in ('reactor', 'reactor_oop'))
    try:
        t0 = time.perf_counter_ns()
        runner = VerilogRunner(filepath, Circuit.Circuit, Const, is_reactor=is_reactor, use_optimize=optimize, mode=mode)
        t1 = time.perf_counter_ns()
        
        stats = runner.run_benchmark(vectors=vectors, warmup=warmup, use_optimize=optimize, rx_prop=rx_prop, rx_sweep=rx_sweep)
        stats['parse_ms'] = (t1 - t0) / 1_000_000.0
        print(json.dumps(stats))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


# ===========================================================================
# 4. MAIN CONTROLLER & REPORTING
# ===========================================================================

def get_v_files(target):
    if os.path.isfile(target) and target.endswith('.v'):
        return [target]
    v_files = []
    for root, _, files in os.walk(target):
        for f in files:
            if f.endswith('.v'):
                v_files.append(os.path.join(root, f))
    return sorted(v_files, key=os.path.getsize)


def main():
    parser = argparse.ArgumentParser(
        description="Unified 3-Engine ISCAS Logic Sim Benchmark (Engine, Reactor, Icarus)"
    )
    parser.add_argument('target', nargs='?', type=str, help="Path to .v file or directory")
    parser.add_argument('--vectors', type=int, default=50000, help="Total vectors per circuit (warmup + measured)")
    parser.add_argument('--warmup',  type=int, default=5000,  help="Untimed warmup vectors (same for all engines)")
    parser.add_argument('--optimize', action='store_true', help="Enable topological optimization in Engine/Reactor")
    parser.add_argument('--output',  type=str, default="iscas_results", help="Base path for output files")
    parser.add_argument('--dump', action='store_true', help='Only generate final data to stdout')
    parser.add_argument('--json', action='store_true', help='Only generate JSON to stdout')
    parser.add_argument('--plot', action='store_true', help='Generate plots in test_result')
    parser.add_argument('--no-engine', dest='engine', action='store_false',
                        help='Skip the pure Python Engine benchmark')
    parser.set_defaults(engine=True)
    parser.add_argument('--no-rx-prop', dest='rx_prop', action='store_false',
                        help='Skip Reactor BFS propagate (SIMULATE mode) benchmark')
    parser.set_defaults(rx_prop=True)
    parser.add_argument('--no-rx-sweep', dest='rx_sweep', action='store_false',
                        help='Skip Reactor sweep (COMPILE mode) benchmark')
    parser.set_defaults(rx_sweep=True)
    parser.add_argument('--no-rx-oop', dest='rx_oop', action='store_false',
                        help='Skip ReactorOOP benchmark')
    parser.set_defaults(rx_oop=True)
    parser.add_argument('--no-icarus', dest='icarus', action='store_false',
                        help='Skip Icarus Verilog benchmark')
    parser.set_defaults(icarus=True)

    parser.add_argument('--internal-worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--mode',    type=str, choices=['engine', 'reactor', 'reactor_oop'], help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.internal_worker:
        internal_worker_main(args.target, args.mode, args.vectors, args.warmup, args.optimize, args.rx_prop, args.rx_sweep)
        sys.exit(0)

    if not args.target:
        print("[-] Error: No target path specified."); sys.exit(1)

    if getattr(args, 'dump', False) and not hasattr(args, 'json'):
        pass

    measured    = args.vectors - args.warmup
    if measured <= 0:
        print(f"[-] Error: --warmup ({args.warmup}) must be < --vectors ({args.vectors})"); sys.exit(1)

    v_files = get_v_files(args.target)
    if not v_files:
        print("[-] Error: No .v files found."); sys.exit(1)

    W = 175
    cols1 = (
        f"| {'Circuit':<16} "
        f"| {'Engine':^10} "
        f"| {'Reactor':^11} | {'':<12} "
        f"| {'ReactorOOP':^14} |"
        f" {'Icarus':^14} |"
    )
    sep = (
        f"|{'-'*18}"
        f"|{'-'*12}"
        f"|{'-'*13}|{'-'*14}"
        f"|{'-'*16}|"
        f"{'-'*16}|"
    )
    cols2 = (
        f"| {'':<16} "
        f"| {'Time(ms)':>10} "
        f"| {'prop(ms)':>11} | {'sweep(ms)':>12} "
        f"| {'prop(ms)':>14} |"
        f" {'sim(ms)':>14} |"
    )

    if not getattr(args, 'json', False):
        print("=" * W)
        print("  UNIFIED 3-ENGINE LOGIC SIMULATOR BENCHMARK  (harness-based, warmup-symmetric)")
        print(f"  Total vectors  : {args.vectors:,}  |  Warmup (untimed): {args.warmup:,}  |  Measured: {measured:,}")
        print(f"  Circuits       : {len(v_files)}")
        print(cols1)
        print(sep)
        print(cols2)

    all_results = []
    md_lines = []
    md_lines.append("# Unified 3-Engine Logic Simulator Benchmark")
    md_lines.append("")
    md_lines.append(f"- **Total vectors**: {args.vectors:,} (Warmup: {args.warmup:,}, Measured: {measured:,})")
    md_lines.append(f"- **Circuits**: {len(v_files)}")
    md_lines.append(f"- **Icarus VPI**: {'enabled' if os.path.exists(_VPI_TIMER_VPI) else 'disabled'}")
    md_lines.append("")
    md_lines.append(cols1)
    md_lines.append(sep)
    md_lines.append(cols2)

    for filepath in v_files:
        filename = os.path.basename(filepath)

        if args.engine:
            e_res = run_python_backend_process(filepath, 'engine',  args.vectors, args.warmup, args.optimize, args.rx_prop, args.rx_sweep)
        else:
            e_res = {"engine": "Engine", "file": filename, "error": "disabled"}
        if args.rx_prop or args.rx_sweep:
            r_res = run_python_backend_process(filepath, 'reactor', args.vectors, args.warmup, args.optimize, args.rx_prop, args.rx_sweep)
        else:
            r_res = {"engine": "Reactor", "file": filename, "error": "disabled"}
        if args.rx_oop:
            ro_res = run_python_backend_process(filepath, 'reactor_oop', args.vectors, args.warmup, args.optimize, True, False)
        else:
            ro_res = {"engine": "ReactorOOP", "file": filename, "error": "disabled"}
        if args.icarus:
            i_res = run_icarus_harness(filepath, args.vectors, args.warmup)
        else:
            i_res = {"engine": "Icarus", "file": filename, "error": "disabled"}

        e_str      = f"{e_res['time_ms']:.1f}"       if 'error' not in e_res else "N/A"
        r_str      = f"{r_res['time_ms']:.1f}"       if 'error' not in r_res else "N/A"
        rs_str     = (f"{r_res['sweep_ms']:.1f}"     if 'sweep_ms'    in r_res
                      else ("N/A" if 'sweep_error' in r_res else "N/A"))
        ro_str     = f"{ro_res['time_ms']:.1f}"      if 'error' not in ro_res else "N/A"
        i_sim_str  = f"{i_res['time_ms']:.1f}"       if 'error' not in i_res else "N/A"

        # Eval counts sub-line — widths match the timing columns exactly:
        # Engine(ms)=10, Rx-prop(ms)=11, Rx-sweep(ms)=12
        e_ev   = f"{e_res.get('total_evals', 0):>10,}" if 'error' not in e_res else f"{'N/A':>10}"
        r_ev   = f"{r_res.get('total_evals', 0):>11,}" if 'error' not in r_res else f"{'N/A':>11}"
        rs_ev  = (f"{r_res['sweep_evals']:>12,}"        if 'sweep_evals' in r_res
                  else (f"{'N/A':>12}" if 'sweep_error' in r_res else f"{'N/A':>12}"))
        ro_ev  = f"{ro_res.get('total_evals', 0):>14,}" if 'error' not in ro_res else f"{'N/A':>14}"

        row_str = (
            f"| {filename:<16} | "
            f"{e_str:>10} | {r_str:>11} | {rs_str:>12} | "
            f"{ro_str:>14} | "
            f"{i_sim_str:>14} |"
        )
        md_lines.append(row_str)
        evals_str = f"| {'evals':<16} | {e_ev} | {r_ev} | {rs_ev} | {ro_ev} | {'-':>14} |"
        md_lines.append(evals_str)

        if not getattr(args, 'json', False):
            print(row_str)
            print(evals_str)
            sys.stdout.flush()
        all_results.append((filename, e_res, r_res, ro_res, i_res))

    if getattr(args, 'json', False):
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        circuits_data = [{"circuit": fn, "engine": e, "reactor": r, "reactor_oop": ro, "icarus": i} for fn, e, r, ro, i in all_results]
        payload = {
            "meta": {"timestamp": ts, "target": args.target, "total_vectors": args.vectors, "warmup_vectors": args.warmup, "measured_vectors": measured, "optimize": args.optimize, "harness": getattr(args, 'harness', None), "jar": getattr(args, 'jar', None)},
            "circuits": circuits_data
        }
        print(json.dumps(payload, indent=4), file=sys.__stdout__)
        
    if not getattr(args, 'json', False):
        print("=" * W)
        md_lines = [
            "# Unified 3-Engine Logic Simulator Benchmark", "",
            f"- **Total vectors**: {args.vectors:,} (Warmup: {args.warmup:,}, Measured: {measured:,})",
            f"- **Circuits**: {len(v_files)}",
            f"- **Icarus VPI**: {'enabled' if os.path.exists(_VPI_TIMER_VPI) else 'disabled'}", ""
        ]
        _print_speedup_report(all_results, md_lines)

    if getattr(args, 'dump', False):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dump_dir = os.path.join(script_dir, 'test_result', 'benchmark')
        os.makedirs(dump_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_path = os.path.join(dump_dir, f"unified_iscas_benchmark_{timestamp}.md")
        with open(dump_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(md_lines) + "\n")
        print(f"\n[+] Markdown dump saved to -> {dump_path}")

    if not getattr(args, 'json', False):
        _save_results(all_results, args)


def _print_speedup_report(all_results: list, md_lines: list = None):
    import math

    W = 175
    print()
    if md_lines is not None:
        md_lines.append("")

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
        f"{'RxOOP(ms)':<11} | {'RxO-eval':<10} | {'RxO-spd':<10}"
    )
    print(hdr)
    print("-" * W)
    if md_lines is not None:
        md_lines.append(f"| {hdr} |")
        md_lines.append(f"|{'-'*18}|{'-'*12}|{'-'*12}|{'-'*12}|{'-'*10}|{'-'*13}|{'-'*12}|{'-'*13}|{'-'*14}|{'-'*12}|{'-'*12}|{'-'*13}|{'-'*12}|{'-'*12}|")

    engine_speedups        = []
    reactor_prop_speedups  = []
    reactor_sweep_speedups = []
    reactor_oop_speedups   = []

    for filename, e_res, r_res, ro_res, i_res in all_results:
        i_ms  = i_res.get('time_ms', None)
        e_ms  = e_res.get('time_ms', None)
        r_ms  = r_res.get('time_ms', None)
        rs_ms = r_res.get('sweep_ms', None)
        ro_ms = ro_res.get('time_ms', None)

        e_spd  = i_ms / e_ms  if i_ms is not None and e_ms is not None and e_ms > 0 else None
        r_spd  = i_ms / r_ms  if i_ms is not None and r_ms is not None and r_ms > 0 else None
        rs_spd = i_ms / rs_ms if i_ms is not None and rs_ms is not None and rs_ms > 0 else None
        ro_spd = i_ms / ro_ms if i_ms is not None and ro_ms is not None and ro_ms > 0 else None

        if e_spd is not None: engine_speedups.append(e_spd)
        if r_spd is not None: reactor_prop_speedups.append(r_spd)
        if rs_spd is not None: reactor_sweep_speedups.append(rs_spd)
        if ro_spd is not None: reactor_oop_speedups.append(ro_spd)

        i_ms_str   = f"{i_ms:.2f}" if i_ms is not None else "N/A"
        e_ms_str   = f"{e_ms:.1f}" if e_ms is not None else "N/A"
        e_spd_str  = f"{e_spd:.1f}x" if e_spd is not None else "N/A"
        r_ms_str   = f"{r_ms:.1f}" if r_ms is not None else "N/A"
        r_spd_str  = f"{r_spd:.1f}x" if r_spd is not None else "N/A"
        rs_ms_str  = f"{rs_ms:.1f}" if rs_ms is not None else "N/A"
        rs_spd_str = f"{rs_spd:.1f}x" if rs_spd is not None else "N/A"
        ro_ms_str  = f"{ro_ms:.1f}" if ro_ms is not None else "N/A"
        ro_spd_str = f"{ro_spd:.1f}x" if ro_spd is not None else "N/A"

        e_ev_str   = f"{e_res.get('total_evals', 0):,}" if 'error' not in e_res else "N/A"
        r_ev_str   = f"{r_res.get('total_evals', 0):,}" if 'error' not in r_res else "N/A"
        rs_ev_str  = (f"{r_res['sweep_evals']:,}"       if 'sweep_evals' in r_res
                      else ("N/A" if 'sweep_error' in r_res else "N/A"))
        ro_ev_str  = f"{ro_res.get('total_evals', 0):,}" if 'error' not in ro_res else "N/A"

        row = (
            f"{filename:<16} | "
            f"{i_ms_str:>10} | "
            f"{e_ms_str:>10} | {e_ev_str:>10} | {e_spd_str:>8} | "
            f"{r_ms_str:>11} | {r_ev_str:>10} | {r_spd_str:>11} | "
            f"{rs_ms_str:>12} | {rs_ev_str:>10} | {rs_spd_str:>10} | "
            f"{ro_ms_str:>11} | {ro_ev_str:>10} | {ro_spd_str:>10}"
        )
        print(row)
        if md_lines is not None:
            md_lines.append(f"| {row} |")

    if True:
        geo_mean = lambda xs: math.exp(sum(math.log(x) for x in xs) / len(xs))
        g_e  = geo_mean(engine_speedups) if engine_speedups else None
        g_r  = geo_mean(reactor_prop_speedups) if reactor_prop_speedups else None
        g_rs = geo_mean(reactor_sweep_speedups) if reactor_sweep_speedups else None
        g_ro = geo_mean(reactor_oop_speedups) if reactor_oop_speedups else None
        print("-" * W)
        g_e_str  = f"{g_e:.1f}x" if g_e is not None else "N/A"
        g_r_str  = f"{g_r:.1f}x" if g_r is not None else "N/A"
        g_rs_str = f"{g_rs:.1f}x" if g_rs is not None else "N/A"
        g_ro_str = f"{g_ro:.1f}x" if g_ro is not None else "N/A"
        summary = (
            f"{'Geo-mean speedup':<16} | {'(baseline)':<10} | "
            f"{'':<10} | {'':<10} | {g_e_str:>8} | "
            f"{'':<11} | {'':<10} | {g_r_str:>11} | "
            f"{'':<12} | {'':<10} | {g_rs_str:>10} | "
            f"{'':<11} | {'':<10} | {g_ro_str:>10}"
        )
        print(summary)
        print("=" * W)
        if md_lines is not None:
            md_summary = (
                f"| **Geo-mean speedup** | **(baseline)** | "
                f"{'':<10} | {'':<10} | {g_e_str:>8} | "
                f"{'':<11} | {'':<10} | {g_r_str:>11} | "
                f"{'':<12} | {'':<10} | {g_rs_str:>10} | "
                f"{'':<11} | {'':<10} | {g_ro_str:>10} |"
            )
            md_lines.append(md_summary)

def _save_results(all_results: list, args):
    import math
    import datetime

    base = args.output
    json_path = base if base.endswith('.json') else base + '.json'
    txt_path  = (base[:-5] if base.endswith('.json') else base) + '.txt'

    measured = args.vectors - args.warmup
    ts       = datetime.datetime.now(datetime.timezone.utc).isoformat()

    circuits_data = []
    for filename, e_res, r_res, ro_res, i_res in all_results:
        circuits_data.append({
            "circuit":  filename,
            "engine":   e_res,
            "reactor":  r_res,
            "reactor_oop": ro_res,
            "icarus":   i_res,
        })

    valid = all_results
    speedup_summary = None
    if valid:
        geo_mean   = lambda xs: math.exp(sum(math.log(x) for x in xs) / len(xs))
        e_spds  = [i.get('time_ms') / e.get('time_ms')  for _, e, r, ro, i in valid if i.get('time_ms') and e.get('time_ms') and e.get('time_ms') > 0]
        r_spds  = [i.get('time_ms') / r.get('time_ms')  for _, e, r, ro, i in valid if i.get('time_ms') and r.get('time_ms') and r.get('time_ms') > 0]
        rs_spds = [i.get('time_ms') / r.get('sweep_ms') for _, e, r, ro, i in valid if i.get('time_ms') and r.get('sweep_ms') and r.get('sweep_ms') > 0]
        ro_spds = [i.get('time_ms') / ro.get('time_ms') for _, e, r, ro, i in valid if i.get('time_ms') and ro.get('time_ms') and ro.get('time_ms') > 0]

        speedup_summary = {
            "valid_circuits":                    len(valid),
            "engine_geo_mean_speedup":            round(geo_mean(e_spds),   3) if e_spds  else None,
            "reactor_propagate_geo_mean_speedup": round(geo_mean(r_spds),   3) if r_spds  else None,
            "reactor_sweep_geo_mean_speedup":     round(geo_mean(rs_spds),  3) if rs_spds else None,
            "reactor_oop_geo_mean_speedup":       round(geo_mean(ro_spds),  3) if ro_spds else None,
            "icarus_geo_mean_speedup":            None,
        }

    payload = {
        "meta": {
            "timestamp":        ts,
            "target":           args.target,
            "total_vectors":    args.vectors,
            "warmup_vectors":   args.warmup,
            "measured_vectors": measured,
            "optimize":         args.optimize,

        },
        "circuits":        circuits_data,
        "speedup_summary": speedup_summary,
    }

    # with open(json_path, 'w', encoding='utf-8') as f:
    #     json.dump(payload, f, indent=2)
    # print(f"\n[+] Full results saved -> {json_path}")

    W = 175
    lines = []
    lines.append("=" * W)
    lines.append("  UNIFIED LOGIC SIMULATOR BENCHMARK")
    lines.append(f"  Timestamp      : {ts}")
    lines.append(f"  Target         : {args.target}")
    lines.append(f"  Total vectors  : {args.vectors:,}  |  Warmup (untimed): {args.warmup:,}  |  Measured: {measured:,}")
    lines.append(f"  Circuits       : {len(all_results)}")
    lines.append(f"  Optimize       : {args.optimize}")
    lines.append("  Reactor modes  : propagate = BFS wavefront (SIMULATE mode)")
    lines.append("                   sweep     = linear fwd-pass (COMPILE mode, requires topo-sorted infolist)")
    lines.append("=" * W)

    hdr = (
        f"{'Circuit':<16} | "
        f"{'Engine(ms)':<10} | {'Rx-prop(ms)':<11} | {'Rx-sweep(ms)':<12} | "
        f"{'RxOOP(ms)':<11} | "
        f"{'Icarus-sim(ms)':<14}"
    )
    lines.append(hdr)
    lines.append("-" * W)
    for filename, e_res, r_res, ro_res, i_res in all_results:
        e_str   = f"{e_res['time_ms']:.1f}"     if 'error' not in e_res else "N/A"
        r_str   = f"{r_res['time_ms']:.1f}"     if 'error' not in r_res else "N/A"
        rs_str  = (f"{r_res['sweep_ms']:.1f}"   if 'sweep_ms' in r_res
                   else ("N/A" if 'sweep_error' in r_res else "N/A"))
        ro_str  = f"{ro_res['time_ms']:.1f}"    if 'error' not in ro_res else "N/A"
        i_s_str = f"{i_res['time_ms']:.1f}"     if 'error' not in i_res else "N/A"
        lines.append(
            f"{filename:<16} | "
            f"{e_str:>10} | {r_str:>11} | {rs_str:>12} | "
            f"{ro_str:>11} | "
            f"{i_s_str:>14}"
        )
    lines.append("=" * W)

    if True:
        lines.append("")
        lines.append("=" * W)
        lines.append("  SPEEDUP ANALYSIS vs ICARUS BASELINE  (Icarus = 1.00x)")
        lines.append("=" * W)
        spd_hdr = (
            f"{'Circuit':<16} | "
            f"{'Icarus(ms)':<11} | {'Engine(ms)':<10} | {'Eng-spd':<8} | "
            f"{'Rx-prop(ms)':<11} | {'Rx-prop-spd':<11} | "
            f"{'Rx-sweep(ms)':<12} | {'Rx-swp-spd':<10} | "
            f"{'RxOOP(ms)':<11} | {'RxOOP-spd':<10}"
        )
        lines.append(spd_hdr)
        lines.append("-" * W)

        g_e_spds  = []
        g_r_spds  = []
        g_rs_spds = []
        g_ro_spds = []

        for fn, e, r, ro, i in valid:
            i_ms  = i.get('time_ms', None)
            e_ms  = e.get('time_ms', None)
            r_ms  = r.get('time_ms', None)
            rs_ms = r.get('sweep_ms', None)
            ro_ms = ro.get('time_ms', None)

            e_spd  = i_ms / e_ms  if i_ms is not None and e_ms is not None and e_ms > 0 else None
            r_spd  = i_ms / r_ms  if i_ms is not None and r_ms is not None and r_ms > 0 else None
            rs_spd = i_ms / rs_ms if i_ms is not None and rs_ms is not None and rs_ms > 0 else None
            ro_spd = i_ms / ro_ms if i_ms is not None and ro_ms is not None and ro_ms > 0 else None

            if e_spd is not None: g_e_spds.append(e_spd)
            if r_spd is not None: g_r_spds.append(r_spd)
            if rs_spd is not None: g_rs_spds.append(rs_spd)
            if ro_spd is not None: g_ro_spds.append(ro_spd)

            i_ms_str   = f"{i_ms:.1f}" if i_ms is not None else "N/A"
            e_ms_str   = f"{e_ms:.1f}" if e_ms is not None else "N/A"
            e_spd_str  = f"{e_spd:.1f}x" if e_spd is not None else "N/A"
            r_ms_str   = f"{r_ms:.1f}" if r_ms is not None else "N/A"
            r_spd_str  = f"{r_spd:.1f}x" if r_spd is not None else "N/A"
            rs_ms_str  = f"{rs_ms:.1f}" if rs_ms is not None else "N/A"
            rs_spd_str = f"{rs_spd:.1f}x" if rs_spd is not None else "N/A"
            ro_ms_str  = f"{ro_ms:.1f}" if ro_ms is not None else "N/A"
            ro_spd_str = f"{ro_spd:.1f}x" if ro_spd is not None else "N/A"

            lines.append(
                f"{fn:<16} | "
                f"{i_ms_str:>11} | {e_ms_str:>10} | {e_spd_str:>8} | "
                f"{r_ms_str:>11} | {r_spd_str:>11} | "
                f"{rs_ms_str:>12} | {rs_spd_str:>10} | "
                f"{ro_ms_str:>11} | {ro_spd_str:>10}"
            )

        geo_mean = lambda xs: math.exp(sum(math.log(x) for x in xs) / len(xs))
        g_e  = geo_mean(g_e_spds)  if g_e_spds  else None
        g_r  = geo_mean(g_r_spds)  if g_r_spds  else None
        g_rs = geo_mean(g_rs_spds) if g_rs_spds else None
        g_ro = geo_mean(g_ro_spds) if g_ro_spds else None

        lines.append("-" * W)
        g_e_str  = f"{g_e:.1f}x"  if g_e  is not None else "N/A"
        g_r_str  = f"{g_r:.1f}x"  if g_r  is not None else "N/A"
        g_rs_str = f"{g_rs:.1f}x" if g_rs is not None else "N/A"
        g_ro_str = f"{g_ro:.1f}x" if g_ro is not None else "N/A"
        lines.append(
            f"{'Geo-mean speedup':<16} | {'(baseline)':<11} | "
            f"{'':>10} | {g_e_str:>8} | "
            f"{'':>11} | {g_r_str:>11} | "
            f"{'':>12} | {g_rs_str:>10} | "
            f"{'':>11} | {g_ro_str:>10}"
        )
        lines.append("=" * W)

    meps_valid = [(fn, e, r, ro, i) for fn, e, r, ro, i in all_results if 'error' not in e and 'error' not in r]
    if meps_valid:
        lines.append("")
        lines.append("=" * W)
        lines.append("  THROUGHPUT & EVALUATION COUNTS  (MEPS = Mega Gate-Evaluations Per Second)")
        lines.append("=" * W)
        # Header: Circuit | Engine evals | Engine MEPS | Rx-prop evals | Rx-prop MEPS | Rx-sweep evals | Rx-sweep MEPS | RxOOP evals | RxOOP MEPS
        meps_hdr = (
            f"{'Circuit':<16} | "
            f"{'Eng-evals':<16} | {'Eng-MEPS':<9} | "
            f"{'Rx-prop-evals':<16} | {'Rx-p-MEPS':<9} | "
            f"{'Rx-swp-evals':<16} | {'Rx-s-MEPS':<9} | "
            f"{'RxOOP-evals':<16} | {'RxO-MEPS':<9}"
        )
        lines.append(meps_hdr)
        lines.append("-" * W)
        for fn, e, r, ro, i in meps_valid:
            e_ev    = f"{e.get('total_evals', 0):,}"        if 'error' not in e else "N/A"
            e_meps  = f"{e.get('meps', 0):.2f}"             if 'error' not in e else "N/A"
            r_ev    = f"{r.get('total_evals', 0):,}"        if 'error' not in r else "N/A"
            r_meps  = f"{r.get('meps', 0):.2f}"             if 'error' not in r else "N/A"
            rs_ev   = (f"{r.get('sweep_evals', 0):,}"       if 'sweep_evals' in r
                       else ("N/A" if 'sweep_error' in r else "N/A"))
            rs_meps = (f"{r.get('sweep_meps', 0):.2f}"      if 'sweep_meps' in r
                       else ("N/A" if 'sweep_error' in r else "N/A"))
            ro_ev   = f"{ro.get('total_evals', 0):,}"       if 'error' not in ro else "N/A"
            ro_meps = f"{ro.get('meps', 0):.2f}"            if 'error' not in ro else "N/A"
            lines.append(
                f"{fn:<16} | "
                f"{e_ev:>16} | {e_meps:>9} | "
                f"{r_ev:>16} | {r_meps:>9} | "
                f"{rs_ev:>16} | {rs_meps:>9} | "
                f"{ro_ev:>16} | {ro_meps:>9}"
            )
        lines.append("=" * W)

    lines.append("")
    lines.append("=" * W)
    lines.append("  BENCHMARK SUMMARY")
    lines.append("=" * W)
    total_circuits = len(all_results)
    ok_e  = sum(1 for _, e, r, ro, i in all_results if 'error' not in e)
    ok_r  = sum(1 for _, e, r, ro, i in all_results if 'error' not in r)
    ok_ro = sum(1 for _, e, r, ro, i in all_results if 'error' not in ro)
    ok_i  = sum(1 for _, e, r, ro, i in all_results if 'error' not in i)
    ok_rs = sum(1 for _, e, r, ro, i in all_results if 'sweep_ms' in r)
    lines.append(f"  Circuits tested       : {total_circuits}")
    lines.append(f"  Engine results OK     : {ok_e}/{total_circuits}")
    lines.append(f"  Reactor (prop) OK     : {ok_r}/{total_circuits}")
    lines.append(f"  Reactor (sweep) OK    : {ok_rs}/{total_circuits}")
    lines.append(f"  ReactorOOP OK         : {ok_ro}/{total_circuits}")
    lines.append(f"  Icarus results OK     : {ok_i}/{total_circuits}")
    lines.append("")
    if speedup_summary:
        ss = speedup_summary
        e_geo  = ss.get('engine_geo_mean_speedup')
        rp_geo = ss.get('reactor_propagate_geo_mean_speedup')
        rs_geo = ss.get('reactor_sweep_geo_mean_speedup')
        lines.append("  Geo-mean speedup over Icarus baseline:")
        lines.append(f"    Engine (propagate)   : {e_geo:.2f}x"  if e_geo  else "    Engine              : N/A")
        lines.append(f"    Reactor (propagate)  : {rp_geo:.2f}x" if rp_geo else "    Reactor (propagate) : N/A")
        lines.append(f"    Reactor (sweep)      : {rs_geo:.2f}x" if rs_geo else "    Reactor (sweep)     : N/A")
        ro_geo = ss.get('reactor_oop_geo_mean_speedup')
        lines.append(f"    ReactorOOP           : {ro_geo:.2f}x" if ro_geo else "    ReactorOOP          : N/A")
        lines.append("")
        if rp_geo and rs_geo:
            ratio = rs_geo / rp_geo
            lines.append(f"  Reactor sweep vs propagate speedup ratio : {ratio:.2f}x  ({'sweep faster' if ratio > 1 else 'propagate faster'})")
            lines.append("  (sweep = single linear forward-pass; faster for dense fan-out after optimize()")
            lines.append("   propagate = BFS wavefront; more efficient when sparse changes propagate partially)")
            lines.append("")
        if rp_geo and e_geo:
            r_vs_e = rp_geo / e_geo
            lines.append(f"  Reactor propagate vs Engine speedup ratio : {r_vs_e:.2f}x  (Cython reactor vs pure-Python engine)")
            lines.append("")
    lines.append("  Methodology:")
    lines.append("    - All engines use the same PRNG seed (42) and identical vector sequences.")
    lines.append("    - Warmup vectors are run untimed; GC is disabled during the measurement window.")
    lines.append("    - Engine/Reactor: timing covers only the core batch_toggle loop.")
    lines.append("    - Reactor propagate: SIMULATE mode, BFS double-buffer wavefront per toggle.")
    lines.append("    - Reactor sweep: COMPILE mode, single forward-pass over sorted gate list.")
    lines.append("      sweep() requires optimize() to have run first (topological order).")
    lines.append("    - Icarus: VPI inner-loop timer (QueryPerformanceCounter) excludes $readmemb.")
    lines.append("=" * W)
    # with open(txt_path, 'w', encoding='utf-8') as f:
    #     f.write('\n'.join(lines) + '\n')
    # print(f"[+] Human-readable results saved -> {txt_path}")


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
    import sys
    
    if '--json' in sys.argv:
        import os
        sys.stdout = open(os.devnull, 'w')

    try:
        main()
    finally:
        if sys.stdout is not _orig:
            sys.stdout.close()
        sys.stdout = _orig
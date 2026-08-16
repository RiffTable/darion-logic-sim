"""
unified_iscas_benchmark.py  (v5 — 4-Engine Comparison: Python, Cython, Logisim, Icarus Verilog)
===============================================================================================
Unified benchmark runner comparing four simulation engines on identical ISCAS datasets:
  1. Pure Python Engine
  2. Cython Reactor (Data-Oriented Design with batch_toggle)
  3. Logisim-Evolution via LogisimBenchmarkHarness.java
  4. Icarus Verilog (iverilog compiler + vvp runtime execution)

Methodology:
  - Logisim: custom Java harness embeds Logisim as a library. Untimed JIT warm-up
    + System.gc(); timed simulation window measured with System.nanoTime().
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
try:
    from verilog_to_circ import convert_file, vector_file_path
except ImportError:
    try:
        from tests.verilog_to_circ import convert_file, vector_file_path
    except ImportError:
        convert_file = None
        vector_file_path = None


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
# 2. LOGISIM HARNESS RUNNER  (no overhead calibration needed)
# ===========================================================================

def run_logisim_harness(v_file: str, harness_cp: str, vectors: int, warmup: int) -> dict:
    """Run the custom Java benchmark harness for Logisim-Evolution."""
    filename  = os.path.basename(v_file)
    circ_file = os.path.splitext(v_file)[0] + "_converted.circ"
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
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1200)
        except subprocess.TimeoutExpired:
            return {"engine": "Logisim", "file": filename,
                    "error": "Logisim benchmark execution timed out (limit: 1200s)"}

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
        meps             = (total_evals / (net_ms / 1000.0)) / 1_000_000.0 if net_ms > 0 else 0.0

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
# 3. INTERNAL WORKER FOR ENGINE / REACTOR ISOLATED RUNS
# ===========================================================================

class VerilogRunner:
    def __init__(self, v_file_path, circuit_cls, const_mod, is_reactor=True):
        self.Circuit = circuit_cls
        self.const = const_mod
        self.circuit = self.Circuit()
        self.is_reactor = is_reactor
        self.nodes = {}
        self.outputs = []

        self.VERILOG_GATE_MAP = {
            'and': self.const.AND_ID, 'nand': self.const.NAND_ID, 'or': self.const.OR_ID,
            'nor': self.const.NOR_ID, 'xor': self.const.XOR_ID, 'xnor': self.const.XNOR_ID, 'not': self.const.NOT_ID
        }

        self.input_vars = []

        self._parse_verilog(v_file_path)

    def _parse_verilog(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'//.*', '', content)
        statements = [s.strip() for s in content.split(';') if s.strip()]
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
                    if p.strip(): self.outputs.append(p.strip())
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

    def run_benchmark(self, vectors=10000, warmup=5000, use_optimize=True):
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
                batch.append((var_node.location, val))
            all_instructions.append(batch)
        warmup_batches   = all_instructions[:warmup]
        measured_batches = all_instructions[warmup:]

        flat_warmup_batches = [item for sublist in warmup_batches for item in sublist]
        flat_measured_batches = [item for sublist in measured_batches for item in sublist]
        batch_size = len(self.input_vars)

        # ── PASS 1: propagate (SIMULATE / BFS wavefront) ─────────────────────
        self.circuit.simulate(self.const.SIMULATE)

        if flat_warmup_batches:
            self.circuit.batch_toggle(flat_warmup_batches, batch_size)

        gc.collect()
        self.circuit.eval_count = 0
        gc.disable()

        propagate_ms = self.circuit.batch_toggle(flat_measured_batches, batch_size) if flat_measured_batches else 0.0

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
        if has_sweep:
            try:
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
                
                sweep_ms = self.circuit.batch_toggle(flat_measured_batches, batch_size) if flat_measured_batches else 0.0

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


def run_python_backend_process(filepath: str, mode: str, vectors: int, warmup: int, optimize: bool) -> dict:
    cmd = [
        sys.executable, os.path.abspath(__file__),
        "--internal-worker", filepath,
        "--mode", mode,
        "--vectors", str(vectors),
        "--warmup", str(warmup),
    ]
    if optimize:
        cmd.append("--optimize")

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            return json.loads(res.stdout)
        else:
            return {"error": res.stderr.strip() or "Worker process failed"}
    except Exception as e:
        return {"error": str(e)}


def internal_worker_main(filepath: str, mode: str, vectors: int, warmup: int, optimize: bool):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    target_path = os.path.join(script_dir, mode)
    if not os.path.exists(target_path):
        target_path = os.path.join(project_root, mode)

    sys.path.insert(0, project_root)
    sys.path.insert(0, target_path)
    import Circuit
    import Const

    is_reactor = (mode == 'reactor')
    try:
        runner = VerilogRunner(filepath, Circuit.Circuit, Const, is_reactor=is_reactor)
        stats = runner.run_benchmark(vectors=vectors, warmup=warmup, use_optimize=optimize)
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
        description="Unified 4-Engine ISCAS Logic Sim Benchmark (Engine, Reactor, Logisim, Icarus)"
    )
    parser.add_argument('target', nargs='?', type=str, help="Path to .v file or directory")
    parser.add_argument('--jar',     type=str, default="logisim-evolution.jar", help="Path to logisim-evolution JAR")
    parser.add_argument('--harness', type=str, default="harness_build", help="Directory containing LogisimBenchmarkHarness.class")
    parser.add_argument('--vectors', type=int, default=50000, help="Total vectors per circuit (warmup + measured)")
    parser.add_argument('--warmup',  type=int, default=5000,  help="Untimed warmup vectors (same for all engines)")
    parser.add_argument('--optimize', action='store_true', help="Enable topological optimization in Engine/Reactor")
    parser.add_argument('--output',  type=str, default="iscas_results", help="Base path for output files")
    parser.add_argument('--dump', action='store_true', help='Dump output to time-stamped txt in test_results')
    parser.add_argument('--plot', action='store_true', help='Generate plots in test_results')
    parser.add_argument('--no-logisim', dest='logisim', action='store_false',
                        help='Skip the Logisim-Evolution benchmark engine')
    parser.set_defaults(logisim=True)

    parser.add_argument('--internal-worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--mode',    type=str, choices=['engine', 'reactor'], help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.internal_worker:
        internal_worker_main(args.target, args.mode, args.vectors, args.warmup, args.optimize)
        sys.exit(0)

    if not args.target:
        print("[-] Error: No target path specified."); sys.exit(1)

    if getattr(args, 'dump', False):
        import datetime
        dump_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_results', 'unified_iscas_benchmark', 'datas')
        os.makedirs(dump_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = os.path.join(dump_dir, f"unified_iscas_benchmark_{timestamp}")

    harness_dir = os.path.abspath(args.harness)
    if not os.path.exists(harness_dir) and not os.path.isabs(args.harness):
        alt_harness = os.path.join(_PROJECT_ROOT, args.harness)
        if os.path.exists(alt_harness):
            harness_dir = alt_harness

    jar_path = os.path.abspath(args.jar)
    if not os.path.exists(jar_path) and not os.path.isabs(args.jar):
        alt_jar = os.path.join(_PROJECT_ROOT, args.jar)
        if os.path.exists(alt_jar):
            jar_path = alt_jar

    harness_cp  = jar_path + os.pathsep + harness_dir
    measured    = args.vectors - args.warmup
    if measured <= 0:
        print(f"[-] Error: --warmup ({args.warmup}) must be < --vectors ({args.vectors})"); sys.exit(1)

    v_files = get_v_files(args.target)
    if not v_files:
        print("[-] Error: No .v files found."); sys.exit(1)

    W = 180
    print("=" * W)
    print("  UNIFIED 4-ENGINE LOGIC SIMULATOR BENCHMARK  (harness-based, warmup-symmetric)")
    print(f"  Total vectors  : {args.vectors:,}  |  Warmup (untimed): {args.warmup:,}  |  Measured: {measured:,}")
    print(f"  Circuits       : {len(v_files)}")
    print(f"  Harness class  : {os.path.join(harness_dir, 'LogisimBenchmarkHarness.class')}")
    vpi_status = "enabled (inner-loop VPI timer)" if os.path.exists(_VPI_TIMER_VPI) else "disabled (fallback to vvp wall time)"
    print(f"  Icarus VPI     : {vpi_status}")
    print("  Reactor modes  : propagate (BFS wavefront, SIMULATE) | sweep (linear fwd-pass, COMPILE)")
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

        e_res = run_python_backend_process(filepath, 'engine',  args.vectors, args.warmup, args.optimize)
        r_res = run_python_backend_process(filepath, 'reactor', args.vectors, args.warmup, args.optimize)
        if args.logisim:
            l_res = run_logisim_harness(filepath, harness_cp, args.vectors, args.warmup)
        else:
            l_res = {"engine": "Logisim", "file": filename, "error": "disabled"}
        i_res = run_icarus_harness(filepath, args.vectors, args.warmup)

        e_str      = f"{e_res['time_ms']:.1f}"       if 'error' not in e_res else "ERR"
        r_str      = f"{r_res['time_ms']:.1f}"       if 'error' not in r_res else "ERR"
        rs_str     = (f"{r_res['sweep_ms']:.1f}"     if 'sweep_ms'    in r_res
                      else ("ERR" if 'sweep_error' in r_res else "N/A"))
        l_str      = f"{l_res['time_ms']:.1f}"       if 'error' not in l_res else "ERR"
        i_sim_str  = f"{i_res['time_ms']:.2f}"       if 'error' not in i_res else "ERR"

        # Eval counts sub-line — widths match the timing columns exactly:
        # Engine(ms)=10, Rx-prop(ms)=11, Rx-sweep(ms)=12
        e_ev   = f"{e_res.get('total_evals', 0):>10,}" if 'error' not in e_res else f"{'ERR':>10}"
        r_ev   = f"{r_res.get('total_evals', 0):>11,}" if 'error' not in r_res else f"{'ERR':>11}"
        rs_ev  = (f"{r_res['sweep_evals']:>12,}"        if 'sweep_evals' in r_res
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
    _save_results(all_results, args)


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

def _save_results(all_results: list, args):
    import math
    import datetime

    base = args.output
    json_path = base if base.endswith('.json') else base + '.json'
    txt_path  = (base[:-5] if base.endswith('.json') else base) + '.txt'

    measured = args.vectors - args.warmup
    ts       = datetime.datetime.now(datetime.timezone.utc).isoformat()

    circuits_data = []
    for filename, e_res, r_res, l_res, i_res in all_results:
        circuits_data.append({
            "circuit":  filename,
            "engine":   e_res,
            "reactor":  r_res,
            "logisim":  l_res,
            "icarus":   i_res,
        })

    valid = [
        (fn, e, r, l, i) for fn, e, r, l, i in all_results
        if 'error' not in e and 'error' not in r and 'error' not in l
    ]
    speedup_summary = None
    if valid:
        geo_mean   = lambda xs: math.exp(sum(math.log(x) for x in xs) / len(xs))
        e_spds  = [l['time_ms'] / e['time_ms']  for _, e, r, l, _ in valid if e['time_ms']  > 0]
        r_spds  = [l['time_ms'] / r['time_ms']  for _, e, r, l, _ in valid if r['time_ms']  > 0]
        rs_spds = [l['time_ms'] / r.get('sweep_ms', 0)
                   for _, e, r, l, _ in valid if r.get('sweep_ms', 0) > 0]
        i_spds  = [l['time_ms'] / i['time_ms']
                   for _, e, r, l, i in valid
                   if 'error' not in i and i.get('time_ms', 0) > 0]

        speedup_summary = {
            "valid_circuits":                    len(valid),
            "engine_geo_mean_speedup":            round(geo_mean(e_spds),   3) if e_spds  else None,
            "reactor_propagate_geo_mean_speedup": round(geo_mean(r_spds),   3) if r_spds  else None,
            "reactor_sweep_geo_mean_speedup":     round(geo_mean(rs_spds),  3) if rs_spds else None,
            "icarus_geo_mean_speedup":            round(geo_mean(i_spds),   3) if i_spds  else None,
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
        },
        "circuits":        circuits_data,
        "speedup_summary": speedup_summary,
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
    print(f"\n[+] Full results saved -> {json_path}")

    W = 170
    lines = []
    lines.append("=" * W)
    lines.append("  UNIFIED 4-ENGINE LOGIC SIMULATOR BENCHMARK")
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
        f"{'Logisim(ms)':<11} | {'Icarus-sim(ms)':<14}"
    )
    lines.append(hdr)
    lines.append("-" * W)
    for filename, e_res, r_res, l_res, i_res in all_results:
        e_str   = f"{e_res['time_ms']:.1f}"     if 'error' not in e_res else "ERR"
        r_str   = f"{r_res['time_ms']:.1f}"     if 'error' not in r_res else "ERR"
        rs_str  = (f"{r_res['sweep_ms']:.1f}"   if 'sweep_ms' in r_res
                   else ("ERR" if 'sweep_error' in r_res else "N/A"))
        l_str   = f"{l_res['time_ms']:.1f}"     if 'error' not in l_res else "ERR"
        i_s_str = f"{i_res['time_ms']:.1f}"     if 'error' not in i_res else "ERR"
        lines.append(
            f"{filename:<16} | "
            f"{e_str:>10} | {r_str:>11} | {rs_str:>12} | "
            f"{l_str:>11} | {i_s_str:>14}"
        )
    lines.append("=" * W)

    if valid:
        lines.append("")
        lines.append("=" * W)
        lines.append("  SPEEDUP ANALYSIS vs LOGISIM BASELINE  (Logisim = 1.00x)")
        lines.append("=" * W)
        spd_hdr = (
            f"{'Circuit':<16} | "
            f"{'Logisim(ms)':<11} | {'Engine(ms)':<10} | {'Eng-spd':<8} | "
            f"{'Rx-prop(ms)':<11} | {'Rx-prop-spd':<11} | "
            f"{'Rx-sweep(ms)':<12} | {'Rx-swp-spd':<10} | "
            f"{'Icarus-sim(ms)':<14} | {'Icar-spd':<8}"
        )
        lines.append(spd_hdr)
        lines.append("-" * W)

        g_e_spds  = []
        g_r_spds  = []
        g_rs_spds = []
        g_i_spds  = []

        for fn, e, r, l, i in valid:
            l_ms  = l['time_ms']
            e_ms  = e['time_ms']
            r_ms  = r['time_ms']
            rs_ms = r.get('sweep_ms', None)
            i_ms  = i.get('time_ms') if 'error' not in i else None

            e_spd  = l_ms / e_ms  if e_ms  > 0 else 0.0
            r_spd  = l_ms / r_ms  if r_ms  > 0 else 0.0
            rs_spd = l_ms / rs_ms if rs_ms and rs_ms > 0 else None
            i_spd  = l_ms / i_ms  if i_ms  and i_ms > 0 else None

            g_e_spds.append(e_spd)
            g_r_spds.append(r_spd)
            if rs_spd is not None: g_rs_spds.append(rs_spd)
            if i_spd  is not None: g_i_spds.append(i_spd)

            rs_ms_str  = f"{rs_ms:.1f}"   if rs_ms  is not None else "N/A"
            rs_spd_str = f"{rs_spd:.1f}x" if rs_spd is not None else "N/A"
            i_ms_str   = f"{i_ms:.1f}"    if i_ms   is not None else "N/A"
            i_spd_str  = f"{i_spd:.1f}x"  if i_spd  is not None else "N/A"

            lines.append(
                f"{fn:<16} | "
                f"{l_ms:>11.1f} | {e_ms:>10.1f} | {e_spd:>7.1f}x | "
                f"{r_ms:>11.1f} | {r_spd:>10.1f}x | "
                f"{rs_ms_str:>12} | {rs_spd_str:>10} | "
                f"{i_ms_str:>14} | {i_spd_str:>8}"
            )

        geo_mean = lambda xs: math.exp(sum(math.log(x) for x in xs) / len(xs))
        g_e  = geo_mean(g_e_spds)  if g_e_spds  else None
        g_r  = geo_mean(g_r_spds)  if g_r_spds  else None
        g_rs = geo_mean(g_rs_spds) if g_rs_spds else None
        g_i  = geo_mean(g_i_spds)  if g_i_spds  else None

        lines.append("-" * W)
        g_e_str  = f"{g_e:.1f}x"  if g_e  is not None else "N/A"
        g_r_str  = f"{g_r:.1f}x"  if g_r  is not None else "N/A"
        g_rs_str = f"{g_rs:.1f}x" if g_rs is not None else "N/A"
        g_i_str  = f"{g_i:.1f}x"  if g_i  is not None else "N/A"
        lines.append(
            f"{'Geo-mean speedup':<16} | {'(baseline)':<11} | "
            f"{'':>10} | {g_e_str:>8} | "
            f"{'':>11} | {g_r_str:>11} | "
            f"{'':>12} | {g_rs_str:>10} | "
            f"{'':>14} | {g_i_str:>8}"
        )
        lines.append("=" * W)

    meps_valid = [(fn, e, r, l, i) for fn, e, r, l, i in all_results if 'error' not in e and 'error' not in r]
    if meps_valid:
        lines.append("")
        lines.append("=" * W)
        lines.append("  THROUGHPUT & EVALUATION COUNTS  (MEPS = Mega Gate-Evaluations Per Second)")
        lines.append("=" * W)
        # Header: Circuit | Engine evals | Engine MEPS | Rx-prop evals | Rx-prop MEPS | Rx-sweep evals | Rx-sweep MEPS | Logisim evals | Logisim MEPS
        meps_hdr = (
            f"{'Circuit':<16} | "
            f"{'Eng-evals':<16} | {'Eng-MEPS':<9} | "
            f"{'Rx-prop-evals':<16} | {'Rx-p-MEPS':<9} | "
            f"{'Rx-swp-evals':<16} | {'Rx-s-MEPS':<9} | "
            f"{'Lsim-evals':<14} | {'Lsim-MEPS':<9}"
        )
        lines.append(meps_hdr)
        lines.append("-" * W)
        for fn, e, r, l, i in meps_valid:
            e_ev    = f"{e.get('total_evals', 0):,}"        if 'error' not in e else "ERR"
            e_meps  = f"{e.get('meps', 0):.2f}"             if 'error' not in e else "ERR"
            r_ev    = f"{r.get('total_evals', 0):,}"        if 'error' not in r else "ERR"
            r_meps  = f"{r.get('meps', 0):.2f}"             if 'error' not in r else "ERR"
            rs_ev   = (f"{r.get('sweep_evals', 0):,}"       if 'sweep_evals' in r
                       else ("ERR" if 'sweep_error' in r else "N/A"))
            rs_meps = (f"{r.get('sweep_meps', 0):.2f}"      if 'sweep_meps' in r
                       else ("ERR" if 'sweep_error' in r else "N/A"))
            l_ev    = f"{l.get('total_evals', 0):,}"        if 'error' not in l else "ERR"
            l_meps  = f"{l.get('meps', 0):.2f}"             if 'error' not in l else "ERR"
            lines.append(
                f"{fn:<16} | "
                f"{e_ev:>16} | {e_meps:>9} | "
                f"{r_ev:>16} | {r_meps:>9} | "
                f"{rs_ev:>16} | {rs_meps:>9} | "
                f"{l_ev:>14} | {l_meps:>9}"
            )
        lines.append("=" * W)

    lines.append("")
    lines.append("=" * W)
    lines.append("  BENCHMARK SUMMARY")
    lines.append("=" * W)
    total_circuits = len(all_results)
    ok_e  = sum(1 for _, e, r, l, i in all_results if 'error' not in e)
    ok_r  = sum(1 for _, e, r, l, i in all_results if 'error' not in r)
    ok_l  = sum(1 for _, e, r, l, i in all_results if 'error' not in l)
    ok_i  = sum(1 for _, e, r, l, i in all_results if 'error' not in i)
    ok_rs = sum(1 for _, e, r, l, i in all_results if 'sweep_ms' in r)
    lines.append(f"  Circuits tested       : {total_circuits}")
    lines.append(f"  Engine results OK     : {ok_e}/{total_circuits}")
    lines.append(f"  Reactor (prop) OK     : {ok_r}/{total_circuits}")
    lines.append(f"  Reactor (sweep) OK    : {ok_rs}/{total_circuits}")
    lines.append(f"  Logisim results OK    : {ok_l}/{total_circuits}")
    lines.append(f"  Icarus results OK     : {ok_i}/{total_circuits}")
    lines.append("")
    if speedup_summary:
        ss = speedup_summary
        e_geo  = ss.get('engine_geo_mean_speedup')
        rp_geo = ss.get('reactor_propagate_geo_mean_speedup')
        rs_geo = ss.get('reactor_sweep_geo_mean_speedup')
        i_geo  = ss.get('icarus_geo_mean_speedup')
        lines.append("  Geo-mean speedup over Logisim baseline:")
        lines.append(f"    Engine (propagate)   : {e_geo:.2f}x"  if e_geo  else "    Engine              : N/A")
        lines.append(f"    Reactor (propagate)  : {rp_geo:.2f}x" if rp_geo else "    Reactor (propagate) : N/A")
        lines.append(f"    Reactor (sweep)      : {rs_geo:.2f}x" if rs_geo else "    Reactor (sweep)     : N/A")
        lines.append(f"    Icarus Verilog       : {i_geo:.2f}x"  if i_geo  else "    Icarus Verilog      : N/A")
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
    lines.append("    - Logisim: Java harness with JIT warmup + System.nanoTime timed window.")
    lines.append("    - Icarus: VPI inner-loop timer (QueryPerformanceCounter) excludes $readmemb.")
    lines.append("=" * W)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(f"[+] Human-readable results saved -> {txt_path}")


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
    _lf = None
    import sys
    
    # We delay argument parsing to main, but we can do a quick check for --dump to wrap sys.stdout
    if '--dump' in sys.argv:
        import os
        import datetime
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dump_dir = os.path.join(script_dir, 'test_results', 'unified_iscas_benchmark', 'datas')
        os.makedirs(dump_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        _LOG = os.path.join(dump_dir, f"unified_iscas_benchmark_stdout_{timestamp}.txt")
        _lf = open(_LOG, "a", encoding="utf-8")
        sys.stdout = _Tee(_orig, _lf)

    try:
        main()
    finally:
        sys.stdout = _orig
        if _lf:
            _lf.close()
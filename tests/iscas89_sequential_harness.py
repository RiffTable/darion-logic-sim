"""
iscas89_sequential_harness.py
==============================
Icarus Verilog harness for ISCAS89 sequential circuits.

Generates a timing-instrumented testbench with:
  - Proper DFF model injection (if not already defined in the netlist)
  - Clock-aware vector pairs (setup @ CLK=0, trigger @ CLK=1)
  - VPI inner-loop timer support ($start_timer / $stop_timer via vpi_timer.vpi)
  - 50-cycle warmup (inputs=0, alternating clock) to flush DFF states

This module is used by unified_iscas_benchmark_89.py as the Icarus engine runner.
It can also be used standalone for timing individual sequential circuits.

Usage:
    from iscas89_sequential_harness import run_icarus_harness_89
    result = run_icarus_harness_89('/path/to/s27.v', vectors=5000, warmup=500)
    print(result)
"""

import os
import re
import sys
import time
import random
import shutil
import subprocess

_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

# VPI timer paths (shared with the combinational benchmark)
_VPI_DIR       = (os.path.join(_SCRIPT_DIR, "harness_build")
                  if os.path.exists(os.path.join(_SCRIPT_DIR, "harness_build"))
                  else os.path.join(_PROJECT_ROOT, "harness_build"))
_VPI_TIMER_C   = os.path.join(_VPI_DIR, "vpi_timer.c")
_VPI_TIMER_VPI = os.path.join(_VPI_DIR, "vpi_timer.vpi")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def parse_verilog_ports_89(v_file: str):
    """
    Extract module name, ordered input ports, and ordered output ports from an
    ISCAS89 sequential Verilog file.  Skips inner 'dff' module definitions so
    only the main circuit module's ports are returned.
    """
    with open(v_file, 'r', encoding='utf-8') as f:
        content = f.read()

    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'//.*', '', content)

    module_name = "circuit"
    module_body = content

    for m in re.finditer(r'\bmodule\s+([a-zA-Z0-9_]+)(.*?)\bendmodule\b',
                         content, flags=re.DOTALL):
        if m.group(1).lower() != 'dff':
            module_name = m.group(1)
            module_body = m.group(0)
            break

    def extract_ports(keyword):
        ports = []
        for m in re.finditer(r'\b' + keyword + r'\s+([^;]+);', module_body):
            decl = m.group(1).strip()
            cleaned = re.sub(
                r'(\[[^\]]+\]|\bwire\b|\breg\b|\blogic\b|\bsigned\b|\bunsigned\b)',
                '', decl).strip()
            for p in cleaned.split(','):
                p = p.strip()
                if p and p not in ports:
                    ports.append(p)
        return ports

    return module_name, extract_ports('input'), extract_ports('output')


def _find_clock_idx(inputs: list) -> int:
    """Return the index of the clock port, or -1 if not found."""
    for idx, inp in enumerate(inputs):
        if inp.lower() in ('ck', 'clk', 'clock', 'g0'):
            return idx
    return -1


# ---------------------------------------------------------------------------
# Testbench generator
# ---------------------------------------------------------------------------

def generate_icarus_tb_89(v_file: str, tb_file: str,
                           measured: int, vector_file: str,
                           use_vpi_timer: bool = True):
    """
    Generate a Verilog testbench for ISCAS89 sequential circuits.

    Vector format
    -------------
    Each entry in 'vector_file' is a packed binary string of all inputs
    (rightmost bit = inputs[0]).  The caller writes ONLY the measured
    (post-warmup) vectors; 50 warmup cycles are driven inline in the
    testbench with inputs=0 and alternating clock before $readmemb.

    Timing instrumentation
    ----------------------
    When use_vpi_timer=True:
      - $start_timer() fires AFTER $readmemb (disk I/O excluded)
      - $stop_timer()  fires AFTER the simulation loop (before $finish)
    This isolates the pure simulation throughput, matching Engine/Reactor.
    """
    module_name, inputs, outputs = parse_verilog_ports_89(v_file)
    clock_idx = _find_clock_idx(inputs)

    # Read the original netlist content
    with open(v_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Inject 'initial Q = 0' into any embedded dff module that lacks it
    if not re.search(r'\binitial\s+Q\s*=\s*0\b', content):
        content = re.sub(
            r'(?i)(\bmodule\s+dff\b.*?)\balways\b',
            r'\1initial Q = 0;\n    always',
            content, flags=re.DOTALL)

    tb = [content, "\n"]
    tb.append("`timescale 1ns/1ps\n")
    tb.append(f"module tb_{module_name};\n")

    for inp in inputs:
        tb.append(f"    reg {inp};\n")
    for outp in outputs:
        tb.append(f"    wire {outp};\n")

    total_inputs = len(inputs)
    tb.append(f"    reg [{total_inputs-1}:0] test_vectors [0:{measured-1}];\n")
    tb.append("    integer i;\n\n")

    # Instantiate DUT
    tb.append(f"    {module_name} uut (\n")
    conn = [f"        .{p}({p})" for p in inputs + outputs]
    tb.append(",\n".join(conn))
    tb.append("\n    );\n\n")

    v_path_str = str(vector_file).replace("\\", "/")

    tb.append("    initial begin\n")

    # --- 50-cycle warmup inline (no timer, inputs = 0, clock alternates) ---
    # Initialise all regs to 0
    for inp in inputs:
        tb.append(f"        {inp} = 0;\n")
    tb.append("        // 50-cycle warmup: flush DFF state\n")
    tb.append("        repeat (50) begin\n")
    if clock_idx != -1:
        clk_name = inputs[clock_idx]
        tb.append(f"            {clk_name} = 0; #1;\n")
        tb.append(f"            {clk_name} = 1; #1;\n")
    else:
        tb.append("            #1;\n")
    tb.append("        end\n\n")

    # Load measured vectors (disk I/O happens here, before the timer)
    tb.append(f'        $readmemb("{v_path_str}", test_vectors);\n')

    # VPI timer starts AFTER $readmemb
    if use_vpi_timer:
        tb.append("        $start_timer();\n")

    tb.append(f"        for (i = 0; i < {measured}; i = i + 1) begin\n")
    for idx, inp in enumerate(inputs):
        tb.append(f"            {inp} = test_vectors[i][{idx}];\n")
    tb.append("            #1;\n")
    tb.append("        end\n")

    # VPI timer stops AFTER loop
    if use_vpi_timer:
        tb.append("        $stop_timer();\n")

    tb.append("        $finish;\n")
    tb.append("    end\n")
    tb.append("endmodule\n")

    # Inject DFF model if the netlist doesn't define one
    has_dff_def = re.search(r'\bmodule\s+(?i:dff)\b', content)
    if not has_dff_def:
        tb.append("\n// Injected DFF model for Icarus Verilog ISCAS89 Testing\n")
        tb.append("module DFF (input CK, output reg Q, input D);\n")
        tb.append("    initial Q = 0;\n")
        tb.append("    always @(posedge CK) Q <= D;\n")
        tb.append("endmodule\n")
        tb.append("module dff (input CK, output reg Q, input D);\n")
        tb.append("    initial Q = 0;\n")
        tb.append("    always @(posedge CK) Q <= D;\n")
        tb.append("endmodule\n")

    with open(tb_file, 'w', encoding='utf-8') as f:
        f.write("".join(tb))

    return module_name, inputs, outputs


# ---------------------------------------------------------------------------
# Main harness runner
# ---------------------------------------------------------------------------

def run_icarus_harness_89(v_file: str, vectors: int, warmup: int) -> dict:
    """
    Compile and run an ISCAS89 sequential circuit with Icarus Verilog.

    Vector strategy
    ---------------
    For sequential circuits, each "logical" test vector is split into a pair:
      setup   : data inputs randomised, clock = 0  (data settles)
      trigger : same data inputs, clock = 1        (rising edge, DFF captures)

    The testbench drives ``measured`` physical vectors from the file (which
    already contain the paired clock encoding).  Warmup (50 cycles) is driven
    inline in the testbench before $readmemb so the warm-up cost is not timed.

    Timing strategy
    ---------------
    compile_ms : iverilog wall time
    sim_ms     : VPI inner-loop (QueryPerformanceCounter inside vvp) —
                 measured AFTER $readmemb, excludes warmup, disk I/O, teardown
    run_ms     : total vvp wall time
    total_ms   : compile_ms + run_ms

    Returns a dict with keys: engine, file, compile_ms, run_ms, total_ms,
    time_ms (= sim_ms if VPI available, else run_ms), vpi_timer, error (if any)
    """
    filename    = os.path.basename(v_file)
    base_path   = os.path.splitext(v_file)[0]
    tb_file     = base_path + "_89bench_tb.v"
    vvp_file    = base_path + "_89bench.vvp"
    vector_file = base_path + "_89bench_vectors.txt"

    if not shutil.which("iverilog") or not shutil.which("vvp"):
        return {
            "engine": "Icarus",
            "file":   filename,
            "error":  "iverilog or vvp command not found in PATH"
        }

    # Build VPI timer if needed (one-time, cached)
    use_vpi = build_vpi_timer()

    try:
        t_start_total = time.perf_counter_ns()
        module_name, inputs, outputs = parse_verilog_ports_89(v_file)
        clock_idx = _find_clock_idx(inputs)

        # ── Generate measured vectors (clock-paired) ──────────────────────────
        # Each logical vector → 2 physical vectors (CLK=0 setup, CLK=1 trigger)
        # warmup is handled inline in the testbench, NOT written to the file.
        logical_count = max(vectors - warmup, 1)
        rng = random.Random(42)

        physical_vectors = []
        for _ in range(logical_count):
            base_vec = [rng.randint(0, 1) for _ in range(len(inputs))]

            if clock_idx != -1:
                setup = list(base_vec)
                setup[clock_idx] = 0
                trigger = list(base_vec)
                trigger[clock_idx] = 1
                physical_vectors.append(setup)
                physical_vectors.append(trigger)
            else:
                physical_vectors.append(base_vec)

        measured = len(physical_vectors)

        # Write packed binary vector file (rightmost bit = inputs[0])
        with open(vector_file, 'w', encoding='utf-8') as f:
            for vec in physical_vectors:
                bin_str = "".join(str(v) for v in reversed(vec))
                f.write(bin_str + "\n")

        # ── Generate testbench ────────────────────────────────────────────────
        generate_icarus_tb_89(v_file, tb_file, measured, vector_file,
                               use_vpi_timer=use_vpi)

        # ── Compile ───────────────────────────────────────────────────────────
        t_comp_start = time.perf_counter_ns()
        comp_res = subprocess.run(
            ["iverilog", "-o", vvp_file, tb_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        t_comp_end = time.perf_counter_ns()
        compile_ms = (t_comp_end - t_comp_start) / 1_000_000.0

        if comp_res.returncode != 0:
            return {"engine": "Icarus", "file": filename,
                    "error": f"Compile failure: {comp_res.stderr.strip()}"}

        # ── Execute ───────────────────────────────────────────────────────────
        if use_vpi:
            run_cmd = ["vvp", "-M", _VPI_DIR, "-mvpi_timer", vvp_file]
        else:
            run_cmd = ["vvp", vvp_file]

        t_run_start = time.perf_counter_ns()
        run_res = subprocess.run(
            run_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        t_run_end = time.perf_counter_ns()
        run_ms = (t_run_end - t_run_start) / 1_000_000.0

        t_end_total = time.perf_counter_ns()
        total_ms_overall = (t_end_total - t_start_total) / 1_000_000.0

        if run_res.returncode != 0:
            return {"engine": "Icarus", "file": filename,
                    "error": f"Run failure: {run_res.stderr.strip()}"}

        # ── Parse VPI inner-loop time from stdout ($ELAPSED_NS:<value>) ───────
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
            "engine":           "Icarus",
            "file":             filename,
            "compile_ms":       compile_ms,
            "run_ms":           run_ms,
            "total_ms":         compile_ms + run_ms,
            "vpi_timer":        use_vpi,
            "logical_vectors":  logical_count,
            "physical_vectors": measured,
        }
        if sim_ms is not None:
            result["time_ms"] = sim_ms
        else:
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


# ---------------------------------------------------------------------------
# CLI (standalone usage)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse, json

    ap = argparse.ArgumentParser(
        description="Icarus Verilog harness for ISCAS89 sequential circuits"
    )
    ap.add_argument("v_file", type=str, help="Path to ISCAS89 .v file")
    ap.add_argument("--vectors", type=int, default=5000,
                    help="Total vectors (warmup + measured logical)")
    ap.add_argument("--warmup",  type=int, default=500,
                    help="Logical warmup vectors (50 extra hardware cycles driven inline)")
    args = ap.parse_args()

    result = run_icarus_harness_89(args.v_file, args.vectors, args.warmup)
    print(json.dumps(result, indent=2))

import os
import sys
import subprocess
import glob
import re
import datetime
import argparse

if sys.platform != "linux":
    print("Error: Hardware profiling ('perf' and FIFOs) is Linux-exclusive. Aborting.")
    sys.exit(0)

parser = argparse.ArgumentParser(description="Multi-engine hardware profiling")
parser.add_argument("--vectors", type=int, default=5000, help="Number of test vectors (default: 500)")
parser.add_argument("--filter", type=str, default="", help="Filter circuits by name (e.g., 'voter')")
parser.add_argument("--limit", type=int, default=None, help="Limit number of circuits tested")
args = parser.parse_args()

CIRCUITS = sorted(glob.glob("tests/ISCAS85/*.v"), key=lambda x: os.path.getsize(x))
if args.filter:
    CIRCUITS = [c for c in CIRCUITS if args.filter in os.path.basename(c)]
if args.limit is not None:
    CIRCUITS = CIRCUITS[:args.limit]

EVENTS = "L1-dcache-loads:u,L1-dcache-load-misses:u,l2_cache_req_stat.ic_dc_miss_in_l2:u,cache-misses:u,ex_ret_brn:u,ex_ret_brn_misp:u,instructions:u,cycles:u"
VECTORS = args.vectors

ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
os.makedirs("tests/test_result/perf", exist_ok=True)
REPORT_FILE = f"tests/test_result/perf/perf_report_{ts}.md"

header = f"| {'Circuit':<10} | {'IPC':<5} | {'Branch':<8} | {'Brn Miss':<8} | {'L1 Load':<8} | {'L1 Hit%':<8} | {'L2 Load':<8} | {'L2 Hit%':<8} | {'L3/RAM Load':<12} |"
divider = f"|{'-'*12}|{'-'*7}|{'-'*10}|{'-'*10}|{'-'*10}|{'-'*10}|{'-'*10}|{'-'*10}|{'-'*14}|"

print("Collecting full multi-engine hardware profiling... This will take a few minutes.\n")

results = {"engine": [], "prop": [], "sweep": [], "oop": [], "icarus": []}

for c_path in CIRCUITS:
    c_name = os.path.basename(c_path)
    if "c17" in c_name: continue
    print(f"Profiling {c_name}...")
    
    fifo_path = "/tmp/rx_perf_ctrl"
    if os.path.exists(fifo_path):
        try: os.remove(fifo_path)
        except: pass
    os.mkfifo(fifo_path)
    
    # PASS 1: Run unified benchmark which internally traces all engines separately
    cmd_record = [
        "python3", "tests/benchmark.py", c_path,
        "--vectors", str(VECTORS), "--warmup", "10", "--optimize", "--json", "--no-engine",
        "--perf", "--perf-events", EVENTS
    ]
    subprocess.run(cmd_record, capture_output=True)
    
    # Parse individual reports
    engine_stats = {"engine": {}, "prop": {}, "sweep": {}, "oop": {}, "icarus": {}}
    
    report_files = {
        "engine": f"perf_engine_prop_{c_name}.txt",
        "prop": f"perf_reactor_prop_{c_name}.txt",
        "sweep": f"perf_reactor_sweep_{c_name}.txt",
        "oop": f"perf_reactor_oop_prop_{c_name}.txt",
        "icarus": f"perf_icarus_{c_name}.txt"
    }

    for eng, rep_file in report_files.items():
        if os.path.exists(rep_file):
            with open(rep_file, "r", encoding="utf-8") as f:
                current_event = None
                for line in f:
                    m_event = re.search(r"# Samples: .* of event '(.*?)'", line)
                    if m_event:
                        current_event = m_event.group(1)
                        continue
                    m_total = re.search(r"# Event count \(approx\.\):\s+(\d+)", line)
                    if m_total and current_event:
                        engine_stats[eng][current_event] = int(m_total.group(1))
            os.remove(rep_file)

    def fmt(n):
        if n >= 1e9: return f"{n/1e9:.2f}B"
        if n >= 1e6: return f"{n/1e6:.2f}M"
        if n >= 1e3: return f"{n/1e3:.2f}K"
        return str(n)

    for engine in ["engine", "prop", "sweep", "oop", "icarus"]:
        def get_count(evt):
            return engine_stats[engine].get(evt, 0)

        l1_load = get_count("L1-dcache-loads:u") or get_count("L1-dcache-loads")
        l1_miss = get_count("L1-dcache-load-misses:u") or get_count("L1-dcache-load-misses")
        l2_miss = get_count("l2_cache_req_stat.ic_dc_miss_in_l2:u") or get_count("l2_cache_req_stat.ic_dc_miss_in_l2")
        l3_miss = get_count("cache-misses:u") or get_count("cache-misses")
        brn = get_count("ex_ret_brn:u")
        brn_miss = get_count("ex_ret_brn_misp:u")
        inst = get_count("instructions:u") or get_count("instructions")
        cyc = get_count("cycles:u") or get_count("cycles")
        
        l1_hit = max(0, l1_load - l1_miss)
        l2_hit = max(0, l1_miss - l2_miss)
        l3_hit = max(0, l2_miss - l3_miss)
        
        ipc = inst / cyc if cyc > 0 else 0
        brn_hr = ((brn - brn_miss) / brn * 100) if brn > 0 else 0
        l1_hr = (l1_hit / l1_load * 100) if l1_load > 0 else 0
        l2_hr = (l2_hit / l1_miss * 100) if l1_miss > 0 else 0
        l3_hr = (l3_hit / l2_miss * 100) if l2_miss > 0 else 0
        
        row_str = f"| {c_name:<10} | {ipc:>5.2f} | {fmt(brn):<8} | {fmt(brn_miss):<8} | {fmt(l1_load):<8} | {l1_hr:>7.2f}% | {fmt(l1_miss):<8} | {l2_hr:>7.2f}% | {fmt(l2_miss):<12} |"
        results[engine].append(row_str)

with open(REPORT_FILE, "w") as f:
    f.write("# Hardware Profiling\n\n")
    f.write(f"**Test Parameters:**\n- **Vectors simulated:** {VECTORS:,}\n\n")
    f.write("Extracted purely from hardware counters (`perf`) to isolate the true computational core of each simulation engine, bypassing Python and Icarus VPI harness overhead.\n\n")
    
    for engine, title in [("icarus", "Icarus Verilog (`vvp`)"), ("engine", "Pure Python Engine"), ("prop", "Reactor: `rx-prop` (Wavefront BFS)"), ("oop", "Reactor OOP: (Wavefront BFS)"), ("sweep", "Reactor: `rx-sweep` (Linear Compiled)")]:
        f.write(f"## {title}\n\n")
        f.write(header + "\n")
        f.write(divider + "\n")
        for row in results[engine]:
            f.write(row + "\n")
        f.write("\n")

print(f"\n[+] Multi-engine report generated and saved to {REPORT_FILE}")

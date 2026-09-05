import os
import sys
import subprocess
import glob
import re
import datetime

if sys.platform != "linux":
    print("Error: Hardware profiling ('perf' and FIFOs) is Linux-exclusive. Aborting.")
    sys.exit(0)

CIRCUITS = sorted(glob.glob("tests/ISCAS85/*.v"), key=lambda x: os.path.getsize(x))
EVENTS = "L1-dcache-loads:u,L1-dcache-load-misses:u,l2_cache_req_stat.ic_dc_miss_in_l2:u,cache-misses:u,ex_ret_brn:u,ex_ret_brn_misp:u,instructions:u,cycles:u"
VECTORS = 10000

ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
os.makedirs("tests/test_result/perf", exist_ok=True)
REPORT_FILE = f"tests/test_result/perf/perf_report_{ts}.md"

header = f"| {'Circuit':<10} | {'IPC':<5} | {'Branch':<8} | {'L1 Load':<8} | {'L1 Hit%':<8} | {'L2 Load':<8} | {'L2 Hit%':<8} | {'L3/RAM Load':<12} |"
divider = f"|{'-'*12}|{'-'*7}|{'-'*10}|{'-'*10}|{'-'*10}|{'-'*10}|{'-'*10}|{'-'*14}|"

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
    
    # PASS 1: Pure Python Engine (isolated via internal worker)
    cmd_engine = [
        "perf", "record", "-D", "-1", f"--control=fifo:{fifo_path}", "-e", EVENTS, "-o", "perf_engine.data",
        "--", "python3", "tests/benchmark.py", "--internal-worker", c_path,
        "--mode", "engine", "--vectors", str(VECTORS), "--warmup", "100"
    ]
    if os.path.exists("perf_engine.data"): os.remove("perf_engine.data")
    subprocess.run(cmd_engine, capture_output=True)
    
    res_engine = subprocess.run(["perf", "report", "-i", "perf_engine.data", "--stdio", "--no-children", "--percent-limit=0.01"], capture_output=True, text=True)
    stats_eng = {}
    current_event = None
    for line in res_engine.stdout.split("\n"):
        m_event = re.search(r"# Samples: .* of event '(.*?)'", line)
        if m_event:
            current_event = m_event.group(1)
            continue
        m_total = re.search(r"# Event count \(approx\.\):\s+(\d+)", line)
        if m_total:
            stats_eng[current_event] = {"total": int(m_total.group(1))}

    # PASS 1.5: Reactor OOP
    cmd_oop = [
        "perf", "record", "-D", "-1", f"--control=fifo:{fifo_path}", "-e", EVENTS, "-o", "perf_oop.data",
        "--", "python3", "tests/benchmark.py", "--internal-worker", c_path,
        "--mode", "reactor_oop", "--vectors", str(VECTORS), "--warmup", "100",
        "--no-rx-sweep"
    ]
    if os.path.exists("perf_oop.data"): os.remove("perf_oop.data")
    subprocess.run(cmd_oop, capture_output=True)
    
    res_oop = subprocess.run(["perf", "report", "-i", "perf_oop.data", "--stdio", "--no-children", "--percent-limit=0.01"], capture_output=True, text=True)
    stats_oop = {}
    current_event = None
    for line in res_oop.stdout.split("\n"):
        m_event = re.search(r"# Samples: .* of event '(.*?)'", line)
        if m_event:
            current_event = m_event.group(1)
            continue
        m_total = re.search(r"# Event count \(approx\.\):\s+(\d+)", line)
        if m_total:
            stats_oop[current_event] = {"total": int(m_total.group(1))}

    
    # PASS 2: Reactor + Icarus
    cmd_record = [
        "perf", "record", "-D", "-1", f"--control=fifo:{fifo_path}", "-e", EVENTS, "-o", "perf_tmp.data",
        "--", "python3", "tests/benchmark.py", c_path,
        "--vectors", str(VECTORS), "--warmup", "100", "--optimize", "--no-engine", "--json"
    ]
    if os.path.exists("perf_tmp.data"): os.remove("perf_tmp.data")
    subprocess.run(cmd_record, capture_output=True)
    if os.path.exists(fifo_path):
        try: os.remove(fifo_path)
        except: pass
        
    cmd_report = ["perf", "report", "-i", "perf_tmp.data", "--stdio", "--no-children", "--percent-limit=0.01"]
    res = subprocess.run(cmd_report, capture_output=True, text=True)
    output = res.stdout
    
    stats = {}
    current_event = None
    
    for line in output.split("\n"):
        m_event = re.search(r"# Samples: .* of event '(.*?)'", line)
        if m_event:
            current_event = m_event.group(1)
            continue
            
        m_total = re.search(r"# Event count \(approx\.\):\s+(\d+)", line)
        if m_total:
            stats[current_event] = {"total": int(m_total.group(1)), "prop": 0.0, "sweep": 0.0, "icarus": 0.0}
            continue
            
        if current_event:
            m_pct = re.search(r"^\s*([0-9\.]+)\%", line)
            if m_pct:
                pct = float(m_pct.group(1))
                if "Circuit_propagate" in line:
                    stats[current_event]["prop"] += pct
                elif "Circuit_sweep" in line:
                    stats[current_event]["sweep"] += pct
                elif " vvp " in line or re.search(r"^\s*[0-9\.]+\%\s+(vvp|:\d+)\s+", line):
                    stats[current_event]["icarus"] += pct

    def fmt(n):
        if n >= 1e9: return f"{n/1e9:.2f}B"
        if n >= 1e6: return f"{n/1e6:.2f}M"
        if n >= 1e3: return f"{n/1e3:.2f}K"
        return str(n)

    for engine in ["engine", "prop", "sweep", "oop", "icarus"]:
        def get_count(evt):
            if engine == "engine":
                if evt not in stats_eng: return 0
                return stats_eng[evt]["total"]
            elif engine == "oop":
                if evt not in stats_oop: return 0
                return stats_oop[evt]["total"]
            else:
                if evt not in stats: return 0
                return int(stats[evt]["total"] * (stats[evt][engine] / 100.0))

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
        
        row_str = f"| {c_name:<10} | {ipc:>5.2f} | {fmt(brn):<8} | {fmt(l1_load):<8} | {l1_hr:>7.2f}% | {fmt(l1_miss):<8} | {l2_hr:>7.2f}% | {fmt(l2_miss):<12} |"
        results[engine].append(row_str)

if os.path.exists("perf_tmp.data"): os.remove("perf_tmp.data")
if os.path.exists("perf_engine.data"): os.remove("perf_engine.data")

with open(REPORT_FILE, "w") as f:
    f.write("# Hardware Profiling\n\n")
    f.write(f"**Test Parameters:**\n- **Vectors simulated:** {VECTORS:,}\n\n")
    f.write("Extracted purely from hardware counters (`perf`) to isolate the true computational core of each simulation engine, bypassing Python and Icarus VPI harness overhead.\n\n")
    
    for engine, title in [("engine", "Pure Python Engine"), ("prop", "Reactor: `rx-prop` (Wavefront BFS)"), ("sweep", "Reactor: `rx-sweep` (Linear Compiled)"), ("oop", "Reactor OOP: (Wavefront BFS)"), ("icarus", "Icarus Verilog (`vvp`)")]:
        f.write(f"## {title}\n\n")
        f.write(header + "\n")
        f.write(divider + "\n")
        for row in results[engine]:
            f.write(row + "\n")
        f.write("\n")

print(f"\n[+] Multi-engine report generated and saved to {REPORT_FILE}")

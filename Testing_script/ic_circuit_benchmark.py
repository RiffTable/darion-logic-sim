"""
DARION LOGIC SIM — IC & CIRCUIT BENCHMARK SUITE
===============================================
Benchmarks both Engine and Reactor backends for:
  1. IC Creation & Loading
  2. Full Circuit Creation & Loading

Run:
  python Testing_script/ic_circuit_benchmark.py
"""

import sys
import os
import time
import gc
import tempfile
import platform
import statistics

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


# ─── PATH SETUP ───────────────────────────────────────────────────
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
sys.path.append(os.path.join(root_dir, 'control'))


# ─── UTILITIES ────────────────────────────────────────────────────

def format_time(ms):
    """Format time in ms with adaptive units."""
    if ms >= 1000:
        return f"{ms / 1000:.3f} s"
    elif ms >= 0.1:
        return f"{ms:.2f} ms"
    elif ms >= 0.001:
        return f"{ms * 1000:.1f} µs"
    else:
        return f"{ms * 1_000_000:.0f} ns"


def timed(func, warmup=0):
    """Run func with GC disabled, return elapsed ms."""
    for _ in range(warmup):
        func()

    gc_was = gc.isenabled()
    gc.disable()
    start = time.perf_counter_ns()
    result = func()
    end = time.perf_counter_ns()
    if gc_was:
        gc.enable()
    return (end - start) / 1_000_000, result


def divider(char='═', width=85):
    return char * width


def header(title, char='═', width=85):
    pad = (width - len(title) - 2) // 2
    return f"{char * pad} {title} {char * (width - pad - len(title) - 2)}"


# ─── BACKEND LOADER ──────────────────────────────────────────────

def load_backend(use_reactor):
    """Load engine or reactor backend, return module dict."""
    for mod_name in ['Circuit', 'IC', 'Const', 'Gates', 'Store']:
        if mod_name in sys.modules:
            del sys.modules[mod_name]

    engine_path = os.path.join(root_dir, 'engine')
    reactor_path = os.path.join(root_dir, 'reactor')
    sys.path = [p for p in sys.path if p not in (engine_path, reactor_path)]

    if use_reactor:
        sys.path.insert(0, reactor_path)
    else:
        sys.path.insert(0, engine_path)

    from Circuit import Circuit
    from IC import IC
    from Const import (
        IC_ID, INPUT_PIN_ID, OUTPUT_PIN_ID,
        NOT_ID, AND_ID, NAND_ID, OR_ID, NOR_ID, XOR_ID, XNOR_ID,
        VARIABLE_ID, PROBE_ID,
        HIGH, LOW, UNKNOWN, ERROR, SIMULATE, set_MODE,
    )

    return {
        'Circuit': Circuit, 'IC': IC,
        'IC_ID': IC_ID, 'INPUT_PIN_ID': INPUT_PIN_ID,
        'OUTPUT_PIN_ID': OUTPUT_PIN_ID, 'NOT_ID': NOT_ID,
        'AND_ID': AND_ID, 'NAND_ID': NAND_ID, 'OR_ID': OR_ID,
        'NOR_ID': NOR_ID, 'XOR_ID': XOR_ID, 'XNOR_ID': XNOR_ID,
        'VARIABLE_ID': VARIABLE_ID, 'PROBE_ID': PROBE_ID,
        'HIGH': HIGH, 'LOW': LOW, 'UNKNOWN': UNKNOWN, 'ERROR': ERROR,
        'SIMULATE': SIMULATE, 'set_MODE': set_MODE,
    }


# ═══════════════════════════════════════════════════════════════════
#  BENCHMARK 1: IC CREATION & LOADING
# ═══════════════════════════════════════════════════════════════════

def bench_ic_create(backend, gate_count, pin_count):
    C = backend['Circuit']
    SIMULATE = backend['SIMULATE']

    def create():
        c = C()
        c.simulate(SIMULATE)

        in_pins = []
        for _ in range(pin_count):
            in_pins.append(c.getcomponent(backend['INPUT_PIN_ID']))

        out_pins = []
        for _ in range(pin_count):
            out_pins.append(c.getcomponent(backend['OUTPUT_PIN_ID']))

        gates_per_chain = max(1, gate_count // pin_count)
        for p in range(pin_count):
            prev = in_pins[p]
            for _ in range(gates_per_chain):
                g = c.getcomponent(backend['NOT_ID'])
                c.connect(g, prev, 0)
                prev = g
            c.connect(out_pins[p], prev, 0)

        return c

    ms, c = timed(create)
    return ms, c


def bench_ic_save_load(backend, circuit, tmp_path):
    C = backend['Circuit']
    SIMULATE = backend['SIMULATE']

    def do_save():
        circuit.save_as_ic(tmp_path, "BenchIC")

    save_ms, _ = timed(do_save)

    def do_load():
        c2 = C()
        c2.simulate(SIMULATE)
        loaded = c2.getIC(tmp_path)
        c2.counter += loaded.counter if loaded else 0
        return c2, loaded

    load_ms, (c2, loaded) = timed(do_load)
    return save_ms, load_ms, c2, loaded


# ═══════════════════════════════════════════════════════════════════
#  BENCHMARK 2: FULL CIRCUIT CREATION & LOADING
# ═══════════════════════════════════════════════════════════════════

def bench_circuit_create(backend, chain_length):
    C = backend['Circuit']
    SIMULATE = backend['SIMULATE']

    def create():
        c = C()
        c.simulate(SIMULATE)
        v = c.getcomponent(backend['VARIABLE_ID'])
        prev = v
        for _ in range(chain_length):
            g = c.getcomponent(backend['NOT_ID'])
            c.connect(g, prev, 0)
            prev = g
        return c

    ms, c = timed(create)
    return ms, c


def bench_circuit_save_load(backend, circuit, tmp_path):
    C = backend['Circuit']
    SIMULATE = backend['SIMULATE']

    def do_save():
        circuit.writetojson(tmp_path)

    save_ms, _ = timed(do_save)

    def do_load():
        c2 = C()
        c2.readfromjson(tmp_path)
        return c2

    load_ms, c2 = timed(do_load)
    return save_ms, load_ms, c2


# ═══════════════════════════════════════════════════════════════════
#  RUNNER
# ═══════════════════════════════════════════════════════════════════

def run_single_backend(label, use_reactor):
    print(f"\n{header(f'  {label}  ')}")

    try:
        backend = load_backend(use_reactor)
    except ImportError as e:
        print(f"  ⚠ SKIPPED — Cannot import {label}: {e}")
        return None

    results = {}
    tmp_dir = tempfile.mkdtemp()

    # ──────────────────────────────────────────
    # 1. IC CREATION
    # ──────────────────────────────────────────
    print(f"\n  {'─' * 81}")
    print(f"  IC CREATION & LOADING")
    print(f"  {'─' * 81}")

    ic_configs = [
        ("Micro IC",         10,   2),
        ("Small IC",        100,   2),
        ("Medium IC",     1_000,   4),
        ("Large IC",     10_000,   8),
        ("Massive IC",   50_000,  16),
        ("Colossal IC", 100_000,  32),
    ]

    print(f"  | {'Configuration':<14} | {'Gates':>9} | {'Pins':>5} | {'Create':>10} | {'Save':>10} | {'Load':>10} | {'Sim':>10} |")
    print(f"  |{'-'*16}+{'-'*11}+{'-'*7}+{'-'*12}+{'-'*12}+{'-'*12}+{'-'*12}|")

    for name, gate_count, pin_count in ic_configs:
        gc.collect()

        create_ms, c = bench_ic_create(backend, gate_count, pin_count)
        tmp_path = os.path.join(tmp_dir, f"bench_ic_{gate_count}.json")
        save_ms, load_ms, c2, loaded = bench_ic_save_load(backend, c, tmp_path)

        for p in loaded.inputs:
            v = c2.getcomponent(backend['VARIABLE_ID'])
            c2.connect(p, v, 0)
            
        sim_ms = 0
        if c2.get_variables():
            sim_start = time.perf_counter_ns()
            c2.toggle(c2.get_variables()[0], backend['HIGH'])
            sim_ms = (time.perf_counter_ns() - sim_start) / 1_000_000

        results[f'ic_create_{gate_count}'] = create_ms
        results[f'ic_save_{gate_count}'] = save_ms
        results[f'ic_load_{gate_count}'] = load_ms
        results[f'ic_sim_{gate_count}'] = sim_ms

        print(f"  | {name:<14} | {gate_count:>9,} | {pin_count:>5} | {format_time(create_ms):>10} | {format_time(save_ms):>10} | {format_time(load_ms):>10} | {format_time(sim_ms):>10} |")

        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # ──────────────────────────────────────────
    # 2. CIRCUIT CREATION & LOADING
    # ──────────────────────────────────────────
    print(f"\n  {'─' * 81}")
    print(f"  CIRCUIT CREATION & LOADING")
    print(f"  {'─' * 81}")

    circuit_sizes = [
        ("Micro Circ",         100),
        ("Small Circ",       1_000),
        ("Medium Circ",     10_000),
        ("Large Circ",     100_000),
        ("Massive Circ",   500_000),
        ("Colossal Circ",1_000_000),
    ]

    print(f"  | {'Configuration':<14} | {'Gates':>9} | {'Create':>12} | {'Save':>12} | {'Load':>12} | {'Sim':>10} |")
    print(f"  |{'-'*16}+{'-'*11}+{'-'*14}+{'-'*14}+{'-'*14}+{'-'*12}|")

    for name, chain_len in circuit_sizes:
        gc.collect()

        create_ms, c = bench_circuit_create(backend, chain_len)
        tmp_path = os.path.join(tmp_dir, f"bench_circuit_{chain_len}.json")
        save_ms, load_ms, c2 = bench_circuit_save_load(backend, c, tmp_path)

        sim_start = time.perf_counter_ns()
        v = c2.get_variables()[0]
        c2.toggle(v, backend['HIGH'])
        sim_ms = (time.perf_counter_ns() - sim_start) / 1_000_000

        results[f'circ_create_{chain_len}'] = create_ms
        results[f'circ_save_{chain_len}'] = save_ms
        results[f'circ_load_{chain_len}'] = load_ms
        results[f'circ_sim_{chain_len}'] = sim_ms

        print(f"  | {name:<14} | {chain_len:>9,} | {format_time(create_ms):>12} | {format_time(save_ms):>12} | {format_time(load_ms):>12} | {format_time(sim_ms):>10} |")

        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass

    return results


def run_all():
    print(divider())
    print(header("  IC & CIRCUIT BENCHMARK SUITE  "))
    print(divider())
    print(f"  Platform : {platform.system()} {platform.release()}")
    print(f"  Python   : {platform.python_version()}")
    print(f"  Time     : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(divider())

    all_results = {}

    engine_results = run_single_backend("ENGINE (Python)", use_reactor=False)
    if engine_results:
        all_results['engine'] = engine_results

    reactor_results = run_single_backend("REACTOR (Cython)", use_reactor=True)
    if reactor_results:
        all_results['reactor'] = reactor_results

    if 'engine' in all_results and 'reactor' in all_results:
        print(f"\n{header('  HEAD-TO-HEAD COMPARISON  ')}")
        e = all_results['engine']
        r = all_results['reactor']

        common_keys = sorted(set(e.keys()) & set(r.keys()))

        ic_keys = [k for k in common_keys if k.startswith('ic_')]
        circ_keys = [k for k in common_keys if k.startswith('circ_')]

        for group_name, keys in [("IC Benchmarks", ic_keys), ("Circuit Benchmarks", circ_keys)]:
            if not keys:
                continue
            print(f"\n  {group_name}:")
            print(f"  | {'Benchmark':<25} | {'Engine':>13} | {'Reactor':>13} | {'Speedup':>10} |")
            print(f"  |{'-'*27}+{'-'*15}+{'-'*15}+{'-'*12}|")

            for key in keys:
                e_ms = e[key]
                r_ms = r[key]
                speedup = e_ms / r_ms if r_ms > 0 else float('inf')
                label = key.replace('_', ' ').title()
                print(f"  | {label:<25} | {format_time(e_ms):>13} | {format_time(r_ms):>13} | {speedup:>9.1f}x |")

    print(f"\n{divider()}")
    print(f"  BENCHMARK COMPLETE")
    print(divider())


if __name__ == "__main__":
    run_all()

# Darion Logic Sim — Benchmark & Test Documentation

> **Audience:** You know Python, but know nothing about digital logic circuits.
> This document tells you *exactly* what every benchmark and test builds, wire by wire, and what it is measuring.
> Every file listed here actually exists in the `tests/` directory and runs as-is.

---

## Table of Contents

1. [Shared Concepts](#0-shared-concepts)
2. [book_benchmark.py](#1-book_benchmarkpy)
3. [cache_test.py](#2-cache_testpy)
4. [Complexity_scale.py](#3-complexity_scalepy)
5. [ic_circuit_benchmark.py](#4-ic_circuit_benchmarkpy)
6. [iscas_test.py](#5-iscas_testpy)
7. [unified_iscas_benchmark.py](#6-unified_iscas_benchmarkpy)
8. [defragmentation_test.py](#7-defragmentation_testpy)
9. [integrity_test.py](#8-integrity_testpy)
10. [Summary Table](#9-summary-table)

---

## 0. Shared Concepts

Before reading anything else, you need these mental models.

### 0.1 What is a "gate"?

Think of a gate as a Python object that reads one or more *input* voltage values (`HIGH=1` or `LOW=0`) and immediately computes an *output*. The gates used throughout these files are:

| Name | Symbol | Rule |
|------|--------|------|
| **VARIABLE** | `V` | A free input — you set it with `toggle()`. Has only an output. |
| **NOT** | `¬` | Output = opposite of input: `HIGH→LOW`, `LOW→HIGH` |
| **AND** | `&` | Output = `HIGH` only when **all** inputs are `HIGH` |
| **OR** | `\|` | Output = `HIGH` when **any** input is `HIGH` |
| **XOR** | `^` | Output = `HIGH` when an **odd number** of inputs are `HIGH` |
| **NAND** | `¬&` | Output = NOT(AND): `HIGH` unless all inputs are `HIGH` |
| **NOR** | `¬\|` | Output = NOT(OR): `HIGH` only when all inputs are `LOW` |
| **XNOR** | `≡` | Output = NOT(XOR): `HIGH` when an **even number** of inputs are `HIGH` |
| **PROBE** | `P` | A read-only buffer: output mirrors its single input. Used to observe a signal without affecting it. |
| **INPUT_PIN / OUTPUT_PIN** | `IN`/`OUT` | Boundary markers for packaging a circuit as an IC |

### 0.2 What does `connect(gate, source, slot)` do?

It wires `source.output` into input slot `slot` of `gate`. After every `toggle()`, the engine re-evaluates all gates that are downstream of the changed node, in topological order.

### 0.3 Two backends

Every benchmark can run against two implementations of the same engine API:

| Backend | Language | Location | How to select |
|---------|----------|----------|---------------|
| **Engine** | Pure Python | `engine/` | `--engine` flag |
| **Reactor** | Cython (compiled C) | `reactor/` | default (no flag) |

The measured numbers quantify the speedup of Reactor over Engine.

### 0.4 The Book Algorithm

When a gate's output changes, only the gates **directly connected** to it need to be re-evaluated. The Book Algorithm stores an exact "hitlist" per gate so it visits only those downstream gates — nothing more. Each gate maintains a `book` dictionary that counts how many of its inputs are currently HIGH, LOW, or UNKNOWN. When an input transitions, only the count is updated; the gate re-computes its output from the count rather than re-reading all sources.

### 0.5 `optimize()` / Defragmentation

After building a circuit programmatically (or after many delete operations from the UI), heap objects may be scattered in memory. `circuit.optimize()` performs a **topological sort** of all gates and copies them into a fresh, contiguous memory layout — improving CPU cache utilization. This is the Data-Oriented Design (DOD) trick that produces the performance difference visible in `defragmentation_test.py`.

---

---

## 1. `book_benchmark.py`

### 1.1 Purpose & Special Requirements
**Purpose:** Prove that the engine's *Book Algorithm* is faster than a naïve BFS propagation for a variety of circuit shapes.
**Special Requirements:** None. Runs standalone using the core engine and reactor.

### 1.2 How It Works
The file contains three circuit constructions, each tested with both algorithms (Book and Naïve) side by side:
- **TEST 1 (Single AND Gate Chain, Varying Fan-In):** Builds a chain of 1000 AND gates. Simulates a wide AND gate that must count its HIGH inputs before deciding.
- **TEST 2 (Fan-Out: Many OR Gates, Shared Variables):** Tests extreme fan-out where one source wire drives hundreds of thousands of downstream OR gates simultaneously.
- **TEST 3 (NOT Chain Propagation):** Builds the simplest dependency chain (`V → NOT → NOT → ...`). Measures per-gate evaluation latency.

### 1.3 Execution Instructions
Run directly via python.
```bash
python tests/book_benchmark.py
```
Output will print tables with `ns/g(B)` (nanoseconds per gate, Book algorithm) and `ns/g(N)` (nanoseconds per gate, Naïve algorithm).

---

## 2. `cache_test.py`

### 2.1 Purpose & Special Requirements
**Purpose:** Find the exact circuit sizes where data no longer fits in CPU cache, causing measurable performance cliffs (tier boundaries).
**Special Requirements:** None. Uses the Cython (Reactor) backend.

### 2.2 How It Works
Builds a mixed chain topology (`AND → OR → XOR → NOT`) to exercise the propagation scheduler with a representative mix of gate types. The same circuit is built in three ways (fragmentation modes) to change how gate objects are laid out in memory:
- **Linear:** Gates allocated and wired in order (Code written top-to-bottom).
- **Realistic:** Gates pre-allocated, shuffled in 64-gate chunks, then wired (User builds in sub-modules).
- **Chaotic:** 100% random shuffle before wiring (cache-miss pathological case).
The script tests geometric growth from 100 to 2,000,000 gates to detect cache boundary evacuations.

### 2.3 Execution Instructions
Run directly via python.
```bash
python tests/cache_test.py
```

---

## 3. `Complexity_scale.py`

### 3.1 Purpose & Special Requirements
**Purpose:** Profile 22 different circuit topologies (L0–L21) across 5 gate-count sizes (1K, 5K, 10K, 50K, 100K) and report throughput in Million Evaluations per Second (ME/s).
**Special Requirements:** None.

### 3.2 How It Works
Builds standard circuit structures ranging from purely sequential (Linear Chain L0) to highly parallel (Binary Fan-Out L2), all the way to complex systems like a Ripple Carry Adder (L10) and a 1-bit ALU Slice (L21). For each shape and size, it toggles a master clock/variable repeatedly and measures `eval_count` over time. The results help quantify why certain digital circuits are expensive to simulate.

### 3.3 Execution Instructions
Run directly via python.
```bash
python tests/Complexity_scale.py
```

---

## 4. `ic_circuit_benchmark.py`

### 4.1 Purpose & Special Requirements
**Purpose:** Test the full IC (Integrated Circuit) system — packaging circuits as reusable components, saving/loading them to JSON, and verifying performance at scale.
**Special Requirements:** None.

### 4.2 How It Works
Runs performance benchmarks in phases per backend:
- **COMPLEX IC BENCHMARK:** Builds ICs with a mixed gate topology. Measures Create, Save, Load, and Sim operations across sizes from 10 to 150,000 gates.
- **COMPLEX CIRCUIT BENCHMARK:** Evaluates a raw circuit with three combined sub-circuits (NOT chain, AND pyramid, XOR parity chain).
- **NESTED IC STRESS TEST:** Packages NOT gates up to 10 IC levels deep to ensure nested components serialize and evaluate correctly.
Finally, prints a Cython vs Pure-Python head-to-head comparison table.

### 4.3 Execution Instructions
Run directly via python.
```bash
python tests/ic_circuit_benchmark.py
```

---

## 5. `iscas_test.py`

### 5.1 Purpose & Special Requirements
**Purpose:** Reality-check the engine against real-world industry-standard benchmarks (ISCAS-85 and ISCAS-89).
**Special Requirements:** Requires the ISCAS `.v` files (located in `tests/ISCAS85/` and `tests/ISCAS89/`).

### 5.2 How It Works
Uses `VerilogRunner` to parse `.v` netlist files.
- Creates 8 independent master variables (chaos generators).
- Translates Verilog gates to internal API calls (using XOR to drive random noise).
- Handles sequential loops in ISCAS-89 by turning DFF (`dff`) outputs into primary inputs (Loop Cut).
- Simulates circuits for tens of thousands of random vectors and measures total throughput (ME/s).

### 5.3 Execution Instructions
Requires specifying the ISCAS directory containing `.v` files.
**Flags:**
- `directory` (positional): Path to folder containing `.v` files (e.g., `tests/ISCAS89`).
- `--engine`: Use pure Python Engine instead of Cython Reactor.
- `--no-optimize`: Skip `circuit.optimize()` (DOD topological sort).
- `--vectors N`: Override the auto-selected vector count.

**Example usage:**
```bash
python tests/iscas_test.py tests/ISCAS89
python tests/iscas_test.py tests/ISCAS85 --engine --no-optimize --vectors 200
```

---

## 6. `unified_iscas_benchmark.py`

### 6.1 Purpose & Special Requirements
**Purpose:** A unified benchmark runner comparing four simulation engines on identical ISCAS datasets: Pure Python Engine, Cython Reactor, Logisim-Evolution, and Icarus Verilog.
**Special Requirements:**
- ISCAS `.v` files.
- **Logisim-Evolution:** Requires Java and the `logisim-evolution.jar` file. It uses a custom Java harness (`LogisimBenchmarkHarness.java`) to embed Logisim as a library.
- **Icarus Verilog:** Requires `iverilog` and `vvp` installed on your system. It compiles a custom VPI timer (`vpi_timer.c`) to isolate raw simulation throughput (excluding disk I/O and process teardown).

### 6.2 How It Works
- **Vector Generation:** The script uses a fixed Python PRNG seed (42) to generate identical input vectors for all four engines, ensuring fairness.
- **Logisim:** Calls the Java harness, runs JIT untimed warmups, performs garbage collection, and logs timed evaluations via `System.nanoTime()`.
- **Icarus Verilog:** Transpiles identical test vectors and loads them via `$readmemb`. The VPI timer wraps the inner evaluation loop directly inside the `vvp` process.
- **Engine/Reactor:** Executes batch toggles and evaluates via `SIMULATE` (BFS propagate) or `COMPILE` (Linear Sweep) modes.
- Generates a side-by-side speedup ratio comparison report.

### 6.3 Execution Instructions
**Flags:**
- `target` (positional): Path to `.v` file or directory.
- `--jar`: Path to Logisim-Evolution JAR (default: `logisim-evolution.jar`).
- `--harness`: Directory containing `LogisimBenchmarkHarness.class` (default: `harness_build`).
- `--vectors`: Total vectors per circuit (default: `50000`).
- `--warmup`: Untimed warmup vectors (default: `5000`).
- `--optimize`: Enable topological optimization in Engine/Reactor.
- `--output`: Base path for output files.
- `--dump`: Dump output to time-stamped txt in test_results.
- `--plot`: Generate plots in test_results.

**Example usage:**
```bash
python tests/unified_iscas_benchmark.py tests/ISCAS85 --optimize --dump
```

---

## 7. `defragmentation_test.py`

### 7.1 Purpose & Special Requirements
**Purpose:** Directly measure the performance impact of memory fragmentation in the Cython Reactor backend and quantify how much `circuit.optimize()` (DOD topological reordering) recovers.
**Special Requirements:** None. Uses the Cython (Reactor) backend.

### 7.2 How It Works
Builds 1.5M gate circuits in two distinct shapes (Linear Chain, Dense Braid).
Executes simulations in three phases:
1. **Pristine (Ideal Layout):** Allocates and wires in order. Best-case CPU cache performance.
2. **Fragmented (GUI-Realistic):** Shuffles objects completely before wiring, resulting in maximum cache-miss penalties.
3. **Optimized (DOD):** Calls `circuit.optimize()` on the fragmented circuit to perform a topological sort and memory copy, recovering contiguous layout.
Calculates how effectively `optimize()` recovers lost performance (often 500%+ improvement).

### 7.3 Execution Instructions
Run directly via python.
```bash
python tests/defragmentation_test.py
```

---

## 8. `integrity_test.py`

### 8.1 Purpose & Special Requirements
**Purpose:** The master correctness test suite. Verifies that every feature of the Darion engine (gates, connections, IC packaging, serialization, undo/redo, truth tables, optimization) produces exact correct results across thousands of assertions.
**Special Requirements:** None.

### 8.2 How It Works
The file is comprehensive (~5000 lines) and is organized into 9 major testing sections:
1. **Unit Tests:** Individual API calls and gate instances.
2. **Comprehensive Coverage:** Truth table validation across multi-input variants.
3. **Circuit Stress:** Deep chains and wide fan-outs.
4. **Event Manager:** Undo/Redo command stack.
5. **IC Tests:** Deeply nested integrated circuits, I/O pin mapping, memory leaks.
6. **Serialization:** JSON saving, loading, copy, paste.
7. **Truth Table:** Exhaustive 2^N state verification for multi-input subcircuits.
8. **Refresh / Optimize:** Tests DOD memory layout functions in Cython (`refresh()` and `optimize()`).
9. **Real-World Stress:** Simulates ALU slices, Ripple Carry Adders, Ring Oscillators, etc.

### 8.3 Execution Instructions
Run directly via python. Uses `aioconsole` internally for menus if needed, but runs autonomously.
```bash
python tests/integrity_test.py
```

---

## 9. Summary Table

| File | Primary Question | Special Dependencies |
|------|-----------------|----------------------|
| `book_benchmark.py` | Is the Book Algorithm faster than naïve BFS? | None |
| `cache_test.py` | At what circuit size does CPU cache fall? | None |
| `Complexity_scale.py` | Which circuit shapes are cheaper/harder to simulate? | None |
| `ic_circuit_benchmark.py` | Do IC packaging + JSON serialization work at scale? | None |
| `iscas_test.py` | How fast is the engine on real-world industry netlists? | ISCAS `.v` files |
| `unified_iscas_benchmark.py`| Apples-to-apples comparison of Python/Cython/Java/Icarus? | Java, Icarus, ISCAS |
| `defragmentation_test.py` | How much does memory fragmentation hurt vs `optimize()`? | None |
| `integrity_test.py` | Is every single feature correct and stable under stress? | None |


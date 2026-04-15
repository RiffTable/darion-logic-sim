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
7. [defragmentation_test.py](#6-defragmentation_testpy)
8. [integrity_test.py](#7-integrity_testpy)
9. [Summary Table](#8-summary-table)

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

## 1. `book_benchmark.py`

**Purpose:** Prove that the engine's *Book Algorithm* is faster than a naïve BFS propagation for a variety of circuit shapes.

The file contains **three** circuit constructions, each tested with both algorithms side by side.

---

### TEST 1 — Single AND Gate Chain, Varying Fan-In

**What is built:**

```
V_toggle ──┐
           ├─→ [AND, N inputs] ─→ [AND, N inputs] ─→ ... (1000 chain)
V_high   ──┤   (slot 0 = prev)    (slot 0 = prev)
  (also  ──┤   (slot 1..N = Vhigh) ...
  feeds  ──┘
  slots
  1..N-1)
```

`input_count` ranges from 2 to 1024. For each value:

1. Create a **VARIABLE** `toggle_var` (starts UNKNOWN).
2. Create a **VARIABLE** `high_var` and permanently set it to `HIGH`.
3. Build a **chain of 1000 AND gates**:
   - Slot 0 of each AND = previous gate (or `toggle_var` for gate #1).
   - Slots 1 through N-1 all tie to `high_var`.
4. Trigger: `toggle(toggle_var, HIGH)` then `toggle(toggle_var, LOW)`.

**What this simulates:**
A wide AND gate (e.g., 1024 inputs) that must count its HIGH inputs before deciding. The Book version updates the HIGH-count incrementally; the Naïve version re-checks every source every evaluation.

**Example for N=4, chain length 3:**
```
V_toggle ──→ [AND4] ──→ [AND4] ──→ [AND4] → output
V_high   ──↗↗↗       ↗↗↗       ↗↗↗
(slots 1,2,3 tied to V_high)
```

**Output columns:** `ns/g(B)` = nanoseconds per gate (Book), `ns/g(N)` = nanoseconds per gate (Naïve).

---

### TEST 2 — Fan-Out: Many OR Gates, Shared Variables

**What is built:**

```
V[0] ──┬──→ [OR, N inputs]   (gate 0)
       ├──→ [OR, N inputs]   (gate 1)
       ├──→ [OR, N inputs]   (gate 2)
V[1] ──┤         ...
  ...  │──→ [OR, N inputs]   (gate M-1)
V[N-1]─┘
```

Each OR gate has `inputs_per_gate` inputs, all from **the same shared set of VARIABLE nodes**. Toggling any variable causes all M OR gates to re-evaluate.

Configurations tested:

| Gates (M) | Inputs/gate (N) |
|-----------|-----------------|
| 100 | 50 |
| 500 | 20 |
| 1,000 | 10 |
| 5,000 | 10 |
| 10,000 | 10 |
| 20,000 | 5 |

**What this simulates:**
Extreme fan-out — one source wire drives hundreds of thousands of downstream gates simultaneously (like a clock signal in real hardware).

---

### TEST 3 — NOT Chain Propagation

**What is built:** The simplest possible dependency chain:

```
V ──→ [NOT] ──→ [NOT] ──→ [NOT] ──→ ... (N times) ──→ final_NOT
```

Chain lengths tested: 1K, 10K, 100K, 500K, 1M NOT gates.

Each toggle of `V` must propagate a signal change all the way through the chain. This directly measures **per-gate evaluation latency** since there is zero parallelism.

**Output columns:**
- `ns/g(B)` = nanoseconds per gate in the Book algorithm
- `ns/g(N)` = nanoseconds per gate in the Naïve algorithm

---

## 2. `cache_test.py`

**Purpose:** Find the exact circuit sizes where data no longer fits in CPU cache, causing measurable performance cliffs (tier boundaries).

### 2.1 One circuit topology is built: a Mixed Chain

```
V_first ──→ [AND] ──→ [OR] ──→ [XOR] ──→ [NOT] ──→ [AND] ──→ [OR] ──→ ...
              ↑          ↑        ↑
           V_high    V_low    V_low
```

The pattern rotates through 4 gate types: AND, OR, XOR, NOT. Their second inputs are tied to constant `HIGH` or `LOW` variables so every gate always has a valid, stable second input — but the only *interesting* signal is from the chain itself.

**Exact wiring rule (from `build_chain`):**
- `AND` gate: `connect(g, prev, 0)` and `connect(g, const_high, 1)` → AND(prev, 1) = just prev
- `OR/XOR` gate: `connect(g, prev, 0)` and `connect(g, const_low, 1)` → OR(prev, 0) = just prev
- `NOT` gate: `connect(g, prev, 0)` → NOT(prev)

Functionally it is a long inverting/non-inverting pass-through, but structurally it exercises the propagation scheduler with a representative mix of gate types.

### 2.2 Three fragmentation modes

The same circuit is built in three ways, changing how gate objects are laid out **in memory**:

| Mode | What happens | Real-world analog |
|------|-------------|-------------------|
| `linear` | Gates allocated and wired in order | Code written top-to-bottom |
| `realistic` | Gates pre-allocated, then shuffled in 64-gate chunks, then wired | User builds in sub-modules; modules arranged randomly |
| `chaotic` | Gates pre-allocated, then completely random shuffle, then wired | 100% cache-miss pathological case |

**Why does this matter?** When `gate[i]` needs `gate[i-1]`'s output, a `linear` layout means they're adjacent in memory — one cache line fetch. In `chaotic` mode they're random, so every gate access causes a **cache miss**.

### 2.3 Size sweep

Circuit size grows geometrically (~15% per step) from **100 gates** to **2,000,000 gates**. For each size:
1. Build the chain.
2. Calibrate: measure one round-trip toggle to estimate how many iterations fit in 100ms.
3. Warmup: 3 round-trips.
4. Benchmark: best of 3–5 passes, each running N round-trips.
5. Record `ns/eval` (nanoseconds per gate evaluation).

### 2.4 Zone detection

The code tracks `ns/eval` as circuit size increases. When `ns/eval` jumps >15% compared to a rolling 3-point average, it marks a **cache boundary**:

```
ns/eval
  │         L1/L2 zone
  │  ────────────────────────┐  ← CACHE BOUNDARY EVACUATION
  │                           └──────────────┐  ← MAIN RAM WALL
  │                                           └──────────────────
  └──────────────────────────────────────────────── Active Gates
       fast                              slow
```

**Tier 1 (Core Cache):** Fits in L1+L2. Near-zero memory latency.
**Tier 2 (Last Level):** Spills to L3/shared cache.
**Tier 3 (Main RAM):** Cache is exhausted. The memory bus is the bottleneck.

---

## 3. `Complexity_scale.py`

**Purpose:** Profile 22 different circuit topologies (L0–L21) across 5 gate-count sizes (1K, 5K, 10K, 50K, 100K) and report throughput in **Million Evaluations per Second (ME/s)**.

The key insight: different circuit shapes stress the engine differently. A linear chain has no parallelism; a binary fan-out tree has maximum parallelism. This reveals *why* some real digital circuits are expensive to simulate.

### 3.1 Circuit Topology Catalog

Each level uses `target_gates` as its size parameter.

---

#### L0 — Linear Chain
```
V ──→ NOT ──→ NOT ──→ NOT ──→ ... (target_gates NOT gates total)
```
Zero parallelism. Pure sequential latency measurement.

---

#### L1 — Wide Fan-Out
```
         ┌──→ NOT ──→ NOT ──→ ... (depth NOTs, lane 0)
         ├──→ NOT ──→ NOT ──→ ... (lane 1)
V ───────┤
         ├──→ NOT ──→ NOT ──→ ... (lane N-2)
         └──→ NOT ──→ NOT ──→ ... (lane N-1)
```
`lanes = target_gates // 50`. `depth = target_gates // lanes`. All lanes trigger simultaneously on one toggle.

---

#### L2 — Binary Fan-Out Tree
```
           V
         /   \
       NOT   NOT
       / \   / \
     NOT NOT NOT NOT
     ...
```
Each node fans out to exactly 2 NOT children. Depth = log₂(target_gates). Exploits maximum tree parallelism.

---

#### L3 — Memory Maze
Wiring: identical to L0 (linear NOT chain). Structure in memory: **randomly shuffled** with `random.seed(42)` before connecting. Same logic, maximally fragmented RAM layout — isolates the cache-miss penalty vs L0.

---

#### L4 — Glitch Avalanche
```
V ──→ NOT ──→ NOT ──→ ... ──→ NOT (half-chain)
│              │               │
└──→ XOR ──┘  └──→ XOR ──┘  └──→ XOR
     ↑              ↑              ↑
     V              chain[1]       chain[N/2-1]
```
Two sub-circuits:
1. A **NOT chain** of `half = target_gates // 2` gates.
2. A set of **XOR gates**, one per chain position, each connected to `master` (input 0) and `chain[i]` (input 1).

One toggle → both chains fire → **O(N) simultaneous events** hit the scheduler. Tests event-queue saturation.

---

#### L5 — Queue Thrash O(N²)
```
           ┌──────────────────────────────────┐
           │                                   ↓
V ──→ XOR[0] ──→ XOR[1] ──→ XOR[2] ──→ ... ──→ XOR[N-1]
│    ↑ (slot 1: static_low)
└────┘ (slot 0: master for ALL XOR gates)
```
XOR chain where every gate also fans in from `master`. One toggle fires all N XOR gates immediately, which cascade as their predecessors' outputs change → **O(N²) re-evaluations**. Absolute worst case.

---

#### L6 — Sparse Fan-In
```
V ───┐
V2 ──┤
V3 ──┼──→ XOR ──→ XOR ──→ XOR ──→ ... → single output
V4 ──┤
...  ┘
```
Independent VARIABLE nodes feed a **binary XOR reduction tree**. All sources change together → tests simultaneous wide fan-in merging.

---

#### L7 — Dense Braid (4 lanes, wrap-around AND)
```
Layer 0:    [V] [V] [V] [V]   (all alias to master)
             │   │   │   │
             ▼   ▼   ▼   ▼
Layer 1:  AND(0,1) AND(1,2) AND(2,3) AND(3,0)   ← wrap-around
             │       │       │       │
Layer 2:  AND(0,1) AND(1,2) AND(2,3) AND(3,0)
             ...
```
4 parallel lanes of AND gates. Each AND gate takes inputs from lane `i` and lane `(i+1) % 4`. This maximises **wire density**: every gate depends on two neighbors.

---

#### L8 — Diamond (Expand then Contract)
```
Phase 1 (expand):
            V
          /   \
        NOT   NOT
        / \   / \
      NOT NOT NOT NOT
      (binary fanout until target_gates/2 leaves)

Phase 2 (contract):
      NOT NOT NOT NOT
        \  /   \  /
        AND    AND
           \  /
           AND  ← apex
```
Expands in a binary fan-out tree, then AND-reduces all leaves pair-by-pair back to one output. Tests both expand and contract phases.

---

#### L9 — Hamming(7,4) ECC

A [7,4] Hamming code computes 3 parity bits (p1, p2, p3) from 4 data bits (d1–d4):

```
master ──→ NOT ──→ NOT (d2)
                │
                └──→ NOT ──→ NOT (d3)
                               │
                               └──→ NOT ──→ NOT (d4)
```
(d1 = master, d2/d3/d4 are delayed versions)

For each "block":
```
p1 = XOR(XOR(d1, d2), d4)   → two XOR gates
p2 = XOR(XOR(d1, d3), d4)   → two XOR gates
p3 = XOR(XOR(d2, d3), d4)   → two XOR gates
```
6 XOR gates per block. `blocks = target_gates // 6`. Models DRAM ECC syndrome logic.

---

#### L10 — Ripple Carry Adder

`bits = target_gates // 5`. One full-adder cell per bit:

```
Bit 0 cell (5 gates):
A ──→ XOR ──→ XOR ──→ SUM
B ──↗    ↗cin
A ──→ AND ──→      ↘
B ──↗        → OR ──→ COUT
        AND ──↗
       (XAB & cin)

Bit 1 cell: same, cin = COUT from bit 0
...
```
The critical path is the carry chain. Each bit must wait for the carry from the previous bit.

---

#### L11 — Priority Encoder

`n_inputs = target_gates`. All input slots are aliased to `master`:

```
master master master master
  │      │      │      │
 OR     OR     OR (leaf OR gates: each is OR(master, master))
   \   /         \  /
    OR              OR
       \           /
         OR (root)
```
A balanced OR-reduction tree. Every leaf fires when master changes → O(N) evaluations cascade through O(log₂ N) levels.

---

#### L12 — Wallace Tree Multiplier

A 3-to-2 compressor (full adder) reduces 3 inputs to 2 (sum + carry), then repeats until 2 signals remain:

```
Inputs: [master, NOT(master), master, NOT(master), ...]  (n_inputs)

Round 1: groups of 3 → full-adder → 2 outputs
  XOR(A,B), XOR(XOR(A,B),C),  AND(A,B), AND(C,XOR(A,B)), OR(AND,AND)
  (sum=2 gates, carry=3 gates per cell)

Round 2: same reduction on outputs of round 1
...until 2 signals remain
```
Irregular shrinking width + mixed XOR/AND/OR mirrors hardware multiplier internals.

---

#### L13 — SR Latch Farm

Each SR latch is built from 2 NOR gates (simulated as OR+NOT):

```
master ──→ OR(master, R_node) ──→ NOT → Q_bar
                                  │
S_node ──→ OR(S_node, Q_bar)  ──→ NOT → Q
```
`R_node` and `S_node` are VARIABLE nodes set to LOW. `latches = target_gates // 4`. Tests graceful behavior under cyclic-adjacent topology.

---

#### L14 — Sparse Random DAG

A randomly seeded DAG (seed `0xDEADBEEF`) where each gate's sources are randomly chosen from already-created gates:

```
V[0], V[1], ... V[N/20]   (random initial values)
       ↓ ↓ random connections
gate[0] = NOT(random_source)
gate[1] = XOR(random_source0, random_source1)
gate[2] = AND(random_source0, random_source1)
...
```
Connections point backward only (no cycles). Gate types chosen randomly from {NOT, XOR, AND, OR}. Cache-unfriendly, branch-predictor-hostile — a synthesized netlist worst case.

---

#### L15 — Decoder Tree

An N-bit binary address decoder produces 2^N outputs:

```
addr[0], addr[1], ..., addr[9]   (up to 10 address bits)
NOT(addr[0]), NOT(addr[1]), ...   (complement lines)

output[0]    = AND(NOT(addr[0]), NOT(addr[1]), ..., NOT(addr[9]))  = minterm 0000000000
output[1]    = AND(addr[0],     NOT(addr[1]), ..., NOT(addr[9]))   = minterm 0000000001
...
output[1023] = AND(addr[0], addr[1], ..., addr[9])                 = minterm 1111111111
```
Extreme fan-out: `addr[0]` feeds half of all 1024 AND chains.

---

#### L16 — Carry Lookahead Adder (4-bit CLA, repeated)

`blocks = target_gates // 20`. Each block is a 4-bit CLA. Within one block:

```
For each of 4 bits i:
  Pi = XOR(master, B[i])      ← Propagate signal
  Gi = AND(master, B[i])      ← Generate signal

Carry logic (parallel, no ripple):
  C1 = G0 | (P0 & Cin)
  C2 = G1 | (P1&G0) | (P1&P0&Cin)   [approximated as 2-level]
```
Key advantage over L10: **all carries are computed in parallel** using P/G signals.

---

#### L17 — D-Latch Array

`latches = target_gates // 4`. Each D latch implements `Q = (D & En) | (Q_prev & ~En)`:

```
en ──→ NOT ──→ nen

master ───→ AND(master, en)  → d_en
q_prev ───→ AND(q_prev, nen) → q_nen
                              OR(d_en, q_nen) → Q

Next latch: q_prev = Q of this latch
```
4 gates per latch (NOT, AND, AND, OR). Output of latch N feeds latch N+1. Models a shift-register.

---

#### L18 — 8-bit Barrel Shifter (3 stages, blocks repeated)

3 mux stages (shift by 1, 2, 4). Each stage contains 8 two-to-one muxes:

```
Stage 0 (shift by 1):
  sel, nsel = NOT(sel)

  For each of 8 data lanes:
    Out[i] = OR(
               AND(data[i],          nsel),   ← select original
               AND(data[(i-1)%8],    sel )    ← select shifted
             )

Stage 1 (shift by 2): same pattern with shift_amt=2
Stage 2 (shift by 4): same pattern with shift_amt=4
```
Gates per stage: 1 NOT + 8*(AND+AND+OR) = 25. Total per block: 3*25 + 7 (extra data vars) = 82 gates.

---

#### L19 — CRC-8/MAXIM LFSR

`stages_n = target_gates // 12`. Each LFSR stage:

```
reg[0..7] = VARIABLE registers (all start at 0)

feedback = XOR(reg[7], master)    ← MSB XOR serial_in

new_reg[0] = feedback
new_reg[i] = reg[i-1]            if (i-1) not in tap_positions {4, 5}
new_reg[i] = XOR(reg[i-1], fb)   if (i-1) in {4, 5}

output = XOR(new_reg[7], master)  ← read MSB
```
Tap positions 4 and 5 implement the CRC-8/MAXIM polynomial `x⁸+x⁵+x⁴+1`. Models UART/SPI hardware error-detection logic.

---

#### L20 — 8-bit Magnitude Comparator

`blocks = target_gates // 40`. Each block checks if two 8-bit words are equal:

```
For each bit i in 0..7:
  XNOR[i] = NOT(XOR(A[i], B[i]))   ← 1 if A[i] == B[i]

eq = AND(XNOR[0], XNOR[1], ..., XNOR[7])  ← chained AND tree
```
`A[0] = master`, others alternate HIGH/LOW, `B[0..7]` alternate LOW/HIGH (always differ → eq=0). The signal **still propagates** through all XNORs and ANDs when master changes.

---

#### L21 — 1-bit ALU Slice × N

`slices = target_gates // 19`. Each slice computes 4 operations simultaneously and picks one via a 2-bit opcode mux:

```
master ──→ AND(master, B) → res_and
master ──→ OR(master, B)  → res_or
master ──→ XOR(master, B) → res_xor
master ──→ XOR(master, B) ──→ XOR(xab, cin) → res_add   (half-adder sum)

2-bit mux (op0, op1 = opcode):
  Selects one of {res_and, res_or, res_xor, res_add} via AND/OR mux trees
```
The mux is 11 gates. 19 gates total per slice. Stacking N slices models an N-bit RISC processor datapath.

---

### 3.2 What is Measured

For each topology × size:
- **How many times** to toggle `master` is auto-calculated so total theoretical evaluations ≈ 20M (for a fair wall-clock comparison).
- **Best of 3 passes** (OS jitter filtering).
- **ME/s** = actual engine evaluations per second (from the hardware counter `eval_count` if available, else theoretical).
- **Scaling %** = throughput at 100K vs 1K gates, expressed as retention. 100% = perfectly linear scaling. <50% = worse than linear (cache pressure or quadratic algorithms).

---

## 4. `ic_circuit_benchmark.py`

**Purpose:** Test the full IC (Integrated Circuit) system — packaging circuits as reusable components, saving/loading them to JSON, and verifying performance at scale.

This file runs **performance benchmarks** in two phases per backend: IC benchmarks and raw circuit benchmarks.

---

### 4.1 COMPLEX IC BENCHMARK

Builds ICs with a **mixed gate topology** (NOT, XOR, AND, OR, NAND cycles through 5 types per chain):

```
IN[p] ──→ NOT ──→ XOR ──→ AND ──→ OR ──→ NAND ──→ NOT ──→ ...  ──→ OUT[p]
                  ↑        ↑        ↑       ↑
               IN[p]    IN[p]    IN[p]   IN[p]   (second input ties back to same input pin)
```

Each output pin gets a chain of `gate_count // pin_count` gates. For 2-input gate types, the second input always ties back to the same `IN[p]` pin.

| Name | Gates | Pins |
|------|-------|------|
| Micro IC | 10 | 2 |
| Small IC | 500 | 4 |
| Medium IC | 5,000 | 8 |
| Large IC | 25,000 | 16 |
| Massive IC | 75,000 | 32 |
| Colossal IC | 150,000 | 64 |

Measured: **Create**, **Save** (to JSON), **Load** (from JSON into new circuit), **Sim** (toggle all inputs once).

---

### 4.2 COMPLEX CIRCUIT BENCHMARK

A raw circuit (no IC wrapping) built from **three sub-circuits combined**:

```
Segment 1 (1/3 of gates): NOT chain
  V1 ──→ NOT ──→ NOT ──→ NOT ──→ ... (seg gates)

Segment 2 (1/3 of gates): AND pyramid
  V[0..width-1] → AND reduction tree (width = nearest power-of-2 ≥ √seg)

Segment 3 (1/3 of gates): XOR parity chain
  V[0..n_parity-1] → XOR chain (n_parity = min(seg, 1024))
```

All three sub-circuits exist independently in the same `Circuit` object (no connections between them).

| Name | ~Gates |
|------|--------|
| Tiny Circ | 300 |
| Small Circ | 3,000 |
| Medium Circ | 30,000 |
| Large Circ | 150,000 |
| Massive Circ | 500,000 |
| Colossal Circ | 900,000 |

Measured: **Create**, **Save** (`.writetojson()`), **Load** (`.readfromjson()`), **Sim** (toggle first variable).

---

### 4.3 NESTED IC STRESS TEST

**10 levels of nested NOT gates**, each level wrapping the previous in a new IC:

```
Level 0: [IN ──→ NOT ──→ OUT]           saved as nest_0.json

Level 1: [IN ──→ [Level0 IC] ──→ OUT]  saved as nest_1.json
               NOT(x)

Level 2: [IN ──→ [Level1 IC] ──→ OUT]  saved as nest_2.json
               NOT(NOT(x)) = x

...

Level 9: [IN ──→ [Level8 IC] ──→ OUT]  saved as nest_9.json
               NOT⁹(x) = NOT(x) (9 is odd)
```

After building: load `nest_9.json` into a final circuit:
- V = HIGH → `NOT¹⁰(HIGH)` = `HIGH` (10 NOTs: even count → same). **1 check.**
- V = LOW → `NOT¹⁰(LOW)` = `LOW`. **1 check.**

**Confirms: deeply nested ICs chain correctly through 10-level JSON deserialization.**

---

### 4.4 HEAD-TO-HEAD COMPARISON TABLE

After running both Engine and Reactor backends, the benchmark prints a comparison:

```
| Benchmark        | Engine    | Reactor   | Speedup |
|------------------+-----------+-----------+---------|
| Ic Create 10     |  0.72 ms  |  0.23 ms  |   3.1x  |
| Ic Sim   150000  | 32.63 ms  |  0.43 ms  |  75.5x  |
```

The simulation speedup is typically **75x** for large ICs — that's the Cython backend's advantage over pure Python for tight propagation loops.

---

## 5. `iscas_test.py`

**Purpose:** Reality-check the engine against real-world industry-standard benchmarks. The ISCAS-85 and ISCAS-89 benchmark suites are collections of actual synthesized digital circuits used since 1985 to evaluate logic simulation tools. Running Darion against them proves correctness and measures raw throughput on non-trivial netlists.

---

### 5.1 What are ISCAS circuits?

**ISCAS-85** (`tests/ISCAS85/*.v`) — 11 purely combinational circuits (no memory):

| File | Inputs | Outputs | Gates | What it models |
|------|--------|---------|-------|----------------|
| `c17.v` | 5 | 2 | 6 | Tiny NAND-only proof-of-concept |
| `c432.v` | 36 | 7 | 160 | 27-channel interrupt controller |
| `c499.v` | 41 | 32 | 202 | 32-bit error correcting circuit |
| `c880.v` | 60 | 26 | 383 | 8-bit ALU |
| `c1355.v` | 41 | 32 | 546 | 32-bit error correcting circuit (variant) |
| `c1908.v` | 33 | 25 | 880 | 16-bit SEC/DED circuit |
| `c2670.v` | 233 | 140 | 1193 | 12-bit ALU and controller |
| `c3540.v` | 50 | 22 | 1669 | 8-bit ALU |
| `c5315.v` | 178 | 123 | 2307 | 9-bit ALU |
| `c6288.v` | 32 | 32 | 2416 | 16×16-bit multiplier |
| `c7552.v` | 207 | 108 | 3512 | 32-bit adder/comparator |

**ISCAS-89** (`tests/ISCAS89/*.v`) — 15 sequential circuits (circuits with D-type flip-flops / memory):

| File | Inputs | Outputs | DFFs | Gates | What it models |
|------|--------|---------|------|-------|----------------|
| `s27.v` | 4 | 1 | 3 | 10 | Tiny sequential proof-of-concept |
| `s382.v` | 6 | 6 | 21 | 91 | 8-bit linear feedback shift register |
| `s420.v` | 18 | 16 | 16 | 119 | 8-bit counter/comparator |
| `s641.v` | 54 | 42 | 19 | 229 | BCD counter |
| `s713.v` | 54 | 42 | 19 | 253 | BCD counter (variant) |
| `s1238.v` | 14 | 14 | 18 | 340 | 8-bit counter/output select |
| `s1488.v` | 8 | 19 | 6 | 422 | Priority encoder + controller |
| `s1423.v` | 17 | 5 | 74 | 411 | Self-correcting counter |
| `s5378.v` | 35 | 49 | 179 | 1004 | 8-bit multiplier-accumulate |
| `s9234.v` | 36 | 39 | 211 | 1572 | Sequential multiplier core |
| `s13207.v` | 62 | 152 | 638 | 2233 | Complex controller |
| `s15850.v` | 77 | 150 | 597 | 3048 | Large data path |
| `s35932.v` | 35 | 320 | 1728 | 8870 | Systolic array processor |
| `s38584.v` | 38 | 304 | 1452 | 11448 | Large systolic array |
| `s38417.v` | 28 | 106 | 1636 | 10098 | Large systolic array (variant) |

All circuits are provided as Verilog netlist files (`.v`). They are structurally flat: no behavioral RTL, just gate-level interconnects.

---

### 5.2 How the Verilog parser works (`VerilogRunner`)

The `VerilogRunner` class reads each `.v` file and translates it directly into Darion circuit objects:

#### Step 1 — Build 8 Master Variables (the stimulus source)

```python
self.master_vars = [circuit.getcomponent(Const.VARIABLE_ID) for _ in range(8)]
```

These 8 VARIABLE nodes are the "chaos generators." Each one is independently toggled during the benchmark with random HIGH/LOW values. They are connected through XOR gates to drive the circuit inputs (see Step 2).

Two constant rails are also created:
```
VCC (HIGH)  →  always HIGH
GND (LOW)   →  always LOW
```

#### Step 2 — Parse `input` declarations → XOR-driven input nodes

For every port listed in `input N1, N2, ...;`, a special **hardware-accelerated noise generator** is created:

```
master[random] ──→ XOR ──→ IN_N1
                ↗
polarity (random HIGH or LOW)
```

- One of the 8 master variables is chosen at random.
- The second XOR input is randomly VCC or GND (50/50).
- This makes every circuit input toggle pseudo-randomly, correlated to the master clock — produces realistic, dense switching activity.

Why XOR? Because `XOR(master, 0) = master` and `XOR(master, 1) = NOT(master)`. The polarity flip creates variety across inputs without needing separate toggle calls per input.

#### Step 3 — Parse gate declarations

Each gate statement like `nand NAND2_1 (N10, N1, N3);` is translated:

| Verilog gate | Darion gate | Notes |
|---|---|---|
| `and` | `AND_ID` | |
| `nand` | `NAND_ID` | |
| `or` | `OR_ID` | |
| `nor` | `NOR_ID` | |
| `xor` | `XOR_ID` | |
| `xnor` | `XNOR_ID` | |
| `not` | `NOT_ID` | |
| `dff` | XOR input node (**loop cut**) | See §5.3 |

The first port in the list is always the *output* wire. Remaining ports are *inputs*. `setlimits` is called for multi-input gates.

#### Step 4 — Wire connections

After all gates are created, a second pass resolves the wires:
- `1'b0`, `gnd`, `GND` → connects to the GND constant VARIABLE.
- `1'b1`, `vcc`, `VDD` → connects to the VCC constant VARIABLE.
- A wire name that has a gate → `circuit.connect(target_gate, source_gate, pin_index)`.
- A wire name that was never assigned (dangling) → a new XOR noise generator is created for it (graceful handling of partial netlists).

#### Step 5 — Attach PROBE buffers to all declared outputs

```python
for wire_name in self.outputs:
    driver = self.nodes.get(wire_name)
    if driver is not None:
        probe = self.circuit.getcomponent(Const.PROBE_ID)
        probe.rename(f"OUT_{wire_name}")
        self.circuit.connect(probe, driver, 0)
```

Each declared output wire gets a **PROBE** node attached. Probes are single-input pass-through buffers — they do not alter the signal but serve as stable, named observation points. This prevents output nodes from being "leaf" nodes that the simulator might skip evaluating under certain optimizations.

---

### 5.3 DFF Loop Cut (ISCAS-89 specific)

Sequential circuits (ISCAS-89) contain D-type flip-flops (`dff`) which create feedback cycles:

```
DFF output Q ──→ combinational logic ──→ DFF input D ──→ (next clock cycle → Q)
```

This would create a circular dependency that the combinational event-driven simulator cannot handle. The solution: **loop cutting**. When a `dff` statement is parsed, its output wire is treated as a **primary input** — it gets its own XOR noise generator:

```verilog
// Original:
dff DFF_0(CK, Q, D);   // flip-flop: output=Q, clock=CK, data=D

// Treated as:
master[random] ──→ XOR ──→ DFF_Q   (Q becomes a freely-toggling input)
```

The D-input and clock are ignored. This transforms the sequential circuit into a purely combinational simulation target, which is valid for **throughput benchmarking** — we want to measure how fast the engine evaluates the gate network, not simulate accurate flip-flop behavior.

---

### 5.4 Benchmark execution (`run_benchmark`)

```python
def run_benchmark(self, vectors=10_000, use_optimize=True):
```

1. **Simulate**: `circuit.simulate(Const.SIMULATE)` — initializes the propagation engine.
2. **Optimize**: if `use_optimize` and the circuit has `.optimize()`, call it (DOD topological sort).
3. **Pre-compute instructions**: build a flat list of `(master_var, HIGH_or_LOW)` toggle commands. For `vectors` iterations, all 8 master variables get a random state assignment. Total instruction count = `vectors × 8`.
4. **Measure loop overhead**: time an empty Python for-loop over the instructions (measures pure Python object-access latency without any simulation work).
5. **Execute**: replay the instruction list, calling `circuit.toggle(gate, state)` for each.
6. **Compute net time**: `pure_execution_ns = (active_time) - (empty_loop_overhead)`.

**Default vector counts:**
- Reactor backend: **50,000 vectors** (= 400,000 toggle calls per circuit)
- Engine backend: **500 vectors** (Engine is ~100x slower; this prevents test runs taking hours)

**Stats returned per circuit:**
- `nodes` — total gate objects in the circuit
- `duration` — benchmark time in milliseconds (net, overhead subtracted)
- `evals` — total gate evaluations performed (`circuit.eval_count`)
- `throughput` — `evals / duration` in **Million evals/sec**

---

### 5.5 Report generation

All results are written to `tests/iscas89_summary.txt` (despite the name, it covers both ISCAS-85 and ISCAS-89 when you point to either directory).

The report is sorted by node count (ascending). A footer prints:
- Total valid circuits tested
- Total gate evaluations performed across all circuits
- Total wall-clock time
- **Average throughput** in ME/s

**Sample output (ISCAS-89, Reactor, 50K vectors):**

```
Circuit         |      Nodes |    Time (ms) |     Total Evals | Speed (M evals/s)
s27.v           |         19 |        14.56 |         763,931 |           52.46
s382.v          |        183 |        36.50 |       9,063,009 |          248.33
...
s38417.v        |     23,705 |      8537.31 |   1,043,127,761 |          122.18

Total Valid Circuits : 15
Total Evaluations    : 4,551,863,768
Total Benchmark Time : 34.38 seconds
AVERAGE THROUGHPUT   : 132.40 Million evals/sec
```

**Interpretation:** Smaller circuits (s27, 19 nodes) show lower throughput because the fixed overhead of 8 master-variable toggles dominates. Larger circuits do more useful work per toggle call, so their ME/s rises before eventually plateauing where memory bandwidth becomes the bottleneck (~130–260 ME/s depending on topology density).

---

### 5.6 CLI flags

| Flag | Effect |
|------|--------|
| `directory` (positional) | Path to folder containing `.v` files. Searched recursively. |
| `--engine` | Use pure Python Engine instead of Cython Reactor |
| `--no-optimize` | Skip `circuit.optimize()` (DOD topological sort) |
| `--vectors N` | Override the auto-selected vector count |

**Typical invocations:**
```bash
# ISCAS-89 on Reactor (default)
python tests/iscas_test.py tests/ISCAS89

# ISCAS-85 on Engine, no optimization, 200 vectors
python tests/iscas_test.py tests/ISCAS85 --engine --no-optimize --vectors 200
```

---

## 6. `defragmentation_test.py`

**Purpose:** Directly measure the performance impact of memory fragmentation in the Reactor backend and quantify how much `circuit.optimize()` (DOD topological reordering) recovers.

This test is the cleanest possible proof that **physical memory layout** — not algorithm complexity — dominates simulation throughput once circuits reach a certain size.

---

### 6.1 Constants

```python
GATE_COUNT = 1_500_000   # Gate objects allocated per test
VECTORS = 100            # Toggle round-trips per benchmark pass
```

1.5 million gates is large enough that the difference between linear and fragmented layout is clearly visible across CPU cache tiers.

---

### 6.2 Two Topology Builders

#### `wire_linear_chain(circuit, master, pool)`

```
master ──→ pool[0] ──→ pool[1] ──→ pool[2] ──→ ... ──→ pool[GATE_COUNT-1]
```

All gates are NOT gates wired in a strict sequential chain. `setlimits(g, 1)` ensures each gate has exactly one input. This maximizes the chance that cache-ordered access patterns benefit from `optimize()`.

#### `wire_dense_braid(circuit, master, pool)`

```
Layer 0:    [master] [master] [master] [master]   (4 lanes, all start from master)
             │         │         │         │
             ▼         ▼         ▼         ▼
Layer 1:  AND(0,1)  AND(1,2)  AND(2,3)  AND(3,0)   ← wrap-around
             │         │         │         │
Layer 2:  AND(0,1)  AND(1,2)  AND(2,3)  AND(3,0)
             ...
```

AND gates with 2 inputs each. Each gate connects to lane `i` and lane `(i+1) % 4` from the previous layer. Consumes `GATE_COUNT` AND gates in groups of 4 per layer. This topology has **high inter-dependency between adjacent gates**, making memory layout especially important.

---

### 6.3 Three-Phase Profiling (`run_test`)

For each topology, three passes are run **on the same wiring** but with different physical memory layouts:

#### Pass 1 — PRISTINE (Ideal Layout)

```python
circuit = Circuit()
master = circuit.getcomponent(Const.VARIABLE_ID)
gates_pool = [circuit.getcomponent(NOT_ID) for _ in range(GATE_COUNT)]

# Wire in order (gates_pool[0] → gates_pool[1] → ...)
actual_count = wiring_func(circuit, master, gates_pool)
circuit.simulate(Const.SIMULATE)
t_pristine = execute_pass(circuit, master, actual_count)
```

Gates are allocated in the order they are used. The Cython memory allocator places them in (nearly) contiguous heap positions. This is the **best-case layout** — simulates a circuit built entirely programmatically in one pass.

After measuring, `circuit.clearcircuit()` is called and the circuit object is deleted to free memory before the next pass.

#### Pass 2 — FRAGMENTED (GUI-Realistic / Worst Case)

```python
circuit = Circuit()
master = circuit.getcomponent(Const.VARIABLE_ID)
gates_pool = [circuit.getcomponent(NOT_ID) for _ in range(GATE_COUNT)]

random.seed(42)
random.shuffle(gates_pool)   # ← Randomize order BEFORE wiring

wiring_func(circuit, master, gates_pool)
circuit.simulate(Const.SIMULATE)
t_fragmented = execute_pass(circuit, master, actual_count)
```

All 1.5M gate objects are allocated, **then** shuffled randomly, **then** wired. The simulation engine traverses them in the same logical order as Pristine — but the physical objects are now scattered randomly throughout heap memory. Every gate access → **cache miss**.

This simulates the real-world GUI scenario: users build circuits non-sequentially, delete gates in the middle, paste sub-circuits from different sessions, etc.

#### Pass 3 — OPTIMIZED (DOD Topological Sort)

```python
# Same circuit object from Pass 2 (still fragmented)
circuit.optimize()   # ← Topological sort + memory copy into contiguous layout

t_optimized = execute_pass(circuit, master, actual_count)
```

`circuit.optimize()` performs:
1. **Topological sort** of all gates from inputs to outputs.
2. **Memory copy** into a fresh, contiguous internal array in topological order.
3. **Pointer update** of all cross-references (sources, hitlists) to point to new locations.

After `optimize()`, the physical memory layout again matches the traversal order. This should recover most of the Pristine throughput.

---

### 6.4 `execute_pass(circuit, master, actual_count)`

```python
def execute_pass(circuit, master, actual_count):
    start_evals = circuit.eval_count
    start_time = time.perf_counter()
    for _ in range(VECTORS // 2):
        fast_toggle(master, Const.HIGH)
        fast_toggle(master, Const.LOW)
    end_time = time.perf_counter()

    pass_evals = circuit.eval_count - start_evals
    throughput = (pass_evals / duration) / 1_000_000
    return throughput  # ME/s
```

- `VECTORS // 2 = 50` round-trip toggle pairs = 100 total toggles.
- The delta of `eval_count` gives the exact number of gate evaluations performed (not estimated).
- Throughput in **ME/s**.

---

### 6.5 Output format

```
=======================================================================
 DARION LOGIC SIM: ADVANCED TOPOLOGY RAM/CACHE PROFILER (V4)
=======================================================================
Gate Count per Test: ~1,500,000 | Vectors: 100

Topology        |   Pristine (Ideal) |   GUI Fragmented |   Optimized (DOD)
-------------------------------------------------------------------------
Linear Chain    |        812.34 ME/s |       121.45 ME/s |       798.23 ME/s (+557%)
Dense Braid     |        544.12 ME/s |        89.34 ME/s |       521.87 ME/s (+484%)
=======================================================================
```

**Column interpretation:**

| Column | Meaning |
|--------|---------|
| **Pristine** | Ideal throughput — the ceiling the engine can achieve |
| **GUI Fragmented** | Expected real-world performance without optimization |
| **Optimized (DOD)** | Throughput after `circuit.optimize()` call |
| **+N%** | Relative recovery from Fragmented to Optimized |

**Key insight:** A ~6–7x fragmentation penalty (Pristine ÷ Fragmented) is typical on modern x86 processors with 1.5M gates, because the L3 cache cannot hold more than ~1–2M small objects. After `optimize()`, throughput typically recovers to within 2–5% of Pristine. This demonstrates that `optimize()` is not a minor micro-optimization — it is a **fundamental architectural requirement** for high-performance simulation of large circuits.

---

## 7. `integrity_test.py`

**Purpose:** The master correctness test suite. Verifies that every feature of the Darion engine (gates, connections, IC packaging, serialization, undo/redo, truth tables, optimization) produces exact correct results across thousands of assertions. This is the gatekeeper test — everything must pass before a change ships.

This file is ~5000 lines and runs asynchronously. It is organized into **8 sequential sections**:

---

### 7.1 Section: UNIT TESTS

Heavy stress tests of individual API calls.

| Subsection | What it does | Key assertion |
|---|---|---|
| Gate Construction (1000 each) | Creates 1000 instances of every gate type (NOT, AND, NAND, OR, NOR, XOR, XNOR) | All 1000 have `output == UNKNOWN` |
| Gate Logic (Full Truth Tables) | For each gate type, checks all 4 combinations of 2-input truth table 100 times | Exact truth-table match |
| Profile Operations (1000 connections) | Creates 1000 AND gates all connected to one source VARIABLE | `len(source.hitlist) == 1000`; all 1000 go HIGH on toggle |
| Book Tracking (100-input gate) | Creates a 100-input AND gate, toggles inputs from LOW→HIGH one at a time | `book[LOW]` and `book[HIGH]` counters track correctly |
| Connection Stress (500 cycles) | Connects/disconnects same slot 500 times | After disconnect, `sources[0] is None` |
| Delete Stress | Creates and `delobj`s gates under load | No dangling references |
| Disconnection Stress (50-source gate) | Connects 50 sources, disconnects them all in reverse | All `sources[i] is None` |
| Variable Rapid Toggle (10000) | Toggles a VARIABLE 10,000 times alternating HIGH/LOW | Final state is HIGH (10000 is even) |
| Probe Chain (100 probes) | Connects 100 PROBE gates to one VARIABLE | All 100 probes show HIGH after one toggle |
| IO Pins (50 chains) | Creates 50 `V → INPUT_PIN → NOT → OUTPUT_PIN` chains | All chains created without error |
| setlimits (Expand/Contract) | Expands and contracts an AND gate's input limit: 2→10→100→500→1000→500→100→10→2 | `gate.inputlimit` matches exactly each step |

---

### 7.2 Section: COMPREHENSIVE COVERAGE

Full truth-table verification of every gate type in `SIMULATE` mode, plus multi-input variants.

| Subsection | Checks |
|---|---|
| Every Gate (SIMULATE mode) | NOT: 2 checks. AND: 4. NAND: 4. OR: 4. NOR: 4. XOR: 4. XNOR: 4. Variable: 3. Probe: 2. InputPin: 1. OutputPin: 1 |
| Every Gate (Multi-Input) | Each gate type expanded to 4 inputs via `setlimits`. Tests boundary states (all HIGH, all LOW, one-flip). |
| All Gate Methods | Verifies `rename()`, `reset()`, `hide()`/`reveal()`, `transfer_info()` work on every gate type |
| All Circuit Methods | Verifies `clearcircuit()`, `getcomponents()`, `simulate()`, `optimize()` |
| Mixed Gate Circuit | Builds a combined NOT+AND+OR+XOR+NAND circuit, toggles inputs, verifies all outputs |
| Transfer Info | Verifies that `transfer_info(source, target)` correctly copies name, location, and book state |

---

### 7.3 Section: CIRCUIT STRESS

| Subsection | What it builds | Key assertion |
|---|---|---|
| Circuit Management (create/delete/reconnect) | Creates 100 circuits, builds gates, connects, disconnects, and deletes | No memory corruption across create/delete cycles |
| Propagation Deep Chain | NOT chain of 10,000 gates | Signal propagates all the way to end in one toggle |
| Propagation Wide Fan-Out | One VARIABLE drives 10,000 AND gates | All 10,000 outputs update correctly |
| Hide/Reveal Stress | Hides and reveals 1,000 gates 10 times each | `gate.hidden` flag toggles correctly |
| Reset Stress | Resets circuits under various configuration states | All outputs return to UNKNOWN |

---

### 7.4 Section: EVENT MANAGER

Tests the undo/redo command stack (Edit → Undo in the UI).

| Subsection | Tests |
|---|---|
| Undo/Redo Stress (1000 ops) | Performs Add, Connect, Rename, Delete, SetLimits commands, then undo/redo the entire stack | Each undo restores exact previous state |
| Rapid Undo/Redo | Alternates undo/redo 500 times at maximum speed | No state corruption under rapid alternation |

---

### 7.5 Section: IC TESTS

Verifies the IC packaging system end-to-end.

| Subsection | What it builds | Key assertions |
|---|---|---|
| IC Basic Functionality | Wraps a NOT gate in an IC, exposes 1 IN, 1 OUT pin | Output = NOT(input) |
| IC Nested | Places one IC inside another IC | Correct logical output through both levels |
| IC Deeply Nested | 5-level nesting | Consistent output through all 5 levels |
| IC Many Pins | IC with 64 input pins and 64 output pins | All 64 outputs receive correct values |
| IC Complex Internal | IC containing a full 8-bit ripple-carry adder | Correct addition results |
| IC Save/Load | Saves IC to JSON, loads into fresh circuit | Post-load results identical to pre-save |
| IC Hide/Reveal | Hides and reveals IC contents | Hidden IC still propagates correctly |
| IC Reset | Resets IC and connected circuit | Both return to UNKNOWN |
| IC Copy/Paste | Pastes an IC into a new circuit position | Pasted IC behaves identically |
| IC Massive Internal | IC containing 50,000 gates | No crash, correct output |
| IC Cascade | Chain of 10 ICs, each wrapping the previous | Correct output through all 10 |
| IC Multi-Output | IC with 16 distinct output pins | Each pin independently correct |
| IC Stress Bulk | Creates and destroys 100 ICs in a loop | No memory leaks |
| IC Pin Change & Reorder | Adds/removes pins from a live IC | Circuit remains valid and correct |

---

### 7.6 Section: SERIALIZATION

Tests `.writetojson()` / `.readfromjson()`.

| Subsection | Tests |
|---|---|
| Save/Load Large Circuit | 100,000-gate circuit saved and reloaded | All gates, connections, and book states restored exactly |
| Copy/Paste Stress (1000 ops) | Copies and pastes circuit fragments 1000 times | No state corruption, correct logical behavior |
| Copy/Paste Complex | Pastes circuits with nested ICs and mixed gate types | Nested structure survives round-trip |

---

### 7.7 Section: TRUTH TABLE

Exhaustively verifies truth tables for larger circuits using all 2^N input combinations.

| Subsection | Circuit | Inputs | Patterns |
|---|---|---|---|
| 4-input truth table | Mixed AND/OR/XOR logic | 4 | 16 |
| 6-input truth table | Mixed logic | 6 | 64 |
| 8-input truth table | Mixed logic | 8 | 256 |
| 10-input truth table | Mixed logic | 10 | 1,024 |
| Complex truth table | 8-bit parity checker | 8 | 256 |
| Partial truth table | 12-input randomly sampled | 12 | 4,096 sampled |

---

### 7.8 Section: REFRESH / OPTIMIZE (Reactor only)

Tests the `circuit.optimize()` and `circuit.refresh()` operations in depth.

| Subsection | Tests |
|---|---|
| Optimize Topological Order | After optimize, gate traversal order equals topological depth order |
| Optimize Location Remap | Gate `.location` fields updated consistently after optimize |
| Refresh Trims Trailing Deleted | Deleted gates at end of array are trimmed |
| Delobj Marks Negative Type | `delobj()` sets `gate.type = -1` (tombstone marker) |
| Delobj Counter Decrements | `circuit.gate_count` decreases by 1 after each `delobj` |
| Refresh Delete Middle Gate | Deleting a gate in the middle of the array leaves others intact |
| Refresh Delete All Gates | Deleting every gate leaves `gate_count == 0` |
| Optimize Functional Correctness | After optimize, gates produce the same outputs as before |
| Optimize Cache Ordering | Memory addresses of gates are monotonically increasing after optimize |
| Optimize with Cycles | Optimize on a circuit with feedback loops does not crash |
| Refresh After IC Deletion | Deleting an IC's internal gates then calling refresh is safe |
| Optimize Reconnect After | Can add new gates and reconnect after optimize |
| Refresh Idempotent | Calling `refresh()` twice gives same result as once |
| Optimize Large Circuit | 500,000-gate circuit optimizes in finite time |
| Optimize Gate-Verse Sync | `circuit.gate_verse` (Python side) and Cython array stay in sync |
| Refresh Delete Re-Add | Delete a gate, add a new one to the same slot, verify index reuse |

---

### 7.9 Section: REAL-WORLD STRESS

End-to-end correctness tests using real digital logic primitives.

| Subsection | What it builds | Scale | Key assertion |
|---|---|---|---|
| Ripple Adder Correctness | Full 16-bit ripple-carry adder | 80 gates | Correct sum for 50 random A+B pairs |
| SR Latch Metastability | 1000 SR latches, rapid S/R toggling | 4000 gates | No infinite loop, stable output |
| Mux Tree | 10-bit address → 1024-output decoder mux | ~10K gates | Correct output selected for each address |
| Ring Oscillator | 50-NOT ring | 50 gates | Engine detects oscillation (runner alive or ERROR state) |
| Decoder/Encoder | 8-bit decoder + 8-bit priority encoder (round-trip) | ~512 gates | Encoded address matches original |
| Cascade Adder Pipeline | 4 stages of 8-bit adgers chained | ~160 gates | Pipeline output correct after all stages settle |
| XOR Parity Generator | 1024-bit XOR tree | 1023 gates | Correct parity for a sweep of input patterns |
| Glitch Propagation | 500-NOT chain with parallel XOR observers | 1000 gates | No oscillation, correct final outputs |
| Hot Swap Under Load | 200 connect/disconnect ops on live simulating circuit | N/A | No crash or stale propagation |
| Reconvergent Fan-Out | Depth-10 diamond (one source, many reconvergent paths) | ~2K gates | Output computed correctly despite multiple paths from same source |

---

## 8. Summary Table

| File | Primary Question | Key Metric | Backend |
|------|-----------------|------------|---------|
| `book_benchmark.py` | Is the Book Algorithm faster than naïve BFS? | ns/gate, speedup ratio | Engine + Reactor |
| `cache_test.py` | At what circuit size does CPU cache fall? | ns/eval, cache tier boundary | Reactor |
| `Complexity_scale.py` | Which circuit shapes are cheaper/harder to simulate? | ME/s per topology per size | Engine + Reactor |
| `ic_circuit_benchmark.py` | Do IC packaging + JSON serialization work at scale? | ms per operation | Engine + Reactor |
| `iscas_test.py` | How fast is the engine on real-world industry netlists? | ME/s per ISCAS circuit | Engine + Reactor |
| `defragmentation_test.py` | How much does memory fragmentation hurt, and how much does `optimize()` recover? | ME/s: Pristine vs Fragmented vs Optimized | Reactor only |
| `integrity_test.py` | Is every single feature correct and stable under stress? | Pass/Fail count, thousands of assertions | Engine + Reactor |

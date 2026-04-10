# Darion Logic Sim — Benchmark Documentation
> **Audience:** You know Python, but know nothing about digital logic circuits.
> This document tells you exactly what every benchmark builds, wire by wire, and what it's measuring.

---

## Table of Contents
1. [Shared Concepts](#0-shared-concepts)
2. [book_benchmark.py](#1-book_benchmarkpy)
3. [cache_test.py](#2-cache_testpy)
4. [Complexity_scale.py](#3-complexity_scalepy)
5. [ic_circuit_benchmark.py](#4-ic_circuit_benchmarkpy)

---

## 0. Shared Concepts

Before reading anything else, you need three mental models.

### 0.1 What is a "gate"?
Think of a gate as a Python object that reads one or more *input* voltage values (`HIGH=1` or `LOW=0`) and immediately computes an *output*. The gates used are:

| Name | Symbol | Rule |
|------|--------|------|
| **VARIABLE** | `V` | A free input — you set it with `toggle()`. Has only an output. |
| **NOT** | `¬` | Output = opposite of input: `HIGH→LOW`, `LOW→HIGH` |
| **AND** | `&` | Output = `HIGH` only when **all** inputs are `HIGH` |
| **OR** | `\|` | Output = `HIGH` when **any** input is `HIGH` |
| **XOR** | `^` | Output = `HIGH` when an **odd number** of inputs are `HIGH` |
| **NAND** | `¬&` | Output = NOT(AND): `HIGH` unless all inputs are `HIGH` |
| **INPUT_PIN / OUTPUT_PIN** | `IN`/`OUT` | Boundary markers for packaging a circuit as an IC |

### 0.2 What does `connect(gate, source, slot)` do?
It wires `source.output` into input slot `slot` of `gate`. After every `toggle()`, the engine re-evaluates all gates that are downstream of the changed node.

### 0.3 Two backends
Every benchmark can run against two implementations of the same engine API:

| Backend | Language | Location |
|---------|----------|----------|
| **Engine** | Pure Python | `engine/` |
| **Reactor** | Cython (compiled C) | `reactor/` |

The measured numbers let you see the speedup of Reactor over Engine.

---

## 1. `book_benchmark.py`

**Purpose:** Prove that the engine's *Book Algorithm* is faster than a naïve BFS propagation.

### 1.1 What is the Book Algorithm?

When a gate's output changes, only the gates **directly connected** to it need to be re-evaluated. The Book Algorithm maintains an exact "hitlist" per gate so it visits only those gates — nothing more. Naïve BFS uses a queue and re-scans every gate in the frontier, which is wasteful.

The file contains **three** circuit constructions, each tested with both algorithms side by side.

---

### TEST 1 — Single AND Gate, Varying Fan-In

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

More precisely, `input_count` ranges from 2 to 1024. For each value:

1. Create a **VARIABLE** called `toggle_var` (starts UNKNOWN).
2. Create a **VARIABLE** called `high_var` and set it permanently to `HIGH`.
3. Build a **chain of 1000 AND gates**:
   - Slot 0 of each AND gets the previous gate (or `toggle_var` for the first).
   - Slots 1 through N-1 all get `high_var`.
4. Trigger: `toggle(toggle_var, HIGH)` then `toggle(toggle_var, LOW)`.

**What this simulates:**
A wide AND gate (e.g., 1024 inputs) that must count how many of its inputs are HIGH before deciding its output. The Book version updates the HIGH-count incrementally; the Naive version checks all sources every time.

**Example for N=4, chain length 3:**
```
V_toggle ──→ [AND4] ──→ [AND4] ──→ [AND4] → output
V_high   ──↗↗↗       ↗↗↗       ↗↗↗
(slots 1,2,3 all tie to V_high)
```

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

Each `OR` gate has `inputs_per_gate` inputs, all from **the same shared set of VARIABLE nodes**. Toggling any variable causes all M OR gates to re-evaluate.

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

**What is built:** The simplest possible depchain:

```
V ──→ [NOT] ──→ [NOT] ──→ [NOT] ──→ ... (N times) ──→ final_NOT
```

Chain lengths tested: 1K, 10K, 100K, 500K, 1M NOT gates.

Each toggle of `V` must propagate a signal change all the way through the chain. This directly measures **per-gate evaluation latency** since there is zero parallelism.

**Output columns:**
- `ns/g(B)` = nanoseconds per gate in the Book algorithm
- `ns/g(N)` = nanoseconds per gate in the Naive algorithm

---

## 2. `cache_test.py`

**Purpose:** Find the exact sizes where circuits no longer fit in CPU cache, causing measurable performance cliffs.

### 2.1 One circuit is built: a Mixed Chain

```
V_first ──→ [AND] ──→ [OR] ──→ [XOR] ──→ [NOT] ──→ [AND] ──→ [OR] ──→ ...
              ↑          ↑        ↑
           V_high    V_low    V_low
```

The pattern rotates through 4 gate types: AND, OR, XOR, NOT. Their second inputs are tied to constant `HIGH` or `LOW` variables so every gate always has a valid output — but the only *interesting* input is from the chain itself.

**Exact wiring rule (from `build_chain`):**
- `AND` gate: `connect(g, prev, 0)` and `connect(g, const_high, 1)` → AND(prev, 1) = just prev
- `OR/XOR` gate: `connect(g, prev, 0)` and `connect(g, const_low, 1)` → OR(prev, 0) = just prev
- `NOT` gate: `connect(g, prev, 0)` → NOT(prev)

So functionally it's just a long inverting/non-inverting pass-through, but structurally it exercises the propagation scheduler.

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

The code tracks `ns/eval` as circuit size increases. When `ns/eval` suddenly jumps >15% compared to a rolling 3-point average, it marks a **cache boundary**:

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

Each level uses `target_gates` as its size parameter. Here is exactly what is built:

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

Toggle → both chains fire → **O(N) simultaneous events** hit the scheduler. Tests event-queue saturation.

---

#### L5 — Queue Thrash O(N²)
```
           ┌──────────────────────────────────┐
           │                                   ↓
V ──→ XOR[0] ──→ XOR[1] ──→ XOR[2] ──→ ... ──→ XOR[N-1]
│    ↑ (slot 1: static_low)
└────┘ (slot 0: master for ALL XOR gates)
```
This is an XOR **chain** where:
- XOR[0]: inputs = `master`, `static_low`
- XOR[i]: inputs = `master`, `XOR[i-1]` (previous output)

Every XOR depends on `master` (slot 0). One toggle fires ALL N XOR gates immediately, which fire again as their predecessors' outputs change → **O(N²) re-evaluations**. This is the absolute worst case.

---

#### L6 — Sparse Fan-In
```
V ───┐
V2 ──┤
V3 ──┼──→ XOR ──→ XOR ──→ XOR ──→ ... → single output
V4 ──┤
...  ┘
```
A set of independent VARIABLE nodes (each set LOW, except master) feeds a **binary XOR reduction tree**. All sources change together → tests simultaneous wide fan-in merging.

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
4 parallel lanes of AND gates. Each AND gate takes inputs from lane `i` and lane `(i+1) % 4` (wraps around). This maximises **wire density**: every gate depends on two neighbors, modeling a tightly coupled datapath.

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
First expands in a binary fan-out tree, then AND-reduces all leaves pair-by-pair back to one output. The hourglass tests both the expand and contract phases in one circuit.

---

#### L9 — Hamming(7,4) ECC

A [7,4] Hamming code computes 3 parity bits (p1, p2, p3) from 4 data bits (d1-d4). The wiring:

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
The critical path is the carry chain. Each bit must wait for the carry from the previous bit. The final output of a 100-bit adder requires 100 carry propagations in sequence.

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
A balanced OR-reduction tree. Every leaf fires when master changes → O(N) evaluations cascade through O(log₂ N) levels. Models interrupt-controller "any-bit-set" logic.

---

#### L12 — Wallace Tree Multiplier

A 3-to-2 compressor (a full adder) reduces 3 inputs to 2 (a sum bit and a carry bit), then repeats until only 2 signals remain:

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
`R_node` and `S_node` are VARIABLE nodes set to LOW. `latches = target_gates // 4`. Partial feedback path (Q feeds into Q_bar's OR gate's second input is S, not Q — this avoids true feedback loops). Tests graceful behavior under cyclic-adjacent topology.

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
Connections point backward only (no cycles). Gate types are chosen randomly from {NOT, XOR, AND, OR}. Cache-unfriendly, branch-predictor-hostile — a synthesized netlist worst case.

---

#### L15 — Decoder Tree

An N-bit binary address decoder produces 2^N outputs, one per address combination:

```
addr[0], addr[1], ..., addr[9]   (up to 10 address bits)
NOT(addr[0]), NOT(addr[1]), ...   (complement lines)

output[0] = AND(NOT(addr[0]), NOT(addr[1]), ..., NOT(addr[9]))  = minterm 0000000000
output[1] = AND(addr[0],     NOT(addr[1]), ..., NOT(addr[9]))   = minterm 0000000001
...
output[1023] = AND(addr[0], addr[1], ..., addr[9])              = minterm 1111111111
```
Each output is a chain of `addr_bits - 1` two-input AND gates selecting true or complement. Extreme fan-out: `addr[0]` feeds half of all 1024 AND chains.

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
The key advantage over L10: **all carries are computed in parallel** using the P/G signals. The carry chain length is constant per block rather than growing with bit width.

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
4 gates per latch (NOT, AND, AND, OR). Output of latch N feeds latch N+1. Models a shift-register or pipelined register file. `en` is set to `HIGH=1`, so `D` passes through directly.

---

#### L18 — 8-bit Barrel Shifter (3 stages, blocks repeated)

3 mux stages (shift by 1, 2, 4). Each stage contains 8 two-to-one muxes:

```
Stage 0 (shift by 1):
  sel, nsel = sel's NOT

  For each of 8 data lanes:
    Out[i] = OR(
               AND(data[i],          nsel),   ← select original
               AND(data[(i-1)%8],    sel )    ← select shifted
             )

Stage 1 (shift by 2): same pattern with shift_amt=2
Stage 2 (shift by 4): same pattern with shift_amt=4
```
Gates per stage: 1 NOT + 8*(AND+AND+OR) = 25. Total per block: 3*25 + 7 (extra data vars) = 82 gates. `master` is `data[0]`, so toggling it propagates through all 3 mux stages.

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
`A[0] = master`, `A[1..7]` alternate HIGH/LOW, `B[0..7]` alternate LOW/HIGH (so they always differ → eq=0). But the signal **still propagates** through all XNORs and ANDs when master changes. Models address comparators and content-addressable memory (CAM).

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
The mux is 11 gates (4 sub-selectors → 2 ORs → 1 OR). 19 gates total per slice. Stacking N slices models an N-bit RISC processor datapath.

---

### 3.2 What is Measured

For each topology × size:
- **How many times** to toggle `master` is auto-calculated so total theoretical evaluations ≈ 20M (for a fair wall-clock comparison).
- **Best of 3 passes** (OS jitter filtering).
- **ME/s** = actual engine evaluations per second (from the hardware counter `eval_count` if available, else theoretical).
- **Scaling %** = throughput at 100K vs 1K gates, expressed as retention. 100% = perfectly linear scaling. <50% = worse than linear (cache pressure or quadratic algorithms).

---

## 4. `ic_circuit_benchmark.py`

**Purpose:** Test the full IC (Integrated Circuit) system — packaging circuits as reusable components, saving/loading them to JSON, and verifying correctness.

This is the most comprehensive file. It runs in two phases per backend: **integrity tests** (correctness) and **performance benchmarks** (speed).

---

### 4.1 INTEGRITY TESTS (33 checks)

These build small circuits and verify exact logical correctness.

---

#### Test 1 — NOT Chain (even/odd inversion)

```
V ──→ NOT(1) ──→ NOT(2) ──→ NOT(3) ──→ NOT(4) → end4
V ──→ NOT(1) ──→ NOT(2) ──→ NOT(3) ──→ NOT(4) ──→ NOT(5) → end5
```
*(Both chains start from the same V)*

- Toggle V = HIGH
- `end4.output` must be `HIGH` (even inversions: HIGH→LOW→HIGH→LOW→HIGH)
- `end5.output` must be `LOW` (odd inversions)
- Toggle V = LOW
- `end4.output` must be `LOW`

**3 checks.**

---

#### Test 2 — Half Adder Correctness

```
VA ──→ XOR → SUM
VA ──→ AND → CARRY
VB ──↗↗
```

A half adder adds two 1-bit numbers. It has no carry-in.

Truth table verified:

| A | B | SUM | CARRY |
|---|---|-----|-------|
| 0 | 0 |  0  |   0   |
| 1 | 0 |  1  |   0   |
| 0 | 1 |  1  |   0   |
| 1 | 1 |  0  |   1   |

**4 checks (one per row).**

---

#### Test 3 — 8-bit Ripple-Carry Adder

Built from: **1 half adder** (bit 0) + **7 full adders** (bits 1–7).

One full adder cell (5 gates):
```
A ──→ XOR1 ──→ XOR2 → SUM
B ──↗        ↗CIN
A ──→ AND1 ──→ OR → CARRY
B ──↗        ↗
AND2 (XOR1 & CIN) ──↗
```

Full circuit (8-bit ripple):
```
[VA[0], VB[0]] → HalfAdder → SUM[0], CARRY[0]
[VA[1], VB[1], CARRY[0]] → FullAdder → SUM[1], CARRY[1]
[VA[2], VB[2], CARRY[1]] → FullAdder → SUM[2], CARRY[2]
...
[VA[7], VB[7], CARRY[6]] → FullAdder → SUM[7], CARRY[7=COUT]
```

Tests:
- **170 + 85 = 255** (`0b10101010 + 0b01010101 = 0b11111111`): all sum bits HIGH, no carry-out. **2 checks.**
- **200 + 100 = 300**: 300 > 255, so carry-out = HIGH, low 8 bits = 44. **2 checks.**

---

#### Test 4 — XOR Parity (16 inputs)

```
V[0] ──→ XOR ──→ XOR ──→ XOR ... ──→ PARITY
V[1] ──↗
V[2] ──────────↗
V[3] ─────────────────↗
...
V[15] ───────────────────────────────↗
```

An XOR chain: `parity = V[0] ^ V[1] ^ V[2] ^ ... ^ V[15]`.

- All 16 inputs set to HIGH → even parity → output = LOW. **1 check.**
- Flip V[0] to LOW → odd parity → output = HIGH. **1 check.**

---

#### Test 5 — Binary AND Tree (32 inputs)

```
V[0]  V[1]  V[2]  V[3] ... V[30] V[31]
  \  /        \  /               \   /
  AND          AND    ...         AND
    \          /                   /
       AND           ...        AND
           \                   /
               AND  ···  AND
                    AND  (apex)
```

- All 32 HIGH → apex = HIGH. **1 check.**
- V[17] = LOW → apex = LOW. **1 check.**

---

#### Test 6 — Binary OR Tree (32 inputs)

Same structure as Test 5 but with OR gates.

- All 32 LOW → apex = LOW. **1 check.**
- V[5] = HIGH → apex = HIGH. **1 check.**

---

#### Test 7 — AND Pyramid (64 wide × 6 deep)

Same as Test 5 but with 64 inputs and forced depth limit of 6 layers. At depth 6, a 64-wide tree has 64/2⁶ = 1 gate remaining (converges fully).

- All HIGH → apex = HIGH. **1 check.**
- Input[32] = LOW → apex = LOW. **1 check.**

---

#### Test 8 — NAND Crossbar (8 rows × 4 columns)

```
ROW_VARS[0..7]
    │ │ │ │ │ │ │ │
    ├─┼─┼─┼─┼─┼─┼─┤──→ NAND[col=0] (8 inputs)
    ├─┼─┼─┼─┼─┼─┼─┤──→ NAND[col=1] (8 inputs)
    ├─┼─┼─┼─┼─┼─┼─┤──→ NAND[col=2] (8 inputs)
    └─┴─┴─┴─┴─┴─┴─┘──→ NAND[col=3] (8 inputs)
```

Every row variable connects to **every** NAND gate's corresponding input slot. This is an 8×4 crossbar.

- All 8 row inputs HIGH → NAND(HIGH×8) = LOW → all 4 NAND outputs = LOW. **1 check.**
- One row LOW → NAND(has-a-LOW) = HIGH → all 4 outputs = HIGH. **1 check.**

---

#### Test 9 — 4-bit Ripple Adder saved as IC

Same half+full adder structure as Test 3 but 4-bit, wrapped in INPUT/OUTPUT pins and saved as a JSON file, then loaded into a new circuit as a black-box IC component.

**Structure of the IC file:**
```
IN_A[0..3]  IN_B[0..3]   (8 INPUT_PINs)
     │  │         │  │
  [4-bit ripple adder wiring]
     │  │  │  │  │
OUT[0..3]  OUT[4=COUT]   (5 OUTPUT_PINs)
```

After loading:
- Wire `VARIABLE` nodes to IC inputs.
- **9 + 6 = 15**: output pins 0–3 show `1111` (binary 15), pin 4 (carry) = LOW. **2 checks.**
- **10 + 10 = 20**: output pins = `10100` (binary 20), no carry needed. **1 check.**

**Confirms: ICs correctly encapsulate and re-expose circuit logic through JSON serialization.**

---

#### Test 10 — Nested IC (IC inside IC)

**Step 1:** Build `InnerNOT` IC:
```
IN ──→ NOT ──→ OUT
```
Save to `_bench_inner.json`.

**Step 2:** Build `DoubleNOT` IC containing two `InnerNOT` ICs:
```
IN ──→ [InnerNOT IC] ──→ [InnerNOT IC] ──→ OUT
       NOT(x)               NOT(NOT(x)) = x
```
Save to `_bench_outer.json`.

**Step 3:** Load `DoubleNOT` into a fresh circuit. Connect a VARIABLE.
- V = HIGH → DoubleNOT output = HIGH (NOT(NOT(HIGH))). **1 check.**
- V = LOW → DoubleNOT output = LOW. **1 check.**

**Confirms: ICs can contain other ICs and maintain correct behavior after nested serialization.**

---

#### Test 11 — Feedback Safety (Oscillation/ERROR detection)

A **self-referential XOR** is wired:
```
V_trig ──→ XOR ──→ Passthrough_IC ──→ outputs
              ↑        (IN→OUT pin wire)
              └────────────────────────┘
              (XOR input 1 = XOR's own output → infinite loop)
```

The XOR's second input is connected to its **own output**. This creates an infinite feedback loop. The engine must either:
- Launch an async oscillation-breaker task (`runner`), OR
- Set the IC output to `ERROR` state.

**1 check:** either `c.runner` is alive OR output == ERROR.

---

#### Test 12 — UNKNOWN State Propagation

```
VA (UNKNOWN, never toggled) ──→ AND ──→ output
VB                           ──↗
```
- Toggle VB = LOW → `AND(UNKNOWN, LOW)` = LOW (LOW absorbs). **1 check.**
- Toggle VB = HIGH → `AND(UNKNOWN, HIGH)` = LOW (can't confirm all-HIGH). **1 check.**

---

### 4.2 COMPLEX IC BENCHMARK

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

### 4.3 COMPLEX CIRCUIT BENCHMARK

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

> **Note:** The output showed `ERROR: 'int' object has no attribute 'location'` for all circuit sizes. This is a known bug in `.writetojson()` / `.readfromjson()` when gates have no location set (they are built programmatically, not through the UI which assigns locations).

---

### 4.4 NESTED IC STRESS TEST

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
- V = HIGH → `NOT¹⁰(HIGH)` = `NOT(LOW)` = `HIGH`... wait — 10 layers of NOT: HIGH → LOW (since 10 is even). **1 check.**
- V = LOW → `NOT¹⁰(LOW)` = HIGH. **1 check.**

**Confirms: deeply nested ICs chain correctly through 10-level JSON deserialization.**

---

### 4.5 HEAD-TO-HEAD COMPARISON TABLE

After running both Engine and Reactor backends, the benchmark prints a comparison:

```
| Benchmark        | Engine    | Reactor   | Speedup |
|------------------+-----------+-----------+---------|
| Ic Create 10     |  0.72 ms  |  0.23 ms  |   3.1x  |
| Ic Sim   150000  | 32.63 ms  |  0.43 ms  |  75.5x  |
```

The simulation speedup is **75x** for large ICs — that's the Cython backend's advantage over pure Python for tight propagation loops.

---

## Summary

| File | Question Answered | Key Metric |
|------|-------------------|------------|
| `book_benchmark.py` | Is the Book Algorithm faster than naïve BFS? | ns/gate, speedup ratio |
| `cache_test.py` | At what circuit size does CPU cache fall? | ns/eval, cache tier boundary |
| `Complexity_scale.py` | Which circuit shapes are cheaper/harder to simulate? | ME/s per topology per size |
| `ic_circuit_benchmark.py` | Do IC packaging + correctness work at scale? | ms per operation, pass/fail |

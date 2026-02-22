# Darion Logic Sim

A Python-based Digital Logic Simulator with a PySide6 GUI editor and a dual-backend simulation engine.

## Features

- **Dual-Backend Architecture:** Choose between a pure **Python Engine** or a high-performance **Cython/C++ Reactor** for simulation.
- **Event-Driven Propagation:** Only propagates signals when an input actually changes — no polling.
- **O(1) Gate Evaluation:** Gates handle any number of inputs in constant time using the "Book" algorithm.
- **Unified Simulation Mode:** A single mode handles both combinatorial and sequential logic, with a built-in wave limiter that detects infinite oscillations and burns them to `ERROR`.
- **Recursive Integrated Circuits (ICs):** Circuits can be saved as ICs and nested arbitrarily deep (e.g., a CPU built from ALUs built from Adders built from XOR/AND gates).
- **Stack-Based Undo/Redo:** Every action is recorded as a reversible transaction.
- **Save/Load:** Circuits and ICs are serialized to JSON.
- **Comprehensive Test Suite:** Over 3,000 lines of aggressive unit tests and real-world benchmarks (ripple adders, mux trees, barrel shifters, etc.).

## Build

Create and activate a Python virtual environment:

```bash
python -m venv env
source env/bin/activate    # Linux / macOS
env\Scripts\activate.bat   # Windows
```

Install dependencies:

```bash
pip install pyside6 setuptools cython psutil
```

Build the Cython reactor (optional — only needed if you want the high-performance backend):

```bash
bash scripts/build.sh    # Linux / macOS
scripts\build.bat        # Windows
```

> **Note:** The pure Python engine (`engine/`) works without building. The reactor (`reactor/`) requires Cython compilation.

## Usage

### CLI

```bash
python interface/CLI.py              # Interactive backend selection
python interface/CLI.py --engine     # Force Python engine
python interface/CLI.py --reactor    # Force Cython reactor
```

### GUI

```bash
python main.py
```

### Speed Tests

```bash
python interface/speed_test.py --engine     # Benchmark the Python engine
python interface/speed_test.py --reactor    # Benchmark the Cython reactor
```

## Architecture

### Dual Backends

The simulator has two interchangeable backends that share the same API:

| | **Engine** (`engine/`) | **Reactor** (`reactor/`) |
|---|---|---|
| Language | Pure Python | Cython / C++ |
| Build Step | None | `scripts/build.sh` |
| Use Case | Development, portability | Production, benchmarking |
| Data Structures | Python `list` | C++ `vector<void*>` |
| Gate Evaluation | Python method calls | Inline C-level evaluation |

Both backends implement the same core modules: `Circuit`, `Gates`, `IC`, `Const`, and `Store`.

### The "Book" Algorithm (O(1) Logic)

Instead of iterating through every input pin to evaluate a gate, each gate maintains a 4-element "book": `[Count_Low, Count_High, Count_Error, Count_Unknown]`.

- When an input changes (e.g., Low → High), the book updates in O(1): `Book[Low]--`, `Book[High]++`.
- **Decision logic is a single comparison:**
  - AND: `low == 0` → HIGH
  - OR: `high > 0` → HIGH
  - XOR: `high & 1` → HIGH
  - Inverted gates (NAND, NOR, XNOR) flip the result with `output ^= (gate_type & 1)`.
- **Result:** A 100,000-input AND gate evaluates as fast as a 2-input gate.

### Event-Driven Propagation

The propagation loop uses a **single flat queue** with index-based traversal (not `deque.popleft()`). Each gate carries a `scheduled` flag to prevent duplicate enqueuing.

1. **Wavefront BFS:** When a gate's output changes, it scans its `hitlist` (list of `Profile` structs: `{target, pin_index, last_known_output}`). If a target's book changes its output, the target is appended to the queue.
2. **Wave Limiter:** A counter tracks propagation waves. If the counter exceeds the circuit's component count, it assumes an infinite oscillation, clears the queue, and flood-fills `ERROR` from the offending gate via the `burn()` function.
3. **Not gate & Buffer shortcircuit:** These type of gates bypass book management and follow a simpler logic flow

### Recursive IC Architecture

Integrated Circuits use the **Composite Design Pattern**:

- An `IC` is treated identically to a `Gate` by the engine.
- Every IC encapsulates its own internal components, input pins, and output pins.
- `IC` has a map which is the blueprint used during copy-paste and also used to build the `IC` from scratch 
- ICs can be nested inside other ICs to arbitrary depth (e.g., a 4-bit Adder built from Full Adders, built from Half Adders, built from XOR/AND gates).

### Time Travel (Undo/Redo)

The project implements the **Command Pattern** for history management:

- Every user action (Create, Delete, Wire, Toggle) is encapsulated as a "Transaction" tuple.
- Transactions are pushed onto an Undo Stack.
- Reversing an action pops the transaction and executes its mathematical inverse (e.g., the inverse of "Delete Gate A" is "Restore Gate A at Index X").

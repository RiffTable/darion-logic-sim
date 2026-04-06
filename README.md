# Darion Logic Sim

Darion Logic Sim is a Python-based digital logic simulator featuring a PySide6 visual editor and a dual-backend simulation architecture built with Cython. It is designed to be highly interactive, visually stunning, and parallel to real-life simulation, allowing the user to practice Logic Design skills with ease of use. 

## Dual-Backend Architecture

The simulator ships with two interchangeable backends sharing the exact same API, demonstrating a practical transition from Object-Oriented Programming (OOP) to Data-Oriented Design (DOD).

* **Engine (Pure Python & OOP):** Built with standard Python objects, this backend is highly flexible and made for simplicity and debugability. It prioritizes exact chronological realism, precise hardware delay modeling, and visual observation over raw throughput.
* **Reactor (Cython/C++ & DOD):** Python's object overhead scatters data across memory, which bottlenecks massive circuits. The Reactor shifts to a strict Data-Oriented Design. By dropping the Global Interpreter Lock (`nogil`) and packing gate states into contiguous C-structs (`std::vector`), it strips Python entirely out of the propagation hot-loop. While Cython makes debugging more complex, it allows the CPU cache to process logic at native C speeds, scaling the performance to extreme lengths. 

### The DOD Bridge: Memory as Identity
In the Reactor, the circuit's state is split into two layers:
* `gate_infolist`: A C++ vector of packed structs containing purely numeric physics data (outputs, hitlists, limits) where the `nogil` execution occurs.
* `gate_verse`: A Python list holding the high-level UI wrappers (names, custom data).

The bridge is the `location` attribute. Rather than just an ID, `location` is the exact memory index of the gate within the C++ array. This guarantees $O(1)$ memory lookups for the physics engine and allows the UI to instantly map a physical change to its graphical widget without searching.

---

## Core Simulation Mechanics

### 1. Evaluation ($O(1)$ Logic & Short-Circuiting)
To achieve consistent evaluation times regardless of a gate's fan-in (number of inputs), the engine avoids traditional input-polling.
* **The Book Algorithm (`id < VARIABLE_ID`):** Complex gates (AND, OR, XOR) maintain a 3-element book tracking the count of their active incoming signals: `[LOW, HIGH, UNKNOWN]`. Sources push changes to targets. The target updates its tally and uses its `id` (gate type) attribute to perform a fast bitwise arithmetic check, determining its new output instantly.  
* **Short-Circuiting (`id >= NOT_ID`):** Components with 1:1 input-output mappings (NOT gates, Input Pins, Output Pins) bypass the Book algorithm entirely, utilizing a direct logic flow to save CPU cycles.
* **Forward Evaluation:** Gates are evaluated directly from their source to target. This makes the queue strictly based on gates that have changed their output and need to propagate. 

### 2. Propagation & Time Management
Propagation utilizes dual buffers (`read_queue` and `write_queue`) to simulate synchronous hardware delta-cycles, ensuring parallel logic paths evaluate simultaneously.
* **State Flags (`mark` & `scheduled`):** The `mark` flag ensures a gate is added to the active wave buffer only once per cycle, even if multiple inputs trigger it. The `scheduled` flag prevents duplicate entries in the broader time manager.
* **Realism vs. Throughput:** * The **Engine** uses a priority queue (`heapq`) to model physical gate delays, input-limit penalties, and transient hardware glitches (race conditions).
  * The **Reactor** uses a fast FIFO queue (`std::deque`), discarding physical delay modeling in favor of strict causal correctness and maximum throughput.
* **Oscillation Protection:** A dynamic counter monitors the propagation depth. If an infinite loop or rapid oscillation is detected, the engine intentionally throttles the raw execution, passing the state to the slower time managers. This yields execution back to the UI, allowing users to watch the oscillation without freezing the application.

### 3. Optimization & Defragmentation (Reactor)
The Cython backend features an `optimize()` function that runs Kahn’s algorithm for topological sorting. It physically reorders the C++ memory array so signals always flow forward, guaranteeing the CPU prefetcher never has to "look back" in memory. Simultaneously, it pushes deleted (tombstoned) gates to the end of the array, acting as a zero-cost memory defragmenter.

---

## UI Synchronization: The Visual Queue

The physics backend crunches logic millions of times faster than the 60 FPS PySide6 frontend can render.
* When a gate changes state, its `update` flag is set to true, and its `location` is pushed to a lightweight `visual_queue`. The flag ensures it is only queued once per frame.
* An asynchronous UI task operates on a strict time budget (e.g., ~16ms). It drains the visual queue, looks up the corresponding widget via the `location` index, and repaints only the specific wires and gates that changed.
* This completely decouples the UI from the physics engine, maintaining fluid rendering while the backend handles massive calculations.

---

## Integrated Circuits (ICs) & Serialization

### Hierarchical ICs & Netlist Flattening
Users can select clusters of components and package them into reusable Integrated Circuits.
* **Infinite Nesting (UI/Storage):** IC definitions can be nested hierarchically to any depth (e.g., a CPU built from ALUs, built from Adders).
* **Zero-Cost Execution:** The execution is explicitly not recursive. During simulation prep, the Reactor’s `build_ic()` flattens the hierarchy, dissolving all IC boundaries. A deeply nested chip is physically unpacked into a single, flat 1D array of primitive gates. This guarantees that deep UI hierarchies incur zero function-call overhead during the physics simulation.

### Save/Load & State Management
* **Two-Phase Deserialization:** Deserialization runs in two passes. Phase 1 instantiates all components and builds a fast hash map (`pseudo`) linking old JSON file IDs to new memory locations. Phase 2 wires the components together using the map, ensuring flawless topology reconstruction.
* **Sandboxed Exports:** When copying components or saving custom ICs, the engine detects and gracefully marks the components and uses ‘Partial Data’ to recreate the component or the entire cluster.
* **Time Travel (Undo/Redo):** Built on the Command Pattern, every user action is encapsulated as a reversible transaction (storing only the minimum required delta). These are managed by dual `deque` history stacks capped at 250 steps, allowing memory-efficient, instant time travel.
* **Gray Code Truth Tables:** Truth tables iterate through states using a Gray Code sequence (`i ^ (i >> 1)`), ensuring only one variable toggles per row. This avoids the chaotic logic cascades of standard binary counting, significantly accelerating table generation.

---

## Installation & Build Instructions

**1. Create and activate a Python virtual environment:**

```bash
# Linux / macOS
python -m venv env
source env/bin/activate

# Windows
python -m venv env
env\Scripts\activate.bat
```

**2. Install dependencies:**

```bash
pip install pyside6 setuptools cython psutil orjson
```

**3. Build the Cython Reactor (Optional):**
*Note: The pure Python engine runs out of the box. The high-performance Reactor requires C++ compilation via Cython.*

```bash
# Linux / macOS
bash scripts/build.sh

# Windows
scripts\build.bat
```

---

## Usage

**Start the Visual Editor:**

```bash
python main.py
```

**Command Line Interface (CLI):**

```bash
python interface/CLI.py              # Interactive backend selection
python interface/CLI.py --engine     # Force Python engine
python interface/CLI.py --reactor    # Force Cython reactor
```

**Benchmarking:**

```bash
python interface/speed_test.py --engine     # Benchmark the Python engine
python interface/speed_test.py --reactor    # Benchmark the Cython reactor
```

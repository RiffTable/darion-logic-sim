# Darion Logic Sim
**A Python-based Digital Logic Simulator featuring O(1) gate processing and recursive ICs.**

## Features
- **Optimized Event-Driven Engine:** Gates propagate only when they change their outputs, significantly saving processing power compared to continuous polling.
- **Constant Time Complexity (O(1)):** Utilizes a "Book" keeping algorithm that allows gates to process logic in O(1) time, regardless of whether they have 2 inputs or 200.
- **Hybrid Propagation:** Implements Breadth-First Search (BFS) for general signal propagation and Depth-First Search (DFS) for tunneling into Integrated Circuits.
- **Dual Simulation Modes:**
  - **Simulation Mode:** Optimized for combinatorial logic (DAGs), preventing infinite loops and maximizing speed.
  - **Flip-Flop Mode:** Supports sequential circuits and feedback loops with oscillation detection (fuse) to handle memory states.
- **Recursive Integrated Circuits (ICs):** Circuits can be encapsulated into "Black Box" ICs, which can then be nested inside other ICs infinitely. Supports custom naming and I/O mapping.
- **Robust Undo/Redo System:** A stack-based history manager (Command Pattern) that tracks actions including component creation, deletion, wiring, and property changes.
- **Circuit Analysis Tools:**
  - **Truth Table Generator:** Automatically cycles through $2^n$ input combinations to generate a complete truth table for the current circuit.
  - **Diagnostics:** Detailed reporting of internal gate states, source/target connections, and signal "book" counts for debugging.
- **Granular Component Management:**
  - **Renaming:** Custom naming for gates and components for better readability.
  - **Dynamic Input Limits:** Runtime modification of gate input sizes (e.g., changing a 2-input AND to a 5-input AND).
  - **IC Pin Selection:** Specialized logic to handle connections to specific input/output pins of black-box ICs.
- **Project Management:**
  - Save and Load full circuit projects via JSON.
  - Export circuits as reusable IC files to build a component library.
  - Clipboard functionality (Copy/Paste) for duplicating logic blocks.
- **Comprehensive CLI:**
  - **Cross-Platform Interface:** Auto-detects OS (Windows/Linux) for clean screen refreshing.
  - **Hierarchical Menu System:** Organized workflows for Components, Simulation, and Project Management.

## How It Works

### The "Book" Algorithm (O(1) Logic)
Instead of iterating through every input pin to calculate a gate's state, **Darion Logic Sim** uses a specialized accounting system called the "Book".
- Every gate maintains a list of size 4: `[Count_Low, Count_High, Count_Error, Count_Unknown]`.
- When an input signal changes (e.g., from Low to High), the gate updates its book in constant time: `Book[Low]--` and `Book[High]++`.
- **Decision Logic:** An AND gate simply checks `if Book[Low] == 0`. An OR gate checks `if Book[High] > 0`.
- **Result:** A 1,000-input AND gate calculates its output as instantly as a 2-input gate.

### Event-Driven Propagation
The engine does not poll components. It uses a **Hybrid Propagation** model:
1. **BFS (Breadth-First Search):** Standard signal propagation uses a `deque` (Double Ended Queue). When a gate changes, it pushes its connected targets into the queue. This ensures signals spread in layers, simulating electrical wavefronts.
2. **DFS (Depth-First Search):** Inside Integrated Circuits (ICs), logic is encapsulated. The engine "tunnels" into the IC using recursion to resolve internal states before returning the result to the main circuit.

### Simulation Modes
- **Simulation Mode (Combinatorial):** Optimized for DAGs (Directed Acyclic Graphs). It processes the queue strictly. Since it assumes no loops, it skips cycle detection overhead for maximum speed.
- **Flip-Flop Mode (Sequential):** Enables handling of feedback loops (like Latches and Clocks). It introduces a `fuse` set mechanism during propagation to detect and break infinite oscillations within a single tick, preventing the engine from freezing while maintaining state memory.

### Recursive IC Architecture
Integrated Circuits are implemented using the **Composite Design Pattern**.
- An `IC` class is treated exactly like a `Gate` class by the engine.
- Every IC contains its own internal `map` of components.
- Since an IC is just a component, it can be placed inside *another* IC. This allows for infinite recursion (e.g., A 4-bit Adder built from Full Adders, which are built from Half Adders, which are built from XOR/AND gates).

### Time Travel (Undo/Redo)
The project implements the **Command Pattern** to manage history.
- Every user action (Create, Delete, Wire, Toggle) is encapsulated as a "Transaction" tuple.
- These transactions are pushed onto an Undo Stack.
- Reversing an action pops the transaction and executes its mathematical inverse (e.g., the inverse of "Delete Gate A" is "Restore Gate A at Index X").

## Usage
Run the Command Line Interface to start the simulator:
```bash
python Farhan/CLI.py
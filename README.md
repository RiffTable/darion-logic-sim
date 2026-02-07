# Darion Logic Sim
A Python-based Digital Logic Simulator made in PySide6 (Python binding for Qt).

## Features
- A fast lightweight simulator that only propagates signal when input changes.
- Specialized **Flip-Flop Mode** for sequential logic analysis (default is **Simulation Mode**.)
- Gates can handle multiple inputs in O(1) constant time.
- Projects can be imported as integrated circuits (IC), which can help build using other ICs via "nesting".
- Logic circuits are simulated using the isolated "Darion logic engine" and simulations can be run without the GUI editor.
- Stack-based undo/redo feature.
- Save/load feature using JSON.

## Build
The project requires the pip package manager to run. To build and run the project, first create an python virtual environment:
```bash
python -m venv env
```

Then activate the environment using the specific command for your OS:
```bash
source env/bin/activate    # Linux and MacOS
env\Scripts\activate.bat   # Windows
```

Now install the required modules using pip (hopefully you have pip installed):
```bash
pip install pyside6 setuptools cython
```

Finally, run the build script. After building, you can read usage to run the project.
```bash
bash build.sh    # Linux and MacOS
build.bat        # Windows
```

## Usage

### CLI Version
Run the simulator using its command-line interface (CLI):
```bash
python engine/CLI.py
```

### GUI Version


Run the simulator (with the GUI editor):
```bash
python main.py
```


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

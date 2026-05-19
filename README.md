# Darion Logic Sim

Darion Logic Sim is a Python-based digital logic simulator featuring a PySide6 visual editor and a dual-backend simulation architecture built with Cython. It is designed to be highly interactive, visually stunning, and parallel to real-life simulation, allowing the user to practice Logic Design skills with ease of use.

![Darion Screenshot](assets/darion-decoder.png)

## Features

- Extremely fast circuit simulation using precompiled Cython backend.
- Very accurate to real-life circuit behavior, as it accounts for propagation delay and self-oscillations.
- Minimal but powerful and customizable user interface.
- Circuit building experience is made to be as smooth and unobtrusive as possible with QoL features.
- For wiring components, pin-to-pin approach is used instead of manual path-drawing for a smoother design experience. Created wires will path-find to maintain a clean layout without clutter.
- Simulation speed can be controlled to view and diagnose circuit propagation in great detail.
- Projects can be converted and reused as integrated circuits (IC) to build large complex systems.
- Runs locally without any the need of internet connection.
- Cross-platform compatibility.

---

## Build Instructions

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

**3. Build the Cython Reactor (Optional):** The pure Python engine runs out of the box. The high-performance Reactor requires C++ compilation via Cython.

```bash
# Linux / macOS
bash scripts/build.sh

# Windows
scripts\build.bat
```


#### Usage

**Run the Simulator with GUI:**

```bash
python main.py
```

**Command Line Interface (CLI):** Run the simulator in a headless state. Upon starting, you can select which backend to use.

```bash
python interface/CLI.py
```

---

## Structure

*I want to warn you, this section is very messy. It will be cleaned up in the future.*

### Dual-Backend Architecture

The simulator ships with two interchangeable backends sharing the exact same API, demonstrating a practical transition from Object-Oriented Programming (OOP) to Data-Oriented Design (DOD).

- **Engine (Pure Python & OOP):** Built with standard Python objects, this backend is highly flexible and made for simplicity and debugability. It prioritizes exact chronological realism, precise hardware delay modeling, and visual observation over raw throughput.
- **Reactor (Cython/C++ & DOD):** Python's object overhead scatters data across memory, which bottlenecks massive circuits. The Reactor shifts to a strict Data-Oriented Design. By dropping the Global Interpreter Lock (`nogil`) and packing gate states into contiguous C-structs (`std::vector`), it strips Python entirely out of the propagation hot-loop. While Cython makes debugging more complex, it allows the CPU cache to process logic at native C speeds, scaling the performance to extreme lengths. 

#### The DOD Bridge: Memory as Identity
In the Reactor, the circuit's state is split into two layers:
- `gate_infolist`: A C++ vector of packed structs containing purely numeric physics data (outputs, hitlists, limits) where the `nogil` execution occurs.
- `gate_verse`: A Python list holding the high-level UI wrappers (names, custom data).

The bridge is the `location` attribute. Rather than just an ID, `location` is the exact memory index of the gate within the C++ array. This guarantees $O(1)$ memory lookups for the physics engine and allows the UI to instantly map a physical change to its graphical widget without searching.


### Core Simulation Mechanics

#### Evaluation ($O(1)$ Logic)
To achieve consistent evaluation times regardless of a gate's fan-in (number of inputs), the engine avoids traditional input-polling.

- **The Book Algorithm:** All gates (other than NOT gates) maintain a tuple called 'Book'. It tracks the number of inputs with HIGH, LOW or UNKNOWN signal. Every input change updates the 'Book', determining its new output instantly using a simple algorithm. Examples:
  - AND gate output is HIGH only when `book[LOW]` is zero.
  - NOR gate output is HIGH only when `book[HIGH]` is zero.

- **Forward Evaluation:** Gates are evaluated directly from their source to target. This makes the queue strictly based on gates that have changed their output and need to propagate. 

#### Propagation & Time Management
Propagation utilizes dual buffers (`read_queue` and `write_queue`) to simulate synchronous hardware delta-cycles, ensuring parallel logic paths evaluate simultaneously.
- **State Flags (`mark` & `scheduled`):** The `mark` flag ensures a gate is added to the active wave buffer only once per cycle, even if multiple inputs trigger it. The `scheduled` flag prevents duplicate entries in the broader time manager.
- **Realism vs. Throughput:** The **Engine** uses a priority queue (`heapq`) to model physical gate delays, input-limit penalties, and transient hardware glitches (race conditions).
  - The **Reactor** uses a priority queue, discarding physical delay modeling in favor of strict causal correctness and maximum throughput.
- **Oscillation Protection:** A dynamic counter monitors the propagation depth. If an infinite loop or rapid oscillation is detected, the engine intentionally throttles the raw execution, passing the state to the slower time managers. This yields execution back to the UI, allowing users to watch the oscillation without freezing the application.

### UI Synchronization: The Visual Queue

The physics backend crunches logic millions of times faster than the 60 FPS PySide6 frontend can render.
- When a gate changes state, its `update` flag is set to true, and its `location` is pushed to a lightweight `visual_queue`. The flag ensures it is only queued once per frame.
- An asynchronous UI task operates on a strict time budget (e.g., ~16ms). It drains the visual queue, looks up the corresponding widget via the `location` index, and repaints only the specific wires and gates that changed.
- This completely decouples the UI from the physics engine, maintaining fluid rendering while the backend handles massive calculations.


### Integrated Circuits (ICs) & Serialization

Users can select components and package them into reusable Integrated Circuits (IC).
- **Infinite Nesting (UI/Storage):** IC definitions can be nested hierarchically to any depth (e.g., a CPU built from ALUs, built from Adders).
- **Zero-Cost Execution:** The execution is explicitly not recursive. During simulation prep, the Reactor's `build_ic()` flattens the hierarchy. This restores the IC into primitive gates. This guarantees that deep UI hierarchies incur zero function-call overhead during simulation.

---

## Credits

- This project was developed and submitted as part of the Software Development course for our Bachelor's degree in Computer Science & Engineering.
- Thank you [Logisim](http://www.cburch.com/logisim/) for inspiring this project.

---

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
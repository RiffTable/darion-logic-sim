# Hardware Profiling

**Test Parameters:**
- **Vectors simulated:** 50

Extracted purely from hardware counters (`perf`) to isolate the true computational core of each simulation engine, bypassing Python and Icarus VPI harness overhead.

## Icarus Verilog (`vvp`)

| Circuit    | IPC   | Branch   | Brn Miss | L1 Load  | L1 Hit%  | L2 Load  | L2 Hit%  | L3/RAM Load  |
|------------|-------|----------|----------|----------|----------|----------|----------|--------------|
| hyp.v      |  1.20 | 121.58B  | 1.72B    | 394.92B  |   95.96% | 15.96B   |   12.65% | 13.94B       |

## Pure Python Engine

| Circuit    | IPC   | Branch   | Brn Miss | L1 Load  | L1 Hit%  | L2 Load  | L2 Hit%  | L3/RAM Load  |
|------------|-------|----------|----------|----------|----------|----------|----------|--------------|
| hyp.v      |  0.00 | 0        | 0        | 0        |    0.00% | 0        |    0.00% | 0            |

## Reactor: `rx-prop` (Wavefront BFS)

| Circuit    | IPC   | Branch   | Brn Miss | L1 Load  | L1 Hit%  | L2 Load  | L2 Hit%  | L3/RAM Load  |
|------------|-------|----------|----------|----------|----------|----------|----------|--------------|
| hyp.v      |  1.16 | 701.18B  | 56.91B   | 3085.62B |   89.88% | 312.27B  |   33.12% | 208.84B      |

## Reactor OOP: (Wavefront BFS)

| Circuit    | IPC   | Branch   | Brn Miss | L1 Load  | L1 Hit%  | L2 Load  | L2 Hit%  | L3/RAM Load  |
|------------|-------|----------|----------|----------|----------|----------|----------|--------------|
| hyp.v      |  1.13 | 717.33B  | 53.20B   | 2675.93B |   87.25% | 341.12B  |   20.52% | 271.11B      |

## Reactor: `rx-sweep` (Linear Compiled)

| Circuit    | IPC   | Branch   | Brn Miss | L1 Load  | L1 Hit%  | L2 Load  | L2 Hit%  | L3/RAM Load  |
|------------|-------|----------|----------|----------|----------|----------|----------|--------------|
| hyp.v      |  1.51 | 76.12M   | 7.44M    | 297.03M  |   94.09% | 17.55M   |   85.77% | 2.50M        |


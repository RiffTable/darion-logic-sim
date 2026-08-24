# Unified 3-Engine Logic Simulator Benchmark

- **Total vectors**: 50 (Warmup: 5, Measured: 45)
- **Circuits**: 1
- **Icarus VPI**: enabled


## Speedup vs Icarus Verilog Baseline
*Icarus VPI sim time = 1x*
*Reactor modes: prop = BFS wavefront (SIMULATE)  |  sweep = linear fwd-pass (COMPILE)*

| Circuit          | Icarus(ms) | Engine(ms) | Eng-eval   | Eng-spd  | Rx-prop(ms) | Rx-p-eval  | Rx-prop-spd | Rx-sweep(ms) | Rx-s-eval  | Rx-swp-spd |
|------------------|------------|------------|------------|----------|-------------|------------|-------------|--------------|------------|------------|
| hyp.v            |  139810.07 |        N/A |        N/A |      N/A |   1701166.2 | 159,746,841,406 |        0.1x |        117.8 | 12,612,026 |    1186.9x |
| **Geo-mean speedup** | **(baseline)** |            |            |      N/A |             |            |        0.1x |              |            |    1186.9x |

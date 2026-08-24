# Unified 3-Engine Logic Simulator Benchmark

- **Total vectors**: 500 (Warmup: 50, Measured: 450)
- **Circuits**: 6
- **Icarus VPI**: enabled


## Speedup vs Icarus Verilog Baseline
*Icarus VPI sim time = 1x*
*Reactor modes: prop = BFS wavefront (SIMULATE)  |  sweep = linear fwd-pass (COMPILE)*

| Circuit          | Icarus(ms) | Engine(ms) | Eng-eval   | Eng-spd  | Rx-prop(ms) | Rx-p-eval  | Rx-prop-spd | Rx-sweep(ms) | Rx-s-eval  | Rx-swp-spd |
|------------------|------------|------------|------------|----------|-------------|------------|-------------|--------------|------------|------------|
| square.v         |    1076.94 |        N/A |        N/A |      N/A |      1165.1 | 130,476,672 |        0.9x |        103.6 | 10,132,097 |      10.4x |
| sqrt.v           |  120926.83 |        N/A |        N/A |      N/A |    396353.2 | 40,285,807,134 |        0.3x |         86.9 | 13,350,220 |    1391.9x |
| multiplier.v     |    8633.02 |        N/A |        N/A |      N/A |     13592.6 | 1,481,442,537 |        0.6x |        130.1 | 16,357,200 |      66.3x |
| log2.v           |   39627.98 |        N/A |        N/A |      N/A |     71610.4 | 7,831,765,765 |        0.6x |        148.5 | 14,858,595 |     266.8x |
| mem_ctrl.v       |    2577.44 |        N/A |        N/A |      N/A |       304.5 | 35,276,422 |        8.5x |        228.3 | 24,822,359 |      11.3x |
| div.v            |    3510.04 |        N/A |        N/A |      N/A |       517.6 | 72,949,206 |        6.8x |        209.4 | 29,111,513 |      16.8x |
| **Geo-mean speedup** | **(baseline)** |            |            |      N/A |             |            |        1.3x |              |            |      60.4x |

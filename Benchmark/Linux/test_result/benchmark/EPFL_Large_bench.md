# Unified 3-Engine Logic Simulator Benchmark

- **Total vectors**: 500 (Warmup: 10, Measured: 490)
- **Circuits**: 7
- **Icarus VPI**: enabled


## Speedup vs Icarus Verilog Baseline
*Icarus VPI sim time = 1x*
*Reactor modes: prop = BFS wavefront (SIMULATE)  |  sweep = linear fwd-pass (COMPILE)*

| Circuit          | Icarus(ms) | Engine(ms) | Eng-eval   | Eng-spd  | Rx-prop(ms) | Rx-p-eval  | Rx-prop-spd | Rx-sweep(ms) | Rx-s-eval  | Rx-swp-spd | RxOOP(ms)   | RxO-eval   | RxO-spd    |
|------------------|------------|------------|------------|----------|-------------|------------|-------------|--------------|------------|------------|-------------|------------|------------|
| voter.v          |    1357.30 |        N/A |        N/A |      N/A |      4186.9 | 809,633,217 |        0.3x |        267.4 | 42,507,804 |       5.1x |      4522.6 | 809,633,217 |       0.3x |
| square.v         |    1025.04 |        N/A |        N/A |      N/A |       962.2 | 142,761,610 |        1.1x |        225.7 | 31,956,737 |       4.5x |      1040.5 | 142,761,610 |       1.0x |
| sqrt.v           |  128571.23 |        N/A |        N/A |      N/A |    317548.4 | 43,545,238,853 |        0.4x |      24175.8 | 3,172,089,918 |       5.3x |    346473.2 | 43,545,238,853 |       0.4x |
| multiplier.v     |    8787.16 |        N/A |        N/A |      N/A |     10488.0 | 1,616,953,172 |        0.8x |       1847.6 | 254,265,116 |       4.8x |     11273.9 | 1,616,953,172 |       0.8x |
| log2.v           |   40817.75 |        N/A |        N/A |      N/A |     60605.1 | 8,633,986,837 |        0.7x |       8330.2 | 1,104,142,382 |       4.9x |     67921.7 | 8,633,986,837 |       0.6x |
| mem_ctrl.v       |    1741.66 |        N/A |        N/A |      N/A |       280.7 | 43,900,941 |        6.2x |        293.4 | 39,409,969 |       5.9x |       304.9 | 43,900,941 |       5.7x |
| div.v            |    2415.39 |        N/A |        N/A |      N/A |       426.6 | 79,479,300 |        5.7x |        412.5 | 63,102,026 |       5.9x |       458.2 | 79,479,300 |       5.3x |
| **Geo-mean speedup** | **(baseline)** |            |            |      N/A |             |            |        1.2x |              |            |       5.2x |             |            |       1.1x |

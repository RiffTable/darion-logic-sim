# Unified 3-Engine Logic Simulator Benchmark

- **Total vectors**: 50,000 (Warmup: 5,000, Measured: 45,000)
- **Circuits**: 12
- **Icarus VPI**: enabled


## Speedup vs Icarus Verilog Baseline
*Icarus VPI sim time = 1x*
*Reactor modes: prop = BFS wavefront (SIMULATE)  |  sweep = linear fwd-pass (COMPILE)*

| Circuit          | Icarus(ms) | Engine(ms) | Eng-eval   | Eng-spd  | Rx-prop(ms) | Rx-p-eval  | Rx-prop-spd | Rx-sweep(ms) | Rx-s-eval  | Rx-swp-spd | RxOOP(ms)   | RxO-eval   | RxO-spd    |
|------------------|------------|------------|------------|----------|-------------|------------|-------------|--------------|------------|------------|-------------|------------|------------|
| ctrl.v           |        N/A |       31.4 |          0 |      N/A |         2.0 |          0 |         N/A |          2.6 |          0 |        N/A |         2.6 |          0 |        N/A |
| int2float.v      |        N/A |       47.5 |          0 |      N/A |         3.2 |          0 |         N/A |          3.9 |          0 |        N/A |         4.5 |          0 |        N/A |
| router.v         |        N/A |      259.8 |          0 |      N/A |        17.6 |          0 |         N/A |         18.7 |          0 |        N/A |        21.1 |          0 |        N/A |
| dec.v            |        N/A |       35.4 |          0 |      N/A |         2.4 |          0 |         N/A |          7.6 |          0 |        N/A |         2.8 |          0 |        N/A |
| cavlc.v          |        N/A |       43.9 |          0 |      N/A |         2.9 |          0 |         N/A |          2.9 |          0 |        N/A |         3.7 |          0 |        N/A |
| priority.v       |        N/A |      559.5 |          0 |      N/A |        37.4 |          0 |         N/A |         38.2 |          0 |        N/A |        45.3 |          0 |        N/A |
| adder.v          |        N/A |     1125.4 |          0 |      N/A |        74.8 |          0 |         N/A |         75.6 |          0 |        N/A |       102.1 |          0 |        N/A |
| i2c.v            |    2814.68 |      639.2 |          0 |     4.4x |        42.9 |          0 |       65.6x |         45.7 |          0 |      61.5x |        53.6 |          0 |      52.5x |
| max.v            |        N/A |     2261.1 |          0 |      N/A |       149.4 |          0 |         N/A |        147.8 |          0 |        N/A |       203.2 |          0 |        N/A |
| bar.v            |        N/A |      591.5 |          0 |      N/A |        39.5 |          0 |         N/A |         43.6 |          0 |        N/A |        47.9 |          0 |        N/A |
| sin.v            |        N/A |      112.1 |          0 |      N/A |         7.1 |          0 |         N/A |          8.5 |          0 |        N/A |         8.4 |          0 |        N/A |
| arbiter.v        |        N/A |     1108.6 |          0 |      N/A |        74.6 |          0 |         N/A |         75.7 |          0 |        N/A |       101.5 |          0 |        N/A |
| **Geo-mean speedup** | **(baseline)** |            |            |     4.4x |             |            |       65.6x |              |            |      61.5x |             |            |      52.5x |

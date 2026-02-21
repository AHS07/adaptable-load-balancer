# Research Data Tables

Generated on Fri Feb 20 17:57:46 2026

### Table 5.1 – Failure Resilience Metrics
| Strategy            |   Hit % |   Miss % |   Server Down % |   Timeout % |
|:--------------------|--------:|---------:|----------------:|------------:|
| Round Robin         |   61.7  |    24.38 |            0.14 |        8.98 |
| Least Connections   |   20.1  |     8.8  |            1.54 |        3.42 |
| Least Response Time |   41    |     2.58 |            0.24 |       20.26 |
| AURA                |   55.12 |    18.9  |            0.16 |       11.04 |

### Table 5.2 – Tail Latency Metrics
| Strategy            |   P50 |    P95 |     P99 |   P99.9 |
|:--------------------|------:|-------:|--------:|--------:|
| Round Robin         | 46.12 | 364.02 | 1362.32 | 3093.72 |
| Least Connections   |  0    | 240.06 |  502.96 | 1823.38 |
| Least Response Time | 48.28 | 242.96 |  537.96 | 1550.75 |
| AURA                | 48.19 | 360.15 | 1243.36 | 2389.25 |

### Table 5.3 – Burst Handling Metrics
| Strategy            |   Peak Latency | Recovery Time (ms)   |   Variance |
|:--------------------|---------------:|:---------------------|-----------:|
| Round Robin         |        4382.91 | 2081.89 (P99.9)      |    48371.2 |
| Least Connections   |        1919.35 | 1735.60 (P99.9)      |    22719.5 |
| Least Response Time |        5939.85 | 1753.33 (P99.9)      |    30436.5 |
| HELIOS              |        4603.72 | 1716.57 (P99.9)      |    30373.8 |

### Table 5.4 – Cache Performance
| Strategy            |   Hit Rate % |   Miss % |   Avg Latency (Hit) |   Avg Latency (Miss) |
|:--------------------|-------------:|---------:|--------------------:|---------------------:|
| Round Robin         |        88.26 |     1.62 |               39.41 |               235.56 |
| Least Connections   |        70.04 |     1.2  |               34.12 |               232.45 |
| Least Response Time |        13.56 |     0.26 |               58.63 |               233.5  |
| HELIOS              |        64.1  |     0.52 |               56.63 |               233.16 |

### Table 5.5 – Overall Improvement Over Round Robin
| Metric             | AURA Improvement   | HELIOS Improvement   |
|:-------------------|:-------------------|:---------------------|
| P99 Reduction      | 8.7%               | --                   |
| Timeout Reduction  | -22.9%             | --                   |
| Cache Hit Increase | --                 | +-24.2%              |


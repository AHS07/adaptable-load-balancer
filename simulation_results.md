# Simulation Results: ALPHA1 vs BETA1

This document summarizes the results of a realistic load balancing simulation comparing **ALPHA1 (Tail-Aware/Aura)** and **BETA1 (Cache-Aware/Helios)** against a standard **Round Robin** baseline.

## Executive Summary
- **BETA1 (Helios Equivalent)** consistently outperformed all other strategies, demonstrating superior cache locality (Hit Rate ~88% vs ~72%) and significantly reduced timeouts (30-50% reduction).
- **ALPHA1 (Aura Equivalent)** showed mixed results in this specific configuration, performing comparably to Round Robin in raw P99 latency but showing promise in specific failure scenarios.
- **Key Win:** BETA1's cache-aware approach is highly effective for the tested heavy-tailed and bursty workloads.

## Detailed Scenario Results

### 1. Heterogeneous Servers
*Mixed server speeds (0.7x - 1.3x) with random spikes.*

| Strategy | P99 (ms) | Hit Rate (%) | Timeouts | Notes |
|----------|----------|--------------|----------|-------|
| Round Robin | 248.14 | 77.0 | 736 | Baseline |
| ALPHA1 | 248.59 | 75.3 | 628 | Reduced timeouts by ~15% |
| **BETA1** | **244.35** | **88.9** | **376** | **Lowest latency, 50% fewer timeouts** |

### 2. Heavy-Tailed Latency
*Pareto distribution for request sizes.*

| Strategy | P99 (ms) | Hit Rate (%) | Timeouts | Notes |
|----------|----------|--------------|----------|-------|
| Round Robin | 248.22 | 72.3 | 535 | |
| ALPHA1 | 248.89 | 71.6 | 583 | |
| **BETA1** | **247.09** | **88.5** | **365** | **Highest cache efficiency** |

### 3. Burst Traffic
*Periodic spikes in request rate.*

| Strategy | P99 (ms) | Hit Rate (%) | Timeouts | Notes |
|----------|----------|--------------|----------|-------|
| Round Robin | 248.55 | 72.9 | 518 | |
| ALPHA1 | 249.06 | 72.8 | 553 | |
| **BETA1** | **246.44** | **87.5** | **224** | **Best stability under burst** |

### 4. Partial Failures
*Servers slowing down or dropping packets.*

| Strategy | P99 (ms) | Hit Rate (%) | Timeouts | Drops |
|----------|----------|--------------|----------|-------|
| Round Robin | 248.11 | 72.4 | 513 | 5 |
| ALPHA1 | 248.51 | 73.5 | 592 | 3 |
| **BETA1** | **245.82** | **88.4** | **234** | **1** |

### 5. Cache Locality
*Zipfian workload favoring hot keys.*

| Strategy | P99 (ms) | Hit Rate (%) | Timeouts | Notes |
|----------|----------|--------------|----------|-------|
| Round Robin | 231.06 | 98.4 | 30 | |
| ALPHA1 | 235.64 | 98.3 | 29 | |
| **BETA1** | **222.60** | **99.0** | **20** | **Near perfect efficiency** |

## Conclusion
The simulation confirms that **BETA1** is the superior choice for workloads where cache locality is a factor. Its ability to maintain high hit rates directly translates to lower latencies and fewer timeouts, even under adverse conditions like burst traffic and partial failures.

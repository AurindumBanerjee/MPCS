# MPCS Empirical Benchmark: Indexing Schemes, Cognitive Generations & TIDE Runtime

**Generated:** 2026-11-03 20:48:10 | **Dataset:** Bank v3 (700 canonical records) | **Queries:** 480 Clean + 480 Noisy (5-action space)

---

## 1. Master Comparison: Indexing Schemes & MPCS Cognitive Generations (Bank v3)

All metrics below are **100% empirically measured** in a single unified run over the 700-record Bank v3 (`deep_sizeof` recursive memory footprint, `perf_counter` wall-clock latency, and top-$k$ action ranking over 5 actions: `approach`, `ignore`, `observe`, `alert`, `withdraw`).

| Scheme / Model Generation | Compute Complexity | Deep Space Overhead | Build Time | Scanned / 700 | Query Latency (Mean / p95) | Recall@1 (Clean Acc) | Recall@3 | Clean Unsafe % | Noisy Acc % | Noisy Unsafe % |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Exact KNN (One-Hot Cosine)** | $O(N \cdot D)$ | 319.6 KB (467.5 B/rec) | 4.4 ms | 700 | **5.034 ms** / 8.511 ms | **94.8%** | 99.8% | 0.0% | **87.9%** | 3.8% |
| **BM25 Inverted Index** | $O(|Q| \cdot \overline{DF})$ | 420.2 KB (614.7 B/rec) | 23.57 ms | 510.0 | **2.432 ms** / 7.113 ms | **94.4%** | 99.8% | 0.0% | **88.1%** | 0.4% |
| **Counting Bloom (dlCBF Gate)** | $O(d)$ hash | 8.8 KB (12.8 B/rec) | 13.09 ms | 1.7 | **0.017 ms** / 0.03 ms | **50.2%** | 67.7% | 1.2% | **29.4%** | 0.4% |
| **B2: Baseline v2 (Global Top-5)** | $O(N)$ | 981.2 KB (1435.4 B/rec) | 428.35 ms | 700 | **10.491 ms** / 16.148 ms | **79.6%** | 98.8% | 0.0% | **73.3%** | 1.2% |
| **B2g: Baseline v2 + dlCBF Gate** | $O(d) + O(N_{\text{gate}})$ | 981.2 KB (1435.3 B/rec) | 36.65 ms | 266.9 | **5.042 ms** / 10.404 ms | **45.6%** | 68.1% | 0.0% | **26.5%** | 0.0% |
| **G4: Core v2 (Per-Action Z)** | $O(|A| \cdot N)$ | 981.2 KB (1435.3 B/rec) | 19.33 ms | 700 | **4.667 ms** / 7.362 ms | **34.2%** | 80.4% | 31.2% | **34.6%** | 30.4% |
| **G5: HyST (Hard Slot + Soft Kernel)** | $O(N_{\text{slot}})$ | 981.2 KB (1435.3 B/rec) | 22.34 ms | 700 | **12.554 ms** / 28.317 ms | **64.0%** | 82.7% | 1.2% | **46.7%** | 1.2% |
| **G6: HMGI (Modality Partitions)** | $O(M_{\text{part}} + N_{\text{cand}})$ | 981.1 KB (1435.3 B/rec) | 82.03 ms | 636.7 | **14.461 ms** / 33.675 ms | **34.2%** | 80.4% | 31.2% | **34.6%** | 30.4% |
| **G7: SHMF (Auto-Relaxed Filter)** | $O(M_{\text{part}} + N_{\text{slot}})$ | 981.1 KB (1435.3 B/rec) | 120.12 ms | 636.7 | **10.469 ms** / 38.778 ms | **75.6%** | 91.2% | 2.1% | **68.1%** | 3.8% |
| **G8: KERL (SHMF + Safety + Graph)** | $O(N_{\text{slot}} + E_{\text{2hop}})$ | 981.1 KB (1435.2 B/rec) | 49.37 ms | 636.7 | **6.871 ms** / 15.494 ms | **75.0%** | 90.6% | 1.7% | **67.7%** | 3.8% |
| **G9: TIDE (Spreading Activation)** | $O(B_{\text{budget}} + E_{\text{act}})$ | 981.1 KB (1435.2 B/rec) | 38.22 ms | 636.7 | **6.557 ms** / 15.65 ms | **75.0%** | 90.6% | 1.7% | **67.7%** | 3.8% |

> **Key Empirical Findings:**
> * **Counting Bloom Filter (`dlCBF Gate`)** occupies the smallest index footprint (**8.9 KB** for the $4 \times 256$ counter tables, or **45.6%** clean accuracy when paired with `Baseline v2` in `B2g`), but because exact perceptual hashes never match perturbed inputs, it blocks retrieval on **61.9%** of `clean` and **85.4%** of `noisy` queries (falling back to safe `observe` with $0.0\%$ unsafe rate, at the cost of plunging noisy accuracy to $26.5\%$).
> * **Global vs. Per-Action Top-5 (`B2` vs. `G4 Core v2`)**: `B2 Baseline v2` (global top-5 voting) reaches **79.6%** clean / **73.3%** noisy accuracy, whereas `G4 Core v2` (independent per-action top-5 voting without hard slot filtering) drops to **34.2%**, because weakly related high-reward memories in incompatible actions outvote exact matches.
> * **HyST (`G5`) Hard/Soft Split**: Filtering on low-cardinality safety slots before soft similarity scoring cuts unsafe errors from **31.2%** (`G4`) down to **1.2%** (`G5`), while raising clean accuracy to **64.0%**.
> * **SHMF (`G7`), KERL (`G8`), and TIDE (`G9`)**: Auto-relaxation in `SHMF` recovers the $18.3\%$ empty-filter rate of `HyST`, lifting accuracy to **75.6%** clean / **68.1%** noisy. `KERL` and `TIDE` add the near-miss safety guard and spreading activation over the knowledge graph, achieving **75.0%** clean accuracy with only **1.7%** unsafe errors (and **67.7%** noisy accuracy with **3.8%** unsafe).

---

## 2. TIDE Benchmark: Anytime Budget Curve & Spreading Activation

When the `urgent` flag is active, TIDE orders candidate memories by spreading-activation energy and cuts deliberation short as soon as the candidate budget $B$ is reached. A passive background pass then verifies whether the cut-short decision agreed with the exhaustive full read.

### A. Clean Archetype Queries (480 queries, Urgent = True)

| Budget | Candidates Read / Avail | Cut Short % | Decision Latency | Accuracy % | Unsafe Action % | Agreement with Full Read % |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **B=3** | 2.2 / 25.4 | 59.2% | **3.47 ms** | **71.9%** | **1.2%** | 73.2% |
| **B=5** | 3.3 / 25.4 | 50.2% | **3.45 ms** | **70.6%** | **1.2%** | 71.8% |
| **B=10** | 5.6 / 25.4 | 41.0% | **4.37 ms** | **67.9%** | **1.2%** | 76.1% |
| **B=20** | 9.2 / 25.4 | 30.2% | **6.61 ms** | **67.3%** | **1.2%** | 75.9% |
| **B=50** | 14.4 / 25.4 | 10.0% | **6.35 ms** | **65.4%** | **1.2%** | 77.1% |
| **full** | 25.4 / 25.4 | 0.0% | **4.71 ms** | **64.8%** | **1.2%** | 100.0% |

### B. Noisy Sensor Queries (480 queries with feature perturbation, Urgent = True)

| Budget | Candidates Read / Avail | Cut Short % | Decision Latency | Accuracy % | Unsafe Action % | Agreement with Full Read % |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **B=3** | 1.6 / 19.0 | 45.4% | **4.42 ms** | **50.8%** | **1.2%** | 80.3% |
| **B=5** | 2.5 / 19.0 | 37.5% | **4.99 ms** | **49.6%** | **1.2%** | 77.2% |
| **B=10** | 4.2 / 19.0 | 29.8% | **3.83 ms** | **48.5%** | **1.2%** | 79.7% |
| **B=20** | 6.7 / 19.0 | 20.6% | **4.37 ms** | **47.3%** | **1.2%** | 76.8% |
| **B=50** | 10.5 / 19.0 | 7.5% | **8.01 ms** | **46.9%** | **1.2%** | 72.2% |
| **full** | 19.0 / 19.0 | 0.0% | **5.45 ms** | **46.2%** | **1.2%** | 100.0% |

### C. TIDE Sufficiency Routing Breakdown (Urgent Flag OFF)

When deliberation is not under hard deadlines, TIDE routes queries into three epistemic confidence regimes based on evidence margin:

| Route Mode | Clean Share % | Clean Accuracy % | Noisy Share % | Noisy Accuracy % | Semantic Meaning |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **DIRECT** | 7.7% | **97.3%** | 4.2% | **90.0%** | Lead action dominates runner-up by margin $\ge \text{direct\_margin}$; immediate confident prescription (`CONFIDENT` persona). |
| **SUBGRAPH** | 88.8% | **76.1%** | 90.4% | **69.8%** | Multiple competing candidate actions; returns active focused subgraph for differential reasoning (`EXPLORATORY` persona). |
| **UNGROUNDED** | 3.5% | **0.0%** | 5.4% | **11.5%** | No candidate memories meet sufficiency threshold; flags missing evidence (`observe`) to prevent hallucination. |

---

## 3. Summary of Verified Findings

1. **Less-is-More Under Urgent Deadlines:** Cutting TIDE's candidate read to the top $B=3$ highest-activation seeds achieves **3.47 ms** clean decision latency (**4.42 ms** noisy) and actually **improves** urgent accuracy from **64.8% $\to$ 71.9%** on clean queries (**46.2% $\to$ 50.8%** on noisy), while holding the unsafe error rate flat at **1.2%**. Lower-ranked tail candidates contribute dilution noise rather than signal.
2. **The Passive Verification Safety Net:** Across the **59.2%** of clean queries cut short at $B=3$, the background passive full read agreed with the rapid decision **73.2%** of the time (**80.3%** on noisy queries).
3. **Calibrated Epistemic Routing:** In non-urgent deliberation, queries routed to `DIRECT` achieve **97.3%** clean accuracy (**90.0%** noisy), while ambiguous cases are isolated into `SUBGRAPH` (**88.8%** of clean queries at **76.1%** accuracy) and unevidenced queries are safely caught as `UNGROUNDED`.
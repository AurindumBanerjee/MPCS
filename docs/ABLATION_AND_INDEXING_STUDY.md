# Ablation Studies and Extended Perceptual Indexing Benchmarks (LocalKG Materia Medica KG)

## Dataset Summary (LocalKG Materia Medica Knowledge Graph)

- **Source occurrences:** `LocalKG/data/extracted/kg_full_materia_medica.jsonl` (202 JSONL rows, **953** clinical occurrences, **452** unique 4-channel MPCS percepts)
- **Source graph:** `LocalKG/data/extracted/kg_full_materia_medica_cleaned.graph.json` (**1106** nodes, **2024** links)
- **Query sets:** **300** clean queries (77 safety-critical) + **300** noisy queries (77 safety-critical, 1 non-safety feature perturbed)
- **Action distribution (raw):** `{'ignore': 58, 'observe': 511, 'approach': 165, 'alert': 87, 'withdraw': 132}`
- **Action distribution (consensus ground truth):** `{'ignore': 60, 'observe': 495, 'approach': 149, 'alert': 114, 'withdraw': 135}`

## Study A: Extended Perceptual Indexing & MPCS Generations (MMKG: 953 Occurrences, 300 Clean + 300 Noisy)

| Scheme / Model | Category | Complexity | Space (KB) | Build (ms) | Scanned | Mean Lat (ms) | p95 Lat (ms) | Clean Acc % | R@3 % | Clean Unsafe % | Noisy Acc % | Noisy Unsafe % |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Exact KNN (Cosine)** | Indexing | $O(N \cdot D)$ | 423.8 | 14.5 | 953 | 8.505 | 13.835 | **84.3%** | 97.3% | 14.3% | **76.3%** | 16.9% |
| **BM25 Inverted Index** | Indexing | $O(|Q| \cdot \overline{DF})$ | 800.0 | 24.75 | 953.0 | 6.133 | 7.532 | **83.3%** | 97.3% | 13.0% | **63.0%** | 20.8% |
| **dlCBF Gate** | Indexing | $O(d)$ hash | 9.2 | 15.11 | 11 | 0.020 | 0.030 | **95.0%** | 100.0% | 10.4% | **45.7%** | 10.4% |
| **Cuckoo Filter Gate** | Indexing | $O(1)$ 2-choice | 35.1 | 17.3 | 11 | 0.025 | 0.035 | **95.0%** | 100.0% | 10.4% | **45.7%** | 10.4% |
| **SimHash LSH (64-bit)** | Indexing | $O(N)$ XOR popcnt | 106.4 | 36.67 | 953 | 0.689 | 0.836 | **82.7%** | 97.3% | 18.2% | **65.3%** | 18.2% |
| **Slot Inverted Bitset** | Indexing | $O(|Q| \cdot \text{hits})$ | 48.9 | 6.85 | 953.0 | 3.660 | 4.345 | **84.7%** | 97.3% | 15.6% | **77.7%** | 15.6% |
| **NSW Proximity Graph** | Indexing | $O(\text{ef} \cdot M \log N)$ | 591.3 | 1791.06 | 278.9 | 2.651 | 4.633 | **84.7%** | 97.3% | 15.6% | **75.3%** | 15.6% |
| **B2 Global Top-5** | MPCS | $O(N)$ | 1561.2 | 49.0 | 953 | 11.324 | 12.561 | **85.0%** | 91.0% | 14.3% | **70.7%** | 19.5% |
| **G4 Core** | MPCS | $O(|A| \cdot N)$ | 1560.7 | 44.93 | 953 | 13.127 | 14.556 | **10.0%** | 68.7% | 46.8% | **15.3%** | 33.8% |
| **G5 HyST** | MPCS | $O(N_{\text{slot}})$ | 1561.7 | 51.48 | 953 | 10.651 | 14.520 | **44.0%** | 56.3% | 11.7% | **43.7%** | 14.3% |
| **G6 HMGI** | MPCS | $O(M_{\text{part}} + N_{\text{cand}})$ | 1611.8 | 49.01 | 953 | 14.488 | 15.953 | **10.0%** | 68.7% | 46.8% | **15.3%** | 33.8% |
| **G7 SHMF** | MPCS | $O(M_{\text{part}} + N_{\text{slot}})$ | 1613.7 | 63.08 | 953 | 4.946 | 6.957 | **44.0%** | 56.3% | 11.7% | **43.7%** | 14.3% |
| **G8 KERL** | MPCS | $O(N_{\text{slot}} + E_{\text{2hop}})$ | 1615.7 | 48.91 | 953 | 6.169 | 11.773 | **42.3%** | 55.3% | 26.0% | **42.3%** | 26.0% |
| **G9 TIDE** | MPCS | $O(B_{\text{budget}} + E_{\text{act}})$ | 1617.3 | 47.6 | 953 | 6.605 | 12.091 | **42.3%** | 55.3% | 26.0% | **42.3%** | 26.0% |

## Study B: MPCS G9 TIDE Component Ablation, Anytime Budgets & Sufficiency Routing (MMKG)

### B1. Component Ablation (8 Variants)

| Configuration | Clean Acc % | Clean Unsafe % | Clean Lat (ms) | Noisy Acc % | Noisy Unsafe % | Noisy Lat (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Full G9 TIDE (Urgent=False)** | 42.7% | 26.0% | 6.81 | 42.0% | 26.0% | 6.57 |
| **w/o TIDE Spread (hops=0, w_g=0)** | 42.7% | 26.0% | 6.15 | 42.0% | 26.0% | 6.33 |
| **w/o VAD Affect & Salience (salience_gain=0, affect=False)** | 42.3% | 26.0% | 6.92 | 42.3% | 26.0% | 6.93 |
| **w/o KERL Near-Miss Guard** | 42.7% | 26.0% | 6.76 | 42.0% | 26.0% | 6.82 |
| **w/o SHMF Auto-Relaxation** | 42.7% | 26.0% | 6.84 | 42.0% | 26.0% | 6.82 |
| **w/o HyST Hard Slots (Soft Only)** | 12.7% | 0.0% | 34.48 | 12.7% | 0.0% | 35.58 |
| **w/o Expert Grade Boost (boost=1.0)** | 42.3% | 26.0% | 6.85 | 42.0% | 26.0% | 6.97 |
| **w/o Full-Read (Urgent B=3)** | 91.0% | 11.7% | 7.15 | 78.7% | 14.3% | 7.25 |

### B2. TIDE Anytime Deadline Budgets (Urgent = True)

| Split | Budget | Read / Avail | Cut Short % | Accuracy % | Unsafe % | Agreement w/ Full % | Mean Lat (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Clean | **B=3** | 2.8 / 67.3 | 81.7% | **91.0%** | 11.7% | 38.4% | 5.67 |
| Clean | **B=5** | 4.4 / 67.3 | 74.0% | **87.0%** | 14.3% | 37.4% | 5.71 |
| Clean | **B=10** | 7.9 / 67.3 | 65.7% | **79.0%** | 3.9% | 37.6% | 5.68 |
| Clean | **B=20** | 13.8 / 67.3 | 49.7% | **68.0%** | 14.3% | 43.6% | 5.75 |
| Clean | **B=50** | 26.4 / 67.3 | 31.0% | **55.3%** | 18.2% | 54.8% | 6.18 |
| Clean | **Full** | 67.3 / 67.3 | 0.0% | **44.0%** | 27.3% | 100.0% | 6.89 |
| Noisy | **B=3** | 2.8 / 67.3 | 81.7% | **78.7%** | 14.3% | 43.7% | 5.39 |
| Noisy | **B=5** | 4.4 / 67.3 | 74.0% | **76.7%** | 14.3% | 43.7% | 5.69 |
| Noisy | **B=10** | 7.9 / 67.3 | 65.7% | **67.7%** | 14.3% | 47.7% | 5.66 |
| Noisy | **B=20** | 13.8 / 67.3 | 49.7% | **61.3%** | 13.0% | 50.3% | 6.12 |
| Noisy | **B=50** | 26.4 / 67.3 | 31.0% | **50.7%** | 19.5% | 63.4% | 6.49 |
| Noisy | **Full** | 67.3 / 67.3 | 0.0% | **43.7%** | 27.3% | 100.0% | 7.36 |

### B3. TIDE Sufficiency Routing Breakdown (Urgent = False)

| Route Mode | Clean Count | Clean Share % | Clean Accuracy % | Noisy Count | Noisy Share % | Noisy Accuracy % |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **DIRECT** | 59 | 19.7% | 44.1% | 59 | 19.7% | 44.1% |
| **SUBGRAPH** | 241 | 80.3% | 42.3% | 241 | 80.3% | 41.5% |
| **UNGROUNDED** | 0 | 0.0% | 0.0% | 0 | 0.0% | 0.0% |

## Study C: LocalKG PersonaQueryEngine Component Ablation (1106 nodes, 2024 links; 40 queries x 10 runs = 400 calls/variant)

> Deterministic Medicine ranking tie-break (`top3_tie_break`): `(-score, label.lower())`.

| Configuration | Mean Kept Nodes | Pruned % | Internal Edges | Remedy Top-1 | Remedy Top-3 | Mean Lat (ms) | p95 Lat (ms) | Speedup vs Linear |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Full Exploratory Persona (theta=0.35)** | 86.2 | 92.2% | 108.4 | 24/40 (60.0%) | 32/40 (80.0%) | 11.299 | 23.268 | 0.59x |
| **Full Confident Persona (theta=0.70)** | 6.0 | 99.4% | 0 | 0/40 (0.0%) | 0/40 (0.0%) | 4.387 | 8.462 | 1.52x |
| **w/o 2-Hop Spreading Activation (hops=0)** | 65.2 | 94.1% | 0.2 | 0/40 (0.0%) | 0/40 (0.0%) | 3.574 | 9.284 | 1.86x |
| **w/o 2nd Hop (hops=1)** | 86.2 | 92.2% | 108.4 | 24/40 (60.0%) | 32/40 (80.0%) | 9.844 | 20.655 | 0.68x |
| **w/o VAD Arousal & Grade Multiplier (mu_v=1.0)** | 105.8 | 90.4% | 118.6 | 32/40 (80.0%) | 36/40 (90.0%) | 11.222 | 23.115 | 0.59x |
| **w/o Clinical Synonym Expansion** | 87.0 | 92.1% | 108.2 | 24/40 (60.0%) | 34/40 (85.0%) | 11.018 | 22.600 | 0.60x |
| **w/o Edge-Weight Modulation (uniform w_uv=1.0)** | 86.2 | 92.2% | 108.4 | 24/40 (60.0%) | 32/40 (80.0%) | 11.753 | 23.330 | 0.57x |
| **w/o Precomputed Inverted Index (Linear Scan)** | 137.2 | 87.6% | 181.8 | 19/40 (47.5%) | 27/40 (67.5%) | 6.661 | 9.546 | 1.00x |

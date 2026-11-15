# Ablation Studies and Extended Perceptual Indexing Benchmarks

## Study A: Extended Perceptual Indexing Schemes (Bank v3: 700 records, 480 Clean + 480 Noisy)

| Indexing Scheme | Complexity | Space (KB) | Build (ms) | Scanned | Mean Lat (ms) | p95 Lat (ms) | Clean Acc % | R@3 % | Clean Unsafe % | Noisy Acc % | Noisy Unsafe % |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Exact KNN (Cosine)** | $O(N \cdot D)$ | 319.6 | 6.08 | 700 | 6.815 | 9.588 | **94.8%** | 99.8% | 0.0% | **87.9%** | 3.8% |
| **BM25 Inverted Index** | $O(|Q| \cdot \overline{DF})$ | 420.2 | 6.16 | 510.0 | 1.337 | 2.256 | **94.4%** | 99.8% | 0.0% | **88.1%** | 0.4% |
| **dlCBF Gate** | $O(d)$ hash | 8.8 | 10.03 | 1.7 | 0.017 | 0.029 | **50.2%** | 67.7% | 1.2% | **29.4%** | 0.4% |
| **Cuckoo Filter Gate** | $O(1)$ 2-choice | 35.7 | 14.71 | 1.7 | 0.020 | 0.033 | **50.2%** | 67.7% | 1.2% | **29.4%** | 0.4% |
| **SimHash LSH (64-bit)** | $O(N)$ XOR popcnt | 87.3 | 26.77 | 700 | 0.510 | 0.712 | **85.4%** | 96.9% | 2.9% | **80.0%** | 8.3% |
| **Slot Inverted Bitset** | $O(|Q| \cdot \text{hits})$ | 38.5 | 3.91 | 510.0 | 0.802 | 1.285 | **90.6%** | 99.6% | 0.4% | **82.3%** | 2.1% |
| **NSW Proximity Graph** | $O(\text{ef} \cdot M \log N)$ | 444.4 | 944.38 | 160.8 | 1.731 | 2.283 | **94.8%** | 99.8% | 0.0% | **87.3%** | 3.8% |

## Study B: MPCS G9 TIDE Systematic Component Ablation (Bank v3)

| Configuration | Clean Acc % | Clean Unsafe % | Noisy Acc % | Noisy Unsafe % | Clean Lat (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Full G9 TIDE (Urgent=False)** | 75.0% | 1.7% | 67.5% | 3.8% | 5.33 |
| **w/o TIDE Spread (hops=0, w_g=0)** | 75.0% | 1.7% | 67.7% | 3.8% | 4.94 |
| **w/o VAD Affect & Salience** | 75.0% | 1.7% | 67.5% | 3.8% | 5.09 |
| **w/o KERL Near-Miss Guard** | 76.2% | 2.1% | 67.7% | 3.8% | 5.15 |
| **w/o SHMF Auto-Relaxation** | 64.6% | 1.2% | 46.9% | 1.2% | 3.56 |
| **w/o HyST Hard Slots (Soft Only)** | 21.0% | 13.3% | 21.0% | 10.8% | 20.96 |
| **w/o Expert Boost (boost=1.0)** | 75.0% | 1.7% | 67.7% | 3.8% | 5.37 |
| **w/o Full-Read (Urgent B=3)** | 71.9% | 1.2% | 50.8% | 1.2% | 3.83 |

## Study C: LocalKG PersonaQueryEngine Component Ablation (1,106 nodes, 2,024 links)

| Configuration | Mean Kept Nodes | Pruned % | Internal Edges | Remedy Top-1 | Remedy Top-3 | Mean Lat (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Full Exploratory (theta=0.35)** | 36.6 | 96.7% | 38.4 | 4/8 | 6/8 | 7.00 |
| **Full Confident (theta=0.70)** | 2.5 | 99.8% | 0 | 0/8 | 0/8 | 3.07 |
| **w/o 2-Hop Spread (hops=0)** | 23 | 97.9% | 0.1 | 0/8 | 0/8 | 1.51 |
| **w/o VAD Arousal & Severity** | 94.4 | 91.5% | 113 | 3/8 | 6/8 | 12.92 |
| **w/o Clinical Synonyms** | 35.4 | 96.8% | 33.8 | 3/8 | 6/8 | 6.96 |
| **w/o Inverted Index (Linear Scan)** | 58.8 | 94.7% | - | - | - | 6.49 |
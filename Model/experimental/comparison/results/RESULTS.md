# MPCS model comparison — raw results

Generated 2026-09-28T20:32:03 by `run_comparison.py`. Do not edit by hand; see `README.md` for method and analysis.

## Bank v1 (30 records)

Memory build time (ms): Basic 0.1, Bloom 2.7, Z+dlCBF 1.0, Core v2 1.2, HyST 1.0, HMGI 1.3, SHMF 1.0, KERL 1.2

### v1 / seen — 29 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 51.7 | 0.0 | 0.0 | — | 100.0 | 0.000 | 30.0 | 0.06 |
| G2 | Bloom | 51.7 | 0.0 | 0.0 | 100.0 | 100.0 | 0.000 | 30.0 | 0.29 |
| G3 | Z+dlCBF | 51.7 | 0.0 | 0.0 | 100.0 | 100.0 | 0.000 | 30.0 | 0.12 |
| G4 | Core v2 | 24.1 | 0.0 | 0.0 | — | 100.0 | 0.000 | 30.0 | 0.20 |
| G5 | HyST | 79.3 | 0.0 | 0.0 | — | 100.0 | 0.000 | 30.0 | 0.13 |
| G6 | HMGI | 24.1 | 0.0 | 0.0 | — | 100.0 | 0.000 | 30.0 | 0.25 |
| G7 | SHMF | 79.3 | 0.0 | 0.0 | — | 100.0 | 0.000 | 30.0 | 0.10 |
| G8 | KERL | 79.3 | 0.0 | 0.0 | — | 100.0 | 0.000 | 30.0 | 0.17 |

Decision agreement: Basic vs Z+dlCBF 100%; Basic vs Bloom 100%; Core v2 vs HMGI 100%; HyST vs SHMF 100%; SHMF vs KERL 100%

### v1 / near — 173 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 45.7 | 0.0 | 0.0 | — | 100.0 | 0.200 | 30.0 | 0.06 |
| G2 | Bloom | 31.2 | 0.0 | 100.0 | 0.0 | 100.0 | 1.000 | 0.0 | 0.18 |
| G3 | Z+dlCBF | 31.2 | 0.0 | 100.0 | 0.0 | 100.0 | 1.000 | 0.0 | 0.03 |
| G4 | Core v2 | 28.3 | 0.0 | 0.0 | — | 100.0 | 0.201 | 30.0 | 0.19 |
| G5 | HyST | 80.9 | 0.0 | 0.0 | — | 100.0 | 0.190 | 30.0 | 0.13 |
| G6 | HMGI | 28.3 | 0.0 | 0.0 | — | 100.0 | 0.201 | 30.0 | 0.27 |
| G7 | SHMF | 80.9 | 0.0 | 0.0 | — | 100.0 | 0.190 | 30.0 | 0.08 |
| G8 | KERL | 80.9 | 0.0 | 0.0 | — | 100.0 | 0.190 | 30.0 | 0.15 |

Decision agreement: Basic vs Z+dlCBF 17%; Basic vs Bloom 17%; Core v2 vs HMGI 100%; HyST vs SHMF 100%; SHMF vs KERL 100%

## Bank v2 (70 records)

Memory build time (ms): Basic 0.1, Bloom 3.6, Z+dlCBF 1.3, Core v2 1.7, HyST 2.0, HMGI 1.9, SHMF 6.1, KERL 2.3

### v2 / seen — 63 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 44.4 | 20.0 | 3.2 | — | 79.4 | 0.000 | 70.0 | 0.11 |
| G2 | Bloom | 44.4 | 20.0 | 3.2 | 100.0 | 79.4 | 0.000 | 70.0 | 0.30 |
| G3 | Z+dlCBF | 44.4 | 20.0 | 3.2 | 100.0 | 79.4 | 0.000 | 70.0 | 0.18 |
| G4 | Core v2 | 39.7 | 16.0 | 0.0 | — | 100.0 | 0.000 | 70.0 | 0.56 |
| G5 | HyST | 100.0 | 0.0 | 0.0 | — | 100.0 | 0.000 | 70.0 | 0.27 |
| G6 | HMGI | 39.7 | 16.0 | 0.0 | — | 100.0 | 0.000 | 70.0 | 0.58 |
| G7 | SHMF | 100.0 | 0.0 | 0.0 | — | 100.0 | 0.000 | 70.0 | 0.18 |
| G8 | KERL | 100.0 | 0.0 | 0.0 | — | 100.0 | 0.000 | 70.0 | 0.20 |

Decision agreement: Basic vs Z+dlCBF 100%; Basic vs Bloom 100%; Core v2 vs HMGI 100%; HyST vs SHMF 100%; SHMF vs KERL 100%

### v2 / near — 600 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 42.0 | 18.6 | 1.2 | — | 79.8 | 0.111 | 70.0 | 0.10 |
| G2 | Bloom | 29.5 | 9.5 | 56.7 | 44.3 | 79.8 | 0.557 | 31.0 | 0.24 |
| G3 | Z+dlCBF | 29.5 | 9.5 | 56.7 | 44.3 | 79.8 | 0.557 | 31.0 | 0.09 |
| G4 | Core v2 | 37.2 | 16.9 | 0.0 | — | 100.0 | 0.086 | 70.0 | 0.59 |
| G5 | HyST | 100.0 | 0.0 | 0.0 | — | 100.0 | 0.074 | 70.0 | 0.30 |
| G6 | HMGI | 37.2 | 16.9 | 0.0 | — | 100.0 | 0.086 | 70.0 | 0.62 |
| G7 | SHMF | 100.0 | 0.0 | 0.0 | — | 100.0 | 0.074 | 70.0 | 0.17 |
| G8 | KERL | 100.0 | 0.0 | 0.0 | — | 100.0 | 0.074 | 70.0 | 0.22 |

Decision agreement: Basic vs Z+dlCBF 68%; Basic vs Bloom 68%; Core v2 vs HMGI 100%; HyST vs SHMF 100%; SHMF vs KERL 100%

## Bank v3 (700 records)

Memory build time (ms): Basic 4.9, Bloom 25.9, Z+dlCBF 9.3, Core v2 11.6, HyST 10.6, HMGI 13.4, SHMF 12.9, KERL 13.6

### v3 / seen — 406 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 47.3 | 35.3 | 12.6 | — | 71.2 | 0.108 | 700.0 | 0.72 |
| G2 | Bloom | 47.3 | 35.3 | 12.6 | 100.0 | 71.2 | 0.108 | 700.0 | 0.86 |
| G3 | Z+dlCBF | 47.3 | 35.3 | 12.6 | 100.0 | 71.2 | 0.108 | 700.0 | 1.83 |
| G4 | Core v2 | 38.4 | 21.9 | 0.0 | — | 100.0 | 0.000 | 700.0 | 5.50 |
| G5 | HyST | 82.3 | 0.0 | 0.0 | — | 100.0 | 0.000 | 700.0 | 4.66 |
| G6 | HMGI | 38.4 | 21.9 | 0.0 | — | 100.0 | 0.000 | 645.0 | 5.64 |
| G7 | SHMF | 82.3 | 0.0 | 0.0 | — | 100.0 | 0.000 | 645.0 | 2.31 |
| G8 | KERL | 82.0 | 0.0 | 0.0 | — | 100.0 | 0.000 | 645.0 | 3.53 |

Decision agreement: Basic vs Z+dlCBF 100%; Basic vs Bloom 100%; Core v2 vs HMGI 100%; HyST vs SHMF 100%; SHMF vs KERL 97%

### v3 / near — 600 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 46.5 | 35.1 | 4.0 | — | 73.8 | 0.099 | 700.0 | 1.59 |
| G2 | Bloom | 37.0 | 61.9 | 42.0 | 61.8 | 73.8 | 0.415 | 432.8 | 1.50 |
| G3 | Z+dlCBF | 37.0 | 61.9 | 42.0 | 61.8 | 73.8 | 0.415 | 432.8 | 1.39 |
| G4 | Core v2 | 42.7 | 24.5 | 0.0 | — | 100.0 | 0.107 | 700.0 | 5.71 |
| G5 | HyST | 88.5 | 0.0 | 0.0 | — | 100.0 | 0.089 | 700.0 | 4.96 |
| G6 | HMGI | 42.7 | 24.5 | 0.0 | — | 100.0 | 0.107 | 671.4 | 6.57 |
| G7 | SHMF | 88.5 | 0.0 | 0.0 | — | 100.0 | 0.089 | 671.4 | 2.53 |
| G8 | KERL | 88.8 | 0.0 | 0.0 | — | 100.0 | 0.089 | 671.4 | 2.37 |

Decision agreement: Basic vs Z+dlCBF 76%; Basic vs Bloom 76%; Core v2 vs HMGI 100%; HyST vs SHMF 100%; SHMF vs KERL 99%

### v3 / clean — 480 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 43.1 | 47.1 | 14.0 | — | 75.0 | 0.158 | 700.0 | 0.85 |
| G2 | Bloom | 38.1 | 61.7 | 27.5 | 86.5 | 75.0 | 0.271 | 605.2 | 0.82 |
| G3 | Z+dlCBF | 38.1 | 61.7 | 27.5 | 86.5 | 75.0 | 0.271 | 605.2 | 2.42 |
| G4 | Core v2 | 34.2 | 31.2 | 0.0 | — | 100.0 | 0.065 | 700.0 | 5.47 |
| G5 | HyST | 64.0 | 1.2 | 18.3 | — | 100.0 | 0.212 | 700.0 | 4.86 |
| G6 | HMGI | 34.2 | 31.2 | 0.0 | — | 100.0 | 0.065 | 636.7 | 5.72 |
| G7 | SHMF | 75.6 | 2.1 | 2.3 | — | 100.0 | 0.212 | 636.7 | 4.80 |
| G8 | KERL | 75.0 | 1.7 | 3.5 | — | 100.0 | 0.212 | 636.7 | 4.89 |

Decision agreement: Basic vs Z+dlCBF 87%; Basic vs Bloom 87%; Core v2 vs HMGI 100%; HyST vs SHMF 85%; SHMF vs KERL 95%

### v3 / noisy — 480 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 39.8 | 41.2 | 13.1 | — | 75.0 | 0.173 | 700.0 | 1.45 |
| G2 | Bloom | 31.9 | 59.6 | 38.3 | 74.6 | 75.0 | 0.381 | 522.1 | 1.41 |
| G3 | Z+dlCBF | 31.9 | 59.6 | 38.3 | 74.6 | 75.0 | 0.381 | 522.1 | 1.59 |
| G4 | Core v2 | 34.6 | 30.4 | 0.0 | — | 100.0 | 0.129 | 700.0 | 5.05 |
| G5 | HyST | 46.7 | 1.2 | 41.5 | — | 100.0 | 0.458 | 700.0 | 4.43 |
| G6 | HMGI | 34.6 | 30.4 | 0.0 | — | 100.0 | 0.129 | 641.9 | 5.39 |
| G7 | SHMF | 68.1 | 3.8 | 4.8 | — | 100.0 | 0.458 | 641.9 | 5.91 |
| G8 | KERL | 67.7 | 3.8 | 5.4 | — | 100.0 | 0.458 | 641.9 | 6.10 |

Decision agreement: Basic vs Z+dlCBF 82%; Basic vs Bloom 82%; Core v2 vs HMGI 100%; HyST vs SHMF 67%; SHMF vs KERL 95%

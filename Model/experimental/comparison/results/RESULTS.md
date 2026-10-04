# MPCS model comparison — raw results

Generated 2026-10-03T16:16:20 by `run_comparison.py`. Do not edit by hand; see `README.md` for method and analysis.

## Bank v1 (30 records)

Memory build time (ms): Basic 0.1, Bloom 2.6, Z+dlCBF 1.3, Baseline v2 3.1, Baseline v2+dlCBF 1.5, Core v2 1.8, HyST 1.3, HMGI 1.6, SHMF 1.6, KERL 1.2, TIDE 1.4

### v1 / seen — 29 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 51.7 | 0.0 | 0.0 | — | 100.0 | 0.000 | 30.0 | 0.11 |
| G2 | Bloom | 51.7 | 0.0 | 0.0 | 100.0 | 100.0 | 0.000 | 30.0 | 0.37 |
| G3 | Z+dlCBF | 51.7 | 0.0 | 0.0 | 100.0 | 100.0 | 0.000 | 30.0 | 0.14 |
| B2 | Baseline v2 | 51.7 | 0.0 | 0.0 | — | 100.0 | 0.000 | 30.0 | 0.13 |
| B2g | Baseline v2+dlCBF | 51.7 | 0.0 | 0.0 | 100.0 | 100.0 | 0.000 | 30.0 | 0.15 |
| G4 | Core v2 | 24.1 | 0.0 | 0.0 | — | 100.0 | 0.000 | 30.0 | 0.22 |
| G5 | HyST | 79.3 | 0.0 | 0.0 | — | 100.0 | 0.000 | 30.0 | 0.13 |
| G6 | HMGI | 24.1 | 0.0 | 0.0 | — | 100.0 | 0.000 | 30.0 | 0.24 |
| G7 | SHMF | 79.3 | 0.0 | 0.0 | — | 100.0 | 0.000 | 30.0 | 0.09 |
| G8 | KERL | 79.3 | 0.0 | 0.0 | — | 100.0 | 0.000 | 30.0 | 0.24 |
| G9 | TIDE | 79.3 | 0.0 | 0.0 | — | 100.0 | 0.000 | 30.0 | 0.19 |

Decision agreement: Basic vs Z+dlCBF 100%; Basic vs Bloom 100%; Core v2 vs HMGI 100%; HyST vs SHMF 100%; SHMF vs KERL 100%

### v1 / near — 173 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 45.7 | 0.0 | 0.0 | — | 100.0 | 0.200 | 30.0 | 0.07 |
| G2 | Bloom | 31.2 | 0.0 | 100.0 | 0.0 | 100.0 | 1.000 | 0.0 | 0.22 |
| G3 | Z+dlCBF | 31.2 | 0.0 | 100.0 | 0.0 | 100.0 | 1.000 | 0.0 | 0.04 |
| B2 | Baseline v2 | 45.7 | 0.0 | 0.0 | — | 100.0 | 0.200 | 30.0 | 0.15 |
| B2g | Baseline v2+dlCBF | 31.2 | 0.0 | 100.0 | 0.0 | 100.0 | 0.200 | 0.0 | 0.14 |
| G4 | Core v2 | 28.3 | 0.0 | 0.0 | — | 100.0 | 0.201 | 30.0 | 0.26 |
| G5 | HyST | 80.9 | 0.0 | 0.0 | — | 100.0 | 0.190 | 30.0 | 0.18 |
| G6 | HMGI | 28.3 | 0.0 | 0.0 | — | 100.0 | 0.201 | 30.0 | 0.31 |
| G7 | SHMF | 80.9 | 0.0 | 0.0 | — | 100.0 | 0.190 | 30.0 | 0.10 |
| G8 | KERL | 80.9 | 0.0 | 0.0 | — | 100.0 | 0.190 | 30.0 | 0.23 |
| G9 | TIDE | 80.9 | 0.0 | 0.0 | — | 100.0 | 0.190 | 30.0 | 0.17 |

Decision agreement: Basic vs Z+dlCBF 17%; Basic vs Bloom 17%; Core v2 vs HMGI 100%; HyST vs SHMF 100%; SHMF vs KERL 100%

## Bank v2 (70 records)

Memory build time (ms): Basic 0.2, Bloom 4.5, Z+dlCBF 5.6, Baseline v2 2.3, Baseline v2+dlCBF 3.5, Core v2 2.4, HyST 2.2, HMGI 2.3, SHMF 2.2, KERL 2.2, TIDE 2.5

### v2 / seen — 63 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 44.4 | 20.0 | 3.2 | — | 79.4 | 0.000 | 70.0 | 0.12 |
| G2 | Bloom | 44.4 | 20.0 | 3.2 | 100.0 | 79.4 | 0.000 | 70.0 | 0.35 |
| G3 | Z+dlCBF | 44.4 | 20.0 | 3.2 | 100.0 | 79.4 | 0.000 | 70.0 | 0.32 |
| B2 | Baseline v2 | 52.4 | 16.0 | 0.0 | — | 100.0 | 0.000 | 70.0 | 0.55 |
| B2g | Baseline v2+dlCBF | 52.4 | 16.0 | 0.0 | 100.0 | 100.0 | 0.000 | 70.0 | 0.53 |
| G4 | Core v2 | 39.7 | 16.0 | 0.0 | — | 100.0 | 0.000 | 70.0 | 0.82 |
| G5 | HyST | 100.0 | 0.0 | 0.0 | — | 100.0 | 0.000 | 70.0 | 0.58 |
| G6 | HMGI | 39.7 | 16.0 | 0.0 | — | 100.0 | 0.000 | 70.0 | 0.86 |
| G7 | SHMF | 100.0 | 0.0 | 0.0 | — | 100.0 | 0.000 | 70.0 | 0.22 |
| G8 | KERL | 100.0 | 0.0 | 0.0 | — | 100.0 | 0.000 | 70.0 | 0.26 |
| G9 | TIDE | 100.0 | 0.0 | 0.0 | — | 100.0 | 0.000 | 70.0 | 0.26 |

Decision agreement: Basic vs Z+dlCBF 100%; Basic vs Bloom 100%; Core v2 vs HMGI 100%; HyST vs SHMF 100%; SHMF vs KERL 100%

### v2 / near — 600 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 42.0 | 18.6 | 1.2 | — | 79.8 | 0.111 | 70.0 | 0.13 |
| G2 | Bloom | 29.5 | 9.5 | 56.7 | 44.3 | 79.8 | 0.557 | 31.0 | 0.27 |
| G3 | Z+dlCBF | 29.5 | 9.5 | 56.7 | 44.3 | 79.8 | 0.557 | 31.0 | 0.12 |
| B2 | Baseline v2 | 52.0 | 16.9 | 0.0 | — | 100.0 | 0.083 | 70.0 | 0.47 |
| B2g | Baseline v2+dlCBF | 21.8 | 0.0 | 100.0 | 0.0 | 100.0 | 0.083 | 0.0 | 0.26 |
| G4 | Core v2 | 37.2 | 16.9 | 0.0 | — | 100.0 | 0.086 | 70.0 | 0.85 |
| G5 | HyST | 100.0 | 0.0 | 0.0 | — | 100.0 | 0.074 | 70.0 | 0.51 |
| G6 | HMGI | 37.2 | 16.9 | 0.0 | — | 100.0 | 0.086 | 70.0 | 0.88 |
| G7 | SHMF | 100.0 | 0.0 | 0.0 | — | 100.0 | 0.074 | 70.0 | 0.26 |
| G8 | KERL | 100.0 | 0.0 | 0.0 | — | 100.0 | 0.074 | 70.0 | 0.35 |
| G9 | TIDE | 100.0 | 0.0 | 0.0 | — | 100.0 | 0.074 | 70.0 | 0.32 |

Decision agreement: Basic vs Z+dlCBF 68%; Basic vs Bloom 68%; Core v2 vs HMGI 100%; HyST vs SHMF 100%; SHMF vs KERL 100%

## Bank v3 (700 records)

Memory build time (ms): Basic 1.3, Bloom 36.3, Z+dlCBF 16.6, Baseline v2 15.5, Baseline v2+dlCBF 14.4, Core v2 15.7, HyST 24.9, HMGI 17.5, SHMF 20.0, KERL 20.3, TIDE 25.6

### v3 / seen — 406 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 47.3 | 35.3 | 12.6 | — | 71.2 | 0.108 | 700.0 | 1.28 |
| G2 | Bloom | 47.3 | 35.3 | 12.6 | 100.0 | 71.2 | 0.108 | 700.0 | 1.22 |
| G3 | Z+dlCBF | 47.3 | 35.3 | 12.6 | 100.0 | 71.2 | 0.108 | 700.0 | 1.69 |
| B2 | Baseline v2 | 84.7 | 0.5 | 0.0 | — | 100.0 | 0.000 | 700.0 | 4.52 |
| B2g | Baseline v2+dlCBF | 84.7 | 0.5 | 0.0 | 100.0 | 100.0 | 0.000 | 700.0 | 4.37 |
| G4 | Core v2 | 38.4 | 21.9 | 0.0 | — | 100.0 | 0.000 | 700.0 | 4.71 |
| G5 | HyST | 82.3 | 0.0 | 0.0 | — | 100.0 | 0.000 | 700.0 | 2.82 |
| G6 | HMGI | 38.4 | 21.9 | 0.0 | — | 100.0 | 0.000 | 645.0 | 3.75 |
| G7 | SHMF | 82.3 | 0.0 | 0.0 | — | 100.0 | 0.000 | 645.0 | 1.29 |
| G8 | KERL | 82.0 | 0.0 | 0.0 | — | 100.0 | 0.000 | 645.0 | 2.07 |
| G9 | TIDE | 82.0 | 0.0 | 0.0 | — | 100.0 | 0.000 | 645.0 | 1.79 |

Decision agreement: Basic vs Z+dlCBF 100%; Basic vs Bloom 100%; Core v2 vs HMGI 100%; HyST vs SHMF 100%; SHMF vs KERL 97%

### v3 / near — 600 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 46.5 | 35.1 | 4.0 | — | 73.8 | 0.099 | 700.0 | 0.96 |
| G2 | Bloom | 37.0 | 61.9 | 42.0 | 61.8 | 73.8 | 0.415 | 432.8 | 0.74 |
| G3 | Z+dlCBF | 37.0 | 61.9 | 42.0 | 61.8 | 73.8 | 0.415 | 432.8 | 0.95 |
| B2 | Baseline v2 | 82.0 | 3.0 | 0.0 | — | 100.0 | 0.106 | 700.0 | 4.35 |
| B2g | Baseline v2+dlCBF | 18.5 | 0.0 | 100.0 | 0.0 | 100.0 | 0.106 | 0.0 | 1.54 |
| G4 | Core v2 | 42.7 | 24.5 | 0.0 | — | 100.0 | 0.107 | 700.0 | 3.94 |
| G5 | HyST | 88.5 | 0.0 | 0.0 | — | 100.0 | 0.089 | 700.0 | 4.04 |
| G6 | HMGI | 42.7 | 24.5 | 0.0 | — | 100.0 | 0.107 | 671.4 | 4.52 |
| G7 | SHMF | 88.5 | 0.0 | 0.0 | — | 100.0 | 0.089 | 671.4 | 1.84 |
| G8 | KERL | 88.8 | 0.0 | 0.0 | — | 100.0 | 0.089 | 671.4 | 1.51 |
| G9 | TIDE | 88.8 | 0.0 | 0.0 | — | 100.0 | 0.089 | 671.4 | 5.26 |

Decision agreement: Basic vs Z+dlCBF 76%; Basic vs Bloom 76%; Core v2 vs HMGI 100%; HyST vs SHMF 100%; SHMF vs KERL 99%

### v3 / clean — 480 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 43.1 | 47.1 | 14.0 | — | 75.0 | 0.158 | 700.0 | 2.47 |
| G2 | Bloom | 38.1 | 61.7 | 27.5 | 86.5 | 75.0 | 0.271 | 605.2 | 2.45 |
| G3 | Z+dlCBF | 38.1 | 61.7 | 27.5 | 86.5 | 75.0 | 0.271 | 605.2 | 3.36 |
| B2 | Baseline v2 | 79.6 | 0.0 | 0.0 | — | 100.0 | 0.068 | 700.0 | 10.44 |
| B2g | Baseline v2+dlCBF | 45.6 | 0.0 | 61.9 | 38.1 | 100.0 | 0.068 | 266.9 | 4.09 |
| G4 | Core v2 | 34.2 | 31.2 | 0.0 | — | 100.0 | 0.065 | 700.0 | 9.85 |
| G5 | HyST | 64.0 | 1.2 | 18.3 | — | 100.0 | 0.212 | 700.0 | 6.45 |
| G6 | HMGI | 34.2 | 31.2 | 0.0 | — | 100.0 | 0.065 | 636.7 | 8.26 |
| G7 | SHMF | 75.6 | 2.1 | 2.3 | — | 100.0 | 0.212 | 636.7 | 5.15 |
| G8 | KERL | 75.0 | 1.7 | 3.5 | — | 100.0 | 0.212 | 636.7 | 7.49 |
| G9 | TIDE | 75.0 | 1.7 | 3.5 | — | 100.0 | 0.212 | 636.7 | 6.83 |

Decision agreement: Basic vs Z+dlCBF 87%; Basic vs Bloom 87%; Core v2 vs HMGI 100%; HyST vs SHMF 85%; SHMF vs KERL 95%

### v3 / noisy — 480 queries

| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % | Novelty | Scanned | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Basic | 39.8 | 41.2 | 13.1 | — | 75.0 | 0.173 | 700.0 | 2.28 |
| G2 | Bloom | 31.9 | 59.6 | 38.3 | 74.6 | 75.0 | 0.381 | 522.1 | 2.05 |
| G3 | Z+dlCBF | 31.9 | 59.6 | 38.3 | 74.6 | 75.0 | 0.381 | 522.1 | 4.16 |
| B2 | Baseline v2 | 73.3 | 1.2 | 0.0 | — | 100.0 | 0.133 | 700.0 | 14.90 |
| B2g | Baseline v2+dlCBF | 26.5 | 0.0 | 85.4 | 14.6 | 100.0 | 0.133 | 102.1 | 5.56 |
| G4 | Core v2 | 34.6 | 30.4 | 0.0 | — | 100.0 | 0.129 | 700.0 | 12.00 |
| G5 | HyST | 46.7 | 1.2 | 41.5 | — | 100.0 | 0.458 | 700.0 | 9.10 |
| G6 | HMGI | 34.6 | 30.4 | 0.0 | — | 100.0 | 0.129 | 641.9 | 5.11 |
| G7 | SHMF | 68.1 | 3.8 | 4.8 | — | 100.0 | 0.458 | 641.9 | 3.13 |
| G8 | KERL | 67.7 | 3.8 | 5.4 | — | 100.0 | 0.458 | 641.9 | 3.04 |
| G9 | TIDE | 67.7 | 3.8 | 5.4 | — | 100.0 | 0.458 | 641.9 | 3.78 |

Decision agreement: Basic vs Z+dlCBF 82%; Basic vs Bloom 82%; Core v2 vs HMGI 100%; HyST vs SHMF 67%; SHMF vs KERL 95%

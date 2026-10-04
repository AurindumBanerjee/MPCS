# TIDE benchmark (v3 bank)

## clean - 480 queries

Urgent flag on; budget = candidates read before committing.

| Budget | Read / avail. | Cut short % | Acc % | Unsafe % | Agrees with full % (cut-short only) | ms to decide |
|---|---|---|---|---|---|---|
| 3 | 2.2 / 25.4 | 59 | 71.9 | 1.2 | 73.2 | 2.43 |
| 5 | 3.3 / 25.4 | 50 | 70.6 | 1.2 | 71.8 | 2.86 |
| 10 | 5.6 / 25.4 | 41 | 67.9 | 1.2 | 76.1 | 6.78 |
| 20 | 9.2 / 25.4 | 30 | 67.3 | 1.2 | 75.9 | 6.95 |
| 50 | 14.4 / 25.4 | 10 | 65.4 | 1.2 | 77.1 | 8.28 |
| full | 25.4 / 25.4 | 0 | 64.8 | 1.2 | 100.0 | 6.01 |

Routing (urgent off):

| Route | Share % | Acc % on route |
|---|---|---|
| DIRECT | 7.7 | 97.3 |
| SUBGRAPH | 88.8 | 76.1 |
| UNGROUNDED | 3.5 | 0.0 |

## noisy - 480 queries

Urgent flag on; budget = candidates read before committing.

| Budget | Read / avail. | Cut short % | Acc % | Unsafe % | Agrees with full % (cut-short only) | ms to decide |
|---|---|---|---|---|---|---|
| 3 | 1.6 / 19.0 | 45 | 50.8 | 1.2 | 80.3 | 5.50 |
| 5 | 2.5 / 19.0 | 38 | 49.6 | 1.2 | 77.2 | 4.29 |
| 10 | 4.2 / 19.0 | 30 | 48.5 | 1.2 | 79.7 | 5.83 |
| 20 | 6.7 / 19.0 | 21 | 47.3 | 1.2 | 76.8 | 6.06 |
| 50 | 10.5 / 19.0 | 8 | 46.9 | 1.2 | 72.2 | 6.14 |
| full | 19.0 / 19.0 | 0 | 46.2 | 1.2 | 100.0 | 6.44 |

Routing (urgent off):

| Route | Share % | Acc % on route |
|---|---|---|
| DIRECT | 4.2 | 90.0 |
| SUBGRAPH | 90.4 | 69.8 |
| UNGROUNDED | 5.4 | 11.5 |


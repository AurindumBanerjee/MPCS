# Model/reference

Frozen baseline implementations, kept for comparison and benchmarking. These
are **not** the active development trunk — new mechanisms go in
`../experimental/`.

- `mpcs.py` — canonical reference: flat-list memory, linear-scan similarity,
  randomized initial thresholds (`init_state`).
- `BloomMPCS.py` — `mpcs.py` plus a Bloom-filter fast membership layer
  (requires `pip install bloom-filter`).
- `mpcs_preset_memory.py` / `BloomMPCS_preset_memory.py` — launchers that boot
  the respective UI preloaded with the hand-authored 30-experience memory bank.
- `MPCS_Test.py` — latency benchmark comparing baseline vs. Bloom retrieval.

All files here are siblings so their cross-imports (`from mpcs import ...`,
`from BloomMPCS import ...`) resolve without path changes. Run from this folder.

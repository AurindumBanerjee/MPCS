# Model comparison — every MPCS generation, every memory bank

Runs all eight model generations against all three preset memory banks with
one harness, calling each model's own code. Raw numbers are regenerated into
`results/RESULTS.md` and `results/results.json`; this file holds the method
and the analysis of the run dated 2026-09-28, after the two engine fixes this
comparison motivated (see *Fixes applied*).

```
python run_comparison.py              # all banks (~1 min)
python run_comparison.py --bank v1    # one bank
```

Requires `bloom-filter` (in the repo's `requirements.txt`) for the G2 model.

## What is compared

| Gen | Model | Source | Retrieval | Similarity | Senses / actions |
|---|---|---|---|---|---|
| G1 | Basic | `Model/reference/mpcs.py` | global top-5 | exact-match count | vision+audio / 4 |
| G2 | Bloom | `Model/reference/BloomMPCS.py` | G1, gated by a Bloom filter | as G1 | vision+audio / 4 |
| G3 | Z+dlCBF | `01_baseline_z/MPCS_Z.py` | G1, gated by a d-left counting BF | Z-numbers, conf fixed at 1.0 | vision+audio / 4 |
| G4 | Core v2 | `02_core/mpcs_engine.py` | top-5 per action | Z, per-modality conf | 4 / 5 |
| G5 | HyST | `04_hyst` | hard filter, then top-5 per action | graded soft kernel | 4 / 5 |
| G6 | HMGI | `05_hmgi` | modality partitions, then as G4 | as G4 | 4 / 5 |
| G7 | SHMF | `06_shmf` | partitions -> hard filter (auto-relax) | as G5 | 4 / 5 |
| G8 | KERL | `07_kerl` | G7 + near-miss guard + fusion | as G5 + graph term | 4 / 5 |

G1-G3 see a projection of each percept: touch and smell dropped, and no
`withdraw` action. That is what those models can do; the harness does not
paper over it (see *Expressible %*).

**Banks:** v1 = 30 hand-written two-modality records (the reference preset);
v2 = 70 hand-written four-modality records; v3 = 700 generated records with
partial modalities, contradicting twins and expert corrections.

**Query sets** (never stored in memory):

- `seen` — exact stored percepts with a clear verdict (best reward ≥ 0.6). A membership filter's best case.
- `near` — a seen percept with one *non-safety* feature changed, never a verbatim bank entry. Capped at 600 by fixed-seed sample.
- `clean` / `noisy` (v3 only) — fresh samples from the 16 scenario archetypes; `noisy` re-draws one feature from its full range.

**Decision rule:** each model's own greedy choice with exploration off. G1-G3
take `max()` over raw scores (frozen code; an empty retrieval yields random
priors). G4-G8 choose the best *evidenced* action and observe when nothing
is evidenced. Only memory-based recommendation is scored; reflex rules are out
of scope.

## Headline

Accuracy % (unsafe % in brackets — approach/ignore where alert/withdraw was right):

| | v1 seen | v1 near | v2 seen | v2 near | v3 seen | v3 near | v3 clean | v3 noisy |
|---|---|---|---|---|---|---|---|---|
| G1 Basic | 51.7 | 45.7 | 44.4 (20) | 42.0 (19) | 47.3 (35) | 46.5 (35) | 43.1 (47) | 39.8 (41) |
| G2 Bloom | 51.7 | 31.2 | 44.4 (20) | 29.5 (10) | 47.3 (35) | 37.0 (62) | 38.1 (62) | 31.9 (60) |
| G3 Z+dlCBF | 51.7 | 31.2 | 44.4 (20) | 29.5 (10) | 47.3 (35) | 37.0 (62) | 38.1 (62) | 31.9 (60) |
| G4 Core v2 | 24.1 | 28.3 | 39.7 (16) | 37.2 (17) | 38.4 (22) | 42.7 (25) | 34.2 (31) | 34.6 (30) |
| G5 HyST | 79.3 | 80.9 | 100 (0) | 100 (0) | 82.3 (0) | 88.5 (0) | 64.0 (1.2) | 46.7 (1.2) |
| G6 HMGI | 24.1 | 28.3 | 39.7 (16) | 37.2 (17) | 38.4 (22) | 42.7 (25) | 34.2 (31) | 34.6 (30) |
| G7 SHMF | 79.3 | 80.9 | 100 (0) | 100 (0) | 82.3 (0) | 88.5 (0) | **75.6** (2.1) | **68.1** (3.8) |
| G8 KERL | 79.3 | 80.9 | 100 (0) | 100 (0) | 82.0 (0) | **88.8** (0) | 75.0 (**1.7**) | 67.7 (3.8) |

v1 contains no danger scene the legacy schema can't see, so its unsafe rate is 0 throughout.

## Breakdown

### 1. Basic vs Bloom vs Z-numbers — the three legacy generations

- **The filters never improve a decision.** Bloom and Z+dlCBF output exactly the same
  decisions as Basic whenever their gate opens (100% agreement on every `seen` set).
  When the gate closes they retrieve nothing and roll a random prior. On v1 `near`,
  where no query was stored verbatim, the gate is shut 100% of the time: accuracy
  drops 45.7 → 31.2 and every decision is unsupported.
- **The speed gain is illusory.** On v1, Bloom takes ~0.30 ms/query against Basic's
  ~0.07, because hashing costs more than scanning 30 records. It only looks faster on
  v3 `near` and `noisy`, and only because it skips the scan for 25–38% of queries by
  returning nothing.
- **Bloom "recognition" on newer data is false recognition.** On v2 `near` the Bloom
  gate passes 44% of queries that were never stored. Every one is a collision: once
  touch and smell are dropped, 44.4% of those percepts match a stored record exactly.
  The filter says "seen before" about situations that differ in heat or smell.
- **Z-numbers at conf = 1.0 are arithmetically identical to feature counting.**
  G3's outputs match G2's in every row of every set. The Z layer only changes anything
  once confidences differ, which begins in G4.

### 2. Old models on newer banks — schema limits

The legacy models lose ground as the data outgrows their schema. On v2 they cannot
express the right answer for 20% of queries (`withdraw` does not exist for them), and
on v3 for 25–29%. Their unsafe rate climbs with it: 0% on v1 → 19–20% on v2 →
35–62% on v3. Many of those are hot-surface and impact scenes they cannot feel.

### 3. Core v2 (G4) — more senses, worse decisions

G4 adds per-modality confidence and per-action recall, and scores *below* G1 on v1
(24.1 vs 51.7 on `seen`). Fixing its similarity kernel (see below) corrected its
novelty but not its accuracy, which moved by at most a point. The cause is
structural: each action gets its own top-5, and a weighted average is invariant to
how similar those five are. So a high-reward action's weakly related memories can
outvote the exact match. G1's global top-5 at least restricts voting to near
neighbours. HyST's hard filter is what finally breaks this, by removing the
irrelevant voters before any averaging.

### 4. HMGI (G6) — same decisions, less scanning, not faster

G6 agrees with G4 on 100% of decisions in every set; the two decide identically by
construction. On v3 it scans 636–671 of 700 records instead of 700, but it is no
faster than G4 anywhere (equal or ~10–25% slower), because building the partition
candidate list costs more than it saves.

### 5. HyST (G5) — the hard/soft split is the step change

G5 lifts accuracy from ~40% to 79–100% on the hand-written banks and 82–89% on v3
`seen`/`near`, and since the no-evidence fix its unsafe rate is 0–1.2% everywhere.

- **The `near` sets favour it.** They only change non-safety features, and safety
  features are exactly what HyST filters on, so HyST's filter always finds the
  original's neighbours. The 100% on v2 is partly a property of the test. The v3
  `clean`/`noisy` sets have no such bias, and there G5 reaches 64.0 / 46.7.
- **Its cost is silence.** The strict filter leaves nothing for 18% / 41% of
  `clean`/`noisy` queries. Those now resolve to `observe`, which is safe but
  uninformed.

### 6. SHMF (G7) and KERL (G8) — the current state of the art

- SHMF's auto-relax cuts the empty-result rate from 18% / 41% to 2% / 5% and lifts
  archetype accuracy to 75.6 / 68.1, with 2.1% / 3.8% unsafe.
- KERL now matches SHMF within a point on accuracy and within 0.4 points on safety.
  Its earlier safety lead came almost entirely from observing on an empty result,
  and G4–G7 now do the same. What still separates KERL is what it *adds*: the affect
  read-out, the plain-language explanation, near-miss calibration, and an explicit
  UNGROUNDED label.

## Fixes applied

The first version of this comparison exposed two bugs in `02_core/mpcs_engine.py`.
Both are fixed, and the tables above are after the fix.

1. **Similarity kernel.** `similarity_z` scored a matched feature as `c1 × c2` but
   normalised by `Σ c1`, so an exact repeat scored 0.9625 whenever a channel's
   confidence was below 1. It now uses `min(c1, c2)`, and an exact repeat scores 1.0.
2. **Empty-evidence decisions.** `deliberate` (and the copies of it in HyST, HMGI and
   SHMF) took `max()` over raw scores. When nothing was retrieved every action held a
   default 0.5 and the tie went to `ignore`. The new `best_evidenced_action` chooses
   among supported actions only and falls back to `observe`.

| Effect (v3) | Before | After |
|---|---|---|
| Core v2 novelty on exact repeats (v1 / v2 / v3 `seen`) | 0.037 / 0.093 / 0.086 | 0 / 0 / 0 |
| Core v2 accuracy, `clean` / `noisy` | 35.0 / 33.8 | 34.2 / 34.6 |
| HyST unsafe, `clean` / `noisy` | 22.9 / 43.8 | **1.2 / 1.2** |
| HyST accuracy, `clean` / `noisy` | 62.7 / 44.4 | 64.0 / 46.7 |
| SHMF unsafe, `clean` / `noisy` | 5.4 / 10.0 | **2.1 / 3.8** |
| SHMF accuracy, `clean` / `noisy` | 75.6 / 67.9 | 75.6 / 68.1 |

Not done: retiring the Bloom and dlCBF gates. They only gate retrieval in the frozen
legacy models (G2, G3); G4 onward already uses its dlCBF only as an exact-repeat hint.

## Caveats

- Labels are synthetic. On v1/v2 the correct answer is inferred from stored rewards,
  and `near` assumes a non-safety change doesn't change the right answer. On v3 the
  label is the archetype's action.
- `seen` accuracy below 100% is not a retrieval failure. It reflects reward averaging
  across neighbouring memories, which every generation up to G4 does.
- Latency is single-run Python wall-clock and varies ±30% between runs. Treat it as a ranking, not a measurement.
- Reflexes, exploration, hesitation and learning are all off. This compares what each
  model's *memory* recommends, not its full behaviour.

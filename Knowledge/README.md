# Knowledge/

Corpus-grounded knowledge graph over Hahnemann's *Materia Medica Pura*, with
MeSH as the ailment vocabulary. This is where the Meet-5 work lives.

Separate from `Model/` on purpose: `Model/` is the MPCS cognitive engine over
synthetic categorical percepts, scored by `Model/experimental/comparison/`.
This folder is a retrieval system over real text. It **borrows** code from the
engine's layers (named below) but is not a tenth generation inside it.

---

## Decisions taken — 12 Oct 2026

| Question | Decision |
|---|---|
| Index words, records, or both? | **Knowledge graph + record index.** The induced "small world of important words" is dropped — MeSH is a curated concept hierarchy and does that job better. See *Feasibility* below. |
| Where does the ailment vocabulary come from? | **MeSH**, for now. Repertory option deferred, not rejected. |
| Tenth MPCS generation, or separate? | **Separate** — this folder, at the same level as `Model/` and `Reading/`. |
| Which medicines get supplementary literature? | **Arnica montana**, confirmed present. Second remedy needs re-picking — see below. |

### Pulsatilla is not in this volume

`Meet5/Materia Medica Samuel Hahnemann.pdf` is **volume 2 of 6** (Internet
Archive `b28121612_0002`, 742 pages). Its remedy chapters, by extracted
numbered-entry markers:

| Remedy | Markers (printed every 5th) | Highest entry no. | Est. symptoms |
|---|---|---|---|
| Chamomilla | 876 | 1955 | ~1,900 |
| Belladonna | 480 | 1440 | ~1,440 |
| Arsenicum | 388 | 1060 | ~1,060 |
| Camphora | 386 | 1714 | ~1,100 |
| Conium | 352 | 425 | ~425 |
| Bryonia | 292 | 780 | ~780 |
| Ferrum | 282 | 295 | ~295 |
| Hyoscyamus | 266 | 580 | ~580 |
| Drosera | 238 | 400 | ~400 |
| Ambra grisea | 226 | 485 | ~485 |
| Ignatia | 226 | 790 | ~790 |
| Carbo vegetabilis | 206 | 720 | ~720 |
| **Arnica montana** | **184** | — | **~600–900** |
| Asarum | 177 | 355 | ~355 |
| Aconitum | 165 | 540 | ~540 |
| Argentum | 67 | — | ~340 |
| Ipecacuanha | 67 | 237 | ~237 |

Pulsatilla appears only in the preamble's worked cases, cited by symptom
number — the chapter itself is in another volume. Three ways forward:

1. **Arnica + Belladonna** (recommended for now). Belladonna is the largest
   chapter whose marker count and highest entry number agree, so its
   numbering extracts cleanly. No new source file needed.
2. **Arnica + Arsenicum.** Also clean, and has substantial toxicology
   literature on PubMed for the supplementary-papers half.
3. **Fetch the volume containing Pulsatilla** if Pulsatilla specifically
   matters — it is the remedy the preamble's worked cases cite most, so its
   free labelled pairs are the richest. Costs one download.

Arnica is the better of the two for supplementary literature either way:
*Arnica montana* has real PubMed-indexed clinical literature (bruising,
post-surgical oedema), and PubMed records arrive **pre-annotated with MeSH
descriptors by human indexers** — the `discusses` edges come free.

---

## Feasibility: knowledge graph vs. the two-index setup

**The graph is not an alternative to the indexes — it is what the indexes let
you enter.** A graph answers *"which remedies produce this symptom, and what
else do they produce?"* by traversal, once you know which node you mean. It
cannot take the free-text sentence *"dry cough at night in a weepy child"* and
work out which node that is. That step is retrieval, and it needs an index.

This is exactly KERL's shape, which is already implemented in
`Model/experimental/07_kerl/`: parse entities → pull a subgraph → select from
within it, and never recommend anything outside what was retrieved.

So the revision is a **simplification, not extra work**:

| Layer | Status |
|---|---|
| Induced word-similarity map | **Dropped.** MeSH supplies a curated hierarchy instead of an inferred one. |
| Knowledge graph | **Added**, and it absorbs the concept layer. |
| Record index over symptom text (BM25 + dense) | **Still required** — it is the door into the graph. |

### Edge difficulty, in three tiers

**Nearly free — read straight off the book's structure.**

- `remedy —produces→ symptom`: a numbered entry in a remedy's chapter *is*
  this edge. No inference.
- `symptom —in_region→ region`: from the entry's position in the head-to-toe
  ordering (mind, head, eyes, … chest, sleep, fever, skin).
- `symptom —onset / modality→ …`: regex over the bracketed `(aft. 4 h.)` and
  the time-of-day phrases.
- `symptom —affect→ (V,A,D)`: VAD-lexicon lookup, pooled over content words.
- `symptom —observed_by→ prover`: the `[Kr.]`-style attributions.

**Real work — needs a linker and a confidence score.**

- `symptom —about→ mesh_descriptor`: mapping *"Dry tussiculation as from a
  tickle in the lower part of the trachea"* onto MeSH `Cough` /
  `Respiratory Tract Diseases`. String matching plus embedding similarity
  against MeSH term strings and synonyms. Will be noisy; every such edge
  carries a confidence and the matched surface form, so bad links are
  auditable rather than invisible.
- `symptom —precedes→ symptom`: from the cause clauses the MoM singled out
  ("After weeping and whining, cough"; "Crying … excites cough"). A dozen
  surface patterns cover most of it; expect partial coverage, and record which
  pattern fired.

**Do not do naively.**

- `remedy —treats→ ailment`. The book does not say this. It says the substance
  *produces* these symptoms in a healthy prover; the therapeutic reading comes
  from the similia principle, not from the text. Collapsing `produces` into
  `treats` would put a claim in the graph that the source never makes, and it
  is the first thing a reviewer will catch. Keep it as a **derived** edge,
  `indicated_for`, explicitly flagged as inferred, with the `produces` edges it
  was derived from recorded on it.

### Scale

Two remedies at ~1,000–1,500 symptoms each gives roughly 2,000–3,000 symptom
nodes, a few hundred MeSH descriptors, ~20 regions, two remedies, and tens of
thousands of edges. That is small: it fits in memory, `networkx` handles it
without complaint, and no graph database is needed. Scale only becomes a
question if all six volumes and ~60 remedies go in.

### Verdict

Feasible, and a better target than what was proposed on 11 Oct. The skeleton
(tier 1) is a parsing job with no modelling in it. The MeSH linking (tier 2) is
the only genuinely uncertain component, and it fails *visibly* — a wrong
descriptor is inspectable, unlike a wrong embedding. Budget most of the risk
there.

---

## Layout

```
Knowledge/
  README.md            this file — decisions, feasibility, status
  SCHEMA.md            node and edge types, with provenance per edge
  01_corpus/           PDF -> records.jsonl  (chapter split, entry numbering,
                       OCR cleaning, region paths, onset, provers)
  02_mesh/             MeSH descriptor subset + symptom->descriptor linker
  03_graph/            node/edge construction, traversal, spreading activation
  04_index/            BM25 postings + dense index over symptom text
  05_eval/             labelled pairs, stratified query sets, benchmark harness
  papers/              supplementary literature for the two chosen remedies
```

Numbered in pipeline order, matching the convention in
`Model/experimental/`. Each stage folder gets its own `instructions.txt` as
it is built, as the model folders do.

### Code borrowed from `Model/experimental/`

| Needed here | Comes from |
|---|---|
| Hierarchy scoring over region paths | `08_tide/place_of()`, `place_similarity()`, weight `w_p` — shared-path-prefix scoring, unchanged except for its input |
| Spreading activation with pruning | `08_tide/ActivationGraph`, `spread()` — per-hop decay, fan-out normalisation, prune below threshold, cap active nodes |
| Routed output (DIRECT / SUBGRAPH / UNGROUNDED) | `08_tide/TideReader` |
| Affect read-out interface | `07_kerl/affect_of()`, `emotional_similarity()` — reimplemented over VAD lexicon, same signature |
| Hard/soft constraint split, auto-relax | `04_hyst/SlotPolicy`, `06_shmf` relaxation |
| Scan instrumentation | `05_hmgi/ScanInstrumentation` |
| Benchmark report format | `08_tide/TIDE_BENCH.md`, `comparison/run_comparison.py` |

Nothing here is imported *into* the engine. The dependency runs one way.

---

## Pipeline status

- [ ] **P0 · Corpus extraction** — chapter split, entry numbering with
      interpolation of unprinted numbers, OCR cleaning, region paths, onset,
      provers. Spot-check recovered count against printed markers per chapter.
      *Blocks everything.*
- [ ] **P0b · Labelled pairs** — harvest the preamble's `remedy (n, n)`
      citations into `05_eval/labels.jsonl`. Free ground truth, a few dozen
      pairs.
- [ ] **P1 · Baselines** — BM25 over raw entry text; exact cosine KNN over an
      off-the-shelf sentence encoder. Plus the archaic-vocabulary neighbour
      audit: are the encoder's nearest neighbours for *tussiculation*,
      *haemoptysis*, *crossness* sensible? Go/no-go on the encoder.
- [ ] **P2 · Affect and impact channels** — VAD pooling, intensity and timing
      features, six-configuration ablation on a **stratified** query set
      (affect-bearing vs. physical). Report the weight surface, not the argmax.
- [ ] **P3 · MeSH linking** — descriptor subset, linker, confidence
      calibration, manual audit of a 100-link sample.
- [ ] **P4 · Graph build** — tier-1 edges, then tier-2, then derived
      `indicated_for` with provenance.
- [ ] **P5 · Model on the graph** — re-target `spread()` onto the new edge
      types; keep the routing contract.
- [ ] **P6 · Indexes and crossover** — BM25 + dense index, `ef`/`M` sweep
      against exact KNN, latency-vs-corpus-size curve from 1k to 100k to settle
      the open HMGI scale question.
- [ ] **P7 · Pruning instrumentation and visuals** — per-stage kept / pruned /
      recall-retained counters; graph view with activation as node size.

## Open

- Second remedy: Belladonna, Arsenicum, or fetch the Pulsatilla volume.
- Evaluation labels beyond the preamble's few dozen pairs — a hand-verified
  stratified set of 100–200 queries is the realistic answer, and it is already
  listed as an open task in `docs/MPCS_Progress_Report.html` §14.
- MeSH distribution: descriptor files need downloading; this environment's
  network is restricted, so fetch locally.
- Repertory licensing, if the MeSH route proves too coarse for symptom-level
  concepts.

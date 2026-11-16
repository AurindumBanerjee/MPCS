# Oral Presentation Script: MPCS & Knowledge Graph (`BTP_PPT_Clean.pptx`)

**Target Duration:** ~10–12 minutes (`18` spacious slides, ~30–40 seconds per slide)  
**Presenters:** Aurindum Banerjee (`B23CS1006`) & Lokesh Motwani (`B23CS1033`)  
**Official Title:** *Cognitive Model of Convergent and Divergent Thinking*

---

## Slide 01 — Title Slide (~20s)
> "Good morning/afternoon everyone. We are Aurindum Banerjee and Lokesh Motwani, presenting our B.Tech Project **'Cognitive Model of Convergent and Divergent Thinking'** — implemented as **MPCS & LocalKG** under Dr. Romi Banerjee."

## Slide 02 — Why Model Contemplation? (~45s)
> "Why did we build this? Our project's core aim is to design an AI model of human **contemplation** for reflection and self-correction. Originally, we imitated how humans understand sensory percepts (`vision`, `audio`, `touch`, `smell`) and alternate between **convergent thinking** — focusing quickly onto one safe action — and **divergent thinking** — exploring related associations before deciding, then self-correcting via reward feedback."

## Slide 03 — Homeopathy Expansion & Data Gap (~45s)
> "We then expanded this cognitive model to **Homeopathy**: mapping symptoms and experiences to remedies, and handling **partial inputs** to surface related symptoms, remedies, and conditions. When we looked for a structured Homeopathy dataset, none was publicly accessible. So we built our **Knowledge Graph** ourselves from *Materia Medica Pura* and cited PubMed abstracts, and added filtering and constraint layers to speed up querying on graph-style data."

## Slide 04 — What Exists Today: Static & Brittle (~40s)
> "Existing tools show this gap clearly. *Homeopathy UK* only gives static condition articles with zero symptom reasoning. *Open Materia Medica* does simple token matching against memory — it handles a simple query like *'violent throbbing headache with high fever'* (*Belladonna*), but adding *', dilated pupils'* returns zero matches even though that phrase is right inside *Belladonna*'s description."

## Slide 05 — Cognitive Model Architecture (~45s)
> "Here is our unified **TIDE + Knowledge Graph** architecture. On the left, the MPCS agent takes a clinical input query with a Doctor/Patient persona toggle, runs a **Stage 1 Safety Reflex Guard** (`EMERGENCY_PATTERN` regex plus dynamically learned red-flag filters), applies constraint filtering (`HMGI`, `HyST`, `SHMF`), performs scoring, spreading, and routing (`KERL`, `TIDE`), and outputs either a `DIRECT` keynote or `SUBGRAPH` differential. On the right, the Knowledge Graph stores `1,106` nodes and `2,024` cited edges, and the Bridge connects both with red-flag guarding, subgraph grounding, differential synthesis, and cited Materia Medica evidence in ~4 ms."

## Slide 06 — Two-Stage Retrieval Cascade (~45s)
> "Inside MPCS, we separated retrieval into a two-stage architectural cascade. **Stage I: Indexing & Filtering** cuts search scope with `dlCBF` for `O(d)` exact-match fast exit, `HMGI` for modality-partitioned scans, `HyST` for hard-slot safety pruning and soft-slot grading, and `SHMF` for auto-relaxation on empty sets. **Stage II: Scoring, Spreading & Dynamic Routing** applies `KERL`'s near-miss safety guard and `TIDE`'s affect-weighted graph diffusion with anytime budget bounds and `DIRECT` vs. `SUBGRAPH` sufficiency routing."

## Slide 07 — Building Knowledge Graph: Hybrid Extraction (~45s)
> "Because no Homeopathy KG existed, we built our Knowledge Graph from *Materia Medica Pura* and `21` PubMed abstracts. Pure 120B LLM extraction failed schema validation on **21% (`24`)** of archaic Materia Medica chunks. Our **Hybrid** extractor proposes verbatim-grounded candidates using rules, audits them with the LLM, and falls back to rules — matching `80.8%` keynote recall with **0 failed chunks** and weighting every symptom by VAD affect and proving grade $W$."

## Slide 08 — Convergent & Divergent Graph Search (~40s)
> "At query time, `PersonaQueryEngine` turns free-text or partial symptom inputs into multi-class subgraphs like *Arnica montana* (`59` nodes, `93` edges). A single threshold $\theta$ switches between **Convergent** mode ($\theta=0.45\cdot\text{maxScore}$, `1.43 ms`, `2.56x` faster than linear scan) and **Divergent** mode ($\theta=0.18\cdot\text{maxScore}$, `1.95 ms`) with every edge tied to a verbatim quote."

## Slide 09 — Main Results: `Bank v3` Accuracy & Safety (~40s)
> "On the 700-episode `Bank v3` benchmark, adding `HyST` hard slots cuts unsafe actions **26-fold** (`31.2%` $\rightarrow$ `1.2%`). `SHMF` auto-relaxation recovers the `18.3%` empty queries to reach `75.6%` clean accuracy (`75.0%` in `TIDE`). End-to-end Bridge latency is `3.91 ms` (`p95 5.41 ms`), with all `38/38` unit and integration tests passing."

## Slide 10 — Anytime TIDE: Less Reading Beats Full Scan (~30s)
> "Under urgent anytime mode on `Bank v3`, reading just **`2.2 / 25.4`** top-activated candidates at `B=3` reaches **`71.9%`** accuracy — beating a full read (`64.8%`) while holding unsafe errors at `1.2%`."

## Slide 11 — Study A (MMKG): Indexing vs. MPCS Plot (~40s)
> "We then benchmarked directly on our `953` Materia Medica KG occurrences (`300` clean + `300` noisy queries). Hash gates (`dlCBF`, `Cuckoo`) reach `95.0%` clean accuracy in `0.02 ms`, but drop to `45.7%` under 1-feature noise. `Slot Inverted Bitset` leads noisy robustness at `77.7%` in `48.9 KB`, and `NSW Graph` cuts candidate scans by `71%`."

## Slide 12 — Study A (MMKG): Indexing Metrics (~25s)
> "This table gives the complete Study A breakdown. Notice unconstrained `TIDE` (`Urgent=False`) scores `42.3%` here — which our Study B1 ablation explains on the next slide."

## Slide 13 — Study B1 (MMKG): TIDE Ablation Plot (~45s)
> "Study B1 ablates all 8 components of `TIDE` on MMKG. Removing `HyST` hard slots collapses accuracy to `12.7%` and slows execution `5.1x` (`34.48 ms`). Conversely, setting `Urgent B=3` jumps clean accuracy **`+48.3 pp` to `91.0%`** (`78.7%` noisy) because `_head_a` in `kerl_layer.py` sets `k=1` instead of averaging `k=5` candidates diluted by frequent `observe` records."

## Slide 14 — Study B1 (MMKG): Ablation Metrics (~20s)
> "Across all 8 variants, `Urgent B=3` also cuts unsafe errors from `26.0%` down to `11.7%`, confirming both hard slots and bounded top-candidate reading are critical."

## Slide 15 — Studies B2 & B3: Budgets & Routing (~35s)
> "Study B2 confirms monotonic scaling across `B=3..Full`: `91.0%` at `B=3` (`2.8 / 67.3` read) down to `44.0%` on Full Read, with `B=10` minimizing unsafe errors at `3.9%`. In Study B3, `19.7%` route `DIRECT` and `80.3%` escalate to `SUBGRAPH`, with `0%` ungrounded failures."

## Slide 16 — Study C (MMKG): `PersonaEngine` Plot (~40s)
> "Study C ablates `PersonaQueryEngine` across `40` clinical queries $\times$ `10` runs (`1,106` nodes) with the calibrated thresholds ($\theta_{\text{conf}}=0.45$, $\theta_{\text{expl}}=0.18$). Lowering $\theta_{\text{conf}}$ from `0.70` to `0.45` restores Confident mode from `0%` to **`60.0%` Top-1 and `75.0%` Top-3** (`96.3%` pruned) because 1-hop `0.58` transfer now passes. Meanwhile, `hops=1` matches `hops=2` (`60%` Top-1, `82.5%` Top-3) while saving `36%` latency (`11.80 ms` vs. `18.32 ms`), and $\mu_v=1.0$ peaks at **`80%` / `90%`** by removing Grade-3 hub bias."

## Slide 17 — Study C (MMKG): Persona Ablation Table (~20s)
> "This table details all 8 variants (`400` calls each). Confident mode ($\theta=0.45$) keeps `41.0` nodes (`96.3%` pruned) with `36.3` cohesive internal edges, while Exploratory ($\theta=0.18$) traverses 2-hop modalities (`589.8` nodes, `1,042.5` edges, `82.5%` Top-3). Uniform `w_uv=1.0` matches Exploratory identically because `min(1.0, edge_w)` in `persona_engine.py` clamps all `[1.0, 2.95]` MMKG edges to `1.0`."

## Slide 18 — Achieved vs. Remaining & Next Steps (~35s)
> "In summary: we built a cognitive model of convergent and divergent thinking with reflection and self-correction, created a cited `1,106`-node Homeopathy Knowledge Graph where no dataset existed, and validated `26x` safer `Bank v3` retrieval, `91.0%` MMKG `B=3` accuracy, `60%/75%` Confident and `60%/82.5%` Exploratory recall (`80%/90%` peak with $\mu_v=1.0$) in `3.91 ms`. Key limitations to address next are global top-$k$ voting, degree and edge-weight normalization, UMLS/SNOMED CT linking, and learned bridge thresholds. Thank you."

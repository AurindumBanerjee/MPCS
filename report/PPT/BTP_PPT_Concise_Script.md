# Oral Presentation Script: MPCS & LocalKG (`BTP_PPT_Concise.pptx`)

**Target Duration:** ~10-12 minutes (`12` slides, ~45-60 seconds per slide)  
**Presenters:** Aurindum Banerjee (`B23CS1006`) & Lokesh Motwani (`B23CS1033`)

---

## Slide 01 — Title Slide (~25s)
> "Good morning/afternoon everyone. I am [Aurindum / Lokesh], presenting our B.Tech Project **'Cognitive Model of Convergent and Divergent Thinking'** — implemented as **MPCS & LocalKG** under Dr. Romi Banerjee. Our goal was to design a model of contemplation following cognitive theories for AI reflection and self-correction, and apply it to a self-built Homeopathy Knowledge Graph."

---

## Slide 02 — Problem & Motivation: Cognitive Contemplation & The Homeopathy Data Gap (~60s)
> "To explain **why** this work was done: our project starts from **cognitive modeling of human contemplation**.  
> Originally, we modeled how humans understand sensory percepts (`vision`, `audio`, `touch`, `smell`) and alternate between **convergent thinking** (focusing quickly onto one safe action) and **divergent thinking** (exploring related associations), enabling reflection and self-correction via reward feedback and threshold adaptation ($\tau$).  
> We then expanded this cognitive model to a real knowledge system — **Homeopathy** — asking how experiences and symptoms map to remedies, and how **partial symptom inputs** can surface related symptoms, remedies, and conditions.  
> Here we hit a concrete barrier: **no accessible, structured Homeopathy dataset existed**. So we built **LocalKG** ourselves from *Materia Medica Pura* (primary text) and cited *PubMed* abstracts (secondary texts), and added filtering and constraint layers to speed up querying on graph data."

---

## Slide 03 — Existing Market Landscape (~50s)
> "Looking at existing market tools shows why this gap mattered:  
> - **Left (`Homeopathy UK`)**: Static condition articles — click 'Burns' or 'Anxiety' and read fixed prose, with zero multi-symptom reasoning or evidence linking.  
> - **Center (`Open Materia Medica`)**: Uses local token matching against memory, which handles simple queries like *'violent throbbing headache with high fever'* (*Belladonna*).  
> - **Right**: Adding just one more detail — *', dilated pupils'* — returns **'No remedy matches'**, even though *'dilated pupils'* appears verbatim in *Belladonna*'s own portrait!  
> No existing tool supported partial-input divergent subgraph exploration or convergent safety filtering over an open Homeopathy KG."

---

## Slide 04 — Our Solution: Convergent + Divergent Cognitive Architecture (~60s)
> "Here is how our final `TIDE` + `LocalKG` architecture solves that gap:  
> - **MPCS Agent (`Model/`)**: Replicates sensory-percept understanding, checks 7 fast reflex rules, then runs our two-stage retrieval — **Indexing & Filtering** (`dlCBF, HMGI, HyST, SHMF`) followed by **Scoring, Spreading & Routing** (`KERL, TIDE`) — with online reflection and self-correction ($\tau$, reward).  
> - **LocalKG (`LocalKG/`)**: Our self-built `1,106`-node, `2,024`-edge typed KG from *Materia Medica Pura* + 21 PubMed texts, queried via **Convergent** (`Confident`, $\theta=0.70$) and **Divergent** (`Exploratory`, $\theta=0.35$) personas.  
> - **TIDE + LocalKG Support Tool (`Bridge`)**: Takes free-text or partial symptom queries, applies a Stage-1 emergency guard, and builds multi-class subgraphs (`Medicine`, `Symptom`, `Modality`, `Condition`) in ~4 ms."

---

## Slide 05 — MPCS 6-Layer Retrieval Cascade (~55s)
> "Why does our retrieval cascade beat flat KNN or BM25 on safety and latency? Because it separates **filtering** from **scoring and routing**:  
> - In the **blue Indexing & Filtering stage**, `dlCBF` checks exact repeats in `9.2 KB` / `0.02 ms`, `HMGI` restricts scanning to relevant modality partitions, `HyST` drops any memory violating hard safety slots (like thermal state), and `SHMF` automatically relaxes soft slots when strict filtering empties the candidate set.  
> - The **filtered candidate set** then enters the **brown Scoring, Spreading & Routing stage**: `KERL` applies a near-miss guard, and `TIDE` runs 3-hop affect-weighted spreading activation under an anytime budget `B` (or `2 ms` cutoff) and emits a sufficiency route (`DIRECT`, `SUBGRAPH`, or `UNGROUNDED`)."

---

## Slide 06 — LocalKG Ingestion & Dual-Persona Query Engine (~55s)
> "On the knowledge graph side, two engineering choices matter most:  
> 1. **Hybrid Extraction (`Table 6.2`)**: Pure rule-based parsing gets `61.5%` recall on our 26-keynote gold set; pure 120B LLM extraction gets `80.8%` recall but fails schema validation on **21% (`24`)** of archaic chunks. Our **Hybrid** pipeline uses rules to propose verbatim-grounded candidates and the model to audit them with automatic rule fallback — matching `80.8%` recall with **0 failed batches** and higher F1 (`10.1%`).  
> 2. **Dual-Persona Query Engine**: Using an inverted token index and 2-hop threshold pruning $\theta$, **Confident mode ($\theta=0.70$)** runs in `1.43 ms` (`2.56x` faster than `3.65 ms` linear scan), while **Exploratory mode ($\theta=0.35$)** widens differential subgraphs in `1.95 ms` (`1.87x` speedup)."

---

## Slide 07 — Main Results: Bank v3 & Integration (~55s)
> "These are our headline results on the 700-episode `Bank v3` benchmark and end-to-end bridge:  
> - **Safety (`26x` improvement)**: `HyST` hard slots cut unsafe actions from `31.2%` (`G4`) down to **`1.2%`**.  
> - **Coverage**: `SHMF` relaxation recovers the `18.3%` empty queries, lifting clean accuracy to **`75.6%`** (`G9 TIDE`: `75.0%`, `1.7%` unsafe).  
> - **Anytime TIDE**: Under urgent mode, reading just **`2.2 / 25.4`** top-activated candidates at `B=3` reaches **`71.9%`** accuracy — beating a full read (`64.8%`) while holding unsafe errors at `1.2%`.  
> - **Integration**: Mean bridge latency is **`3.91 ms`** (`p95 5.41 ms`), with all `33` unit tests and `5` bridge integration tests passing."

---

## Slide 08 — Comparison Study A: Extended Perceptual Indexing on MMKG (~60s)
> "We then built an evaluation directly on **`953` real Materia Medica KG clinical occurrences** (`300` clean and `300` noisy queries). Study A compares 7 indexing structures against MPCS generations:  
> - **Exact hash gates (`dlCBF` & `Cuckoo Filter`)** hit **`95.0%` clean accuracy** in **`0.020-0.025 ms`**, but collapse to **`45.7%`** under 1-feature noise because hashes only recognize exact repeats.  
> - **Slot Inverted Bitset** achieves the best noisy robustness (**`77.7%`**) in just `48.9 KB`.  
> - **NSW Proximity Graph** achieves `84.7%` clean / `75.3%` noisy accuracy while cutting candidate scans by **`71%`** (`278.9 / 953`).  
> - Notice that unconstrained `G9 TIDE` (`Urgent=False`) scores `42.3%` on MMKG — which Study B1 explains."

---

## Slide 09 — Ablation Study B1: MPCS `G9 TIDE` Components on MMKG (~60s)
> "Study B1 ablates all 8 components of `G9 TIDE` on MMKG and reveals two decisive mechanisms:  
> 1. **Hard Slots are critical**: Removing HyST hard slots (`Soft Only`) collapses accuracy to **`12.7%`** and slows latency `5.1x` (`34.48 ms`).  
> 2. **Why `Urgent B=3` jumps `+48.3 pp`**: Bounding reads to `B=3` lifts clean accuracy from **`42.7%` to `91.0%`** and noisy accuracy from **`42.0%` to `78.7%`**, while cutting unsafe error from `26.0%` to `11.7%`.  
> Inspecting `kerl_layer.py` (`_head_a`) explains why: when `Urgent=False`, `_head_a` averages rewards over up to `k=5` candidates per action, allowing frequent `observe` records (`495/953` in MMKG) to outvote exact high-reward matches. `Urgent=True` sets `k=1`."

---

## Slide 10 — Studies B2 & B3: Anytime Scaling & Sufficiency Routing (~50s)
> "Study B2 confirms this monotonicity across all six budgets (`B=3, 5, 10, 20, 50, Full`): because `953` occurrences map into `452` percepts, each bucket averages `67.3` candidates.  
> - At `B=3` (`2.8 / 67.3` read), clean accuracy peaks at **`91.0%`** (`5.67 ms`).  
> - At `B=10`, unsafe error hits its lowest point at **`3.9%`** (`79.0%` accuracy).  
> - On **Study B3** (`Urgent=False`), **`19.7%`** of queries route `DIRECT`, **`80.3%`** escalate to `SUBGRAPH` where multi-symptom evidence helps, and `UNGROUNDED` stays at **`0.0%`**."

---

## Slide 11 — Ablation Study C: `PersonaQueryEngine` on `1,106`-Node MMKG (~60s)
> "Study C ablates `PersonaQueryEngine` over `40` clinical queries $\times$ `10` runs (`400` calls per variant):  
> - **Spreading activation is essential**: `hops=0` gets `0%` remedy recall.  
> - **1-hop sufficiency**: `hops=1` matches `hops=2` identically at `60.0%` Top-1 / `80.0%` Top-3 while cutting latency ~13% (`9.84 ms` vs `11.30 ms`), because MMKG is a bipartite `Remedy -> Symptom` star graph.  
> - **Polychrest hub bias**: Setting $\mu_v=1.0$ (removing VAD arousal & proving-grade amplification) boosts Top-1 recall from **`60.0%` to `80.0%`** (`32/40`) and Top-3 to **`90.0%`** (`36/40`) by preventing Grade-3 polychrest remedies from dominating.  
> - **Edge-weight saturation**: `w_uv=1.0` matches Full Exploratory because `min(1.0, edge_w)` in `persona_engine.py` clamps all `[1.0, 2.95]` MMKG links to `1.0`."

---

## Slide 12 — What We Achieved, What Remains & Future Work (~45s)
> "To close honestly:  
> - **Achieved**: A deterministic, `3.91 ms` neuro-symbolic pipeline, `26x` unsafe-action reduction on `Bank v3`, `91.0%` MMKG TIDE accuracy at `B=3`, `80%` Top-1 / `90%` Top-3 MMKG remedy recall (`mu_v=1.0`), hybrid extraction with zero failed batches, and `38/38` passing tests.  
> - **Not Yet Achieved / Limitations**: Unconstrained `_head_a` `k=5` averaging dilutes dense MMKG buckets (`42.7%`), `min(1.0, edge_w)` saturates edge weights, percept mapping uses regex rules rather than real sensors, our extraction gold set has `26` keynotes, and the historical text is a research testbed rather than clinical evidence.  
> - **Next Steps**: Global top-$k$ voting inside HyST/TIDE, degree and `w_uv / w_max` normalization, UMLS/SNOMED CT linking, and learning bridge thresholds from clinician feedback. Thank you."

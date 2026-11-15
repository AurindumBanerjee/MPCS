# LocalKG — Homeopathic Materia Medica Knowledge Graph (local Ollama edition)

A fully local port of `extraction_KRAG/homeopathy-kg`. Same pipeline, schema, validators,
Neo4j graph and Chroma index — but every LLM call goes to **Ollama** instead of the xAI/Grok API.

| Original (Grok)                              | LocalKG (Ollama)                                                   |
|----------------------------------------------|--------------------------------------------------------------------|
| `XAIClient` (OpenAI SDK, `json_object`)      | `OllamaClient` (`/api/chat`, JSON-**schema** constrained `format`) |
| Several API keys rotated to avoid timeouts   | `OLLAMA_HOSTS` round-robin + failover across Ollama servers/GPUs   |
| Sequential extraction                         | `--workers N` parallel extraction, thread-safe                     |
| Restart from scratch on crash                | **Resumable**: rerun with the same `--run-id` skips done chunks    |
| Hash "embeddings"                            | Ollama embeddings (`nomic-embed-text`), hash fallback              |
| BM25 empty at query time                     | BM25 rebuilt from persisted Chroma store                           |
| Remedy nodes without names, raw rel targets  | Names set; relationship targets resolved via abbreviation resolver |

## Setup

```powershell
conda activate TogAI
pip install -e . pytest          # from LocalKG/
copy .env.example .env

ollama pull qwen2.5:7b-instruct  # extraction model (any instruct model works)
ollama pull nomic-embed-text     # embedding model
docker compose up -d             # Neo4j (optional; Chroma works without it)
lkg doctor
```

### Model choice
JSON-schema constrained decoding makes even small models produce valid output; quality of
symptom splitting scales with size. Suggested: `qwen2.5:7b-instruct` (8 GB VRAM),
`qwen2.5:14b-instruct` / `mistral-small` (16–24 GB), `llama3.1:8b`, `gemma3:12b`.
For reasoning models (`qwen3`, `deepseek-r1`) keep `OLLAMA_THINK=false`.

### Throughput (the local version of "multiple keys")
- **One GPU:** start Ollama with `OLLAMA_NUM_PARALLEL=4` and use `--workers 4`.
- **Several GPUs/machines:** run one `ollama serve` per GPU on different ports
  (`$env:CUDA_VISIBLE_DEVICES=1; $env:OLLAMA_HOST="127.0.0.1:11435"; ollama serve`) and set
  `OLLAMA_HOSTS=http://localhost:11434,http://localhost:11435`. Requests rotate round-robin;
  a timed-out/down host is skipped and the request retried on the next one.
- Results are cached in `data/llm_cache/` (keyed by model + prompt + schema + chunk).

## Run

End-to-end on the Hahnemann book in `docs/`:
```powershell
# pilot on 20 chunks first
lkg run "..\docs\Materia Medica Samuel Hahnemann.pdf" --limit 20 --workers 2
# full run (same command again resumes where it stopped)
lkg run "..\docs\Materia Medica Samuel Hahnemann.pdf" --workers 4
```

Step by step:
```powershell
lkg parse "..\docs\Materia Medica Samuel Hahnemann.pdf" --source-key hahnemann_materia_medica
lkg chunk data/parsed/hahnemann_materia_medica.jsonl --max-chars 3000
lkg extract data/chunks/chunks.jsonl --run-id hahn_qwen7b --workers 4 [--model llama3.1:8b] [--limit 20]
lkg load-neo4j data/extracted/hahn_qwen7b.jsonl
lkg load-chroma data/extracted/hahn_qwen7b.jsonl
lkg ask "burning stomach pain, restlessness, fear of death, worse at midnight"
lkg eval-extraction data/extracted/hahn_qwen7b.jsonl
```
Offline/no-model test: `lkg extract data/chunks/chunks.jsonl --mock`.

## Pipeline
```
PDF/HTML -> parse (bold/italic preserved) -> chunk (remedy x section)
  -> Ollama extraction (JSON schema, cache, round-robin hosts, parallel, resumable)
  -> validators (quote faithfulness, grounding, markup emphasis -> grade, direction check)
  -> Neo4j graph  +  Chroma (Ollama embeddings) & BM25 with RRF
  -> query tools + local agent (emergency guard, citations, disclaimer)
```

> [!NOTE]
> `parse_pdf.py` detects remedy headings as short fully-bold lines and section headings via
> `config/sections.yaml`. Check `data/parsed/*.jsonl` after parsing a new book and adjust
> `sections.yaml` aliases if remedies/sections are mis-split.

## Dual-Persona Query Engine (`persona_engine.py`)

LocalKG provides a standalone, sub-millisecond Dual-Persona Query Engine ([`src/lkg/query/persona_engine.py`](src/lkg/query/persona_engine.py)) implementing neuro-symbolic patch foraging over the 1,106-node / 2,024-link clinical knowledge graph.

### Architectural Optimizations
1. **$O(1)$ Inverted Token Index:** Precomputed at initialization across all node labels, quotes, and clinical sections (`self.inverted_index`), replacing linear full-graph scanning.
2. **Clinical Synonym Expansion:** Bridges archaic 19th-century materia medica rubrics to modern medical terminology (e.g., `headache` -> `cephalalgia`, `throbbing`; `injury` -> `trauma`, `jarring`, `blow`).
3. **Active-Frontier BFS Spreading Activation:** Propagates somatic energy ($A \in [0, 1]$) strictly across non-zero active candidate frontiers using pre-indexed adjacency maps (`self.adj`), eliminating redundant iterations over inactive links.
4. **Fast-Pruned Pydantic Construction:** Pre-filters ambient nodes below threshold before instantiating Pydantic `QueryNode` and `QueryEdge` objects, slashing schema validation overhead.

### Dual-Persona Threshold Gating
- **Confident Persona ($\theta_{\text{conf}} = 0.70$):** High-precision triage mode. Isolates verified keynote symptoms exceeding $70\%$ normalized activation, suppressing $>99\%$ of ambient graph noise.
- **Exploratory Persona ($\theta_{\text{expl}} = 0.35$):** Associative discovery mode. Returns confident core nodes plus exploratory expansion nodes ($0.35 \le \text{Score} < 0.70$), along with internal green subgraph edges and external dashed pink bridging vectors.

### Empirical Benchmarks
Reproducible via `LocalKG/experiments/benchmark_persona_engine.py`:
```powershell
python LocalKG\experiments\benchmark_persona_engine.py
```
| Engine Architecture | Mean Latency | p50 Latency | p95 Latency | Ambient Pruning |
| :--- | :---: | :---: | :---: | :---: |
| **Unoptimized Baseline (Linear)** | 12.75 ms | 11.40 ms | 23.21 ms | — |
| **Optimized Confident Persona** | **6.53 ms** | **5.59 ms** | **14.90 ms** | **99.7%** (3 core keynotes) |
| **Optimized Exploratory Persona** | **8.13 ms** | **6.30 ms** | **21.69 ms** | **96.2%** (42 active nodes) |

*(Raw algorithmic traversal without Pydantic schema serialization runs in **1.29 ms**).*

### Ablation & Extended Indexing Studies (Materia Medica KG)

Empirical evaluation across all 953 clinical occurrences (202 JSONL rows, 452 unique 4-channel percepts; 300 clean + 300 noisy queries with 77 safety-critical queries per split) and the 1,106-node / 2,024-link cleaned MMKG graph:

```powershell
python LocalKG/experiments/run_ablations_and_indexes.py
```

Outputs are saved to `docs/ablation_and_indexing_study.json` and `docs/ABLATION_AND_INDEXING_STUDY.md`.

- **Study A (7 Indexing Structures + MPCS B2, G4-G9 on MMKG):** `dlCBF Gate` (9.2 KB, 0.020 ms) and `Cuckoo Filter Gate` (35.1 KB, 0.025 ms) achieve **95.0%** clean accuracy (**100.0%** R@3, 10.4% unsafe) on exact repeats, dropping to 45.7% under perturbation. `Slot Inverted Bitset` leads noisy accuracy at **77.7%** (84.7% clean, 3.660 ms, 48.9 KB), ahead of `Exact KNN (Cosine)` (84.3% clean / 76.3% noisy, 8.505 ms) and `NSW Proximity Graph` (84.7% clean / 75.3% noisy, 2.651 ms, 278.9 scanned, 1,791.06 ms build). Among MPCS variants, `B2 Global Top-5` reaches 85.0% clean / 70.7% noisy, while full-read per-action voting limits `G4 Core`/`G6 HMGI` (10.0% clean, 46.8% unsafe), `G5 HyST`/`G7 SHMF` (44.0% clean, 11.7% unsafe; `G7 SHMF` at 4.946 ms vs `G5 HyST` at 10.651 ms), and `G8 KERL`/`G9 TIDE` (42.3% clean / 42.3% noisy, 26.0% unsafe).
- **Study B (MPCS G9 TIDE Ablation, Anytime Budgets & Sufficiency Routing):** `Full G9 TIDE (Urgent=False)` (`affect_enabled=True`) scores 42.7% clean / 42.0% noisy (26.0% unsafe; 6.81 / 6.57 ms), whereas enabling `Urgent B=3` resolves full-read reward dilution in `_head_a` to jump to **91.0%** clean / **78.7%** noisy (11.7% / 14.3% unsafe; 5.67 ms clean / 5.39 ms noisy budget latency), and `B=10` cuts clean unsafe errors to **3.9%** (79.0% clean acc). Anytime accuracy sweeps monotonically from `B=3` (91.0% clean / 78.7% noisy) to `Full` (44.0% clean / 43.7% noisy). Removing `HyST Hard Slots (Soft Only)` collapses accuracy to 12.7% (34.48 ms clean / 35.58 ms noisy), while `w/o KERL Near-Miss Guard` and `w/o SHMF Auto-Relaxation` stay invariant (42.7% clean / 42.0% noisy) on dense 4-channel percepts. Sufficiency routing (`Urgent=False`) routes 19.7% (59) to `DIRECT` (44.1% acc), 80.3% (241) to `SUBGRAPH` (42.3% clean / 41.5% noisy), and 0.0% to `UNGROUNDED`.
- **Study C (`PersonaQueryEngine` 8-Variant Ablation, 40 queries x 10 runs = 400 calls/variant, deterministic `(-score, label.lower())` tie-breaker):** `Full Exploratory Persona (theta=0.35)` retains 86.2 nodes (92.2% pruned, 108.4 internal edges) with **24/40 (60.0%)** Remedy Top-1 and **32/40 (80.0%)** Top-3 at 11.299 ms (0.59x vs the 6.661 ms raw-ID linear scan baseline due to Pydantic `QueryNode`/`QueryEdge` serialization, whereas compact `Full Confident Persona` runs in 4.387 ms / 1.52x and linear scan drops Top-1 to 19/40 = 47.5%). `Full Confident Persona (theta=0.70)` and `hops=0` yield 0/40 hits because 1-hop attenuation (`0.58 < 0.70`) keeps symptom-seeded `Medicine` nodes below `theta_conf`; `hops=1` matches `Full Exploratory` (86.2 nodes, 60.0% Top-1, 80.0% Top-3) at 9.844 ms (0.68x) because `0.58^2 = 0.3364 < 0.35`; `w/o Edge-Weight Modulation` is invariant because MMKG link weights in `[1.0, 2.95]` saturate `min(1.0, edge_w)`; `w/o Clinical Synonym Expansion` maintains 24/40 (60.0%) Top-1 and lifts Top-3 to 34/40 (85.0%); and `w/o VAD Arousal & Grade Multiplier (mu_v=1.0)` raises Top-1 to **32/40 (80.0%)** and Top-3 to **36/40 (90.0%)** at the cost of admitting 22.7% more ambient nodes (105.8 vs 86.2).

## MPCS-LocalRAG Neuro-Symbolic Cognitive Bridge & Studio

The integrated bridge connects the **LocalKG Dual-Persona Spreading Activation Engine** with the **MPCS Generation 9 (TIDE) Perception-Decision Core**:
- **Location:** [Model/experimental/09_localrag_bridge/](../Model/experimental/09_localrag_bridge/)
- **One-Click Launcher:** [serve_localrag_mpcs_ui.py](../serve_localrag_mpcs_ui.py)

### Running the Integrated Studio
`powershell
python serve_localrag_mpcs_ui.py --port 8090
`
*Spins up the integrated REST backend at http://localhost:8090 and auto-opens the modern dark-theme clinical studio.*

### 4-Stage Cognitive Pipeline
1. **Safety & dlCBF Reflex Triage:** BLAKE2b hash lookup (\,\mu\text{s}$), reflex red-flag emergency pattern detector (ALERT / WITHDRAW), and HyST hard-slot invariant check (.2\%$ safety violation rate).
2. **LocalRAG Graph Traversal:** Dual-Persona spreading activation, candidate remedy ranking, keynote identification, and $>95\%$ peripheral noise suppression.
3. **MPCS Cognitive Fusion:** Maps retrieved clinical evidence to 3D Somatic Affect (, A, D$), evaluates cognitive action (APPROACH, OBSERVE, WITHDRAW, ALERT), and executes TIDE sufficiency routing (DIRECT vs. SUBGRAPH).
4. **Grounded Provenance & Interactive Subgraph:** Live 60 FPS HTML5 Canvas visualizer rendering active remedy hubs, symptom star-clusters, and green/pink bridging links with verbatim Materia Medica proving citations.
5. **Continuous Clinical Reinforcement:** Real-time feedback buttons (Validate +1.0 / Off-Target 0.0 / Teach Expert Action) that dynamically adapt MPCS episodic memory and action thresholds.

## Principles
Archival research tool only: no medical advice, no dosage/potency, emergency guard on queries,
every Occurrence carries its verbatim evidence quote and source reference.

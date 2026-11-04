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

## Principles
Archival research tool only: no medical advice, no dosage/potency, emergency guard on queries,
every Occurrence carries its verbatim evidence quote and source reference.

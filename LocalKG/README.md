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

## Principles
Archival research tool only: no medical advice, no dosage/potency, emergency guard on queries,
every Occurrence carries its verbatim evidence quote and source reference.

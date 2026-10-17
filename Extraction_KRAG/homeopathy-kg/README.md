# Homeopathic Materia Medica Knowledge Graph (v1)

A clean, provenance-linked knowledge graph and hybrid semantic index built from digitized classical homeopathic materia medica literature. Designed to support research and downstream affective/cognitive modeling.

---

## 1. Principles & Non-Goals

- **Strict Provenance**: Every symptom statement is preserved as an individual `Occurrence` node with exact evidence quote, section, and source reference.
- **No Medical Advice**: This system is strictly an archival research and text-retrieval engine. It does not provide medical advice, diagnosis, or treatment recommendations.
- **No Dosage / Potency**: Instructions regarding dose, potency, and preparation are completely stripped and forbidden.
- **Emergency Guard**: Queries describing acute or life-threatening symptoms (e.g. severe chest pain, difficulty breathing, suicidal intent) trigger an immediate emergency alert advising professional medical care.

---

## 2. Architecture & Pipeline

```
Raw Sources (.html, .pdf)
         │
         ▼ (Stage 0: Style-preserving Parser)
data/parsed/<source>.jsonl (**bold**, _italic_, CAPS markup)
         │
         ▼ (Stage 1: Chunker)
data/chunks/chunks.jsonl (chunk = remedy × section)
         │
         ▼ (Stage 2: LLM Extraction + Disk Cache)
Pydantic ChunkExtraction (Symptoms, Modalities, Relationships)
         │
         ▼ (Stage 3: Validation)
Validators (Quote faithfulness, Grounding, Direction check, Markup override)
         │
         ▼ (Stage 4: Entity Resolution)
Canonical mapping & Merge Proposals (data/extracted/merge_proposals.jsonl)
         │
         ├──────────────────────────┐
         ▼                          ▼
Stage 5: Neo4j Graph        Stage 6: ChromaDB Semantic Store
(Constraints, Nodes, Edges) (Hybrid RRF Semantic + BM25)
         │                          │
         └─────────────┬────────────┘
                       ▼
             Stage 7: Query Layer
   (find_remedies, semantic_search, get_remedy)
                       │
                       ▼
             Single-LLM Agent (CLI `hkg ask`)
```

---

## 3. Quickstart

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (or standard venv)
- Docker & Docker Compose (for Neo4j)

### Environment Setup
```bash
# 1. Create and activate virtual environment
uv venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate # Linux/macOS

# 2. Install dependencies and CLI
uv pip install -e . pytest

# 3. Configure environment
cp .env.example .env
# Edit .env to set XAI_API_KEY (optional for mock testing)
```

### Start Services
```bash
docker compose up -d
```

### Run Diagnostics
```bash
hkg doctor
```

---

## 4. Pipeline CLI Commands

### 1. Parse Raw Source
```bash
hkg parse data/raw/boericke.html --source-key boericke_pocket_manual
```

### 2. Generate Section Chunks
```bash
hkg chunk data/parsed/boericke_pocket_manual.jsonl
```

### 3. Extract & Validate
```bash
hkg extract data/chunks/chunks.jsonl --run-id run_pilot_01
```

### 4. Load Graph (Neo4j)
```bash
hkg load-neo4j data/extracted/run_pilot_01.jsonl
```

### 5. Index Vectors (ChromaDB)
```bash
hkg load-chroma data/extracted/run_pilot_01.jsonl
```

### 6. Query the Agent
```bash
hkg ask "burning stomach pain, restlessness, fear of death, worse at midnight"
```

### 7. Run Gold Set Evaluation
```bash
hkg eval-extraction data/extracted/run_pilot_01.jsonl
```

---

## 5. Running Tests

Run the full suite of unit and integration tests:
```bash
pytest -v
```
Tests cover:
- HTML parser markup preservation
- Section-level chunker and stable ID generation
- Quote faithfulness, symptom grounding, and direction checks
- Typographic emphasis override (markup in text strictly wins)
- Remedy abbreviation & seed modality resolution
- Rule prohibiting auto-merging of mental-state phrases in v1
- Deterministic repertorization scoring (coverage first, then grade)
- Emergency symptom guard and safety disclaimers

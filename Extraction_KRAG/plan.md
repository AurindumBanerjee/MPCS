# Project Plan: Homeopathic Materia Medica Knowledge Graph (v1)

> Handover document for an AI coding agent (Antigravity). Work milestone by milestone, in order. Do not skip ahead. After each milestone, run its acceptance checks and summarize what changed before starting the next.
>
> This plan **replaces** the earlier Ayurveda plan (archived as `plan_ayurveda_v1_archived.md`). The infrastructure is the same; the schema, parsing, and extraction rules are different.

---

## 1. Goal

Build a **provenance-linked knowledge graph** from digitized classical homeopathic materia medica texts. The graph will later feed a larger **cognitive model** (out of scope here), so it must be clean, versioned, auditable, and extensible.

Homeopathic materia medica is a good fit for the affective/cognitive goal: each remedy has a **Mind** section full of emotional and mental states, tied to physical symptoms and to **modalities** (what makes it worse or better).

**Deliverables for v1**
1. An ingestion pipeline: source text → chunks → LLM extraction → validation → entity resolution → Neo4j + ChromaDB.
2. A queryable graph (Neo4j) and semantic index (ChromaDB), linked by shared IDs.
3. A thin query layer: **one LLM + three tools** (no multi-agent routing).
4. A small gold set and a repeatable evaluation harness (basic version in v1; deeper evaluation later).

## 2. Non-goals (explicitly out of scope for v1)

- No Valence/Arousal or any cognitive-psychology mapping. Only **store raw affect phrases** with an empty slot for later categorization.
- No multi-agent orchestration.
- No Ayurveda or other traditions.
- **No dosage, potency, or preparation information.** The prompt must tell the model to ignore "Dose" lines. The query layer must never output dosing.
- No diagnosis or treatment recommendation. This is a text-retrieval and research tool over historical materia medica. It does not assert that any remedy works.
- No UI. CLI + Python API only.

## 3. Decisions already made

| Topic | Decision |
|---|---|
| Tradition | Homeopathy only for v1 |
| LLM provider | xAI Grok API, **free tier / free credits**, via OpenAI-compatible endpoint (`https://api.x.ai/v1`) |
| Default model | Configurable via env (`LLM_MODEL`). Start with a cheap "fast" Grok model (e.g. `grok-4-1-fast-non-reasoning`). **Verify availability in the xAI console first**; models get retired. |
| Graph DB | Neo4j 5.x (Docker) |
| Vector DB | ChromaDB (persistent local client) |
| Evidence modelling | **Occurrence nodes** (one symptom statement = one node) |
| Edge semantics | Neutral `HAS_OCCURRENCE`, not "TREATS". Texts record what provings and clinical use reported; do not encode efficacy claims |
| Provenance | Stored on Occurrence nodes (source, location, chunk id, quote, run id, confidence) |
| Orchestration | Single LLM + 3 tools |
| Evaluation | Plan now, detailed work later |

**Free-tier constraints (design for them):**
- Rate limits are unpublished and may change. Build a rate limiter, retry with exponential backoff on HTTP 429/5xx.
- Pipeline must be **resumable** and **idempotent**: cache every raw LLM response on disk, keyed by `hash(model + prompt_version + schema_version + chunk_text)`. Never re-call the API for a cached chunk.
- Prompts may be used for training under data-sharing programs. Only use **public-domain / permissively licensed** texts. Record the license of each source in `sources.yaml`.
- Keep the LLM client behind an interface (`LLMClient`) so provider/model can be swapped without touching pipeline code.

## 4. Tech stack

- Python 3.11+, `uv` or `pip` + `venv`
- `pydantic` v2 (schemas + structured-output validation)
- `openai` SDK pointed at the xAI base URL
- `neo4j` official Python driver
- `chromadb`
- `sentence-transformers` for local embeddings (configurable; default an English model such as `BAAI/bge-base-en-v1.5`, since these texts are archaic English)
- `rank_bm25` or SQLite FTS5 for the keyword side of hybrid search (Latin remedy names and exact rubric terms need exact matching)
- `pymupdf` for PDF extraction **with font/style info** (bold/italic); Tesseract OCR only as a fallback
- `beautifulsoup4` for HTML sources
- `rapidfuzz` for fuzzy name matching
- `tenacity` for retries, `typer` for CLI, `pytest` for tests, `ruff` for lint
- Docker Compose for Neo4j

## 5. Repository layout

```
homeopathy-kg/
├── plan.md
├── README.md
├── pyproject.toml
├── docker-compose.yml            # neo4j
├── .env.example                  # XAI_API_KEY, LLM_MODEL, NEO4J_*, EMBED_MODEL
├── config/
│   ├── sources.yaml              # texts: license, path, format, emphasis->grade mapping
│   ├── remedy_abbreviations.yaml # seed: "Ars." -> "Arsenicum album", etc.
│   ├── sections.yaml             # section vocabulary (Mind, Head, Stomach, ...)
│   └── modality_seed.yaml        # seed modality vocabulary
├── data/
│   ├── raw/                      # source files (gitignored if large)
│   ├── parsed/                   # parsed text with markup + page refs
│   ├── chunks/                   # chunks.jsonl
│   ├── llm_cache/                # raw LLM responses (jsonl, keyed by hash)
│   ├── extracted/                # validated extraction JSON per run
│   └── gold/                     # hand-annotated gold set (see §11)
├── src/hkg/
│   ├── config.py
│   ├── llm/                      # LLMClient interface, xai_client.py, ratelimit, cache
│   ├── ingest/                   # parse_pdf.py, parse_html.py, ocr.py, chunker.py
│   ├── schema/                   # extraction.py (Pydantic), graph.py (labels/rel names)
│   ├── extract/                  # prompts/, extractor.py, validators.py
│   ├── resolve/                  # normalize.py, aliases.py, merge_proposals.py
│   ├── load/                     # neo4j_loader.py, chroma_loader.py, constraints.cypher
│   ├── query/                    # tools.py (3 tools), scoring.py, agent.py
│   ├── eval/                     # metrics.py, run_eval.py
│   └── cli.py
└── tests/
```

## 6. How these source texts are structured

This drives parsing and chunking, so read it before M1.

- **Boericke-style manuals:** one entry per remedy, with a name heading, a short introduction (source, common name, constitution/type), then **sections by body region** (Mind, Head, Eyes, Ears, Nose, Face, Mouth, Throat, Stomach, Abdomen, Stool, Urine, Chest, Back, Extremities, Sleep, Fever, Skin, ...), then **Modalities** (worse/better), then **Relationship** (compare, antidotes, complementary, etc.), then a Dose line.
- **Typographic emphasis carries meaning.** Bold, italic, and CAPS mark more characteristic ("keynote") symptoms. This is a signal of importance and should become a **grade** (1-3). The exact mapping differs per book; define it per source in `sources.yaml`.
- **Kent-style lectures** are prose, not sectioned lists. They are richer on mental states but harder to chunk.
- Symptoms are often given as **comma-separated lists inside one sentence** ("Anxiety, restlessness, fear of death."). Each item should become its own Occurrence.
- Modalities are compact and easy to get backwards ("worse at night; better from warmth"). Direction errors are the most damaging extraction mistake.

**Recommended order:** start with a Boericke-style manual (consistent structure, strong typography, compact). Add a Kent-style text later for richer Mind content. Candidate sources: Boericke's *Pocket Manual of Homoeopathic Materia Medica*, Kent's *Lectures on Homoeopathic Materia Medica*, Clarke's *Dictionary of Practical Materia Medica*, Hering's *Guiding Symptoms*, Allen's *Encyclopedia of Pure Materia Medica*. Older editions are generally public domain, but **verify the license of the specific file you use** (modern reprints, annotated editions, and some websites' versions may be copyrighted). Possible hosts: Project Gutenberg, archive.org, homeoint.org. Prefer sources with a text layer or HTML that keep bold/italic.

**Pilot scope:** 20 well-known remedies (for example Arsenicum album, Pulsatilla, Nux vomica, Sulphur, Calcarea carbonica, Lycopodium, Phosphorus, Belladonna, Bryonia, Rhus toxicodendron, Aconitum, Ignatia, Natrum muriaticum, Sepia, Silicea, Chamomilla, Gelsemium, Lachesis, Staphysagria, Thuja), mixing plant/mineral/animal sources. Expand only after M4.

## 7. Graph data model

### 7.1 Principles
- **Canonical entities** (Remedy, Symptom, Modality, ...) are merged by stable ID.
- **Occurrences are never merged.** One Occurrence = one symptom statement from one passage.
- Every node/edge created by the pipeline carries `run_id` and `schema_version`.
- Raw strings are always preserved next to canonical labels (needed later by the cognitive model).
- `Symptom.kind` for a chunk comes **deterministically from the section** (Mind → `mental`). The LLM only proposes a kind when the section is unknown (prose sources).

### 7.2 Nodes

| Label | Key properties |
|---|---|
| `Remedy` | `id`, `name`, `abbreviations[]`, `latin_name?`, `common_names[]`, `kingdom` (plant/mineral/animal/nosode/other/unknown) |
| `Alias` | `text` → `[:ALIAS_OF]->(Remedy)` |
| `Symptom` | `id`, `label` (canonical), `kind` (mental/physical/general/clinical/unknown), `raw_phrases[]`, `affect_category` (**empty slot reserved for later cognitive mapping**) |
| `BodyRegion` | `id`, `label` (seeded from `sections.yaml`) |
| `Sensation` | `id`, `label` (burning, stitching, throbbing, ...) |
| `Modality` | `id`, `label`, `factor_type` (time/temperature/weather/position/motion/touch_pressure/food_drink/eating/sleep/emotion/company/season/other) |
| `Occurrence` | `id`, `kind` (symptom/general_modality/constitution/other), `symptom_raw`, `section`, `emphasis`, `grade` (1-3), `laterality`, `evidence_type`, `evidence_quote`, `source_ref`, `chunk_id`, `run_id`, `confidence`, `schema_version` |
| `Chunk` | `id`, `text`, `page?`, `section?`, `source_id` |
| `Source` | `id`, `title`, `author?`, `edition?`, `license`, `language` |

### 7.3 Relationships

```
(Remedy)-[:HAS_OCCURRENCE]->(Occurrence)
(Occurrence)-[:EXPRESSES]->(Symptom)
(Occurrence)-[:LOCATED_IN]->(BodyRegion)
(Occurrence)-[:HAS_SENSATION]->(Sensation)
(Occurrence)-[:AGGRAVATED_BY {raw}]->(Modality)
(Occurrence)-[:AMELIORATED_BY {raw}]->(Modality)
(Occurrence)-[:ACCOMPANIED_BY]->(Symptom)              # concomitants
(Remedy)-[:RELATES_TO {type, chunk_ids[]}]->(Remedy)   # compare|antidote|complementary|follows_well|inimical|similar
(Occurrence)-[:FROM_CHUNK]->(Chunk)-[:IN_SOURCE]->(Source)
(Alias)-[:ALIAS_OF]->(Remedy)
```

- General remedy-level modalities (the "Modalities" section) are Occurrences with `kind=general_modality` and no `EXPRESSES` edge, only `AGGRAVATED_BY` / `AMELIORATED_BY`.
- Direction lives on the relationship type (`AGGRAVATED_BY` vs `AMELIORATED_BY`) so queries cannot confuse it.

### 7.4 Constraints and indexes (`constraints.cypher`)

```cypher
CREATE CONSTRAINT remedy_id IF NOT EXISTS FOR (n:Remedy) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT symptom_id IF NOT EXISTS FOR (n:Symptom) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT region_id IF NOT EXISTS FOR (n:BodyRegion) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT sensation_id IF NOT EXISTS FOR (n:Sensation) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT modality_id IF NOT EXISTS FOR (n:Modality) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT occurrence_id IF NOT EXISTS FOR (n:Occurrence) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT source_id IF NOT EXISTS FOR (n:Source) REQUIRE n.id IS UNIQUE;
CREATE INDEX alias_text IF NOT EXISTS FOR (n:Alias) ON (n.text);
CREATE INDEX symptom_label IF NOT EXISTS FOR (n:Symptom) ON (n.label);
CREATE INDEX symptom_kind IF NOT EXISTS FOR (n:Symptom) ON (n.kind);
CREATE INDEX occurrence_run IF NOT EXISTS FOR (n:Occurrence) ON (n.run_id);
```

### 7.5 ID scheme
- Remedy: `remedy:<slug>` of the canonical full name, e.g. `remedy:arsenicum_album`.
- Symptom / Modality / Sensation / BodyRegion: `<label>:<slug>`.
- Occurrence: `occ:<sha1(chunk_id + normalized_symptom_raw + normalized_quote)[:16]>`. The symptom text is included because one list sentence can yield several Occurrences sharing a quote. IDs are deterministic so reloads are idempotent.
- Chunk: `chunk:<source_id>:<ordinal>`.

## 8. Extraction schema (Pydantic, structured outputs)

Implement in `src/hkg/schema/extraction.py`. The LLM returns one `ChunkExtraction` per chunk. Each chunk is one **remedy section** (for example, "Arsenicum album: Stomach"), and the remedy name and section are given in the prompt header (they come from the parser, not from the LLM).

```python
class ModalityOut(BaseModel):
    direction: Literal["worse", "better"]
    factor_raw: str                          # verbatim, e.g. "after midnight", "warm drinks"
    factor_type: Literal["time","temperature","weather","position","motion",
                         "touch_pressure","food_drink","eating","sleep",
                         "emotion","company","season","other"]

class SymptomOut(BaseModel):
    symptom_raw: str                         # one discrete symptom, verbatim wording
    location_raw: list[str] = []
    sensation_raw: list[str] = []
    laterality: Literal["right","left","both","alternating","unspecified"] = "unspecified"
    modalities: list[ModalityOut] = []
    concomitants_raw: list[str] = []
    emphasis: Literal["plain","italic","bold","caps"] = "plain"   # from markup in the chunk
    evidence_type: Literal["proving","clinical","toxicology","unspecified"] = "unspecified"
    symptom_kind_hint: Literal["mental","physical","general","clinical","unknown"] = "unknown"
    evidence_quote: str                      # verbatim substring of chunk, <= 400 chars
    confidence: float                        # 0..1

class GeneralModalityOut(BaseModel):
    modality: ModalityOut
    emphasis: Literal["plain","italic","bold","caps"] = "plain"
    evidence_quote: str
    confidence: float

class RelationshipOut(BaseModel):
    type: Literal["compare","antidote","complementary","follows_well","inimical","similar"]
    remedy_raw: str
    note_raw: str | None = None

class RemedyIntroOut(BaseModel):          # only populated for intro chunks
    latin_name: str | None = None
    common_names: list[str] = []
    abbreviations: list[str] = []
    kingdom: Literal["plant","mineral","animal","nosode","other","unknown"] = "unknown"
    constitution_note: str | None = None
    evidence_quote: str | None = None

class ChunkExtraction(BaseModel):
    symptoms: list[SymptomOut] = []
    general_modalities: list[GeneralModalityOut] = []
    relationships: list[RelationshipOut] = []
    intro: RemedyIntroOut | None = None
    notes: str | None = None               # ambiguity, for human review
```

**Prompt rules (`extract/prompts/extract_v1.md`, versioned):**
- Extract only what the chunk explicitly states. No outside knowledge, no inference, no "textbook" completion.
- Split comma/semicolon lists into **separate symptoms**. Keep the original wording; do not modernize or translate mental-state phrases.
- Modalities: `<` or "worse", "aggravated", "agg." mean **worse**; `>` or "better", "ameliorated", "relieved", "amel." mean **better**. Copy the factor wording exactly. If the direction is unclear, omit it and note it in `notes`.
- The chunk text contains lightweight markup for emphasis (`**bold**`, `_italic_`, `CAPS`). Report the emphasis of the symptom's own words, not of surrounding text.
- `evidence_quote` must be copied verbatim from the chunk.
- **Ignore dose/potency/preparation lines entirely.**
- If unsure, omit the item and add a line to `notes`.
- Return only JSON matching the schema.

## 9. Pipeline stages

### Stage 0: Parse (style-preserving)
- PDF → text with `pymupdf` using span-level font flags; HTML → text with `beautifulsoup4`. Convert emphasis to lightweight markup (`**bold**`, `_italic_`, CAPS kept as-is).
- Detect remedy headings, section headings (using `sections.yaml`), and page numbers.
- OCR fallback only for pages without a text layer (note: OCR usually loses bold/italic; flag those pages).
- Output: `data/parsed/<source_id>.jsonl` with `{remedy_name, section, page, marked_text}`.

### Stage 1: Chunk
- **Chunk = one remedy × one section.** The remedy name and section go into the chunk header so the LLM has context. Split very long sections (>~1500 tokens) at sentence/semicolon boundaries and repeat the header.
- For prose texts (Kent-style): paragraph chunks of ~800-1500 tokens, with the remedy from the lecture heading, and `section=unknown`.
- Do **not** send whole books or whole remedies in one request. Section-level chunks are cheaper and more accurate.
- Output: `data/chunks/chunks.jsonl` with stable `chunk_id`, `source_id`, `remedy_name`, `section`, `page`.

### Stage 2: Extract
- `LLMClient.extract(chunk) -> ChunkExtraction` using structured outputs / JSON-schema mode. Verify the exact structured-output API in the current xAI docs; if schema mode is unavailable on the chosen model, fall back to JSON mode + Pydantic validation + one repair retry.
- Rate limiting (token bucket), exponential backoff, disk cache (§3).
- Log per chunk: tokens in/out, latency, retries, validation pass/fail.

### Stage 3: Validate
Automated checks (`extract/validators.py`):
1. Pydantic schema validity.
2. **Quote faithfulness:** `evidence_quote` must be a substring of the chunk after whitespace/case/markup-insensitive normalization. Failing items are dropped and logged to `data/extracted/rejected.jsonl`.
3. **Symptom grounding:** `symptom_raw` must appear in (or closely match, via fuzzy ratio) the quote.
4. **Direction sanity check:** if a modality has `direction=worse` but the quote contains only "better"-type cues (`>`, "better", "relieved", "amel.") and no "worse"-type cues (or vice versa), flag it for review. Direction errors are the highest-impact failure.
5. **Emphasis check:** compare the LLM's `emphasis` with the markup actually present around the symptom text in the chunk; on mismatch, **the markup wins** (deterministic) and the item is logged.
6. Grade is computed deterministically from emphasis using the per-source mapping in `sources.yaml` (default plain=1, italic=2, bold=3, caps=3).
7. Confidence below 0.5 → flagged, still stored with low confidence.
8. `kind` for each Symptom comes from the chunk's section (Mind → mental, etc.); use `symptom_kind_hint` only for `section=unknown`.

### Stage 4: Normalize and resolve entities
- **Remedies:** normalize case, punctuation, abbreviations ("Ars. alb." → `Arsenicum album`) using `remedy_abbreviations.yaml`, exact alias match, then fuzzy match. Heading-derived names are authoritative; names inside relationship lines (Compare, Antidotes) need resolution.
- **Symptoms:** keep every raw phrase. Propose a canonical label by light normalization (case, punctuation, plural/word-order variants, archaic spelling via a small synonym list such as "lachrymation"/"tearing", "coryza"/"nasal discharge"). Mid-confidence merges go to `data/extracted/merge_proposals.jsonl` for human review. **Do not semantically merge mental-state phrases automatically in v1** (for example, do not merge "fear of death" with "anxiety about dying").
- **Modalities:** map `factor_raw` to canonical modality IDs using `modality_seed.yaml` plus fuzzy match (e.g. "cold air", "open air" stay separate unless explicitly mapped). Unmapped factors become new Modality nodes tagged `needs_review`.
- **Never auto-merge below the high threshold.** Everything ambiguous goes to the proposals file.

### Stage 5: Load Neo4j
- Run `constraints.cypher` first.
- Use `MERGE` on canonical IDs; deterministic Occurrence IDs make reruns idempotent.
- Batch writes (UNWIND, ~500 rows per transaction).
- Every created node/edge gets `run_id`, `schema_version`.

### Stage 6: Index ChromaDB
- Collection `occurrences`: document = `evidence_quote` plus a short preamble `"{remedy} | {section} | {symptom_raw}"`; metadata = `occurrence_id`, `remedy_id`, `symptom_id`, `section`, `kind`, `grade`, `source_id`, `chunk_id`.
- Collection `chunks`: full chunk text, metadata `chunk_id`, `source_id`, `remedy_id`, `section`, `page`.
- Hybrid search: BM25/FTS over the same documents; merge results with reciprocal rank fusion. Latin names and exact rubric words need the keyword side.
- Optional (flag, off by default): embed an LLM-generated plain-English paraphrase of each quote as a separate field, to help with archaic wording.

## 10. Query layer (single LLM + 3 tools)

Implement as plain Python functions first (usable without any LLM), then expose them to the model.

1. **`find_remedies(symptoms: list[SymptomQuery], modalities: list[ModalityQuery] = [], limit: int = 10)`**
   Graph query plus **deterministic repertorization scoring** (`query/scoring.py`).
   - `SymptomQuery`: `{text, kind?, location?}`; `ModalityQuery`: `{direction: worse|better, factor, attaches_to?: symptom_index | "general"}`.
   - Input terms are resolved to canonical Symptom/Modality IDs (alias + fuzzy; unresolved terms are reported back, not silently dropped).
   - Score per remedy = for each query symptom matched, add the highest occurrence `grade` (1-3) (weighted by confidence); add a bonus when a requested modality matches on the same occurrence or in the remedy's general modalities; track **coverage** (how many of the query symptoms are matched). Rank by coverage first, then score.
   - Returns per-remedy breakdowns: which query symptom matched which occurrence, with `occurrence_id`, grade, quote, and `source_ref`. Remedies that match only one symptom must be visibly marked as partial.
2. **`semantic_search(text: str, filters: dict = {}, k: int = 10)`**
   Hybrid search over `occurrences` (and optionally `chunks`), with filters like `section`, `kind`, `remedy`. Returns passages with occurrence IDs, remedy, source ref.
3. **`get_remedy(id_or_name: str)`**
   Full profile: intro/constitution note, occurrences grouped by section, general modalities, relationships (compare/antidote/complementary), aliases, provenance. **Never returns dose/potency fields** (none are stored).

**Rules**
- **No free-form Cypher by the model.** Tools take parameters; Cypher is fixed and parameterized. The Neo4j user used at query time should be read-only.
- Ranking is code, not LLM.
- `agent.py`: single model, tool-calling loop, **max 4 iterations**, then a final answer.
- System prompt requirements:
  - Answer only from tool results; every claim must cite an `occurrence_id` and source ref.
  - State when evidence is missing or only partial.
  - Describe results as "what the historical text lists", not as proof that a remedy works.
  - No dosage, potency, or treatment advice; no diagnosis.
  - Include a brief note that homeopathy's clinical efficacy is not established by controlled evidence, and that results reflect historical texts, not medical guidance.
  - If the query describes possible emergency symptoms (for example chest pain, severe abdominal pain, difficulty breathing, thoughts of suicide, severe bleeding), do not answer with remedies; advise seeking urgent medical care.

## 11. Evaluation plan (basic now, deeper later)

1. **Gold set:** fully annotate 8 remedies (mix of plant/mineral/animal, with long and short entries) in `data/gold/` using the same schema. Reviewed by someone who knows the materia medica. Frozen and versioned.
2. **Extraction metrics:** precision/recall/F1 for symptoms (after list-splitting), modalities, relationships, and sections.
3. **Direction accuracy:** share of modalities with correct worse/better direction. This should be near-perfect; track it separately.
4. **List-splitting accuracy:** are comma-separated lists split into the right number of items?
5. **Emphasis/grade accuracy:** does the computed grade match the typography? (Deterministic checks; report mismatches.)
6. **Provenance faithfulness:** automated substring check (Stage 3) plus manual sampling that the quote supports the symptom.
7. **Entity resolution:** accuracy of remedy abbreviation/alias resolution and count of unresolved names; symptom merge-proposal precision on a sample.
8. **Competency questions:** 30-50 graph questions with expected answers, for example: "Which remedies list fear of death under Mind?", "Which remedies have burning pains that are worse after midnight?", "Which remedies are listed as antidotes to Nux vomica?", "What are Pulsatilla's Mind symptoms and their modalities?"
9. **Sanity checks against well-known keynotes:** for a few classic remedies, the graph should contain well-documented keynote symptoms from the source text. Missing ones indicate extraction gaps.
10. **Retrieval:** recall@k of hybrid search vs. a plain BM25 baseline, on rephrased-in-modern-language queries.
11. **Expert spot-check:** a reviewer familiar with the materia medica checks ~100 random occurrences.
12. **Regression rule:** rerun the gold set whenever the prompt, model, or schema changes. Use it to compare the free-tier model against alternatives.

## 12. Milestones and acceptance criteria

**M0: Setup**
- Repo scaffold, Docker Compose for Neo4j, `.env.example`, config loader, lint/test wiring.
- ✅ `docker compose up` works; `hkg doctor` confirms Neo4j, Chroma, and the xAI API (one tiny test call) are reachable and prints the resolved model name.

**M1: Source acquisition, parsing, chunking**
- Choose one Boericke-style source (see §6), fill `sources.yaml` (license, format, emphasis→grade mapping), implement Stage 0-1.
- ✅ Parsed output preserves bold/italic markup; remedy and section headings correctly detected on 20 random chunks; page refs present; chunk = remedy × section.

**M2: Extraction with cache and validators**
- Implement `LLMClient`, rate limiter, cache, Stage 2-3.
- ✅ Run on 50 chunks across at least 5 remedies; report schema-validity rate, quote-faithfulness rate, direction-check flags; rerun makes **zero** API calls (cache hit); a mid-run crash can be resumed.

**M3: Gold set (small)**
- Hand-annotate 8 remedies in `data/gold/`.
- ✅ `hkg eval extraction` reports metrics from §11 items 2-6.

**M4: Resolve and load (pilot of 20 remedies)**
- Stage 4-6 on the pilot remedies.
- ✅ Full load into Neo4j and Chroma; rerun is idempotent (node/edge counts unchanged); merge-proposals file generated; a test verifies every Chroma `occurrence_id` exists in Neo4j and vice versa.

**M5: Tools and thin agent**
- Implement the 3 tools, `scoring.py`, CLI `hkg ask "..."`, single-LLM loop.
- ✅ 10 hand-written competency questions answered with citations; tools work standalone without the LLM; the example query "burning stomach pain, restlessness, fear of death, worse at midnight" returns a ranked list with per-symptom evidence and a visible coverage indicator; emergency-symptom guard works; no free-form Cypher anywhere in code.

**M6: Evaluation harness (basic)**
- Wire up §11 so metrics can be rerun on every prompt/model/schema change.
- ✅ One command reproduces the report; results stored with `run_id`.

## 13. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Free tier limits unclear or removed | Cache, resume, backoff, swappable `LLMClient`; verify in console in M0 |
| Source text loses bold/italic (OCR, bad PDF) | Prefer text-layer or HTML sources; flag affected pages; default `emphasis=plain` and record `grade_unreliable=true` |
| Worse/better direction swapped | Direction is encoded in relationship type; sanity check in Stage 3; separate direction-accuracy metric |
| Comma lists not split correctly | Explicit prompt rule, list-splitting metric, quote-based IDs that keep items distinct |
| Remedy names/abbreviations ambiguous | Seeded abbreviation table, heading names authoritative, fuzzy match with human-reviewed proposals |
| Archaic terms ("coryza", "lachrymation") hurt retrieval | Preserve raw phrases; small synonym list; hybrid search; optional paraphrase embedding |
| Over-merging mental-state phrases | No automatic semantic merging of mental symptoms in v1; proposals only |
| Provings vs. clinical statements blurred | `evidence_type` field; default `unspecified` rather than guessing |
| Misuse as medical advice; unproven efficacy | No dose data stored; disclaimers; emergency guard; answers framed as "what the text lists" |
| Neo4j/Chroma drift | Shared deterministic IDs; Chroma metadata carries Neo4j IDs; idempotent loaders; consistency-check command |
| Copyright | Verify license per file; record in `sources.yaml`; do not commit raw texts |

## 14. Instructions for the coding agent

- Follow the milestones in order; stop and report after each one with: what was built, test results, and deviations from this plan.
- **Ask before assuming** on open items (which exact source file, exact model name, structured-output API details). Do not invent API parameters; check the current xAI docs.
- Never commit secrets or raw copyrighted texts. Keep `.env` out of git.
- Write tests for: parser (markup preservation), chunker, validators (quote faithfulness, direction check, emphasis override), ID generation/idempotency, cache behavior, scoring, and each query tool.
- Keep prompts and schemas **versioned** (`extract_v1`, `schema_version`); never edit a released version in place.
- Prefer small, readable modules over frameworks. No LangChain/LlamaIndex unless there is a specific, stated need.
- Do not add dosing, potency, or treatment-recommendation features, even if asked by later prompts, without explicit written approval from the project owner.

## 15. Future work (after v1, not now)

- Map `Symptom.raw_phrases` (especially Mind symptoms) to cognitive/affective frameworks. This is the purpose of the empty `affect_category` slot.
- Add Kent-style prose texts, Hering, Clarke; add a hierarchical rubric tree for mental symptoms.
- Link to external ontologies (for example MeSH or SNOMED for physical conditions) where it makes sense.
- Native Neo4j vector index to replace ChromaDB if a single store becomes preferable.
- Larger evaluation, inter-annotator agreement, and an expert review workflow.
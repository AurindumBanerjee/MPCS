"""
Smoke test: verifies API connectivity and runs a mini end-to-end pipeline
(parse → chunk → extract) on a small slice of the Materia Medica PDF.

Run:
    conda run -n et_hack python tests/test_pipeline_smoke.py
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

# ── 0. Bootstrap ──────────────────────────────────────────────────────────────
# Ensure src is importable
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from hkg.config import DATA_DIR, settings  # noqa: E402
from hkg.llm.groq_client import GroqClient   # noqa: E402

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
SEP = "=" * 60


def banner(title: str) -> None:
    print(f"\n{SEP}\n  {title}\n{SEP}")


# ── 1. API Health Check ──────────────────────────────────────────────────────
def test_api_health() -> bool:
    banner("Step 1 / 4: Groq API Health Check")
    client = GroqClient()
    result = client.health_check()
    status = result.get("status")
    print(f"  Status     : {status}")
    print(f"  Model      : {result.get('model')}")
    print(f"  Base URL   : {result.get('base_url')}")
    if status == "ok":
        models = result.get("available_models", [])
        print(f"  Top models : {models}")
        print(f"  {PASS} API key is valid and the endpoint is reachable.")
        return True
    else:
        print(f"  Error      : {result.get('error', result.get('message'))}")
        print(f"  {FAIL} API health check failed.")
        return False


# ── 2. Parse a few pages from the PDF ─────────────────────────────────────────
def test_parse_pdf() -> Path | None:
    banner("Step 2 / 4: PDF Parse (first 10 pages)")
    pdf_path = DATA_DIR / "Materia_medica.pdf"
    if not pdf_path.exists():
        print(f"  {FAIL} PDF not found at {pdf_path}")
        return None

    print(f"  PDF        : {pdf_path}  ({pdf_path.stat().st_size / 1e6:.1f} MB)")

    try:
        import fitz  # PyMuPDF
    except ImportError:
        print(f"  {FAIL} pymupdf not installed")
        return None

    from hkg.ingest.parse_pdf import extract_page_spans_with_markup
    from hkg.config import get_sections_config
    from hkg.schema.graph import make_source_id
    import re

    sections_cfg = get_sections_config()
    section_map: dict[str, str] = {}
    for canon, data in sections_cfg.items():
        section_map[canon.lower()] = data.get("canonical", canon)
        for alias in data.get("aliases", []):
            section_map[alias.lower()] = data.get("canonical", canon)

    source_key = "boericke_smoke_test"
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    # Parse pages 10-20 (more likely to contain remedy entries)
    start_page = min(10, total_pages - 1)
    end_page = min(start_page + 10, total_pages)
    print(f"  Total pages: {total_pages}")
    print(f"  Parsing    : pages {start_page+1} to {end_page}")

    records = []
    current_remedy = "Introduction"
    current_section = "Intro"
    buffer = []

    def flush():
        nonlocal buffer
        content = "\n".join(buffer).strip()
        if content:
            records.append({
                "source_id": make_source_id(source_key),
                "remedy_name": current_remedy,
                "section": current_section,
                "page": current_page,
                "marked_text": content,
            })
        buffer = []

    for page_idx in range(start_page, end_page):
        page = doc[page_idx]
        current_page = page_idx + 1
        lines = extract_page_spans_with_markup(page)

        for line_item in lines:
            line = line_item["text"]
            plain_line = re.sub(r"[\*_]", "", line).strip()
            token = plain_line.rstrip(".:- ").strip().lower()
            if token in section_map:
                flush()
                current_section = section_map[token]
                continue
            if line.startswith("**") and line.endswith("**") and len(plain_line.split()) <= 4:
                flush()
                current_remedy = plain_line
                current_section = "Intro"
                continue
            buffer.append(line)

    flush()
    doc.close()

    # Write to a temp parsed file
    out_file = DATA_DIR / "parsed" / f"{source_key}.jsonl"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"  Records    : {len(records)}")
    if records:
        remedies = set(r["remedy_name"] for r in records)
        print(f"  Remedies   : {remedies}")
        print(f"  Output     : {out_file}")
        print(f"  {PASS} PDF parsed successfully.")
    else:
        print(f"  {WARN} No records extracted from these pages (may be TOC/intro).")
    return out_file


# ── 3. Chunk the parsed output ────────────────────────────────────────────────
def test_chunk(parsed_file: Path) -> Path | None:
    banner("Step 3 / 4: Chunking")
    from hkg.ingest.chunker import create_chunks_from_parsed

    chunks_file = DATA_DIR / "chunks" / "smoke_test_chunks.jsonl"
    out = create_chunks_from_parsed(parsed_file, output_path=chunks_file)
    
    # Count chunks
    with open(out, "r", encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f if line.strip()]

    print(f"  Chunks     : {len(chunks)}")
    if chunks:
        print(f"  First chunk: {chunks[0]['chunk_id']}")
        print(f"  Remedy     : {chunks[0]['remedy_name']}")
        print(f"  Section    : {chunks[0]['section']}")
        text_preview = chunks[0]["chunk_text"][:200].replace("\n", " ")
        print(f"  Preview    : {text_preview}...")
        print(f"  {PASS} Chunking succeeded.")
        return out
    else:
        print(f"  {FAIL} No chunks generated.")
        return None


# ── 4. LLM Extraction on 1 chunk ─────────────────────────────────────────────
def test_extraction(chunks_file: Path) -> bool:
    banner("Step 4 / 4: LLM Extraction (1 chunk)")
    
    # Read the first chunk
    with open(chunks_file, "r", encoding="utf-8") as f:
        first_chunk = None
        for line in f:
            if line.strip():
                first_chunk = json.loads(line)
                break

    if not first_chunk:
        print(f"  {FAIL} No chunk to extract from.")
        return False

    chunk_id = first_chunk["chunk_id"]
    remedy = first_chunk["remedy_name"]
    section = first_chunk["section"]
    chunk_text = first_chunk["chunk_text"]

    print(f"  Chunk ID   : {chunk_id}")
    print(f"  Remedy     : {remedy}")
    print(f"  Section    : {section}")
    print(f"  Text len   : {len(chunk_text)} chars")
    print(f"  Calling Groq ({settings.LLM_MODEL})...")

    client = GroqClient()
    try:
        extraction = client.extract(
            chunk_text=chunk_text,
            remedy_name=remedy,
            section=section,
        )
    except Exception as e:
        print(f"  {FAIL} Extraction error: {e}")
        return False

    # Print results
    print(f"\n  --- Extraction Results ---")
    print(f"  Symptoms        : {len(extraction.symptoms)}")
    print(f"  Gen. Modalities : {len(extraction.general_modalities)}")
    print(f"  Relationships   : {len(extraction.relationships)}")
    print(f"  Intro           : {'Yes' if extraction.intro else 'No'}")
    print(f"  Notes           : {extraction.notes or '(none)'}")

    if extraction.symptoms:
        print(f"\n  --- First 3 Symptoms ---")
        for i, sym in enumerate(extraction.symptoms[:3]):
            print(f"  [{i+1}] {sym.symptom_raw[:100]}")
            print(f"       kind={sym.symptom_kind_hint}, conf={sym.confidence}")
            if sym.modalities:
                for m in sym.modalities[:2]:
                    print(f"       mod: {m.direction} from '{m.factor_raw}' ({m.factor_type})")
            print(f"       quote: {sym.evidence_quote[:80]}...")

    if extraction.relationships:
        print(f"\n  --- Relationships ---")
        for rel in extraction.relationships[:3]:
            print(f"  {rel.type}: {rel.remedy_raw} — {rel.note_raw or ''}")

    # Save raw extraction JSON
    out_json = DATA_DIR / "extracted" / "smoke_test_extraction.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(extraction.model_dump(), f, indent=2, ensure_ascii=False)
    print(f"\n  Saved to   : {out_json}")
    print(f"  {PASS} LLM extraction succeeded and output is valid Pydantic schema.")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "🧪 HOMEOPATHY-KG PIPELINE SMOKE TEST".center(60))
    results: dict[str, bool] = {}

    # 1. API health check
    api_ok = test_api_health()
    results["API Health"] = api_ok
    if not api_ok:
        print(f"\n  ⚠️  API is not working. Stopping here.")
        print_summary(results)
        return

    # 2. PDF parse
    parsed_file = test_parse_pdf()
    results["PDF Parse"] = parsed_file is not None
    if not parsed_file:
        print_summary(results)
        return

    # 3. Chunking
    chunks_file = test_chunk(parsed_file)
    results["Chunking"] = chunks_file is not None
    if not chunks_file:
        print_summary(results)
        return

    # 4. LLM extraction
    results["LLM Extraction"] = test_extraction(chunks_file)

    print_summary(results)


def print_summary(results: dict[str, bool]):
    banner("SUMMARY")
    for step, ok in results.items():
        status = f"✅ {PASS}" if ok else f"❌ {FAIL}"
        print(f"  {status}  {step}")
    all_ok = all(results.values())
    if all_ok:
        print(f"\n  🎉 All pipeline stages passed! The setup is working correctly.")
    else:
        print(f"\n  ⚠️  Some stages failed. See details above.")
    print()


if __name__ == "__main__":
    main()

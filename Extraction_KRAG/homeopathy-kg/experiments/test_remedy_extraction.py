"""Test LLM extraction on an actual remedy chunk (not the intro)."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hkg.config import DATA_DIR, settings
from hkg.llm.xai_client import XAIClient

chunks_file = DATA_DIR / "chunks" / "smoke_test_chunks.jsonl"
with open(chunks_file) as f:
    chunks = [json.loads(l) for l in f if l.strip()]

# Find a non-intro chunk with a real remedy
remedy_chunk = None
for c in chunks:
    if c["remedy_name"] != "Introduction":
        remedy_chunk = c
        break

if not remedy_chunk:
    print("No remedy chunks found. Parsing more pages...")
    import fitz
    from hkg.ingest.parse_pdf import extract_page_spans_with_markup

    doc = fitz.open(str(DATA_DIR / "Materia_medica.pdf"))
    text_parts = []
    for i in range(15, 20):
        lines = extract_page_spans_with_markup(doc[i])
        text_parts.extend(l["text"] for l in lines)
    doc.close()
    sample = "\n".join(text_parts)[:2500]
    remedy_chunk = {
        "chunk_id": "test_remedy_chunk",
        "remedy_name": "Abrotanum",
        "section": "General",
        "chunk_text": f"### Abrotanum: General\n\n{sample}",
    }

print(f"Remedy : {remedy_chunk['remedy_name']}")
print(f"Section: {remedy_chunk['section']}")
print(f"Text   : {len(remedy_chunk['chunk_text'])} chars")
print(f"Model  : {settings.LLM_MODEL}")
print(f"URL    : {settings.XAI_BASE_URL}")
print()

client = XAIClient()
result = client.extract(
    chunk_text=remedy_chunk["chunk_text"],
    remedy_name=remedy_chunk["remedy_name"],
    section=remedy_chunk["section"],
)

print(f"Symptoms        : {len(result.symptoms)}")
print(f"Gen. Modalities : {len(result.general_modalities)}")
print(f"Relationships   : {len(result.relationships)}")
print(f"Intro           : {'Yes' if result.intro else 'No'}")
print(f"Notes           : {result.notes or '(none)'}")

if result.symptoms:
    print("\n--- Extracted Symptoms ---")
    for i, s in enumerate(result.symptoms[:5]):
        print(f"\n  [{i+1}] {s.symptom_raw[:120]}")
        print(f"      kind={s.symptom_kind_hint}, conf={s.confidence}, lat={s.laterality}")
        if s.modalities:
            for m in s.modalities:
                print(f"      MOD: {m.direction} from \"{m.factor_raw}\" ({m.factor_type})")
        print(f"      evidence: \"{s.evidence_quote[:100]}...\"")

if result.relationships:
    print("\n--- Relationships ---")
    for r in result.relationships[:5]:
        print(f"  {r.type}: {r.remedy_raw} — {r.note_raw or ''}")

if result.intro:
    print(f"\n--- Intro ---")
    print(f"  Latin: {result.intro.latin_name}")
    print(f"  Common: {result.intro.common_names}")
    print(f"  Kingdom: {result.intro.kingdom}")

print("\n✅ Remedy extraction test complete!")

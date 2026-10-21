"""Quick smoke test: extract sample chunks with the local Ollama model and generate an interactive KG.

Usage:  python experiments/smoke_ollama.py [model]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lkg.config import DATA_DIR, settings  # noqa: E402
from lkg.extract.extractor import ExtractionPipeline  # noqa: E402
from lkg.llm.ollama_client import OllamaClient  # noqa: E402
from lkg.viz.graph_viz import export_interactive_html  # noqa: E402

if len(sys.argv) > 1:
    settings.LLM_MODEL = sys.argv[1]

# Clear cache for this sample so prompt/schema updates are always tested live
SAMPLE_CHUNKS = [
    {
        "chunk_id": "chunk:smoke:1",
        "source_id": "source:boericke_pocket_manual",
        "remedy_name": "Aconitum Napellus",
        "section": "Mind",
        "page": 8,
        "chunk_text": (
            "### Aconitum Napellus: Mind\n\n"
            "**Great fear, anxiety, and worry** accompany every ailment, however trivial.\n"
            "_Fears death_, believes that he will soon die; predicts the day.\n"
            "Restlessness, tossing about. Worse in the evening and at night; better in open air."
        ),
    },
    {
        "chunk_id": "chunk:smoke:2",
        "source_id": "source:boericke_pocket_manual",
        "remedy_name": "Arsenicum Album",
        "section": "Mind",
        "page": 79,
        "chunk_text": (
            "### Arsenicum Album: Mind\n\n"
            "**Great anguish and restlessness.** Changes place continually. "
            "**Fear of death**, of being left alone. _Melancholy_, sad, tearful. "
            "Worse after midnight and from being alone."
        ),
    },
    {
        "chunk_id": "chunk:smoke:3",
        "source_id": "source:boericke_pocket_manual",
        "remedy_name": "Arsenicum Album",
        "section": "Stomach",
        "page": 80,
        "chunk_text": (
            "### Arsenicum Album: Stomach\n\n"
            "**Burning pains**, like coals of fire, relieved by heat and warm drinks. "
            "Asthma and dyspnea worse at midnight."
        ),
    },
]

client = OllamaClient()
print("Health:", json.dumps(client.health_check(), indent=2))

# Invalidate cached entries for the smoke chunks so we test the live v2 prompt/schema
for ch in SAMPLE_CHUNKS:
    key = client.cache.make_cache_key(
        model=client.model,
        prompt_version=settings.PROMPT_VERSION,
        schema_version=settings.SCHEMA_VERSION,
        chunk_text=ch["chunk_text"],
    )
    cache_file = client.cache._file_path(key)
    if cache_file.exists():
        cache_file.unlink()

pipeline = ExtractionPipeline(llm_client=client, run_id="smoke_v2")
if pipeline.extracted_file.exists():
    pipeline.extracted_file.unlink()

with open(pipeline.extracted_file, "w", encoding="utf-8") as out:
    for ch in SAMPLE_CHUNKS:
        res = pipeline.process_chunk(ch)
        out.write(json.dumps(res, ensure_ascii=False) + "\n")
        print(f"\n--- {ch['remedy_name']} ({ch['section']}) ---")
        for occ in res["occurrences"]:
            canon = occ.get("canonical_label") or occ.get("symptom_raw")
            w = occ.get("composite_weight", 1.0)
            dom = occ.get("cognitive_domain", "None")
            vad = occ.get("vad", {})
            mods = occ.get("modalities", [])
            conds = occ.get("clinical_conditions", [])
            print(
                f"  * [{occ['emphasis']}|G{occ['grade']}|W={w:.2f}] "
                f"{canon} (raw: '{occ['symptom_raw']}') "
                f"| Domain: {dom} | VAD: {vad} "
                f"| Modalities: {mods} | Conditions: {conds}"
            )

html_path = export_interactive_html(
    [pipeline.extracted_file],
    output_html=DATA_DIR / "extracted" / "smoke_v2_kg.html",
    title="Arsenicum Album & Aconitum Schema (LocalKG v2)",
)
print(f"\nStats: {pipeline.stats}")
print(f"Interactive KG HTML saved to: {html_path}")

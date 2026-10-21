"""Quick smoke test: extract one sample chunk with the local Ollama model.

Usage:  python experiments/smoke_ollama.py [model]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lkg.config import settings  # noqa: E402
from lkg.extract.validators import validate_chunk_extraction  # noqa: E402
from lkg.llm.ollama_client import OllamaClient  # noqa: E402

if len(sys.argv) > 1:
    settings.LLM_MODEL = sys.argv[1]

SAMPLE = """### Aconitum Napellus: Mind

**Great fear, anxiety, and worry** accompany every ailment, however trivial.
_Fears death_, believes that he will soon die; predicts the day.
Restlessness, tossing about. Worse in the evening and at night; better in open air."""

client = OllamaClient()
print("Health:", json.dumps(client.health_check(), indent=2))
ext = client.extract(SAMPLE, "Aconitum Napellus", "Mind")
print(json.dumps(ext.model_dump(), indent=2))
val = validate_chunk_extraction(ext, SAMPLE, "Aconitum Napellus", "Mind")
print(f"accepted={len(val.accepted_symptoms)} rejected={len(val.rejected_items)} flags={len(val.flags)}")

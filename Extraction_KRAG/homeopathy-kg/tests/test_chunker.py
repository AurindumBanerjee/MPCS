import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import tempfile
import json
from hkg.ingest.chunker import create_chunks_from_parsed, split_long_text


def test_split_long_text():
    short_text = "This is a brief symptom description."
    assert split_long_text(short_text, max_chars=100) == [short_text]

    long_text = "Sentence one. Sentence two. Sentence three. Sentence four."
    parts = split_long_text(long_text, max_chars=30)
    assert len(parts) > 1
    assert "".join(parts).replace(" ", "") == long_text.replace(" ", "")


def test_chunker_generates_stable_chunks():
    records = [
        {
            "source_id": "source:boericke",
            "remedy_name": "Pulsatilla",
            "section": "Mind",
            "page": 12,
            "marked_text": "**Weeps easily.** Timid, irresolute.",
        },
        {
            "source_id": "source:boericke",
            "remedy_name": "Pulsatilla",
            "section": "Stomach",
            "page": 13,
            "marked_text": "Thirstless with nearly all complaints. Dry mouth.",
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        in_file = Path(tmpdir) / "parsed.jsonl"
        with open(in_file, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        out_file = Path(tmpdir) / "chunks.jsonl"
        create_chunks_from_parsed(in_file, output_path=out_file)

        assert out_file.exists()
        chunks = [json.loads(l) for l in out_file.read_text(encoding="utf-8").splitlines() if l]
        assert len(chunks) == 2
        assert chunks[0]["chunk_id"] == "chunk:boericke:1"
        assert chunks[1]["chunk_id"] == "chunk:boericke:2"
        assert "### Pulsatilla: Mind" in chunks[0]["chunk_text"]
        assert "**Weeps easily.**" in chunks[0]["chunk_text"]

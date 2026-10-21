from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from lkg.config import DATA_DIR
from lkg.schema.graph import make_chunk_id


def split_long_text(text: str, max_chars: int = 4000) -> list[str]:
    """Split text into smaller parts at paragraph, sentence, or semicolon boundaries."""
    if len(text) <= max_chars:
        return [text]

    # Split by paragraphs first
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current_buf: list[str] = []
    current_len = 0

    for p in paragraphs:
        if current_len + len(p) + 2 <= max_chars:
            current_buf.append(p)
            current_len += len(p) + 2
        else:
            if current_buf:
                chunks.append("\n\n".join(current_buf))
                current_buf = []
                current_len = 0

            # If a single paragraph exceeds max_chars, split on sentence/semicolon
            if len(p) > max_chars:
                sentences = re.split(r"(?<=[.;])\s+", p)
                sub_buf: list[str] = []
                sub_len = 0
                for s in sentences:
                    if sub_len + len(s) + 1 <= max_chars:
                        sub_buf.append(s)
                        sub_len += len(s) + 1
                    else:
                        if sub_buf:
                            chunks.append(" ".join(sub_buf))
                            sub_buf = []
                            sub_len = 0
                        chunks.append(s)
                if sub_buf:
                    chunks.append(" ".join(sub_buf))
            else:
                current_buf.append(p)
                current_len = len(p)

    if current_buf:
        chunks.append("\n\n".join(current_buf))

    return [c.strip() for c in chunks if c.strip()]


def create_chunks_from_parsed(
    parsed_jsonl: Path,
    output_path: Path | None = None,
    max_chunk_chars: int = 4000,
) -> Path:
    """Create section-level chunks from parsed records.

    Each chunk contains:
    - Stable chunk_id: chunk:<source_id>:<ordinal>
    - remedy_name
    - section
    - page
    - chunk_text (with header: '### {remedy_name}: {section}\n\n{text}')
    """
    output_path = output_path or (DATA_DIR / "chunks" / "chunks.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    chunks: list[dict[str, Any]] = []
    ordinal = 1

    with open(parsed_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            source_id = rec.get("source_id", "source:unknown")
            remedy_name = rec.get("remedy_name", "Unknown").strip()
            section = rec.get("section", "General").strip()
            page = rec.get("page", 1)
            raw_marked = rec.get("marked_text", "").strip()

            if not raw_marked:
                continue

            sub_texts = split_long_text(raw_marked, max_chars=max_chunk_chars)
            for sub_text in sub_texts:
                chunk_id = make_chunk_id(source_id, ordinal)
                header = f"### {remedy_name}: {section}\n\n"
                full_chunk_text = header + sub_text

                chunks.append({
                    "chunk_id": chunk_id,
                    "source_id": source_id,
                    "remedy_name": remedy_name,
                    "section": section,
                    "page": page,
                    "chunk_text": full_chunk_text,
                })
                ordinal += 1

    with open(output_path, "w", encoding="utf-8") as out:
        for c in chunks:
            out.write(json.dumps(c, ensure_ascii=False) + "\n")

    return output_path

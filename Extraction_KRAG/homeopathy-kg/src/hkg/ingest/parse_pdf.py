from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from hkg.config import DATA_DIR, get_sections_config
from hkg.schema.graph import make_source_id


def extract_page_spans_with_markup(page: Any) -> list[dict[str, Any]]:
    """Extract text from a PyMuPDF page, inspecting font flags for bold/italic.

    PyMuPDF font flags:
    2: Italic
    16: Bold (or font name contains 'bold' / 'black')
    """
    text_page = page.get_text("dict")
    lines_output: list[dict[str, Any]] = []

    for block in text_page.get("blocks", []):
        if block.get("type") != 0:  # 0 is text block
            continue
        for line in block.get("lines", []):
            line_parts: list[str] = []
            is_line_heading = False
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text:
                    continue
                flags = span.get("flags", 0)
                font = span.get("font", "").lower()
                size = span.get("size", 10.0)

                is_bold = bool(flags & 16) or ("bold" in font) or ("black" in font)
                is_italic = bool(flags & 2) or ("italic" in font) or ("oblique" in font)

                clean_text = text.strip()
                if not clean_text:
                    line_parts.append(text)
                    continue

                if is_bold and is_italic:
                    line_parts.append(f"**_{clean_text}_** ")
                elif is_bold:
                    line_parts.append(f"**{clean_text}** ")
                elif is_italic:
                    line_parts.append(f"_{clean_text}_ ")
                else:
                    line_parts.append(text + " ")

            rendered_line = "".join(line_parts).strip()
            if rendered_line:
                lines_output.append({"text": rendered_line, "bbox": line.get("bbox")})

    return lines_output


def parse_pdf_source(
    pdf_path: Path,
    source_key: str = "boericke_pocket_manual",
    output_dir: Path | None = None,
) -> Path:
    """Parse a PDF materia medica with font/style markup.

    Outputs JSONL to data/parsed/<source_key>.jsonl
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("pymupdf is required for PDF parsing. Install with `uv pip install pymupdf`")

    output_dir = output_dir or (DATA_DIR / "parsed")
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{source_key}.jsonl"

    sections_cfg = get_sections_config()
    section_map: dict[str, str] = {}
    for canon, data in sections_cfg.items():
        section_map[canon.lower()] = data.get("canonical", canon)
        for alias in data.get("aliases", []):
            section_map[alias.lower()] = data.get("canonical", canon)

    doc = fitz.open(pdf_path)
    records: list[dict[str, Any]] = []

    current_remedy = "Introduction"
    current_section = "Intro"
    buffer: list[str] = []
    current_page = 1

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

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        current_page = page_idx + 1
        lines = extract_page_spans_with_markup(page)

        for line_item in lines:
            line = line_item["text"]
            plain_line = re.sub(r"[\*_]", "", line).strip()

            # Heading candidate (all caps or bold short line)
            token = plain_line.rstrip(".:-").strip().lower()
            if token in section_map:
                flush()
                current_section = section_map[token]
                continue

            # Remedy detection (e.g. bold heading or page header)
            if line.startswith("**") and line.endswith("**") and len(plain_line.split()) <= 4:
                # Remedy heading candidate
                flush()
                current_remedy = plain_line
                current_section = "Intro"
                continue

            buffer.append(line)

    flush()

    with open(out_file, "w", encoding="utf-8") as out:
        for r in records:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")

    return out_file

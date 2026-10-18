from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from bs4 import BeautifulSoup, NavigableString, Tag

from hkg.config import get_sections_config, get_sources_config, PROJECT_ROOT, DATA_DIR
from hkg.schema.graph import make_source_id


def extract_html_with_markup(element: Tag) -> str:
    """Recursively convert HTML DOM element into text with markdown emphasis (**bold**, _italic_)."""
    pieces: list[str] = []

    for child in element.children:
        if isinstance(child, NavigableString):
            text = str(child)
            pieces.append(text)
        elif isinstance(child, Tag):
            tag_name = child.name.lower()
            inner = extract_html_with_markup(child)
            if not inner:
                continue

            if tag_name in ("b", "strong"):
                pieces.append(f"**{inner.strip()}** ")
            elif tag_name in ("i", "em"):
                pieces.append(f"_{inner.strip()}_ ")
            elif tag_name in ("p", "div", "br", "tr", "li"):
                pieces.append(f"\n{inner}\n")
            elif tag_name in ("h1", "h2", "h3", "h4"):
                pieces.append(f"\n\n### {inner.strip()}\n\n")
            else:
                pieces.append(inner)

    res = "".join(pieces)
    # Clean up excessive blank lines and spaces
    res = re.sub(r"[ \t]+", " ", res)
    res = re.sub(r"\n\s*\n\s*\n+", "\n\n", res)
    return res.strip()


def parse_html_source(
    html_path: Path,
    source_key: str = "boericke_pocket_manual",
    output_dir: Path | None = None,
) -> Path:
    """Parse a Boericke-style HTML materia medica document into parsed section records.

    Outputs JSONL to data/parsed/<source_key>.jsonl
    """
    output_dir = output_dir or (DATA_DIR / "parsed")
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{source_key}.jsonl"

    sections_cfg = get_sections_config()
    # Build lookup of section name / alias -> canonical section
    section_map: dict[str, str] = {}
    for canon, data in sections_cfg.items():
        section_map[canon.lower()] = data.get("canonical", canon)
        for alias in data.get("aliases", []):
            section_map[alias.lower()] = data.get("canonical", canon)

    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    records: list[dict[str, Any]] = []

    # Detect remedies: either h1/h2 tags, or dedicated remedy articles/divs
    remedy_tags = soup.find_all(["h1", "h2", "h3"])
    if not remedy_tags:
        # Fallback: treat entire document as single or unstructured text
        text_marked = extract_html_with_markup(soup.body or soup)
        records.append({
            "source_id": make_source_id(source_key),
            "remedy_name": "Unknown",
            "section": "General",
            "page": 1,
            "marked_text": text_marked,
        })
    else:
        current_remedy = "Introduction"
        current_section = "Intro"
        current_page = 1
        buffer: list[str] = []

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

        # Iterate through paragraphs/headings in order
        elements = soup.find_all(["h1", "h2", "h3", "h4", "p", "div", "b", "strong"])
        for el in elements:
            text = el.get_text(strip=True)
            if not text:
                continue

            tag_name = el.name.lower()
            # Remedy heading detection: H1 or H2 with remedy name pattern
            if tag_name in ("h1", "h2"):
                flush()
                current_remedy = text
                current_section = "Intro"
                continue

            # Section heading detection: H3, H4, or strong/b at start of line
            clean_token = text.rstrip(".:-").strip().lower()
            if clean_token in section_map:
                flush()
                current_section = section_map[clean_token]
                continue

            marked = extract_html_with_markup(el)
            if marked:
                buffer.append(marked)

        flush()

    with open(out_file, "w", encoding="utf-8") as out:
        for r in records:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")

    return out_file

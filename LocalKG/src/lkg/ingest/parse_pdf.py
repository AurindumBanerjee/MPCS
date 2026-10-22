from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from lkg.config import DATA_DIR, get_remedy_abbreviations, get_sections_config
from lkg.schema.graph import make_source_id


# Exact page boundaries (0-indexed inclusive) for Hahnemann's Materia Medica Pura Vol. II
# (docs/Materia Medica Samuel Hahnemann.pdf, 742 pages)
HAHNEMANN_VOL2_RANGES: list[tuple[int, int, str]] = [
    (18, 49, "Aconitum napellus"),
    (50, 74, "Ambra grisea"),
    (75, 105, "Argentum metallicum"),
    (106, 129, "Arnica montana"),
    (130, 195, "Arsenicum album"),
    (196, 214, "Asarum europaeum"),
    (215, 272, "Belladonna"),
    (273, 315, "Bryonia alba"),
    (316, 330, "Camphora"),
    (331, 373, "Carbo vegetabilis"),
    (374, 401, "Carbo animalis"),
    (402, 431, "Chamomilla"),
    (432, 468, "Conium maculatum"),
    (469, 490, "Drosera rotundifolia"),
    (491, 518, "Ferrum metallicum"),
    (519, 563, "Hyoscyamus niger"),
    (564, 624, "Ignatia amara"),
    (625, 650, "Ipecacuanha"),
]

# OCR correction map for Boericke's Pocket Manual remedy headers
BOERICKE_OCR_REMEDY_FIXES: dict[str, str] = {
    "aruica": "Arnica montana",
    "arnica": "Arnica montana",
    "arnica montana": "Arnica montana",
    "belladonna": "Belladonna",
    "aconitum napellus": "Aconitum napellus",
    "aconitum": "Aconitum napellus",
    "arsenicum album": "Arsenicum album",
    "bryonia": "Bryonia alba",
    "bryonia alba": "Bryonia alba",
    "chamomilla": "Chamomilla",
    "gelsemium": "Gelsemium sempervirens",
    "hyoscyamus": "Hyoscyamus niger",
    "ignatia": "Ignatia amara",
    "lachesis": "Lachesis mutus",
    "lycopodium": "Lycopodium clavatum",
    "mercurius": "Mercurius solubilis",
    "natrum muriaticum": "Natrum muriaticum",
    "nux vomica": "Nux vomica",
    "phosphorus": "Phosphorus",
    "pulsatilla": "Pulsatilla nigricans",
    "rhus toxicodendron": "Rhus toxicodendron",
    "sepia": "Sepia officinalis",
    "silica": "Silicea",
    "silicea": "Silicea",
    "stramonium": "Stramonium",
    "sulphur": "Sulphur",
    "veratrum album": "Veratrum album",
}

# OCR fixes for Boericke inline section labels
BOERICKE_OCR_SECTION_FIXES: dict[str, str] = {
    "mind": "Mind",
    "head": "Head",
    "eyes": "Eyes",
    "ears": "Ears",
    "nose": "Nose",
    "ifose": "Nose",
    "face": "Face",
    "mouth": "Mouth",
    "throat": "Throat",
    "stomach": "Stomach",
    "abdomen": "Abdomen",
    "rectum": "Rectum",
    "stool": "Stool",
    "urine": "Urine",
    "urinary": "Urine",
    "male": "Male",
    "female": "Female",
    "respiratory": "Respiratory",
    "chest": "Chest",
    "heart": "Heart",
    "back": "Back",
    "extremities": "Extremities",
    "limbs": "Extremities",
    "skin": "Skin",
    "sleep": "Sleep",
    "fever": "Fever",
    "modalities": "Modalities",
    "relationship": "Relationship",
    "compare": "Relationship",
    "dose": "Dose",
    "pose": "Dose",
}


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
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text:
                    continue
                flags = span.get("flags", 0)
                font = span.get("font", "").lower()

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


def classify_hahnemann_section(paragraph: str) -> str:
    """Classify a Hahnemann proving paragraph into Mind/Affective vs anatomical region."""
    low = paragraph.lower()
    if any(
        w in low
        for w in (
            "anxiety", "fear", "delirium", "fright", "weep", "anger", "restless",
            "melancholy", "mood", "mind", "memory", "dream", "hallucination",
            "terror", "despair", "peevish", "obstinate", "quarrelsome", "sighing",
            "groaning", "ill-humour", "indifference", "mania", "rage", "frenzy",
        )
    ):
        return "Mind"
    if any(w in low for w in ("vertigo", "headache", "forehead", "temples", "occiput", "scalp", "brain")):
        return "Head"
    if any(w in low for w in ("pupil", "eyelid", "vision", "photophobia", "eye", "sight")):
        return "Eyes"
    if any(w in low for w in ("ear", "hearing", "tinnitus", "parotid")):
        return "Ears"
    if any(w in low for w in ("nose", "epistaxis", "sneezing", "coryza", "smell")):
        return "Nose"
    if any(w in low for w in ("face", "cheek", "lip", "jaw", "facial")):
        return "Face"
    if any(w in low for w in ("tooth", "teeth", "gum", "tongue", "saliva", "mouth", "palate", "taste")):
        return "Mouth"
    if any(w in low for w in ("throat", "swallowing", "pharynx", "tonsil", "uvula", "deglutition")):
        return "Throat"
    if any(w in low for w in ("appetite", "thirst", "nausea", "vomiting", "eructation", "hiccough", "stomach", "epigastri")):
        return "Stomach"
    if any(w in low for w in ("abdomen", "belly", "umbilic", "hypochondr", "flatulence", "colic", "groin")):
        return "Abdomen"
    if any(w in low for w in ("stool", "rectum", "anus", "diarrhoea", "constipation", "haemorrhoid")):
        return "Stool"
    if any(w in low for w in ("urine", "bladder", "urethra", "micturition")):
        return "Urine"
    if any(w in low for w in ("menses", "menstru", "uterus", "leucorrhoea", "genital", "scrotum", "testes")):
        return "Genitalia"
    if any(w in low for w in ("cough", "larynx", "trachea", "breathing", "respiration", "dyspnoea", "asthma", "expectoration")):
        return "Respiratory"
    if any(w in low for w in ("chest", "thorax", "sternum", "ribs", "heart", "palpitation", "mamm")):
        return "Chest"
    if any(w in low for w in ("back", "spine", "lumbar", "sacrum", "scapula", "neck", "nape")):
        return "Back"
    if any(w in low for w in ("arm", "shoulder", "elbow", "wrist", "hand", "finger", "hip", "thigh", "knee", "leg", "foot", "toe", "joint", "limb")):
        return "Extremities"
    if any(w in low for w in ("sleep", "yawning", "drows", "insomnia", "waking")):
        return "Sleep"
    if any(w in low for w in ("chill", "shivering", "fever", "sweat", "perspiration", "pulse", "heat")):
        return "Fever"
    if any(w in low for w in ("skin", "ulcer", "boil", "eruption", "itching", "pustule", "vesicle")):
        return "Skin"
    return "Generalities"


def parse_boericke_pages(
    doc: Any,
    page_indices: list[int] | None = None,
    source_key: str = "boericke_pocket_manual",
    forced_remedy: str | None = None,
) -> list[dict[str, Any]]:
    """Fast, OCR-tolerant parser for Boericke's Pocket Manual of Homoeopathic Materia Medica."""
    sections_cfg = get_sections_config()
    section_map: dict[str, str] = dict(BOERICKE_OCR_SECTION_FIXES)
    for canon, data in sections_cfg.items():
        section_map[canon.lower()] = data.get("canonical", canon)
        for alias in data.get("aliases", []):
            section_map[alias.lower()] = data.get("canonical", canon)

    known_remedy_lookup: dict[str, str] = dict(BOERICKE_OCR_REMEDY_FIXES)
    for canon_rem in get_remedy_abbreviations().values():
        known_remedy_lookup[canon_rem.lower()] = canon_rem

    inline_sec_re = re.compile(
        r"^\s*([A-Z][A-Za-z]{2,15})\s*[\.\*\^,;:]?\s*(?:--|—|-|\.\s*-)\s*(.*)$"
    )
    caps_heading_re = re.compile(r"^\s*([A-Z][A-Z\s\-]{3,35})\.?\s*$")

    indices = page_indices if page_indices is not None else list(range(10, min(len(doc), 695)))
    records: list[dict[str, Any]] = []
    current_remedy = forced_remedy or "Introduction"
    current_section = "Intro"
    current_page = (indices[0] + 1) if indices else 1
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        content = " ".join(buffer).strip()
        if (
            content
            and len(content) >= 25
            and current_remedy != "Introduction"
            and current_section != "Dose"
        ):
            records.append({
                "source_id": make_source_id(source_key),
                "remedy_name": current_remedy,
                "section": current_section,
                "page": current_page,
                "marked_text": content,
            })
        buffer = []

    for idx in indices:
        if idx < 0 or idx >= len(doc):
            continue
        current_page = idx + 1
        raw_text = doc[idx].get_text("text")
        lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]

        for ln_idx, line in enumerate(lines):
            # Skip running page headers on first 2 lines (e.g., "74 ARNICA", "BELLADONNA. 111")
            if ln_idx <= 1 and re.match(r"^(?:\d+\s+[A-Z\s\.]+|[A-Z\s\.]+\s+\d+)$", line):
                # Still use running header to infer remedy if we don't have one
                if not forced_remedy:
                    hdr_clean = re.sub(r"[\d\.]+", "", line).strip().lower()
                    if hdr_clean in known_remedy_lookup and current_remedy == "Introduction":
                        current_remedy = known_remedy_lookup[hdr_clean]
                continue

            # Check inline section heading (e.g. "Mind. — Fears touch...", "Fever.^ — Dry burning...")
            m_sec = inline_sec_re.match(line)
            if m_sec:
                sec_cand = m_sec.group(1).strip().lower()
                if sec_cand in section_map:
                    flush()
                    current_section = section_map[sec_cand]
                    rem_text = m_sec.group(2).strip()
                    if rem_text and current_section != "Dose":
                        buffer.append(rem_text)
                    continue

            # Check remedy heading if not forced
            if not forced_remedy:
                m_caps = caps_heading_re.match(line)
                if m_caps:
                    cand = m_caps.group(1).strip().rstrip(".").lower()
                    if cand in known_remedy_lookup:
                        flush()
                        current_remedy = known_remedy_lookup[cand]
                        current_section = "Intro"
                        continue
                    # Also accept ALL-CAPS Latin names followed by parenthetical common name on next line
                    if (
                        len(cand) >= 5
                        and cand not in section_map
                        and ln_idx + 1 < len(lines)
                        and lines[ln_idx + 1].startswith("(")
                    ):
                        flush()
                        current_remedy = known_remedy_lookup.get(cand, cand.title())
                        current_section = "Intro"
                        continue

            if current_section != "Dose":
                buffer.append(line)

    flush()
    return records


def parse_hahnemann_remedy_pages(
    doc: Any,
    start_page_0: int,
    end_page_0: int,
    remedy_name: str,
    source_key: str = "hahnemann_materia_medica_pura",
    max_pages_per_remedy: int = 8,
) -> list[dict[str, Any]]:
    """Extract high-yield sections from Hahnemann's Materia Medica Pura Vol. 2 for a remedy.

    Each remedy in Hahnemann starts with a rich introductory clinical/therapeutic essay
    followed by numbered proving observations (Mind/disposition at the end or beginning,
    Head, Eyes, Fever, etc.). We group them into clean section-level records so the LLM
    receives consolidated, high-signal chunks.
    """
    section_buckets: dict[str, list[str]] = {}
    section_first_page: dict[str, int] = {}

    # Sample intro + key pages across the remedy chapter (including the final pages where Mind symptoms live in Hahnemann)
    total_pages = end_page_0 - start_page_0 + 1
    if total_pages <= max_pages_per_remedy:
        selected_pages = list(range(start_page_0, end_page_0 + 1))
    else:
        # First 4 pages (Intro + Head/Eyes) + middle 2 pages + last 2 pages (Fever + Mind/Disposition)
        mid = start_page_0 + total_pages // 2
        selected_pages = sorted(
            set(
                list(range(start_page_0, min(end_page_0 + 1, start_page_0 + 4)))
                + [mid, min(end_page_0, mid + 1)]
                + [max(start_page_0, end_page_0 - 1), end_page_0]
            )
        )

    for p_idx in selected_pages:
        if p_idx < 0 or p_idx >= len(doc):
            continue
        raw = doc[p_idx].get_text("text")
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw) if len(p.strip()) >= 35]
        for para in paragraphs:
            clean_para = re.sub(r"\s+", " ", para).strip()
            # Skip running header lines
            if len(clean_para) < 40 and re.isupper(clean_para[:10]):
                continue
            sec = "Intro" if p_idx == start_page_0 else classify_hahnemann_section(clean_para)
            section_buckets.setdefault(sec, []).append(clean_para)
            section_first_page.setdefault(sec, p_idx + 1)

    records: list[dict[str, Any]] = []
    for sec, paras in section_buckets.items():
        joined = "\n\n".join(paras)
        # Cap each section bucket to ~3200 chars so each section forms 1 concise chunk
        if len(joined) > 3200:
            joined = joined[:3200].rsplit(".", 1)[0] + "."
        records.append({
            "source_id": make_source_id(source_key),
            "remedy_name": remedy_name,
            "section": sec,
            "page": section_first_page.get(sec, start_page_0 + 1),
            "marked_text": joined,
        })
    return records


def parse_pdf_source(
    pdf_path: Path,
    source_key: str = "boericke_pocket_manual",
    output_dir: Path | None = None,
) -> Path:
    """Parse a PDF materia medica (Hahnemann or Boericke) into data/parsed/<source_key>.jsonl."""
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz  # type: ignore

    output_dir = output_dir or (DATA_DIR / "parsed")
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{source_key}.jsonl"

    doc = fitz.open(pdf_path)
    records: list[dict[str, Any]] = []

    if "hahnemann" in pdf_path.name.lower() or "hahnemann" in source_key.lower():
        for start_p, end_p, rem_name in HAHNEMANN_VOL2_RANGES:
            records.extend(
                parse_hahnemann_remedy_pages(
                    doc, start_p, end_p, rem_name, source_key=source_key
                )
            )
    else:
        records = parse_boericke_pages(doc, source_key=source_key)

    with open(out_file, "w", encoding="utf-8") as out:
        for r in records:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")

    return out_file


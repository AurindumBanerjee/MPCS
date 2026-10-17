from __future__ import annotations

import re
from typing import Any
from rapidfuzz import fuzz

from hkg.config import get_sections_config, get_sources_config
from hkg.schema.extraction import ChunkExtraction, ModalityOut, SymptomOut


def normalize_text(text: str) -> str:
    """Normalize whitespace, case, and lightweight markdown for substring checking."""
    # Remove markdown formatting characters
    cleaned = re.sub(r"[\*\_#`]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def is_substring_normalized(sub: str, full: str) -> bool:
    """Check if normalized sub appears inside normalized full text."""
    n_sub = normalize_text(sub)
    n_full = normalize_text(full)
    if not n_sub or not n_full:
        return False
    return n_sub in n_full


def check_symptom_grounding(symptom_raw: str, quote: str, min_ratio: float = 60.0) -> bool:
    """Check whether symptom_raw is grounded in the quote (substring or high fuzzy match)."""
    if is_substring_normalized(symptom_raw, quote):
        return True
    # Fuzzy fallback for minor rewordings or punctuation differences
    ratio = fuzz.partial_ratio(normalize_text(symptom_raw), normalize_text(quote))
    return ratio >= min_ratio


# Directional cue patterns
WORSE_CUES = re.compile(r"(?:\b(?:worse|aggravat\w*|agg\.|aggravation|bad\b|increase\w*)\b|<)", re.IGNORECASE)
BETTER_CUES = re.compile(r"(?:\b(?:better|ameliorat\w*|amel\.|amelioration|reliev\w*|eased)\b|>)", re.IGNORECASE)


def validate_direction(direction: str, quote: str) -> dict[str, Any]:
    """Check if modality direction matches textual cues in the quote."""
    has_worse = bool(WORSE_CUES.search(quote))
    has_better = bool(BETTER_CUES.search(quote))

    flagged = False
    flag_reason = None

    if direction == "worse" and has_better and not has_worse:
        flagged = True
        flag_reason = "Direction is 'worse' but quote only contains 'better' cues."
    elif direction == "better" and has_worse and not has_better:
        flagged = True
        flag_reason = "Direction is 'better' but quote only contains 'worse' cues."

    return {
        "valid": not flagged,
        "flagged": flagged,
        "reason": flag_reason,
    }


def detect_markup_emphasis(symptom_raw: str, chunk_text: str) -> str:
    """Deterministic markup check: inspect chunk_text around symptom text for **bold**, _italic_, or CAPS."""
    clean_sym = symptom_raw.strip()
    if not clean_sym:
        return "plain"

    # Check for bold pattern **...**
    escaped = re.escape(clean_sym)
    if re.search(rf"\*\*[^*]*{escaped}[^*]*\*\*", chunk_text, re.IGNORECASE):
        return "bold"

    # Check for italic pattern _..._ or *...*
    if re.search(rf"(?:_|\*)[^_*\n]*{escaped}[^_*\n]*(?:_|\*)", chunk_text, re.IGNORECASE):
        return "italic"

    # Check if symptom is predominantly in ALL CAPS in chunk
    match = re.search(escaped, chunk_text)
    if match:
        matched_chunk_slice = match.group(0)
        if matched_chunk_slice.isupper() and len(matched_chunk_slice) >= 4:
            return "caps"

    return "plain"


def compute_grade(emphasis: str, source_id: str = "boericke_pocket_manual") -> int:
    """Compute numeric grade (1-3) from emphasis using per-source mapping in sources.yaml."""
    sources = get_sources_config()
    source_cfg = sources.get(source_id, {})
    grade_map = source_cfg.get("emphasis_grade_map", {
        "plain": 1,
        "italic": 2,
        "bold": 3,
        "caps": 3,
    })
    return int(grade_map.get(emphasis, 1))


def resolve_symptom_kind(section: str, symptom_kind_hint: str = "unknown") -> str:
    """Determine symptom kind deterministically from section, falling back to hint for unknown sections."""
    sections_cfg = get_sections_config()
    sec_info = sections_cfg.get(section, {})
    if "kind" in sec_info:
        return sec_info["kind"]

    if section.lower() in ("mind", "mental"):
        return "mental"
    elif section.lower() in ("modalities", "relationship", "generalities", "sleep", "fever"):
        return "general"
    elif section.lower() in ("intro", "introduction"):
        return "general"

    if symptom_kind_hint in ("mental", "physical", "general", "clinical"):
        return symptom_kind_hint
    return "physical"


class ValidationResult:
    def __init__(self):
        self.accepted_symptoms: list[dict[str, Any]] = []
        self.rejected_items: list[dict[str, Any]] = []
        self.flags: list[dict[str, Any]] = []


def validate_chunk_extraction(
    extraction: ChunkExtraction,
    chunk_text: str,
    remedy_name: str,
    section: str,
    source_id: str = "boericke_pocket_manual",
) -> ValidationResult:
    """Validate extraction results against chunk text per plan Stage 3."""
    res = ValidationResult()

    # Validate each symptom
    for sym in extraction.symptoms:
        # 1. Quote Faithfulness: quote must be a substring of chunk
        if not is_substring_normalized(sym.evidence_quote, chunk_text):
            res.rejected_items.append({
                "reason": "quote_not_in_chunk",
                "item": sym.model_dump(),
                "evidence_quote": sym.evidence_quote,
            })
            continue

        # 2. Symptom Grounding: symptom_raw must appear in or match quote
        if not check_symptom_grounding(sym.symptom_raw, sym.evidence_quote):
            res.rejected_items.append({
                "reason": "symptom_not_grounded_in_quote",
                "item": sym.model_dump(),
                "symptom_raw": sym.symptom_raw,
                "evidence_quote": sym.evidence_quote,
            })
            continue

        # 3. Emphasis Check: Markup wins!
        detected_emphasis = detect_markup_emphasis(sym.symptom_raw, chunk_text)
        actual_emphasis = detected_emphasis if detected_emphasis != "plain" else sym.emphasis
        if actual_emphasis != sym.emphasis:
            res.flags.append({
                "type": "emphasis_override",
                "symptom": sym.symptom_raw,
                "llm_emphasis": sym.emphasis,
                "markup_emphasis": actual_emphasis,
            })

        # 4. Compute Grade
        grade = compute_grade(actual_emphasis, source_id=source_id)

        # 5. Symptom Kind
        kind = resolve_symptom_kind(section, sym.symptom_kind_hint)

        # 6. Direction Sanity Check on attached modalities
        validated_modalities = []
        for mod in sym.modalities:
            dir_check = validate_direction(mod.direction, sym.evidence_quote)
            if dir_check["flagged"]:
                res.flags.append({
                    "type": "direction_sanity_warning",
                    "symptom": sym.symptom_raw,
                    "direction": mod.direction,
                    "reason": dir_check["reason"],
                    "quote": sym.evidence_quote,
                })
            validated_modalities.append(mod.model_dump())

        # 7. Confidence check
        confidence = float(sym.confidence)
        if confidence < 0.5:
            res.flags.append({
                "type": "low_confidence",
                "symptom": sym.symptom_raw,
                "confidence": confidence,
            })

        sym_dict = sym.model_dump()
        sym_dict["emphasis"] = actual_emphasis
        sym_dict["grade"] = grade
        sym_dict["kind"] = kind
        sym_dict["modalities"] = validated_modalities
        res.accepted_symptoms.append(sym_dict)

    return res

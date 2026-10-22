from __future__ import annotations

import difflib
import re
from typing import Any

try:
    from rapidfuzz import fuzz as _rf_fuzz
except ImportError:
    _rf_fuzz = None  # type: ignore


def _partial_ratio(a: str, b: str) -> float:
    if _rf_fuzz is not None:
        return float(_rf_fuzz.partial_ratio(a, b))
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 100.0
    return difflib.SequenceMatcher(None, a, b).ratio() * 100.0

from lkg.config import get_sections_config, get_sources_config
from lkg.extract.affect import (
    KNOWN_CLINICAL_CONDITIONS,
    canonicalize_symptom_label,
    compute_adjective_severity,
    compute_linear_regression_weight,
    compute_vad,
    resolve_cognitive_domain,
)
from lkg.schema.extraction import ChunkExtraction, ModalityOut, SymptomOut


def normalize_text(text: str) -> str:
    """Normalize whitespace, case, and lightweight markdown for substring checking."""
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
    ratio = _partial_ratio(normalize_text(symptom_raw), normalize_text(quote))
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
    clean_sym = re.sub(r"[\*\_`]", "", symptom_raw).strip()
    if not clean_sym:
        return "plain"

    escaped = re.escape(clean_sym)
    # 1. Check if symptom_raw sits inside a **bold** span
    for m in re.finditer(r"\*\*([^*]+)\*\*", chunk_text):
        if re.search(escaped, m.group(1), re.IGNORECASE):
            return "bold"

    # 2. Check if symptom_raw sits inside an _italic_ span
    for m in re.finditer(r"(?<!\*)(?:_([^_\n]+)_|\*([^*\n]+)\*)(?!\*)", chunk_text):
        span_txt = m.group(1) or m.group(2) or ""
        if re.search(escaped, span_txt, re.IGNORECASE):
            return "italic"

    # 3. Check if symptom is predominantly in ALL CAPS in chunk
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


def resolve_symptom_kind(section: str, symptom_kind_hint: str = "unknown", symptom_raw: str = "") -> str:
    """Determine symptom kind deterministically from section + content."""
    low_sym = symptom_raw.lower()
    if "dream" in low_sym or "nightmare" in low_sym or symptom_kind_hint == "dream":
        return "dream"

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

    if symptom_kind_hint in ("mental", "affective", "dream", "physical", "general", "clinical"):
        return "mental" if symptom_kind_hint == "affective" else symptom_kind_hint
    return "physical"


def _infer_factor_type(factor_raw: str) -> str:
    low = factor_raw.lower()
    if re.search(r"\b(morning|evening|night|midnight|noon|afternoon|hour|day|periodic)\b", low):
        return "time"
    if re.search(r"\b(heat|warm\w*|cold|cool|open air|heated|chill)\b", low):
        return "temperature"
    if re.search(r"\b(wet|damp|dry|wind\w*|storm\w*|weather|change of)\b", low):
        return "weather"
    if re.search(r"\b(lying|sitting|standing|stooping|rising|bending)\b", low):
        return "position"
    if re.search(r"\b(motion|walking|running|exertion|rest|ascending)\b", low):
        return "motion"
    if re.search(r"\b(touch|pressure|rubbing|scratching|riding)\b", low):
        return "touch_pressure"
    if re.search(r"\b(drink\w*|food|milk|coffee|wine|fat|fruit|eating|fasting)\b", low):
        return "food_drink"
    if re.search(r"\b(sleep\w*|waking|slumber)\b", low):
        return "sleep"
    if re.search(r"\b(alone|company|consolation|strangers)\b", low):
        return "company"
    if re.search(r"\b(fright|grief|anger|vexation|excitement|weeping)\b", low):
        return "emotion"
    return "other"


def harvest_unclaimed_modalities(
    chunk_text: str,
    existing_factors: set[str],
) -> list[dict[str, Any]]:
    """Fallback harvester: catch explicit 'Worse ...; better ...' clauses the LLM missed."""
    harvested: list[dict[str, Any]] = []
    clean_lines = [
        line.strip()
        for line in chunk_text.splitlines()
        if line.strip() and not line.strip().startswith("###")
    ]
    full_text = " ".join(clean_lines)

    # Match clauses starting with Worse / Aggravated / < or Better / Ameliorated / >
    clause_pattern = re.compile(
        r"\b(worse|aggravated|agg\.|better|ameliorated|amel\.|relieved)\b\s*(?:from|by|in|at|on|after|during|,)?\s*([^.;\n]+)",
        re.IGNORECASE,
    )
    for m in clause_pattern.finditer(full_text):
        cue = m.group(1).lower()
        raw_tail = m.group(2).strip()
        direction = "worse" if cue.startswith(("worse", "agg")) else "better"
        quote = m.group(0).strip()
        # Split on ',' or ' and '
        parts = [p.strip() for p in re.split(r",|\band\b", raw_tail) if p.strip()]
        for part in parts:
            norm_part = normalize_text(part)
            if not norm_part or len(norm_part) < 3:
                continue
            if any(norm_part in ef or ef in norm_part for ef in existing_factors):
                continue
            existing_factors.add(norm_part)
            harvested.append({
                "direction": direction,
                "factor_raw": part,
                "factor_type": _infer_factor_type(part),
                "evidence_quote": quote,
            })
    return harvested


class ValidationResult:
    def __init__(self):
        self.accepted_symptoms: list[dict[str, Any]] = []
        self.harvested_modalities: list[dict[str, Any]] = []
        self.rejected_items: list[dict[str, Any]] = []
        self.flags: list[dict[str, Any]] = []


def validate_chunk_extraction(
    extraction: ChunkExtraction,
    chunk_text: str,
    remedy_name: str,
    section: str,
    source_id: str = "boericke_pocket_manual",
) -> ValidationResult:
    """Validate extraction results against chunk text and enrich with VAD, severity, and domains."""
    res = ValidationResult()
    chunk_has_markup = bool(re.search(r"(\*\*[^*]+\*\*|_[^_\n]+_)", chunk_text))
    existing_factors: set[str] = set()

    for gm in extraction.general_modalities:
        existing_factors.add(normalize_text(gm.modality.factor_raw))

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

        # 3. Authoritative Emphasis Check: Markup in chunk_text strictly wins!
        detected_emphasis = detect_markup_emphasis(sym.symptom_raw, chunk_text)
        if chunk_has_markup:
            actual_emphasis = detected_emphasis
        else:
            actual_emphasis = detected_emphasis if detected_emphasis != "plain" else sym.emphasis

        if actual_emphasis != sym.emphasis:
            res.flags.append({
                "type": "emphasis_override",
                "symptom": sym.symptom_raw,
                "llm_emphasis": sym.emphasis,
                "markup_emphasis": actual_emphasis,
            })

        # 4. Compute Typography Grade (1-3)
        grade = compute_grade(actual_emphasis, source_id=source_id)

        # 5. Symptom Kind
        kind = resolve_symptom_kind(section, sym.symptom_kind_hint, sym.symptom_raw)

        # 6. Direction Sanity Check on attached modalities
        validated_modalities = []
        for mod in sym.modalities:
            existing_factors.add(normalize_text(mod.factor_raw))
            dir_check = validate_direction(mod.direction, sym.evidence_quote)
            if dir_check["flagged"]:
                res.flags.append({
                    "type": "direction_sanity_warning",
                    "symptom": sym.symptom_raw,
                    "direction": mod.direction,
                    "reason": dir_check["reason"],
                    "quote": sym.evidence_quote,
                })
            mod_dump = mod.model_dump()
            if mod_dump.get("factor_type", "other") == "other":
                mod_dump["factor_type"] = _infer_factor_type(mod.factor_raw)
            validated_modalities.append(mod_dump)

        # 7. Confidence check
        confidence = float(sym.confidence)
        if confidence < 0.5:
            res.flags.append({
                "type": "low_confidence",
                "symptom": sym.symptom_raw,
                "confidence": confidence,
            })

        # 8. Enrich with Adjective Severity, VAD Affect Vector, Cognitive Domain & Linear Regression Weight
        adj_score, matched_adjs = compute_adjective_severity(
            f"{sym.symptom_raw} {sym.evidence_quote}", sym.severity_modifiers
        )
        vad = compute_vad(f"{sym.symptom_raw} {sym.evidence_quote}")
        cog_domain = resolve_cognitive_domain(sym.symptom_raw, section, sym.cognitive_domain)
        composite_weight = compute_linear_regression_weight(
            grade=grade,
            adj_severity=adj_score,
            arousal=vad["arousal"],
            confidence=confidence,
        )
        canon_label = canonicalize_symptom_label(sym.symptom_raw, sym.canonical_label)

        # Detect clinical conditions mentioned in the symptom
        conds = list(sym.clinical_conditions)
        for tok in re.findall(r"[a-z]+", sym.symptom_raw.lower()):
            if tok in KNOWN_CLINICAL_CONDITIONS and tok.capitalize() not in conds:
                conds.append(tok.capitalize())

        sym_dict = sym.model_dump()
        sym_dict["canonical_label"] = canon_label
        sym_dict["emphasis"] = actual_emphasis
        sym_dict["grade"] = grade
        sym_dict["kind"] = kind
        sym_dict["modalities"] = validated_modalities
        sym_dict["severity_modifiers"] = matched_adjs or sym.severity_modifiers
        sym_dict["adjective_severity"] = adj_score
        sym_dict["vad"] = vad
        sym_dict["cognitive_domain"] = cog_domain
        sym_dict["composite_weight"] = composite_weight
        sym_dict["clinical_conditions"] = conds
        res.accepted_symptoms.append(sym_dict)

    # 9. Harvest any explicit Worse/Better clauses in the chunk that the LLM missed
    unclaimed = harvest_unclaimed_modalities(chunk_text, existing_factors)
    if unclaimed:
        if res.accepted_symptoms and section.lower() != "modalities":
            # Attach to the last symptom in the paragraph (or general_modalities)
            target_sym = res.accepted_symptoms[-1]
            for hm in unclaimed:
                target_sym["modalities"].append({
                    "direction": hm["direction"],
                    "factor_raw": hm["factor_raw"],
                    "factor_type": hm["factor_type"],
                })
        res.harvested_modalities = unclaimed

    return res

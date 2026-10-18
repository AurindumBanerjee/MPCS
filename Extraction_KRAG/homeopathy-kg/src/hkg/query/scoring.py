from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class SymptomQuery(BaseModel):
    text: str
    kind: str | None = None
    location: str | None = None


class ModalityQuery(BaseModel):
    direction: str = Field(description="'worse' or 'better'")
    factor: str
    attaches_to: int | str | None = None  # symptom index or "general"


class RemedyMatch(BaseModel):
    remedy_id: str
    remedy_name: str
    coverage_count: int
    total_query_symptoms: int
    coverage_ratio: float
    total_score: float
    is_partial: bool
    matched_symptoms: list[dict[str, Any]] = []
    matched_modalities: list[dict[str, Any]] = []


def calculate_repertory_scores(
    candidate_occurrences: list[dict[str, Any]],
    query_symptoms: list[SymptomQuery],
    query_modalities: list[ModalityQuery] | None = None,
    modality_bonus: float = 1.5,
) -> list[RemedyMatch]:
    """Calculate deterministic repertorization scores per remedy per plan section 10.

    Ranked by coverage first (how many query symptoms matched), then total score.
    """
    query_modalities = query_modalities or []
    total_symptoms = max(1, len(query_symptoms))

    # Group occurrences by remedy
    by_remedy: dict[str, dict[str, Any]] = {}

    for occ in candidate_occurrences:
        rem_id = occ.get("remedy_id") or occ.get("remedy_name")
        rem_name = occ.get("remedy_name", rem_id)

        if rem_id not in by_remedy:
            by_remedy[rem_id] = {
                "remedy_id": rem_id,
                "remedy_name": rem_name,
                "symptom_matches": {},  # query_idx -> best occurrence
                "modality_matches": [],
            }

        q_idx = occ.get("query_symptom_index", 0)
        grade = float(occ.get("grade", 1))
        conf = float(occ.get("confidence", 1.0))
        effective_score = grade * conf

        # Keep highest scoring occurrence per query symptom
        existing = by_remedy[rem_id]["symptom_matches"].get(q_idx)
        if existing is None or effective_score > existing["score"]:
            by_remedy[rem_id]["symptom_matches"][q_idx] = {
                "score": effective_score,
                "grade": grade,
                "confidence": conf,
                "occurrence_id": occ.get("id", occ.get("occurrence_id")),
                "symptom_raw": occ.get("symptom_raw", ""),
                "section": occ.get("section", ""),
                "evidence_quote": occ.get("evidence_quote", ""),
                "source_ref": occ.get("source_ref", ""),
            }

        # Check modalities attached to this occurrence or general
        for qm in query_modalities:
            for occ_mod in occ.get("modalities", []):
                if occ_mod.get("direction", "").lower() == qm.direction.lower():
                    if qm.factor.lower() in occ_mod.get("factor_raw", "").lower():
                        by_remedy[rem_id]["modality_matches"].append({
                            "factor": occ_mod.get("factor_raw"),
                            "direction": qm.direction,
                            "occurrence_id": occ.get("id"),
                            "bonus": modality_bonus,
                        })

    matches: list[RemedyMatch] = []
    for rem_id, data in by_remedy.items():
        s_matches = list(data["symptom_matches"].values())
        coverage = len(s_matches)
        base_score = sum(sm["score"] for sm in s_matches)
        mod_score = sum(mm.get("bonus", modality_bonus) for mm in data["modality_matches"])
        total = base_score + mod_score

        matches.append(
            RemedyMatch(
                remedy_id=rem_id,
                remedy_name=data["remedy_name"],
                coverage_count=coverage,
                total_query_symptoms=total_symptoms,
                coverage_ratio=coverage / float(total_symptoms),
                total_score=round(total, 2),
                is_partial=(coverage < total_symptoms),
                matched_symptoms=s_matches,
                matched_modalities=data["modality_matches"],
            )
        )

    # Sort primarily by coverage count descending, secondarily by total score descending
    matches.sort(key=lambda m: (m.coverage_count, m.total_score), reverse=True)
    return matches

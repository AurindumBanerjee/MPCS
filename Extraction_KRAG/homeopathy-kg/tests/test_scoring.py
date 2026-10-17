import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hkg.query.scoring import (
    ModalityQuery,
    SymptomQuery,
    calculate_repertory_scores,
)


def test_repertorization_scoring_coverage_first():
    q_symptoms = [
        SymptomQuery(text="burning pain in stomach"),
        SymptomQuery(text="fear of death"),
        SymptomQuery(text="restlessness"),
    ]
    q_modalities = [
        ModalityQuery(direction="worse", factor="midnight"),
    ]

    # Remedy A matches 3 symptoms
    rem_a_occurrences = [
        {
            "id": "occ:a1",
            "remedy_id": "remedy:ars",
            "remedy_name": "Arsenicum album",
            "symptom_raw": "Burning pain in stomach",
            "grade": 3,
            "confidence": 1.0,
            "query_symptom_index": 0,
            "modalities": [{"direction": "worse", "factor_raw": "after midnight"}],
        },
        {
            "id": "occ:a2",
            "remedy_id": "remedy:ars",
            "remedy_name": "Arsenicum album",
            "symptom_raw": "Fear of death",
            "grade": 3,
            "confidence": 1.0,
            "query_symptom_index": 1,
            "modalities": [],
        },
        {
            "id": "occ:a3",
            "remedy_id": "remedy:ars",
            "remedy_name": "Arsenicum album",
            "symptom_raw": "Restlessness",
            "grade": 3,
            "confidence": 1.0,
            "query_symptom_index": 2,
            "modalities": [],
        },
    ]

    # Remedy B matches only 1 symptom with very high grade
    rem_b_occurrences = [
        {
            "id": "occ:b1",
            "remedy_id": "remedy:acon",
            "remedy_name": "Aconitum",
            "symptom_raw": "Fear of death",
            "grade": 3,
            "confidence": 1.0,
            "query_symptom_index": 1,
            "modalities": [],
        }
    ]

    candidate_occurrences = rem_a_occurrences + rem_b_occurrences

    scores = calculate_repertory_scores(
        candidate_occurrences=candidate_occurrences,
        query_symptoms=q_symptoms,
        query_modalities=q_modalities,
    )

    assert len(scores) == 2
    # Remedy A must rank first because coverage is 3/3 vs 1/3
    assert scores[0].remedy_name == "Arsenicum album"
    assert scores[0].coverage_count == 3
    assert not scores[0].is_partial

    # Remedy B must be marked as partial match
    assert scores[1].remedy_name == "Aconitum"
    assert scores[1].coverage_count == 1
    assert scores[1].is_partial
    assert scores[0].total_score > scores[1].total_score

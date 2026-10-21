import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lkg.extract.validators import (
    compute_grade,
    detect_markup_emphasis,
    is_substring_normalized,
    resolve_symptom_kind,
    validate_chunk_extraction,
    validate_direction,
)
from lkg.schema.extraction import ChunkExtraction, ModalityOut, SymptomOut


def test_quote_faithfulness():
    chunk = "Burning pains in stomach, relieved by warm drinks. Worse after midnight."
    assert is_substring_normalized("Burning pains in stomach", chunk)
    assert is_substring_normalized("relieved by warm drinks", chunk)
    assert not is_substring_normalized("Severe headache with nausea", chunk)


def test_direction_sanity_check():
    # Worse direction with "worse" quote -> valid
    check1 = validate_direction("worse", "Pain is much worse after midnight.")
    assert check1["valid"]
    assert not check1["flagged"]

    # Worse direction but quote says "better" -> flagged
    check2 = validate_direction("worse", "Relieved and much better by warm applications.")
    assert not check2["valid"]
    assert check2["flagged"]

    # Better direction with "ameliorated" -> valid
    check3 = validate_direction("better", "Ameliorated in the open air.")
    assert check3["valid"]
    assert not check3["flagged"]


def test_emphasis_override_markup_wins():
    chunk = "Great **anxiety** and _restlessness_."
    assert detect_markup_emphasis("anxiety", chunk) == "bold"
    assert detect_markup_emphasis("restlessness", chunk) == "italic"
    assert detect_markup_emphasis("plain symptom", chunk) == "plain"


def test_deterministic_grade_computation():
    assert compute_grade("plain") == 1
    assert compute_grade("italic") == 2
    assert compute_grade("bold") == 3
    assert compute_grade("caps") == 3


def test_symptom_kind_from_section():
    assert resolve_symptom_kind("Mind") == "mental"
    assert resolve_symptom_kind("Stomach") == "physical"
    assert resolve_symptom_kind("Fever") == "general"


def test_validate_chunk_extraction_full():
    chunk_text = "### Arsenicum album: Stomach\n\n**Burning pain** in epigastrium. Unquenchable thirst."
    sym_valid = SymptomOut(
        symptom_raw="Burning pain",
        emphasis="plain",  # LLM says plain, but chunk has **Burning pain** -> markup wins!
        evidence_quote="Burning pain in epigastrium.",
        confidence=0.95,
    )
    sym_hallucinated = SymptomOut(
        symptom_raw="Stitching in right ovary",
        emphasis="plain",
        evidence_quote="Stitching pain in right ovary after menses.",  # Not in chunk!
        confidence=0.90,
    )

    extraction = ChunkExtraction(symptoms=[sym_valid, sym_hallucinated])
    res = validate_chunk_extraction(
        extraction=extraction,
        chunk_text=chunk_text,
        remedy_name="Arsenicum album",
        section="Stomach",
    )

    assert len(res.accepted_symptoms) == 1
    assert res.accepted_symptoms[0]["symptom_raw"] == "Burning pain"
    # Verify markup override
    assert res.accepted_symptoms[0]["emphasis"] == "bold"
    assert res.accepted_symptoms[0]["grade"] == 3
    assert res.accepted_symptoms[0]["kind"] == "physical"

    # Verify hallucinated quote was rejected
    assert len(res.rejected_items) == 1
    assert res.rejected_items[0]["reason"] == "quote_not_in_chunk"

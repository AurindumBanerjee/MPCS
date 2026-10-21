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


def test_false_positive_emphasis_is_overridden_to_plain():
    chunk_text = "_Fears death_, believes that he will soon die; predicts the day."
    sym1 = SymptomOut(
        symptom_raw="Fears death",
        emphasis="italic",
        evidence_quote=chunk_text,
    )
    sym2 = SymptomOut(
        symptom_raw="believes that he will soon die; predicts the day",
        emphasis="italic",  # LLM falsely claims italic -> validator overrides to plain!
        evidence_quote=chunk_text,
    )
    extraction = ChunkExtraction(symptoms=[sym1, sym2])
    res = validate_chunk_extraction(
        extraction=extraction,
        chunk_text=chunk_text,
        remedy_name="Aconitum Napellus",
        section="Mind",
    )
    assert len(res.accepted_symptoms) == 2
    assert res.accepted_symptoms[0]["emphasis"] == "italic"
    assert res.accepted_symptoms[0]["grade"] == 2
    assert res.accepted_symptoms[1]["emphasis"] == "plain"
    assert res.accepted_symptoms[1]["grade"] == 1
    assert any(f["type"] == "emphasis_override" for f in res.flags)


def test_modality_fallback_harvester_and_cognitive_domains():
    chunk_text = (
        "### Aconitum Napellus: Mind\n\n"
        "Restlessness, tossing about. Worse in the evening and at night; better in open air."
    )
    sym = SymptomOut(
        symptom_raw="Restlessness, tossing about",
        emphasis="plain",
        evidence_quote="Restlessness, tossing about.",
    )
    extraction = ChunkExtraction(symptoms=[sym])
    res = validate_chunk_extraction(
        extraction=extraction,
        chunk_text=chunk_text,
        remedy_name="Aconitum Napellus",
        section="Mind",
    )
    accepted = res.accepted_symptoms[0]
    assert accepted["cognitive_domain"] == "Hyperarousal / Anxiety"
    assert accepted["vad"]["arousal"] >= 0.80
    assert accepted["composite_weight"] > 1.0
    # Verify fallback harvester caught the 3 missed modalities
    mods = accepted["modalities"]
    assert len(mods) >= 3
    dirs = {m["factor_raw"].lower(): m["direction"] for m in mods}
    assert any("evening" in k and v == "worse" for k, v in dirs.items())
    assert any("night" in k and v == "worse" for k, v in dirs.items())
    assert any("open air" in k and v == "better" for k, v in dirs.items())


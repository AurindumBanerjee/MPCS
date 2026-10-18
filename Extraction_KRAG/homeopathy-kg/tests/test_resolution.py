import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hkg.resolve.aliases import RemedyResolver, ModalityResolver
from hkg.resolve.merge_proposals import SymptomMergeProposalManager
from hkg.resolve.normalize import normalize_remedy_name, normalize_symptom_label


def test_remedy_resolver():
    resolver = RemedyResolver(canonical_remedies=["Arsenicum album", "Pulsatilla pratensis", "Nux vomica"])

    # Abbreviation match
    res1 = resolver.resolve("Ars.")
    assert res1["canonical_name"] == "Arsenicum album"
    assert res1["confidence"] >= 0.95

    # Case insensitive exact match
    res2 = resolver.resolve("pulsatilla pratensis")
    assert res2["canonical_name"] == "Pulsatilla pratensis"

    # Dot-stripped match
    res3 = resolver.resolve("Nux-v")
    assert "Nux" in res3["canonical_name"]


def test_modality_resolver():
    resolver = ModalityResolver()

    # Exact seed match
    res1 = resolver.resolve("after midnight")
    assert res1["modality_id"] == "modality:after_midnight"
    assert not res1["needs_review"]

    # Fuzzy seed match
    res2 = resolver.resolve("past midnight")
    assert res2["modality_id"] == "modality:after_midnight"

    # Unmapped modality -> needs_review flag
    res3 = resolver.resolve("eating cold ice cream in winter")
    assert res3["needs_review"]
    assert res3["modality_id"].startswith("modality:")


def test_strict_no_auto_merge_of_mental_symptoms():
    mgr = SymptomMergeProposalManager()

    # Mental symptoms must NEVER be merged automatically in v1
    s1 = mgr.propose_or_resolve("Fear of death", kind="mental", symptom_id="symptom:fear_of_death")
    s2 = mgr.propose_or_resolve("Anxiety about dying", kind="mental", symptom_id="symptom:anxiety_about_dying")

    assert not s1["merged"]
    assert not s2["merged"]
    assert s1["symptom_id"] != s2["symptom_id"]


def test_physical_symptoms_proposal():
    mgr = SymptomMergeProposalManager()
    s1 = mgr.propose_or_resolve("Burning stomach pain", kind="physical", symptom_id="symptom:burning_stomach_pain")
    # Exact proposal should match
    s2 = mgr.propose_or_resolve("burning stomach pain", kind="physical", symptom_id="symptom:burning_stomach_pain_2")
    assert s2["merged"]
    assert s2["symptom_id"] == s1["symptom_id"]

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import json
import tempfile
from hkg.load.neo4j_loader import Neo4jLoader
from hkg.query.tools import HKGQueryTools
from hkg.query.scoring import SymptomQuery, ModalityQuery
from hkg.resolve.merge_proposals import SymptomMergeProposalManager
from hkg.schema.graph import make_occurrence_id


def test_merge_proposals_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        proposals_file = Path(tmpdir) / "proposals.jsonl"
        mgr = SymptomMergeProposalManager(output_path=proposals_file)

        # Propose base symptom
        mgr.propose_or_resolve("Stitching pain in temples", kind="physical", symptom_id="symptom:stitching_temples")
        # Propose similar physical symptom with ~80% similarity -> writes proposal
        mgr.propose_or_resolve("Stitching pain in temple region", kind="physical", symptom_id="symptom:stitching_temple_region")

        assert proposals_file.exists()
        lines = [json.loads(l) for l in proposals_file.read_text(encoding="utf-8").splitlines() if l]
        assert len(lines) >= 1
        assert lines[0]["proposal_type"] == "symptom_merge"


def test_query_tools_standalone():
    tools = HKGQueryTools()

    # Test 1: find_remedies on Classic Symptoms
    res = tools.find_remedies(
        symptoms=[
            {"text": "burning stomach pain"},
            {"text": "fear of death"},
            {"text": "restlessness"},
        ],
        modalities=[
            {"direction": "worse", "factor": "after midnight"}
        ],
        limit=5,
    )
    assert "remedies" in res
    assert "query_symptoms_count" in res
    assert res["query_symptoms_count"] == 3

    # Test 2: get_remedy - strictly no dose
    profile = tools.get_remedy("Arsenicum album")
    assert profile["name"] == "Arsenicum album"
    assert "dose" not in profile
    assert "potency" not in profile


def test_idempotent_occurrence_ids():
    chunk_id = "chunk:test:10"
    symptom = "Intense anxiety with palpitations"
    quote = "Patient exhibits intense anxiety with palpitations."

    id1 = make_occurrence_id(chunk_id, symptom, quote)
    id2 = make_occurrence_id(chunk_id, symptom, quote)
    assert id1 == id2

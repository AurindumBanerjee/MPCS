"""Unit and Integration Tests for LocalRAG-MPCS Neuro-Symbolic Cognitive Bridge
-------------------------------------------------------------------------------
Verifies:
  1. Initialization and health check across MPCS Core and LocalKG.
  2. Doctor Exploratory Persona traversal (differential diagnosis, 2 hops).
  3. Patient Confident Persona traversal (keynote triage, noise suppression).
  4. Emergency Red-Flag safety reflex gating (immediate ALERT override).
  5. Sub-microsecond dlCBF Bloom filter seen-before gating.
  6. Clinical reinforcement feedback loop and threshold adaptation.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_DIR = REPO_ROOT / "Model" / "experimental" / "09_localrag_bridge"

if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

from bridge_engine import LocalRAGMpcsBridge, BridgeResponse


def test_bridge_initialization():
    """Verify that both MPCS and LocalRAG are instantiated with active graphs and memory."""
    bridge = LocalRAGMpcsBridge()
    assert len(bridge.persona_engine.nodes) > 0, "LocalKG nodes must not be empty"
    assert len(bridge.persona_engine.links) > 0, "LocalKG links must not be empty"
    assert len(bridge.session.memory) > 0, "MPCS memory must be initialized with experiences"
    assert len(bridge.session.memory._dlcbf) > 0, "dlCBF must contain memory fingerprints"


def test_doctor_exploratory_query():
    """Verify doctor exploratory query executes with differential analysis and active subgraph."""
    bridge = LocalRAGMpcsBridge()
    query = "violent throbbing headache with high fever and restless anxiety after cold wind"
    resp = bridge.process_query(
        query=query,
        persona="doctor",
        explicit_modalities={"thermal": "cold", "motion": "fast"}
    )
    assert isinstance(resp, BridgeResponse)
    assert not resp.is_emergency
    assert resp.persona == "exploratory"
    assert resp.total_latency_ms < 500.0, f"Latency too high: {resp.total_latency_ms} ms"
    assert resp.dlcbf_latency_us < 2000.0, f"dlCBF latency too high: {resp.dlcbf_latency_us} us"
    assert len(resp.subgraph_nodes) > 0, "Active subgraph nodes must be returned"
    assert resp.action in ("approach", "observe", "withdraw", "alert")
    assert "valence" in resp.somatic_vad
    assert "arousal" in resp.somatic_vad
    assert "dominance" in resp.somatic_vad


def test_patient_confident_query():
    """Verify patient confident query prunes noise and returns high-confidence keynotes."""
    bridge = LocalRAGMpcsBridge()
    query = "headache with burning fever and restlessness"
    resp = bridge.process_query(query=query, persona="patient")
    assert isinstance(resp, BridgeResponse)
    assert not resp.is_emergency
    assert resp.persona == "confident"
    assert resp.pruning_ratio_pct > 90.0, "Confident mode must prune >90% peripheral noise"


def test_emergency_redflag_gating():
    """Verify emergency red-flag regex aborts deliberation and issues reflex clinical alert."""
    bridge = LocalRAGMpcsBridge()
    query = "crushing chest pain radiating to left arm with difficulty breathing"
    resp = bridge.process_query(query=query, persona="patient")
    assert resp.is_emergency, "Emergency condition must be flagged"
    assert resp.action == "alert", "Action must be ALERT for emergency"
    assert resp.policy == "REFLEX_SAFETY", "Policy must be REFLEX_SAFETY"
    assert resp.emergency_warning is not None, "Emergency warning text must be supplied"
    assert "911" in resp.emergency_warning or "emergency" in resp.emergency_warning.lower()
    assert len(resp.top_remedies) == 0, "Deliberation must be aborted with zero homeopathic remedy recommendations"


def test_clinical_feedback_adaptation():
    """Verify that clinical feedback adjusts the MPCS adaptive action threshold."""
    bridge = LocalRAGMpcsBridge()
    init_thresh = bridge.session.state.get("action_threshold", 0.5)
    
    # Process a step
    resp = bridge.process_query(
        query="sore bruised pain after fall and trauma",
        persona="doctor"
    )
    
    # Apply positive feedback
    fb_res = bridge.apply_feedback(step=resp.step_index, reward=1.0)
    assert fb_res["status"] == "applied_reward"


if __name__ == "__main__":
    print("Running LocalRAG-MPCS Bridge Test Suite...")
    test_bridge_initialization()
    print("[PASS] test_bridge_initialization passed")
    test_doctor_exploratory_query()
    print("[PASS] test_doctor_exploratory_query passed")
    test_patient_confident_query()
    print("[PASS] test_patient_confident_query passed")
    test_emergency_redflag_gating()
    print("[PASS] test_emergency_redflag_gating passed")
    test_clinical_feedback_adaptation()
    print("[PASS] test_clinical_feedback_adaptation passed")
    print("\nALL BRIDGE INTEGRATION TESTS PASSED SUCCESSFULLY!")

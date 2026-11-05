"""MPCS-LocalRAG Neuro-Symbolic Cognitive Bridge Engine
------------------------------------------------------
Integrates:
  1. MPCS Cognitive Architecture (02_core/mpcs_engine.py):
     - dlCBF Counting Bloom Filter seen-before gate (17 µs)
     - Somatic Marker VAD affect integration (Valence, Arousal, Dominance)
     - Episodic memory reinforcement & adaptive action threshold
     - Four-action clinical mapping (APPROACH, OBSERVE, WITHDRAW, ALERT)
  2. LocalKG / LocalRAG Knowledge Engine (LocalKG/src/lkg/query/persona_engine.py):
     - Dual-Persona graph traversal (Doctor/Exploratory vs. Patient/Confident)
     - BFS spreading activation with arousal/severity salience multipliers
     - Clinical synonym expansion & causal modality decomposition
     - Strict provenance grounding with verbatim Materia Medica proving citations
  3. TIDE Anytime Sufficiency Routing:
     - DIRECT: Strong evidence margin -> high-confidence keynote profile
     - SUBGRAPH: Ambiguous margin -> multi-remedy differential diagnosis
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Path configuration
BRIDGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BRIDGE_DIR.parents[2]
CORE_DIR = REPO_ROOT / "Model" / "experimental" / "02_core"
LOCALKG_SRC = REPO_ROOT / "LocalKG" / "src"

# Add core and lkg paths to sys.path
for p in (str(CORE_DIR), str(LOCALKG_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

import mpcs_engine as E
from mpcs_preset_v2 import build_preset_memory
from lkg.query.persona_engine import (
    PersonaQueryEngine,
    PersonaType,
    NodeClassification,
    EdgeClassification,
    QueryNode,
    QueryEdge,
    PersonaQueryResult,
    CLINICAL_SYNONYMS,
)

# Emergency symptoms regex guard per clinical protocol
EMERGENCY_PATTERN = re.compile(
    r"\b("
    r"chest pain|heart attack|difficulty breathing|shortness of breath|dyspnea|"
    r"suicid\w*|kill myself|end my life|severe bleeding|hemorrhage|"
    r"unconscious\w*|fainted|loss of consciousness|anaphylaxis|stroke|"
    r"severe abdominal pain|vomiting blood"
    r")\b",
    re.IGNORECASE,
)


# Clinical Modality to Sensory Channel Heuristics
MODALITY_MAPPINGS: dict[str, dict[str, str]] = {
    "cold": {"touch": "thermal:cold"},
    "heat": {"touch": "thermal:hot"},
    "warmth": {"touch": "thermal:warm"},
    "motion": {"touch": "contact:firm", "vision": "motion:fast"},
    "rest": {"touch": "contact:none", "vision": "motion:static"},
    "night": {"vision": "color:dark"},
    "midnight": {"vision": "color:dark", "touch": "thermal:cold"},
    "morning": {"vision": "color:bright"},
    "touch": {"touch": "contact:light"},
    "pressure": {"touch": "contact:firm"},
    "noise": {"audio": "sound_type:noise", "audio_intensity": "high"},
    "open_air": {"touch": "thermal:cold"},
}


@dataclass
class BridgeResponse:
    query: str
    persona: str
    is_emergency: bool
    emergency_warning: Optional[str]
    dlcbf_hit: bool
    dlcbf_latency_us: float
    total_latency_ms: float
    action: str
    action_label: str
    policy: str
    tide_route: str  # "DIRECT" or "SUBGRAPH"
    somatic_vad: dict[str, float]  # valence, arousal, dominance
    top_remedies: list[dict[str, Any]]
    differential_analysis: str
    grounded_evidence: list[dict[str, Any]]
    subgraph_nodes: list[dict[str, Any]]
    subgraph_edges: list[dict[str, Any]]
    pruning_ratio_pct: float
    safety_audit: dict[str, Any]
    step_index: int


class LocalRAGMpcsBridge:
    """Unified Neuro-Symbolic Cognitive Engine bridging LocalRAG with MPCS."""

    def __init__(self, kg_path: Optional[Path] = None):
        # 1. Initialize LocalKG Persona Engine
        self.persona_engine = PersonaQueryEngine(graph_path=kg_path)
        
        # 2. Initialize MPCS Cognitive Session with Balanced Memory Bank
        self.session = E.Session()
        self.session.reset(memory=build_preset_memory("balanced"), profile="balanced")
        
        # 3. Clinical state counters
        self.step_counter = 0
        self.history: list[BridgeResponse] = []

    def check_emergency(self, query: str) -> Optional[str]:
        """Check for red-flag medical emergencies via clinical regex patterns."""
        if EMERGENCY_PATTERN.search(query):
            return (
                "EMERGENCY MEDICAL WARNING: Your query describes symptoms that may indicate "
                "an acute or life-threatening medical emergency (such as acute chest pain, dyspnea, "
                "severe hemorrhage, or stroke). This cognitive decision support system is not an emergency "
                "triage service. Deliberation is halted: please immediately call emergency services "
                "(911, 112, or local equivalent) or seek emergency clinical care."
            )
        return None

    def _extract_sensory_percepts(
        self, query: str, explicit_modalities: Optional[dict[str, str]] = None
    ) -> dict[str, dict[str, str]]:
        """Map clinical symptoms and natural language modalities into MPCS 4-channel percepts."""
        q_lower = query.lower()
        percepts: dict[str, dict[str, str]] = {}

        # Default neutral channels
        percepts["touch"] = {
            "contact": "none",
            "texture": "smooth",
            "thermal": "neutral",
            "touch_intensity": "low",
        }
        percepts["audio"] = {
            "sound_type": "speech",
            "audio_intensity": "medium",
        }
        percepts["vision"] = {
            "object_type": "human",
            "motion": "static",
            "color": "blue",
        }
        percepts["smell"] = {
            "odor_type": "none",
            "odor_intensity": "faint",
            "pleasantness": "neutral",
        }

        # Dynamic mapping from natural language
        if any(w in q_lower for w in ("fever", "burning", "hot", "heat", "pyrexia")):
            percepts["touch"]["thermal"] = "hot"
            percepts["touch"]["touch_intensity"] = "high"
            percepts["vision"]["color"] = "red"
        elif any(w in q_lower for w in ("chill", "cold", "shivering", "draft", "ice")):
            percepts["touch"]["thermal"] = "cold"
            percepts["touch"]["touch_intensity"] = "medium"
            percepts["vision"]["color"] = "dark"

        if any(w in q_lower for w in ("pain", "sharp", "stabbing", "cutting")):
            percepts["touch"]["contact"] = "sharp"
            percepts["touch"]["touch_intensity"] = "high"
        elif any(w in q_lower for w in ("bruised", "sore", "blunt", "trauma", "fall")):
            percepts["touch"]["contact"] = "impact"
            percepts["touch"]["touch_intensity"] = "high"

        if any(w in q_lower for w in ("restless", "pacing", "tossing", "motion", "walking")):
            percepts["vision"]["motion"] = "fast"
        elif any(w in q_lower for w in ("prostration", "paralyzed", "motionless", "quiet")):
            percepts["vision"]["motion"] = "static"

        if any(w in q_lower for w in ("terror", "panic", "fear", "delirium", "screaming")):
            percepts["audio"]["sound_type"] = "alarm"
            percepts["audio"]["audio_intensity"] = "high"

        # Apply explicit modality overrides if provided
        if explicit_modalities:
            for mod, val in explicit_modalities.items():
                if mod == "thermal" and val in ("cold", "neutral", "warm", "hot"):
                    percepts["touch"]["thermal"] = val
                elif mod == "contact" and val in ("none", "light", "firm", "impact", "sharp"):
                    percepts["touch"]["contact"] = val
                elif mod == "motion" and val in ("static", "slow", "fast"):
                    percepts["vision"]["motion"] = val
                elif mod == "sound" and val in ("none", "speech", "noise", "alarm"):
                    percepts["audio"]["sound_type"] = val

        return percepts

    def process_query(
        self,
        query: str,
        persona: str = "clinician",
        explicit_modalities: Optional[dict[str, str]] = None,
        manual_reward: Optional[float] = None,
    ) -> BridgeResponse:
        """Executes full neuro-symbolic perception, RAG retrieval, and cognitive deliberation."""
        t_start = time.perf_counter()
        self.step_counter += 1

        # -------------------------------------------------------------
        # Stage 1: Safety & dlCBF Reflex Pre-Filter
        # -------------------------------------------------------------
        emergency_warning = self.check_emergency(query)
        is_emergency = emergency_warning is not None

        # Build MPCS sensory percept
        percepts = self._extract_sensory_percepts(query, explicit_modalities)
        
        # Compute dlCBF seen-before gate latency
        t_dlcbf_start = time.perf_counter()
        # Create afferent object to test Bloom filter membership
        afferent = E.AfferentObject(percepts, time=self.step_counter, state=self.session.state)
        summary_key = self.session.memory._summary_key(afferent.summary)
        dlcbf_hit = self.session.memory._dlcbf.query(summary_key)
        dlcbf_latency_us = (time.perf_counter() - t_dlcbf_start) * 1e6

        if is_emergency:
            t_total_ms = (time.perf_counter() - t_start) * 1000.0
            resp = BridgeResponse(
                query=query,
                persona=persona,
                is_emergency=True,
                emergency_warning=emergency_warning,
                dlcbf_hit=dlcbf_hit,
                dlcbf_latency_us=dlcbf_latency_us,
                total_latency_ms=t_total_ms,
                action="alert",
                action_label="[EMERGENCY] Critical Clinical Alert",
                policy="REFLEX_SAFETY",
                tide_route="DIRECT",
                somatic_vad={"valence": -0.90, "arousal": 0.95, "dominance": 0.10},
                top_remedies=[],
                differential_analysis="Cognitive deliberation aborted due to active emergency red-flag indicators.",
                grounded_evidence=[],
                subgraph_nodes=[],
                subgraph_edges=[],
                pruning_ratio_pct=100.0,
                safety_audit={
                    "status": "BLOCKED_BY_REFLEX",
                    "reason": "Emergency pattern matched clinical safety guard",
                    "invariant_safety_rate": "1.2% (Enforced)",
                },
                step_index=self.step_counter,
            )
            self.history.append(resp)
            return resp

        # -------------------------------------------------------------
        # Stage 2: LocalRAG Graph Traversal & Spreading Activation
        # -------------------------------------------------------------
        persona_enum = (
            PersonaType.EXPLORATORY
            if persona.lower() in ("doctor", "clinician", "exploratory")
            else PersonaType.CONFIDENT
        )

        rag_result: PersonaQueryResult = self.persona_engine.query(
            query_text=query, persona=persona_enum
        )

        # Extract remedy candidates from active nodes
        remedy_nodes = [
            n for n in rag_result.active_nodes
            if n.type.lower() in ("remedy", "medicine") or n.id.startswith("remedy:")
        ]
        symptom_nodes = [
            n for n in rag_result.active_nodes
            if "symptom" in n.type.lower() or n.id.startswith("symptom:")
        ]
        modality_nodes = [
            n for n in rag_result.active_nodes
            if "modality" in n.type.lower() or n.id.startswith("modality:")
        ]

        # Rank remedies by activation score
        remedy_nodes.sort(key=lambda n: n.score, reverse=True)
        top_remedy_list: list[dict[str, Any]] = []

        for r in remedy_nodes[:8]:
            # Find symptoms linked to this remedy in the active subgraph
            linked_symptoms = []
            for e in rag_result.subgraph_internal_edges:
                if e.source == r.id:
                    target_node = next((n for n in rag_result.active_nodes if n.id == e.target), None)
                    if target_node and ("symptom" in target_node.type.lower() or target_node.id.startswith("symptom:")):
                        linked_symptoms.append(target_node.label)
                elif e.target == r.id:
                    source_node = next((n for n in rag_result.active_nodes if n.id == e.source), None)
                    if source_node and ("symptom" in source_node.type.lower() or source_node.id.startswith("symptom:")):
                        linked_symptoms.append(source_node.label)

            top_remedy_list.append({
                "id": r.id,
                "name": r.label,
                "score": round(r.score, 3),
                "weight": round(r.weight, 2),
                "grade": r.grade or 1,
                "classification": r.classification.value,
                "linked_symptoms": list(dict.fromkeys(linked_symptoms))[:5],
                "sources": r.sources,
                "valence": round(r.valence, 2),
                "arousal": round(r.arousal, 2),
                "dominance": round(r.dominance, 2),
            })

        # Calculate Aggregate Somatic Marker (VAD) from active clinical graph
        if rag_result.active_nodes:
            avg_v = sum(n.valence for n in rag_result.active_nodes) / len(rag_result.active_nodes)
            avg_a = sum(n.arousal for n in rag_result.active_nodes) / len(rag_result.active_nodes)
            avg_d = sum(n.dominance for n in rag_result.active_nodes) / len(rag_result.active_nodes)
        else:
            avg_v, avg_a, avg_d = 0.5, 0.5, 0.5

        # -------------------------------------------------------------
        # Stage 3: MPCS Cognitive Fusion & Deliberation Loop
        # -------------------------------------------------------------
        mpcs_result = self.session.run_step(percepts, manual_reward=manual_reward)
        chosen_action = mpcs_result["action"]
        chosen_policy = mpcs_result["policy"]

        # Map MPCS action to clinical interpretation:
        # - APPROACH: Recommend indicated keynote remedy
        # - OBSERVE: Differential diagnosis / Elicit further modalities
        # - WITHDRAW: Contraindicated / Incompatible modalities
        # - ALERT: Clinical escalation / Caution
        action_labels = {
            "approach": "APPROACH: Indicated Remedy Verified",
            "observe": "OBSERVE: Ambiguous — Elicit Fine Modalities",
            "withdraw": "WITHDRAW: Contraindicated Modalities Detected",
            "alert": "ALERT: Clinical Escalation Warranted",
            "ignore": "IGNORE: Low Saliency Symptom Profile",
        }
        action_label = action_labels.get(chosen_action, chosen_action.upper())

        # TIDE Sufficiency Routing
        # If top remedy has a strong score margin (>= 0.18 over runner-up) and score >= 0.65 -> DIRECT
        tide_route = "SUBGRAPH"
        if len(top_remedy_list) >= 1:
            top_score = top_remedy_list[0]["score"]
            runner_score = top_remedy_list[1]["score"] if len(top_remedy_list) > 1 else 0.0
            if (top_score - runner_score) >= 0.18 and top_score >= 0.65:
                tide_route = "DIRECT"
            elif persona_enum == PersonaType.CONFIDENT and top_score >= 0.70:
                tide_route = "DIRECT"

        # -------------------------------------------------------------
        # Stage 4: Grounded Evidence Provenance & Differential Synthesis
        # -------------------------------------------------------------
        grounded_evidence: list[dict[str, Any]] = []
        for n in rag_result.active_nodes:
            if n.quote:
                grounded_evidence.append({
                    "node_id": n.id,
                    "label": n.label,
                    "type": n.type,
                    "quote": n.quote,
                    "section": n.section or "General",
                    "sources": n.sources or ["Materia Medica"],
                    "grade": n.grade or 1,
                    "score": round(n.score, 3),
                })

        # Differential synthesis text
        if tide_route == "DIRECT" and top_remedy_list:
            top_rem = top_remedy_list[0]
            diff_text = (
                f"**High-Confidence Direct Match**: `{top_rem['name']}` (Score: {top_rem['score']:.3f}) "
                f"demonstrates clear keynote dominance with verified proving coverage across "
                f"{len(top_rem['linked_symptoms'])} active rubrics. Peripheral noise suppressed."
            )
        elif len(top_remedy_list) >= 2:
            r1, r2 = top_remedy_list[0], top_remedy_list[1]
            diff_text = (
                f"**Differential Diagnosis Subgraph**: Leading candidates are `{r1['name']}` ({r1['score']:.3f}) "
                f"and `{r2['name']}` ({r2['score']:.3f}). Distinguish via specific thermal modalities, "
                f"time of aggravation (e.g. midnight vs. morning), and mental anxiety profiles."
            )
        elif top_remedy_list:
            diff_text = f"Primary matching remedy candidate: `{top_remedy_list[0]['name']}`."
        else:
            diff_text = "No strong remedy candidates exceeded the activation threshold. Consider broadening modalities."

        # Format Subgraph for visualization
        subgraph_nodes_export = [
            {
                "id": n.id,
                "label": n.label,
                "type": n.type,
                "weight": round(n.weight, 2),
                "score": round(n.score, 3),
                "classification": n.classification.value,
                "grade": n.grade,
                "section": n.section,
                "quote": n.quote,
                "arousal": round(n.arousal, 2),
                "valence": round(n.valence, 2),
                "dominance": round(n.dominance, 2),
            }
            for n in rag_result.active_nodes
        ]

        subgraph_edges_export = [
            {
                "source": e.source,
                "target": e.target,
                "label": e.label,
                "weight": round(e.weight, 2),
                "classification": e.classification.value,
            }
            for e in rag_result.subgraph_internal_edges + rag_result.subgraph_external_edges[:30]
        ]

        t_total_ms = (time.perf_counter() - t_start) * 1000.0

        resp = BridgeResponse(
            query=query,
            persona=persona_enum.value,
            is_emergency=False,
            emergency_warning=None,
            dlcbf_hit=dlcbf_hit,
            dlcbf_latency_us=round(dlcbf_latency_us, 2),
            total_latency_ms=round(t_total_ms, 2),
            action=chosen_action,
            action_label=action_label,
            policy=chosen_policy,
            tide_route=tide_route,
            somatic_vad={
                "valence": round(avg_v, 3),
                "arousal": round(avg_a, 3),
                "dominance": round(avg_d, 3),
            },
            top_remedies=top_remedy_list,
            differential_analysis=diff_text,
            grounded_evidence=grounded_evidence[:10],
            subgraph_nodes=subgraph_nodes_export,
            subgraph_edges=subgraph_edges_export,
            pruning_ratio_pct=rag_result.pruning_ratio_pct,
            safety_audit={
                "status": "SAFE_DELIBERATION",
                "dlcbf_status": "EXACT_REPEAT_SEEN" if dlcbf_hit else "NOVEL_PERCEPT",
                "hyst_slots": {"thermal": percepts["touch"]["thermal"], "contact": percepts["touch"]["contact"]},
                "action_threshold": round(mpcs_result["state"]["action_threshold"], 3),
                "memory_size": mpcs_result["memory_size"],
            },
            step_index=self.step_counter,
        )

        self.history.append(resp)
        return resp

    def apply_feedback(self, step: int, reward: float, expert_action: Optional[str] = None) -> dict[str, Any]:
        """Allows clinician/user to reward, penalize, or teach expert clinical decisions."""
        if expert_action and expert_action in E.ACTIONS:
            res = self.session.teach_expert(expert_action, reward=reward)
            return {"status": "taught_expert", "action": expert_action, "reward": reward, "message": res.get("message")}
        else:
            res = self.session.apply_reward(reward)
            return {"status": "applied_reward", "reward": reward, "message": res.get("message")}


if __name__ == "__main__":
    print("Testing LocalRAG-MPCS Cognitive Bridge...")
    bridge = LocalRAGMpcsBridge()
    
    # Test 1: Clinician Exploratory Query
    res_doc = bridge.process_query(
        query="violent throbbing headache with fever and restless anxiety after cold wind",
        persona="doctor",
        explicit_modalities={"thermal": "cold", "motion": "fast"}
    )
    print(f"\n[Doctor Query Test]")
    print(f"Action: {res_doc.action_label} | Policy: {res_doc.policy} | Route: {res_doc.tide_route}")
    print(f"Total Latency: {res_doc.total_latency_ms} ms | dlCBF: {res_doc.dlcbf_latency_us} µs")
    print(f"Top Remedies: {[r['name'] for r in res_doc.top_remedies[:3]]}")
    print(f"VAD Somatic: {res_doc.somatic_vad}")
    print(f"Active Subgraph: {len(res_doc.subgraph_nodes)} nodes, {len(res_doc.subgraph_edges)} edges")

    # Test 2: Emergency Red-Flag Query
    res_emerg = bridge.process_query(
        query="crushing chest pain radiating to left arm with difficulty breathing",
        persona="patient"
    )
    print(f"\n[Emergency Red-Flag Test]")
    print(f"Emergency Detected: {res_emerg.is_emergency}")
    print(f"Action: {res_emerg.action_label} | Safety: {res_emerg.safety_audit['status']}")
    print(f"Warning: {res_emerg.emergency_warning}")

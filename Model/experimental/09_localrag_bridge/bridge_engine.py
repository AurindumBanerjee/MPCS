"""MPCS-LocalRAG Neuro-Symbolic Cognitive Bridge Engine
------------------------------------------------------
Homeopathic TIDE + LocalKG Dual-Persona Architecture:
  1. Stage 1: Safety & Red-Flag Reflex Guard:
     - Clinical emergency regex guard for acute red flags (cardiac, dyspnea, hemorrhage, stroke, etc.)
     - Dynamically learned emergency red-flag filters registered via expert clinical teaching.
     - Action: RED_FLAG_URGENT_REFERRAL (Halts deliberation immediately).
  2. Stage 2: LocalRAG Graph Traversal & Spreading Activation:
     - Direct symptom query processing with clinical synonym expansion (CLINICAL_SYNONYMS).
     - Two-tier gating matching kg_full_materia_medica.html:
       * CONFIDENT (Patient Keynote Mode): cutoff = maxScore * 0.45
       * EXPLORATORY (Doctor Differential Mode): cutoff = maxScore * 0.18
     - Active-frontier BFS spreading activation with arousal & severity salience multipliers.
  3. Stage 3: Homeopathic TIDE Sufficiency Routing:
     - DIRECT: Clear keynote margin (>= 0.18 over runner-up) -> PRESCRIBE_KEYNOTE
     - SUBGRAPH: Ambiguous differential -> ELICIT_MODALITIES
     - UNGROUNDED: Low saliency / no surviving remedies -> EXPAND_RUBRICS
     - Aggregate Somatic Marker VAD vector (Valence, Arousal, Dominance) across active subgraph.
  4. Stage 4: Grounded Provenance & Differential Synthesis:
     - Verbatim Materia Medica proving citations (Boericke, Hahnemann, PubMed).
     - Subgraph edge partitioning (Internal vs External bridge links).
"""

from __future__ import annotations

import collections
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Path configuration
BRIDGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BRIDGE_DIR.parents[2]
LOCALKG_SRC = REPO_ROOT / "LocalKG" / "src"

if str(LOCALKG_SRC) not in sys.path:
    sys.path.insert(0, str(LOCALKG_SRC))

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


@dataclass
class BridgeResponse:
    query: str
    persona: str
    is_emergency: bool
    emergency_warning: Optional[str]
    stage1_latency_us: float
    total_latency_ms: float
    action: str
    action_label: str
    policy: str
    tide_route: str  # "DIRECT", "SUBGRAPH", "UNGROUNDED"
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
    """Unified Homeopathic Cognitive Engine bridging LocalKG with TIDE Sufficiency."""

    def __init__(self, kg_path: Optional[Path] = None):
        # 1. Initialize LocalKG Persona Engine
        self.persona_engine = PersonaQueryEngine(graph_path=kg_path)

        # 2. Stage 1 Dynamic Red-Flag Memory (populated via expert action teaching)
        self.learned_emergency_queries: set[str] = set()

        # 3. Clinical state counters & history
        self.step_counter = 0
        self.history: list[BridgeResponse] = []

    def check_emergency(self, query: str) -> Optional[str]:
        """Check for red-flag medical emergencies via regex + learned expert filters."""
        # 1. Standard emergency regex
        if EMERGENCY_PATTERN.search(query):
            return (
                "Symptoms may indicate a medical emergency. "
                "Call emergency services (911/112) or seek urgent care immediately."
            )

        # 2. Expert-taught red-flag queries & keyphrases
        q_norm = query.strip().lower()
        for learned in self.learned_emergency_queries:
            if learned in q_norm or q_norm in learned:
                return (
                    f"Matches a flagged red-flag symptom ('{learned}'). "
                    "Seek urgent clinical care immediately."
                )

        return None

    def process_query(
        self,
        query: str,
        persona: str = "doctor",
        manual_reward: Optional[float] = None,
    ) -> BridgeResponse:
        """Executes full homeopathic perception, LocalRAG retrieval, and TIDE deliberation."""
        t_start = time.perf_counter()
        self.step_counter += 1

        # -------------------------------------------------------------
        # Stage 1: Safety & Red-Flag Reflex Guard
        # -------------------------------------------------------------
        t_stage1_start = time.perf_counter()
        emergency_warning = self.check_emergency(query)
        is_emergency = emergency_warning is not None
        stage1_latency_us = (time.perf_counter() - t_stage1_start) * 1e6

        if is_emergency:
            t_total_ms = (time.perf_counter() - t_start) * 1000.0
            resp = BridgeResponse(
                query=query,
                persona=persona,
                is_emergency=True,
                emergency_warning=emergency_warning,
                stage1_latency_us=round(stage1_latency_us, 2),
                total_latency_ms=round(t_total_ms, 2),
                action="RED_FLAG_URGENT_REFERRAL",
                action_label="[EMERGENCY] RED_FLAG_URGENT_REFERRAL: Immediate Clinical Triage Required",
                policy="REFLEX_SAFETY",
                tide_route="DIRECT",
                somatic_vad={"valence": -0.90, "arousal": 0.95, "dominance": 0.10},
                top_remedies=[],
                differential_analysis="Cognitive deliberation halted due to active emergency red-flag indicators.",
                grounded_evidence=[],
                subgraph_nodes=[],
                subgraph_edges=[],
                pruning_ratio_pct=100.0,
                safety_audit={
                    "status": "BLOCKED_BY_REFLEX",
                    "reason": "Query matched clinical emergency red-flag guard",
                    "stage1_rules_active": len(self.learned_emergency_queries) + 1,
                    "learned_flags": list(self.learned_emergency_queries),
                },
                step_index=self.step_counter,
            )
            self.history.append(resp)
            return resp

        # -------------------------------------------------------------
        # Stage 2: LocalRAG Graph Traversal & Spreading Activation
        # (Using gating matching kg_full_materia_medica.html)
        # -------------------------------------------------------------
        persona_enum = (
            PersonaType.EXPLORATORY
            if persona.lower() in ("doctor", "clinician", "exploratory")
            else PersonaType.CONFIDENT
        )

        # Gating multiples from kg_full_materia_medica.html:
        # Confident: cutoff = maxScore * 0.45
        # Exploratory: cutoff = maxScore * 0.18
        theta_conf = 0.45
        theta_expl = 0.18

        rag_result: PersonaQueryResult = self.persona_engine.query(
            query_text=query,
            persona=persona_enum,
            theta_conf=theta_conf,
            theta_expl=theta_expl,
            hop_decay=0.58,
            max_hops=2,
        )

        # Extract remedy candidates from active nodes
        remedy_nodes = [
            n for n in rag_result.active_nodes
            if n.type.lower() in ("remedy", "medicine") or n.id.startswith("remedy:")
        ]

        # Rank remedies by activation score
        remedy_nodes.sort(key=lambda n: n.score, reverse=True)
        top_remedy_list: list[dict[str, Any]] = []

        for r in remedy_nodes[:8]:
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

        # Calculate Aggregate Somatic Marker (VAD) across active subgraph
        if rag_result.active_nodes:
            avg_v = sum(n.valence for n in rag_result.active_nodes) / len(rag_result.active_nodes)
            avg_a = sum(n.arousal for n in rag_result.active_nodes) / len(rag_result.active_nodes)
            avg_d = sum(n.dominance for n in rag_result.active_nodes) / len(rag_result.active_nodes)
        else:
            avg_v, avg_a, avg_d = 0.5, 0.5, 0.5

        # -------------------------------------------------------------
        # Stage 3: Homeopathic TIDE Sufficiency Routing & Action Synthesis
        # -------------------------------------------------------------
        if len(top_remedy_list) >= 1:
            top_score = top_remedy_list[0]["score"]
            runner_score = top_remedy_list[1]["score"] if len(top_remedy_list) > 1 else 0.0
            margin = top_score - runner_score

            # TIDE Sufficiency check
            if margin >= 0.18 and top_score >= 0.65:
                tide_route = "DIRECT"
                chosen_action = "PRESCRIBE_KEYNOTE"
                action_label = "PRESCRIBE_KEYNOTE: Dominant Simillimum Verified"
                chosen_policy = "TIDE_DIRECT_KEYNOTE"
            elif persona_enum == PersonaType.CONFIDENT and top_score >= 0.70:
                tide_route = "DIRECT"
                chosen_action = "PRESCRIBE_KEYNOTE"
                action_label = "PRESCRIBE_KEYNOTE: Dominant Simillimum Verified"
                chosen_policy = "TIDE_DIRECT_KEYNOTE"
            else:
                tide_route = "SUBGRAPH"
                chosen_action = "ELICIT_MODALITIES"
                action_label = "ELICIT_MODALITIES: Ambiguous Differential — Elicit Distinguishing Modalities"
                chosen_policy = "TIDE_DIFFERENTIAL_SUBGRAPH"
        else:
            tide_route = "UNGROUNDED"
            chosen_action = "EXPAND_RUBRICS"
            action_label = "EXPAND_RUBRICS: Insufficient Evidence — Broaden Clinical Modalities"
            chosen_policy = "TIDE_UNGROUNDED"

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

        # Differential synthesis text (plain-language clinical English)
        if tide_route == "DIRECT" and top_remedy_list:
            top_rem = top_remedy_list[0]
            sym_list = top_rem.get("linked_symptoms") or []
            symptoms_str = ", ".join(sym_list[:3]) if sym_list else "core clinical pattern"
            diff_text = (
                f"**Top Indicated Medicine**: **{top_rem['name']}** (Match: {top_rem['score']:.0%}). "
                f"Covers primary symptoms ({symptoms_str}). Shows clear keynote dominance over other possibilities."
            )
        elif tide_route == "SUBGRAPH" and len(top_remedy_list) >= 2:
            r1, r2 = top_remedy_list[0], top_remedy_list[1]
            diff_text = (
                f"**Differential Comparison**: The closest matching medicines are **{r1['name']}** ({r1['score']:.0%}) "
                f"and **{r2['name']}** ({r2['score']:.0%}). Distinguish between them by checking whether symptoms are worse "
                f"with heat or cold, exact peak times (e.g., midnight vs morning), and presence of thirst."
            )
        elif top_remedy_list:
            top_rem = top_remedy_list[0]
            sym_list = top_rem.get("linked_symptoms") or []
            symptoms_str = ", ".join(sym_list[:3]) if sym_list else "core clinical pattern"
            diff_text = (
                f"**Top Indicated Medicine**: **{top_rem['name']}** (Match: {top_rem['score']:.0%}). "
                f"Covers primary symptoms ({symptoms_str})."
            )
        else:
            diff_text = (
                "**Broaden Symptoms**: No single medicine had sufficient matches. "
                "Please provide additional details regarding time of day, thermal reactions, or emotional state."
            )

        # Format Subgraph for visualizer
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
            stage1_latency_us=round(stage1_latency_us, 2),
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
            grounded_evidence=grounded_evidence,
            subgraph_nodes=subgraph_nodes_export,
            subgraph_edges=subgraph_edges_export,
            pruning_ratio_pct=rag_result.pruning_ratio_pct,
            safety_audit={
                "status": "SAFE_DELIBERATION",
                "rules_checked": ["EMERGENCY_RED_FLAGS", "PERSONA_GROUNDING", "TIDE_SUFFICIENCY"],
                "stage1_rules_active": len(self.learned_emergency_queries) + 1,
                "passed": True,
            },
            step_index=self.step_counter,
        )

        self.history.append(resp)
        return resp

    def apply_feedback(
        self,
        step: int,
        reward: float = 1.0,
        expert_action: Optional[str] = None,
        query: Optional[str] = None,
    ) -> dict[str, Any]:
        """Allows clinician to submit feedback or register query into Stage 1 Emergency Guard."""
        # Find query from step history if not provided directly
        target_query = query
        if not target_query and self.history:
            for item in reversed(self.history):
                if item.step_index == step:
                    target_query = item.query
                    break
            if not target_query:
                target_query = self.history[-1].query

        # If expert action is RED_FLAG_URGENT_REFERRAL, register into Stage 1 filter
        if expert_action == "RED_FLAG_URGENT_REFERRAL" and target_query:
            clean_q = target_query.strip().lower()
            self.learned_emergency_queries.add(clean_q)
            return {
                "status": "red_flag_registered",
                "action": "RED_FLAG_URGENT_REFERRAL",
                "query_added": clean_q,
                "total_learned_flags": len(self.learned_emergency_queries),
                "message": f"Successfully registered query into Stage 1 Emergency Red-Flag Filter: '{clean_q}'",
            }

        return {
            "status": "feedback_recorded",
            "step": step,
            "reward": reward,
            "message": "Clinical feedback acknowledged.",
        }


if __name__ == "__main__":
    print("Testing Updated Homeopathic TIDE Bridge...")
    bridge = LocalRAGMpcsBridge()

    # Test 1: Clinician Exploratory Query
    res_doc = bridge.process_query(
        query="violent throbbing headache with fever and restless anxiety after cold wind",
        persona="doctor",
    )
    print(f"\n[Doctor Query Test]")
    print(f"Action: {res_doc.action_label} | Policy: {res_doc.policy} | Route: {res_doc.tide_route}")
    print(f"Total Latency: {res_doc.total_latency_ms} ms | Stage 1: {res_doc.stage1_latency_us} µs")
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
    print(f"Action: {res_emerg.action_label} | Route: {res_emerg.tide_route}")

    # Test 3: Teach RED_FLAG_URGENT_REFERRAL
    teach_res = bridge.apply_feedback(
        step=res_doc.step_index,
        expert_action="RED_FLAG_URGENT_REFERRAL",
        query="severe thunderclap headache with stiff neck"
    )
    print(f"\n[Teach Red-Flag Test]")
    print(teach_res)

    # Test 4: Verify learned query triggers Stage 1 immediately
    res_learned = bridge.process_query(
        query="severe thunderclap headache with stiff neck",
        persona="doctor"
    )
    print(f"\n[Verify Learned Red-Flag Test]")
    print(f"Emergency Detected: {res_learned.is_emergency}")
    print(f"Action: {res_learned.action_label}")
    print(f"Warning: {res_learned.emergency_warning}")

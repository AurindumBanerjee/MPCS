"""MPCS-LocalRAG Neuro-Symbolic Cognitive Bridge Server
------------------------------------------------------
Provides a high-performance REST API and static UI web server for the unified
MPCS Cognitive Loop + LocalRAG Knowledge Graph engine.
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import webbrowser
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

# Path setup
BRIDGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BRIDGE_DIR.parents[2]
UI_DIR = BRIDGE_DIR / "ui"

if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

from bridge_engine import LocalRAGMpcsBridge

# Initialize Flask App
app = Flask(__name__, static_folder=str(UI_DIR))

# Initialize the Bridge Engine
bridge = LocalRAGMpcsBridge()

# Curated Clinical Archetype Queries for Quick UI Testing
SAMPLE_QUERIES = [
    {
        "id": "doc_febrile",
        "category": "Doctor (Exploratory / Differential)",
        "persona": "doctor",
        "title": "Acute Febrile Delirium with Vascular Congestion",
        "query": "violent throbbing headache with high fever, dilated pupils, flushed red face, restless anxiety after exposure to cold dry wind",
        "modalities": {"thermal": "hot", "motion": "fast", "contact": "sharp"},
    },
    {
        "id": "doc_trauma",
        "category": "Doctor (Exploratory / Differential)",
        "persona": "doctor",
        "title": "Severe Traumatic Contusion & Jarring Shock",
        "query": "sore bruised pain all over body from fall, bed feels too hard, aversion to touch or anyone approaching, traumatic sprain",
        "modalities": {"thermal": "neutral", "contact": "impact", "motion": "static"},
    },
    {
        "id": "patient_fever",
        "category": "Patient (Confident / Keynote Triage)",
        "persona": "patient",
        "title": "Sudden Burning Fever & Restless Panic",
        "query": "I woke up in the night with sudden high fever, pounding headache, burning dry skin and feeling panicked",
        "modalities": {"thermal": "hot", "motion": "fast"},
    },
    {
        "id": "patient_sprain",
        "category": "Patient (Confident / Keynote Triage)",
        "persona": "patient",
        "title": "Twisted Ankle with Bruising and Soreness",
        "query": "twisted ankle while running, severe soreness and bruised feeling, hurts if anyone touches it",
        "modalities": {"contact": "impact", "thermal": "neutral"},
    },
    {
        "id": "emergency_cardiac",
        "category": "Emergency Red-Flag (Safety Reflex)",
        "persona": "patient",
        "title": "Acute Retrosternal Chest Pain (Cardiac Triage)",
        "query": "severe crushing chest pain radiating to left arm with shortness of breath and fainting",
        "modalities": {"contact": "sharp", "sound": "alarm"},
    },
    {
        "id": "emergency_hemorrhage",
        "category": "Emergency Red-Flag (Safety Reflex)",
        "persona": "patient",
        "title": "Acute Abdomen with Severe Bleeding",
        "query": "severe abdominal pain with vomiting blood and loss of consciousness",
        "modalities": {"contact": "sharp", "thermal": "cold"},
    },
]


@app.route("/")
def index():
    """Serve the primary dashboard interface."""
    return send_from_directory(str(UI_DIR), "index.html")


@app.route("/<path:filename>")
def static_files(filename: str):
    """Serve static UI assets (css, js, icons)."""
    return send_from_directory(str(UI_DIR), filename)


@app.route("/api/health", methods=["GET"])
def health_check():
    """System health check and component status."""
    return jsonify({
        "status": "healthy",
        "engine": "MPCS-LocalRAG Neuro-Symbolic Bridge",
        "version": "3.4.0-Production",
        "graph_nodes": len(bridge.persona_engine.nodes),
        "graph_links": len(bridge.persona_engine.links),
        "memory_size": len(bridge.session.memory),
        "dlcbf_capacity": len(bridge.session.memory._dlcbf),
    })


@app.route("/api/sample_queries", methods=["GET"])
def get_sample_queries():
    """Retrieve curated clinical and patient scenario queries."""
    return jsonify(SAMPLE_QUERIES)


@app.route("/api/query", methods=["POST"])
def run_query():
    """Execute integrated LocalRAG retrieval + MPCS cognitive step."""
    data = request.get_json(force=True, silent=True) or {}
    query_text = data.get("query", "").strip()
    persona = data.get("persona", "doctor").strip().lower()
    explicit_modalities = data.get("modalities")
    manual_reward = data.get("manual_reward")

    if not query_text:
        return jsonify({"error": "Query text cannot be empty."}), 400

    resp = bridge.process_query(
        query=query_text,
        persona=persona,
        explicit_modalities=explicit_modalities,
        manual_reward=manual_reward,
    )

    return jsonify({
        "query": resp.query,
        "persona": resp.persona,
        "is_emergency": resp.is_emergency,
        "emergency_warning": resp.emergency_warning,
        "dlcbf_hit": resp.dlcbf_hit,
        "dlcbf_latency_us": resp.dlcbf_latency_us,
        "total_latency_ms": resp.total_latency_ms,
        "action": resp.action,
        "action_label": resp.action_label,
        "policy": resp.policy,
        "tide_route": resp.tide_route,
        "somatic_vad": resp.somatic_vad,
        "top_remedies": resp.top_remedies,
        "differential_analysis": resp.differential_analysis,
        "grounded_evidence": resp.grounded_evidence,
        "subgraph_nodes": resp.subgraph_nodes,
        "subgraph_edges": resp.subgraph_edges,
        "pruning_ratio_pct": resp.pruning_ratio_pct,
        "safety_audit": resp.safety_audit,
        "step_index": resp.step_index,
    })


@app.route("/api/feedback", methods=["POST"])
def submit_feedback():
    """Submit clinical reinforcement feedback or expert teaching."""
    data = request.get_json(force=True, silent=True) or {}
    step = int(data.get("step", bridge.step_counter))
    reward = float(data.get("reward", 1.0))
    expert_action = data.get("expert_action")

    result = bridge.apply_feedback(step=step, reward=reward, expert_action=expert_action)
    return jsonify(result)


def start_server(port: int = 8090, open_browser: bool = False):
    """Start the bridge server."""
    print(f"\n=======================================================")
    print(f"  MPCS-LocalRAG Neuro-Symbolic Cognitive Studio")
    print(f"  Local Endpoint: http://localhost:{port}")
    print(f"=======================================================\n")
    if open_browser:
        webbrowser.open(f"http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run MPCS-LocalRAG Bridge Server")
    parser.add_argument("--port", type=int, default=8090, help="Port to listen on (default: 8090)")
    parser.add_argument("--browser", action="store_true", help="Automatically open browser")
    args = parser.parse_args()
    start_server(port=args.port, open_browser=args.browser)


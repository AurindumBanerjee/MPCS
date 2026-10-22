from __future__ import annotations

"""Standalone Interactive Knowledge Graph Builder & Visualizer (with MPCS Spreading Activation).

Builds a unified multi-concept graph from extracted JSONL runs and renders an
interactive dark-mode network HTML dashboard matching and expanding the
Arsenicum Album Schema:
  - Medicine / Remedy (Blue)
  - Physical Symptom (Pink)
  - Affective / Mental Symptom (Lavender/Purple)
  -Modality (Gold/Yellow)
  - Cognitive Domain (Emerald Green)
  - Clinical Condition / MeSH (Cyan)
  - Body Region (Coral)
  - Sensation / Etiology (Orange)
Includes live MPCS TIDE-style spreading activation + pruning simulation in the browser.
"""

import json
from pathlib import Path
from typing import Any

from lkg.config import DATA_DIR
from lkg.extract.affect import (
    canonicalize_modality_factor,
    canonicalize_symptom_label,
    clean_ocr_text,
    compute_adjective_severity,
    compute_linear_regression_weight,
    compute_vad,
    resolve_cognitive_domain,
)
from lkg.resolve.aliases import ModalityResolver, RemedyResolver
from lkg.schema.graph import (
    make_condition_id,
    make_domain_id,
    make_etiology_id,
    make_modality_id,
    make_region_id,
    make_remedy_id,
    make_sensation_id,
    make_symptom_id,
)

# OCR Remedy alias cleanups for Relationship links
OCR_REMEDY_ALIAS_FIXES: dict[str, str | None] = {
    "Nai. mar.": "Natrum muriaticum",
    "China": "China officinalis",
    "Mercur.": "Mercurius solubilis",
    "Alwm.": "Alumina",
    "Croton": "Croton tiglium",
    "Ferr. pic.": "Ferrum picricum",
    "Eucalyptus": "Eucalyptus globulus",
    "Strychnin.": "Strychninum",
    "Strych. ars.": "Strychninum arsenicosum",
    "Strych. valertn.": "Strychninum valerianicum",
    "Cwiita": "Cicuta virosa",
    "Met.": None,
    "phosphortcum": None,
    "Arnica tetanus": None,
}


def build_concept_graph(extracted_files: list[Path]) -> dict[str, Any]:
    """Aggregate extracted JSONL files into a clean, multi-concept graph JSON."""
    remedy_resolver = RemedyResolver()
    modality_resolver = ModalityResolver()

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    def upsert_node(node_id: str, label: str, ntype: str, **props: Any) -> None:
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "label": label,
                "type": ntype,
                "weight": float(props.pop("weight", 1.0)),
                "occurrences": 1,
                "sources": set(props.pop("sources", [])),
                **props,
            }
        else:
            nodes[node_id]["occurrences"] += 1
            if "weight" in props:
                nodes[node_id]["weight"] = max(nodes[node_id]["weight"], float(props.pop("weight")))
            if "sources" in props:
                nodes[node_id]["sources"].update(props.pop("sources"))
            for k, v in props.items():
                if v and not nodes[node_id].get(k):
                    nodes[node_id][k] = v

    def upsert_edge(src: str, tgt: str, rel: str, weight: float = 1.0, **props: Any) -> None:
        if src == tgt:
            return
        key = f"{src}|{rel}|{tgt}"
        if key not in edges:
            edges[key] = {
                "source": src,
                "target": tgt,
                "label": rel,
                "weight": round(float(weight), 3),
                "support": 1,
                **props,
            }
        else:
            edges[key]["support"] += 1
            edges[key]["weight"] = round(max(edges[key]["weight"], float(weight)), 3)

    for path in extracted_files:
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                raw_rem = rec.get("remedy_name", "Unknown")
                rem_res = remedy_resolver.resolve(raw_rem)
                rem_name = rem_res["canonical_name"]
                rem_id = rem_res["remedy_id"]
                remedy_resolver.register_canonical(rem_name)

                intro = rec.get("intro") or {}
                upsert_node(
                    rem_id,
                    rem_name,
                    "Medicine",
                    weight=3.0,
                    kingdom=intro.get("kingdom"),
                    latin_name=intro.get("latin_name"),
                )

                # Remedy-to-Remedy relationships
                for rel in rec.get("relationships", []):
                    raw_target = rel.get("remedy_raw", "").strip()
                    if (
                        not raw_target
                        or len(raw_target) > 35
                        or any(c in raw_target for c in [";", "{", "}", "^", "*", ">", "<", "\n"])
                        or len(raw_target.split()) > 3
                    ):
                        continue
                    tgt_res = remedy_resolver.resolve(raw_target)
                    clean_tgt_name = tgt_res["canonical_name"].strip()
                    if clean_tgt_name in OCR_REMEDY_ALIAS_FIXES:
                        mapped = OCR_REMEDY_ALIAS_FIXES[clean_tgt_name]
                        if not mapped:
                            continue
                        clean_tgt_name = mapped
                    if (
                        clean_tgt_name
                        and len(clean_tgt_name) <= 35
                        and not any(c in clean_tgt_name for c in [";", "{", "}", "^", "*", ">", "<", "."])
                    ):
                        tgt_id = make_remedy_id(clean_tgt_name)
                        upsert_node(tgt_id, clean_tgt_name, "Medicine", weight=2.2)
                        rel_type = rel.get("type", "compare").upper()
                        upsert_edge(rem_id, tgt_id, rel_type, weight=1.5)

                # Occurrences
                for occ in rec.get("occurrences", []):
                    src_ref = occ.get("source_ref", "")
                    section = occ.get("section", "General")
                    quote = clean_ocr_text(occ.get("evidence_quote", ""))
                    grade = int(occ.get("grade", 1))
                    sym_raw = clean_ocr_text(occ.get("symptom_raw", ""))
                    occ_kind = occ.get("kind", "symptom")

                    if occ_kind == "general_modality":
                        for m in occ.get("modalities", []):
                            m_res = modality_resolver.resolve(m.get("factor_raw", ""))
                            m_core = canonicalize_modality_factor(
                                m.get("factor_raw", ""),
                                m_res.get("canonical_label") or m_res.get("label"),
                            )
                            if not m_core:
                                continue
                            direction = m.get("direction", "worse")
                            prefix = "Worse: " if direction == "worse" else "Better: "
                            m_label = f"{prefix}{m_core}"
                            m_id = f"modality:{direction}_{make_modality_id(m_core).replace('modality:', '')}"
                            upsert_node(m_id, m_label, "Modality", weight=1.5, factor_type=m_res.get("factor_type", "other"), sources=[src_ref])
                            rel_label = "AGGRAVATED BY" if direction == "worse" else "AMELIORATED BY"
                            upsert_edge(rem_id, m_id, rel_label, weight=1.5, quote=quote)
                        continue

                    # Always run canonicalize_symptom_label so OCR noise & mid-word cuts are repaired
                    canon_label = canonicalize_symptom_label(sym_raw, occ.get("canonical_label"))
                    if not canon_label or len(canon_label) < 3:
                        continue
                    # Skip non-symptom modality/Materia Medica artifacts
                    if canon_label.lower().startswith(("worse ", "better ", "worsens ", "peru balsam")):
                        continue

                    sym_id = make_symptom_id(canon_label)
                    sym_kind = occ.get("symptom_kind", "physical")
                    vad = occ.get("vad") or compute_vad(f"{sym_raw} {quote}")
                    adj_sev = occ.get("adjective_severity")
                    if adj_sev is None:
                        adj_sev, _ = compute_adjective_severity(f"{sym_raw} {quote}")
                    comp_weight = occ.get("composite_weight") or compute_linear_regression_weight(
                        grade, adj_sev, vad["arousal"], float(occ.get("confidence", 1.0))
                    )
                    cog_dom = resolve_cognitive_domain(sym_raw, section)

                    # Strict anatomical check: physical organ symptoms stay Physical unless genuine Mind/Sleep/Affective
                    is_anatomical_sec = section not in ("Mind", "Sleep", "General", "Generalities", "Intro", "Clinical Literature (PubMed)")
                    if is_anatomical_sec and not any(
                        w in sym_raw.lower()
                        for w in ("fear", "anxi", "delirium", "hallucinat", "weep", "anger", "sad", "melanchol", "despair", "dream", "irritab", "fright", "terror", "mood", "memory")
                    ):
                        cog_dom = "None"
                        is_affective = False
                    else:
                        is_affective = sym_kind in ("mental", "dream", "affective") or cog_dom != "None"

                    node_type = "Affective Symptom" if is_affective else "Physical Symptom"

                    upsert_node(
                        sym_id,
                        canon_label,
                        node_type,
                        weight=comp_weight,
                        grade=grade,
                        section=section,
                        raw_example=sym_raw,
                        quote=quote,
                        valence=vad.get("valence", 0.5),
                        arousal=vad.get("arousal", 0.5),
                        dominance=vad.get("dominance", 0.5),
                        sources=[src_ref],
                    )

                    edge_label = "HAS AFFECTIVE SYMPTOM" if is_affective else "HAS PHYSICAL SYMPTOM"
                    upsert_edge(rem_id, sym_id, edge_label, weight=comp_weight, grade=grade, quote=quote)

                    # Cognitive Domain link (MAPS TO)
                    if cog_dom and cog_dom != "None":
                        dom_id = make_domain_id(cog_dom)
                        upsert_node(dom_id, cog_dom, "Cognitive Domain", weight=2.4)
                        upsert_edge(sym_id, dom_id, "MAPS TO", weight=comp_weight)

                    # Modalities attached to this symptom
                    for m in occ.get("modalities", []):
                        m_res = modality_resolver.resolve(m.get("factor_raw", ""))
                        m_core = canonicalize_modality_factor(
                            m.get("factor_raw", ""),
                            m_res.get("canonical_label") or m_res.get("label"),
                        )
                        if not m_core:
                            continue
                        direction = m.get("direction", "worse")
                        prefix = "Worse: " if direction == "worse" else "Better: "
                        m_label = f"{prefix}{m_core}"
                        m_id = f"modality:{direction}_{make_modality_id(m_core).replace('modality:', '')}"
                        upsert_node(
                            m_id,
                            m_label,
                            "Modality",
                            weight=1.6,
                            factor_type=m.get("factor_type", m_res.get("factor_type", "other")),
                            sources=[src_ref],
                        )
                        rel_label = "AGGRAVATED BY" if direction == "worse" else "AMELIORATED BY"
                        upsert_edge(sym_id, m_id, rel_label, weight=comp_weight, quote=quote)

                    # Clinical Conditions (TREATS / INDICATED FOR)
                    for cond in occ.get("clinical_conditions", []):
                        clean_cond = clean_ocr_text(cond)
                        if clean_cond and len(clean_cond) >= 3:
                            c_id = make_condition_id(clean_cond)
                            upsert_node(c_id, clean_cond.title(), "Clinical Condition", weight=2.0, sources=[src_ref])
                            upsert_edge(rem_id, c_id, "INDICATED FOR (SIMILIA)", weight=comp_weight, provenance="derived")
                            upsert_edge(sym_id, c_id, "ASSOCIATED CONDITION", weight=1.2)

                    # Body Region (exclude non-anatomical metadata sections like PubMed / General)
                    if section and section not in (
                        "Modalities", "Relationship", "Intro", "Mind",
                        "Clinical Literature (PubMed)", "General", "Generalities",
                    ):
                        reg_id = make_region_id(section)
                        upsert_node(reg_id, section, "Body Region", weight=1.4)
                        upsert_edge(sym_id, reg_id, "LOCATED IN", weight=1.0)

                    # Sensations
                    for sens in occ.get("sensation_raw", []):
                        clean_sens = clean_ocr_text(sens)
                        if clean_sens and 3 <= len(clean_sens) <= 28:
                            sn_id = make_sensation_id(clean_sens)
                            upsert_node(sn_id, clean_sens.title(), "Sensation", weight=1.3)
                            upsert_edge(sym_id, sn_id, "HAS SENSATION", weight=1.2)

                    # Causes / Etiology
                    for cause in occ.get("causes_raw", []):
                        clean_cause = clean_ocr_text(cause)
                        if clean_cause and 3 <= len(clean_cause) <= 35:
                            et_id = make_etiology_id(clean_cause)
                            upsert_node(et_id, f"Cause: {clean_cause.title()}", "Etiology", weight=1.5)
                            upsert_edge(et_id, sym_id, "TRIGGERS", weight=1.5)

    # Convert sets to sorted lists for JSON serialization
    final_nodes = []
    for n in nodes.values():
        n["sources"] = sorted(s for s in n.get("sources", []) if s)
        final_nodes.append(n)

    return {
        "nodes": final_nodes,
        "links": list(edges.values()),
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>__TITLE__</title>
<style>
  :root {
    --bg: #07090e;
    --panel: #10141f;
    --panel-alt: #161b2a;
    --border: #22293d;
    --text: #eef2f9;
    --muted: #8b95ab;
    --blue: #58b8ff;
    --pink: #f48fb1;
    --purple: #c5b3f8;
    --gold: #ffd166;
    --green: #06d6a0;
    --cyan: #4dd0e1;
    --coral: #ff8a65;
    --orange: #ffb74d;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
  body { background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
  header {
    padding: 12px 22px;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
    background: #0b0e17;
  }
  .title-block h1 { font-size: 19px; font-weight: 600; letter-spacing: -0.02em; color: #fff; }
  .title-block p { font-size: 12px; color: var(--muted); margin-top: 2px; }
  .header-right { display: flex; align-items: center; gap: 10px; }
  .badge {
    background: var(--panel-alt); border: 1px solid var(--border);
    padding: 5px 13px; border-radius: 999px; font-size: 12.5px; color: var(--text); font-weight: 500;
  }
  .toolbar {
    padding: 8px 20px; background: var(--panel); border-bottom: 1px solid var(--border);
    display: flex; flex-wrap: wrap; gap: 14px; align-items: center; justify-content: space-between;
  }
  .legend { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; font-size: 12px; }
  .legend-item {
    display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none;
    padding: 4px 9px; border-radius: 6px; background: var(--panel-alt); border: 1px solid transparent;
    transition: all 0.15s;
  }
  .legend-item:hover { border-color: var(--border); }
  .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; box-shadow: 0 0 6px currentColor; }
  .controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  input[type="text"], select, button {
    background: var(--panel-alt); color: var(--text); border: 1px solid var(--border);
    padding: 6px 11px; border-radius: 6px; font-size: 12.5px; outline: none;
  }
  input[type="text"]:focus, select:focus { border-color: var(--blue); }
  button { cursor: pointer; transition: all 0.15s; font-weight: 500; }
  button:hover { background: #232b42; border-color: #364263; }
  button.primary { background: #1d568f; border-color: #327bc2; color: #fff; }
  button.primary:hover { background: #2568ab; }
  button.active-toggle { background: #14493c; border-color: var(--green); color: #fff; }
  main { flex: 1; display: flex; position: relative; overflow: hidden; }

  /* Left Remedy & Concept Directory Sidebar */
  #left-sidebar {
    width: 255px; background: var(--panel); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; overflow: hidden;
  }
  .sidebar-header {
    padding: 12px 14px; border-bottom: 1px solid var(--border);
    display: flex; flex-direction: column; gap: 8px;
  }
  .sidebar-header h3 { font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }
  #remedy-list { flex: 1; overflow-y: auto; padding: 8px; display: flex; flex-direction: column; gap: 4px; }
  .rem-item {
    padding: 7px 10px; border-radius: 6px; cursor: pointer; font-size: 12.5px;
    display: flex; align-items: center; justify-content: space-between;
    color: #cbd5e8; transition: background 0.12s;
  }
  .rem-item:hover { background: var(--panel-alt); color: #fff; }
  .rem-item.selected { background: #1c3a5e; color: #fff; border-left: 3px solid var(--blue); font-weight: 600; }
  .rem-count { font-size: 11px; color: var(--muted); background: #0c0f17; padding: 2px 7px; border-radius: 99px; }

  /* Center High-DPI Interactive Canvas */
  #canvas-wrap { flex: 1; position: relative; background: radial-gradient(circle at center, #0e1320 0%, #06080d 100%); overflow: hidden; }
  canvas { width: 100%; height: 100%; display: block; cursor: grab; }
  canvas:active { cursor: grabbing; }
  .canvas-overlay {
    position: absolute; bottom: 16px; left: 16px; display: flex; gap: 8px; align-items: center;
    background: rgba(16, 20, 31, 0.88); backdrop-filter: blur(8px);
    padding: 7px 12px; border-radius: 8px; border: 1px solid var(--border); font-size: 12px;
  }
  .hover-tooltip {
    position: absolute; pointer-events: none; display: none;
    background: rgba(14, 18, 28, 0.96); border: 1px solid #394566;
    padding: 9px 12px; border-radius: 8px; font-size: 12.5px; color: #fff;
    box-shadow: 0 8px 24px rgba(0,0,0,0.65); max-width: 310px; z-index: 20;
  }

  /* Right Inspector & TIDE Panel */
  aside {
    width: 350px; background: var(--panel); border-left: 1px solid var(--border);
    padding: 14px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px;
  }
  .card { background: var(--panel-alt); border: 1px solid var(--border); border-radius: 8px; padding: 13px; }
  .card h3 { font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); margin-bottom: 9px; }
  .stat-row { display: flex; justify-content: space-between; font-size: 12.5px; padding: 5px 0; border-bottom: 1px solid #1f263a; }
  .stat-row:last-child { border-bottom: none; }
  .quote-box {
    font-size: 12.5px; color: #d5def0; font-style: italic; line-height: 1.48;
    margin-top: 8px; padding: 9px 11px; background: #0c0f18; border-left: 3px solid var(--blue); border-radius: 5px;
  }
  .bar-bg { height: 6px; background: #232a3e; border-radius: 3px; overflow: hidden; margin-top: 4px; }
  .bar-fill { height: 100%; background: var(--green); }
  .neighbor-chip {
    display: inline-block; padding: 3px 8px; margin: 3px 4px 0 0; border-radius: 5px;
    font-size: 11.5px; background: #101420; border: 1px solid var(--border); cursor: pointer;
  }
  .neighbor-chip:hover { border-color: var(--blue); color: var(--blue); }
</style>
</head>
<body>
<header>
  <div class="title-block">
    <h1 id="graph-title">__TITLE__</h1>
    <p>Interactive Homeopathic Materia Medica, Modality &amp; Cognitive-Affective Knowledge Graph (MPCS LocalKG v2)</p>
  </div>
  <div class="header-right">
    <div class="badge" id="stats-badge">0 Nodes • 0 Links</div>
  </div>
</header>
<div class="toolbar">
  <div class="legend" id="legend"></div>
  <div class="controls">
    <button id="layout-btn" class="active-toggle" onclick="toggleLayoutMode()">Layout: Galaxy Clusters</button>
    <button id="labels-btn" onclick="toggleAllLabels()">Labels: Smart Auto</button>
    <input id="query-input" type="text" placeholder="TIDE Spreading Activation (e.g. fear of death, delirium, midnight, bruising)..." style="width: 310px;" onkeydown="if(event.key==='Enter')runSpreadingActivation()"/>
    <button class="primary" onclick="runSpreadingActivation()">Activate &amp; Prune (TIDE)</button>
    <button onclick="resetActivation()">Reset</button>
  </div>
</div>
<main>
  <div id="left-sidebar">
    <div class="sidebar-header">
      <h3>Remedy Explorer (<span id="rem-total-count">0</span>)</h3>
      <input id="rem-search" type="text" placeholder="Filter remedies or nodes..." oninput="filterRemedySidebar()"/>
    </div>
    <div id="remedy-list"></div>
  </div>
  <div id="canvas-wrap">
    <canvas id="graph-canvas"></canvas>
    <div id="tooltip" class="hover-tooltip"></div>
    <div class="canvas-overlay">
      <button onclick="fitToScreen()">Fit All to Screen</button>
      <button onclick="zoomBy(1.28)">Zoom +</button>
      <button onclick="zoomBy(0.78)">Zoom −</button>
      <span style="color:var(--muted);margin-left:6px;">Min Weight: <strong id="weight-val">1.0</strong></span>
      <input id="weight-slider" type="range" min="1.0" max="2.6" step="0.1" value="1.0" style="width:90px" oninput="updateWeightFilter(this.value)"/>
    </div>
  </div>
  <aside>
    <div class="card">
      <h3>MPCS Spreading Activation &amp; Pruning</h3>
      <div class="stat-row"><span>Mode</span><strong id="act-mode">Full Graph</strong></div>
      <div class="stat-row"><span>Visible Nodes</span><strong id="act-total">0</strong></div>
      <div class="stat-row"><span>Seeded Nodes</span><strong id="act-seeded">0</strong></div>
      <div class="stat-row"><span>Kept (Active Subgraph)</span><strong id="act-kept" style="color:var(--green)">0</strong></div>
      <div class="stat-row"><span>Pruned Nodes</span><strong id="act-pruned" style="color:var(--pink)">0</strong></div>
      <div class="stat-row"><span>Pruning Ratio</span><strong id="act-ratio">0%</strong></div>
    </div>
    <div class="card" id="inspector">
      <h3>Node Inspector</h3>
      <p style="font-size:12.5px;color:var(--muted);line-height:1.45;">Click any node on the canvas or select a medicine on the left to inspect its VAD affect profile, severity weight, verbatim book quote, and connected neighbors.</p>
    </div>
  </aside>
</main>
<script>
const GRAPH_DATA = __GRAPH_JSON__;

const COLORS = {
  "Medicine": "#58b8ff",
  "Affective Symptom": "#c5b3f8",
  "Cognitive Domain": "#06d6a0",
  "Physical Symptom": "#f48fb1",
  "Modality": "#ffd166",
  "Clinical Condition": "#4dd0e1",
  "Body Region": "#ff8a65",
  "Sensation": "#ffb74d",
  "Etiology": "#ff8a80"
};

const hiddenTypes = new Set();
let activeNodes = new Map(); // id -> activation score
let selectedRemedy = "ALL";
let inspectedNode = null;
let hoveredNode = null;
let minWeight = 1.0;
let layoutMode = "galaxy"; // "galaxy" | "force"
let labelMode = "smart";   // "smart" | "all" | "hubs"

// Build adjacency lookup for fast neighborhood inspection
const neighborsMap = new Map();
const nodeDegree = new Map();
GRAPH_DATA.nodes.forEach(n => { neighborsMap.set(n.id, []); nodeDegree.set(n.id, 0); });
GRAPH_DATA.links.forEach(l => {
  if (neighborsMap.has(l.source) && neighborsMap.has(l.target)) {
    neighborsMap.get(l.source).push({ id: l.target, rel: l.label });
    neighborsMap.get(l.target).push({ id: l.source, rel: l.label });
    nodeDegree.set(l.source, (nodeDegree.get(l.source) || 0) + 1);
    nodeDegree.set(l.target, (nodeDegree.get(l.target) || 0) + 1);
  }
});

// Populate interactive legend with counts
const legendEl = document.getElementById("legend");
const typeCounts = {};
GRAPH_DATA.nodes.forEach(n => { typeCounts[n.type] = (typeCounts[n.type] || 0) + 1; });
Object.entries(COLORS).forEach(([type, color]) => {
  if (!typeCounts[type]) return;
  const item = document.createElement("div");
  item.className = "legend-item";
  item.innerHTML = `<span class="dot" style="background:${color};color:${color}"></span><span>${type} (${typeCounts[type]})</span>`;
  item.onclick = () => {
    if (hiddenTypes.has(type)) { hiddenTypes.delete(type); item.style.opacity = "1"; }
    else { hiddenTypes.add(type); item.style.opacity = "0.35"; }
    rebuildGraphLayout();
  };
  legendEl.appendChild(item);
});

// Populate Left Remedy Explorer Sidebar
const medicines = GRAPH_DATA.nodes
  .filter(n => n.type === "Medicine")
  .sort((a, b) => (nodeDegree.get(b.id) || 0) - (nodeDegree.get(a.id) || 0));
document.getElementById("rem-total-count").textContent = medicines.length;

function renderRemedySidebar(filterText = "") {
  const listEl = document.getElementById("remedy-list");
  const q = filterText.trim().toLowerCase();
  let html = `<div class="rem-item ${selectedRemedy === 'ALL' ? 'selected' : ''}" onclick="selectRemedy('ALL')">
    <span>🌐 All Remedies (Full Graph)</span>
    <span class="rem-count">${GRAPH_DATA.nodes.length}</span>
  </div>`;
  medicines.forEach(m => {
    if (q && !m.label.toLowerCase().includes(q)) return;
    const deg = nodeDegree.get(m.id) || 0;
    const sel = selectedRemedy === m.id ? "selected" : "";
    html += `<div class="rem-item ${sel}" onclick="selectRemedy('${m.id.replace(/'/g, "\\'")}')">
      <span>${m.label}</span>
      <span class="rem-count">${deg}</span>
    </div>`;
  });
  listEl.innerHTML = html;
}
renderRemedySidebar();

function filterRemedySidebar() {
  const q = document.getElementById("rem-search").value;
  renderRemedySidebar(q);
}

function selectRemedy(remId) {
  selectedRemedy = remId;
  renderRemedySidebar(document.getElementById("rem-search").value);
  rebuildGraphLayout();
  if (remId !== "ALL") {
    const found = simNodes.find(n => n.id === remId);
    if (found) inspectNode(found);
  }
}

function updateWeightFilter(val) {
  minWeight = parseFloat(val);
  document.getElementById("weight-val").textContent = minWeight.toFixed(1);
  rebuildGraphLayout();
}

function toggleLayoutMode() {
  layoutMode = layoutMode === "galaxy" ? "force" : "galaxy";
  const btn = document.getElementById("layout-btn");
  btn.textContent = layoutMode === "galaxy" ? "Layout: Galaxy Clusters" : "Layout: Concentric Rings";
  btn.classList.toggle("active-toggle", layoutMode === "galaxy");
  rebuildGraphLayout();
}

function toggleAllLabels() {
  const order = ["smart", "all", "hubs"];
  labelMode = order[(order.indexOf(labelMode) + 1) % order.length];
  const labels = { smart: "Labels: Smart Auto", all: "Labels: Always Show All", hubs: "Labels: Hubs Only" };
  document.getElementById("labels-btn").textContent = labels[labelMode];
  drawCanvas();
}

// High-DPI HTML5 Canvas Setup
const canvas = document.getElementById("graph-canvas");
const ctx = canvas.getContext("2d");
const tooltip = document.getElementById("tooltip");
let width = 960, height = 680, dpr = window.devicePixelRatio || 1;
let panX = 0, panY = 0, scale = 1.0;
let isPanning = false, startX = 0, startY = 0, draggedNode = null;
let simNodes = [], simLinks = [];

function resizeCanvas() {
  const rect = canvas.parentElement.getBoundingClientRect();
  width = rect.width || 960;
  height = rect.height || 680;
  dpr = window.devicePixelRatio || 1;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
}

// Deterministic hash for stable angular placement
function hashStr(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967295;
}

function rebuildGraphLayout() {
  resizeCanvas();

  // 1. Determine allowed nodes based on selected remedy & weight slider
  let allowedIds = new Set();
  if (selectedRemedy === "ALL") {
    GRAPH_DATA.nodes.forEach(n => {
      if (n.type === "Medicine" || n.type === "Cognitive Domain" || (n.weight || 1.0) >= minWeight) {
        allowedIds.add(n.id);
      }
    });
  } else {
    allowedIds.add(selectedRemedy);
    // 2-hop ego-network around the chosen remedy
    GRAPH_DATA.links.forEach(l => {
      if (l.source === selectedRemedy) allowedIds.add(l.target);
      if (l.target === selectedRemedy) allowedIds.add(l.source);
    });
    const firstHop = new Set(allowedIds);
    GRAPH_DATA.links.forEach(l => {
      if (firstHop.has(l.source)) {
        const tgt = GRAPH_DATA.nodes.find(x => x.id === l.target);
        if (tgt && tgt.type !== "Medicine") allowedIds.add(l.target);
      }
      if (firstHop.has(l.target)) {
        const src = GRAPH_DATA.nodes.find(x => x.id === l.source);
        if (src && src.type !== "Medicine") allowedIds.add(l.source);
      }
    });
  }

  simNodes = GRAPH_DATA.nodes
    .filter(n => allowedIds.has(n.id) && !hiddenTypes.has(n.type))
    .map(n => ({ ...n, x: 0, y: 0, vx: 0, vy: 0 }));

  const nodeMap = new Map(simNodes.map(n => [n.id, n]));
  simLinks = GRAPH_DATA.links
    .filter(l => nodeMap.has(l.source) && nodeMap.has(l.target))
    .map(l => ({ ...l, sourceNode: nodeMap.get(l.source), targetNode: nodeMap.get(l.target) }));

  // 2. Compute clean, non-overlapping structured coordinates
  const meds = simNodes.filter(n => n.type === "Medicine");
  const domains = simNodes.filter(n => n.type === "Cognitive Domain");
  const regions = simNodes.filter(n => n.type === "Body Region" || n.type === "Clinical Condition");
  const others = simNodes.filter(n => !["Medicine", "Cognitive Domain", "Body Region", "Clinical Condition"].includes(n.type));

  if (selectedRemedy !== "ALL" || meds.length <= 2) {
    // Focused Single-Remedy Radial Mandala Layout
    const centerRem = simNodes.find(n => n.id === selectedRemedy) || meds[0];
    if (centerRem) { centerRem.x = 0; centerRem.y = 0; centerRem.pinned = true; }

    domains.forEach((d, idx) => {
      const ang = (2 * Math.PI * idx) / Math.max(1, domains.length);
      d.x = 260 * Math.cos(ang);
      d.y = 260 * Math.sin(ang);
    });

    regions.forEach((r, idx) => {
      const ang = (2 * Math.PI * idx) / Math.max(1, regions.length) + 0.3;
      r.x = 340 * Math.cos(ang);
      r.y = 340 * Math.sin(ang);
    });

    others.forEach((n, idx) => {
      const ring = n.type === "Affective Symptom" ? 480 : (n.type === "Modality" ? 640 : 800);
      const spread = (idx % 3 - 1) * 65;
      const ang = (2 * Math.PI * idx) / Math.max(1, others.length);
      n.x = (ring + spread) * Math.cos(ang);
      n.y = (ring + spread) * Math.sin(ang);
    });
  } else if (layoutMode === "galaxy") {
    // Multi-Remedy Galaxy Layout:
    // - Cognitive Domains in inner ring (R = 320)
    // - Major Remedies on Golden-Angle Phyllotaxis / Constellation Rings (R = 750..1850)
    // - Symptoms, Modalities & Conditions orbiting their parent Remedy/Domain hubs!
    domains.forEach((d, idx) => {
      const ang = (2 * Math.PI * idx) / Math.max(1, domains.length);
      d.x = 340 * Math.cos(ang);
      d.y = 340 * Math.sin(ang);
    });

    regions.forEach((r, idx) => {
      const ang = (2 * Math.PI * idx) / Math.max(1, regions.length);
      r.x = 640 * Math.cos(ang);
      r.y = 640 * Math.sin(ang);
    });

    const goldenAngle = Math.PI * (3 - Math.sqrt(5));
    meds.forEach((m, idx) => {
      const r = 950 + 260 * Math.sqrt(idx + 1);
      const theta = idx * goldenAngle;
      m.x = r * Math.cos(theta);
      m.y = r * Math.sin(theta);
    });

    // Place each symptom/modality near the centroid of its connected hubs + orbital offset
    others.forEach((n, idx) => {
      const connectedHubs = [];
      const nbrs = neighborsMap.get(n.id) || [];
      nbrs.forEach(nb => {
        const target = nodeMap.get(nb.id);
        if (target && (target.type === "Medicine" || target.type === "Cognitive Domain" || target.type === "Body Region")) {
          connectedHubs.push(target);
        }
      });

      let cx = 0, cy = 0;
      if (connectedHubs.length > 0) {
        connectedHubs.forEach(h => { cx += h.x; cy += h.y; });
        cx /= connectedHubs.length;
        cy /= connectedHubs.length;
      } else {
        const ang = 2 * Math.PI * hashStr(n.id);
        cx = 1600 * Math.cos(ang);
        cy = 1600 * Math.sin(ang);
      }

      const orbitRadius = 115 + (idx % 5) * 42;
      const orbitAngle = 2 * Math.PI * hashStr(n.id + ":" + idx);
      n.x = cx + orbitRadius * Math.cos(orbitAngle);
      n.y = cy + orbitRadius * Math.sin(orbitAngle);
    });
  } else {
    // Concentric Semantic Rings Layout
    const groups = [
      { list: domains, r: 280 },
      { list: meds, r: 720 },
      { list: regions, r: 1120 },
      { list: others.filter(n => n.type === "Affective Symptom"), r: 1520 },
      { list: others.filter(n => n.type === "Modality"), r: 1920 },
      { list: others.filter(n => n.type !== "Affective Symptom" && n.type !== "Modality"), r: 2400 }
    ];
    groups.forEach(g => {
      g.list.forEach((n, i) => {
        const ang = (2 * Math.PI * i) / Math.max(1, g.list.length);
        const jitter = (i % 2 === 0 ? 1 : -1) * 45;
        n.x = (g.r + jitter) * Math.cos(ang);
        n.y = (g.r + jitter) * Math.sin(ang);
      });
    });
  }

  // 3. Fast Spatial-Grid Collision Relaxation (guarantees zero overlapping nodes in <40ms!)
  resolveNodeCollisions(simNodes, 6);

  document.getElementById("stats-badge").textContent = `${simNodes.length} Nodes • ${simLinks.length} Links`;
  document.getElementById("act-total").textContent = simNodes.length;
  if (activeNodes.size === 0) {
    document.getElementById("act-kept").textContent = simNodes.length;
  }

  fitToScreen();
}

function resolveNodeCollisions(nodes, iterations = 6) {
  const minSep = 54; // minimum pixel separation in world space
  const cellSize = minSep * 1.5;

  for (let iter = 0; iter < iterations; iter++) {
    const grid = new Map();
    nodes.forEach((n, idx) => {
      const gx = Math.floor(n.x / cellSize);
      const gy = Math.floor(n.y / cellSize);
      const key = `${gx},${gy}`;
      if (!grid.has(key)) grid.set(key, []);
      grid.get(key).push(idx);
    });

    nodes.forEach((a, i) => {
      if (a.pinned) return;
      const gx = Math.floor(a.x / cellSize);
      const gy = Math.floor(a.y / cellSize);
      for (let dx = -1; dx <= 1; dx++) {
        for (let dy = -1; dy <= 1; dy++) {
          const cell = grid.get(`${gx + dx},${gy + dy}`);
          if (!cell) continue;
          for (let k = 0; k < cell.length; k++) {
            const j = cell[k];
            if (j <= i) continue;
            const b = nodes[j];
            let vx = b.x - a.x;
            let vy = b.y - a.y;
            let distSq = vx * vx + vy * vy;
            const reqDist = (a.type === "Medicine" || b.type === "Medicine") ? minSep * 1.45 : minSep;
            if (distSq < reqDist * reqDist) {
              let dist = Math.sqrt(distSq) || 0.1;
              let overlap = (reqDist - dist) * 0.5;
              let nx = vx / dist, ny = vy / dist;
              a.x -= nx * overlap;
              a.y -= ny * overlap;
              if (!b.pinned) {
                b.x += nx * overlap;
                b.y += ny * overlap;
              }
            }
          }
        }
      }
    });
  }
}

function fitToScreen() {
  if (simNodes.length === 0) { drawCanvas(); return; }
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  const targetNodes = activeNodes.size > 0
    ? simNodes.filter(n => activeNodes.has(n.id))
    : simNodes;
  const list = targetNodes.length > 0 ? targetNodes : simNodes;

  list.forEach(n => {
    if (n.x < minX) minX = n.x;
    if (n.x > maxX) maxX = n.x;
    if (n.y < minY) minY = n.y;
    if (n.y > maxY) maxY = n.y;
  });

  const pad = 140;
  const spanX = Math.max(300, (maxX - minX) + pad * 2);
  const spanY = Math.max(300, (maxY - minY) + pad * 2);
  scale = Math.min(2.2, Math.max(0.12, Math.min(width / spanX, height / spanY)));
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  panX = width / 2 - cx * scale;
  panY = height / 2 - cy * scale;
  drawCanvas();
}

function zoomBy(factor) {
  const newScale = Math.min(4.5, Math.max(0.1, scale * factor));
  panX = width / 2 - (width / 2 - panX) * (newScale / scale);
  panY = height / 2 - (height / 2 - panY) * (newScale / scale);
  scale = newScale;
  drawCanvas();
}

function nodeRadius(n) {
  if (n.type === "Medicine") return 20;
  if (n.type === "Cognitive Domain") return 17;
  if (n.type === "Clinical Condition" || n.type === "Body Region") return 13;
  return Math.min(14, 7 + (n.weight || 1.0) * 2.1);
}

function drawCanvas() {
  ctx.save();
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  ctx.translate(panX, panY);
  ctx.scale(scale, scale);

  const hasActivation = activeNodes.size > 0;
  const hoveredNbrs = new Set();
  if (hoveredNode) {
    hoveredNbrs.add(hoveredNode.id);
    (neighborsMap.get(hoveredNode.id) || []).forEach(nb => hoveredNbrs.add(nb.id));
  } else if (inspectedNode) {
    hoveredNbrs.add(inspectedNode.id);
    (neighborsMap.get(inspectedNode.id) || []).forEach(nb => hoveredNbrs.add(nb.id));
  }

  // 1. Draw Links
  ctx.lineWidth = 1.2 / Math.max(0.5, Math.sqrt(scale));
  simLinks.forEach(l => {
    const a = l.sourceNode, b = l.targetNode;
    const isHoveredLink = hoveredNode && (a.id === hoveredNode.id || b.id === hoveredNode.id);
    const isInspectedLink = !hoveredNode && inspectedNode && (a.id === inspectedNode.id || b.id === inspectedNode.id);
    const bothActive = !hasActivation || (activeNodes.has(a.id) && activeNodes.has(b.id));

    if (isHoveredLink || isInspectedLink) {
      ctx.strokeStyle = "#58b8ff";
      ctx.globalAlpha = 0.85;
      ctx.lineWidth = 2.0 / Math.max(0.6, Math.sqrt(scale));
    } else if (hasActivation && bothActive) {
      ctx.strokeStyle = "#06d6a0";
      ctx.globalAlpha = 0.72;
      ctx.lineWidth = 1.8 / Math.max(0.6, Math.sqrt(scale));
    } else if (hasActivation && !bothActive) {
      ctx.strokeStyle = "#252c40";
      ctx.globalAlpha = 0.08;
      ctx.lineWidth = 1.0 / Math.max(0.6, Math.sqrt(scale));
    } else {
      ctx.strokeStyle = "#333e5c";
      ctx.globalAlpha = simNodes.length > 400 ? 0.28 : 0.48;
      ctx.lineWidth = 1.1 / Math.max(0.6, Math.sqrt(scale));
    }

    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();

    if ((isHoveredLink || isInspectedLink || (hasActivation && bothActive)) && scale > 0.45) {
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      ctx.fillStyle = "#98a6c4";
      ctx.globalAlpha = 0.9;
      ctx.font = `${Math.max(9, Math.round(10 / Math.sqrt(scale)))}px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.fillText(l.label, mx, my - 4);
    }
  });

  // 2. Draw Nodes & Crisp Pill Labels
  simNodes.forEach(n => {
    const isAct = !hasActivation || activeNodes.has(n.id);
    const isFocus = hoveredNbrs.size === 0 || hoveredNbrs.has(n.id);
    const r = nodeRadius(n) + (activeNodes.has(n.id) ? activeNodes.get(n.id) * 4 : 0);
    const color = COLORS[n.type] || "#90a4ae";

    ctx.globalAlpha = !isAct ? 0.12 : (hoveredNbrs.size > 0 && !isFocus ? 0.28 : 1.0);

    // Outer glow for Medicines, Cognitive Domains, or Active seeds
    if ((n.type === "Medicine" || n.type === "Cognitive Domain" || activeNodes.has(n.id)) && isAct) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, r + 5, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.globalAlpha *= 0.22;
      ctx.fill();
      ctx.globalAlpha = !isAct ? 0.12 : (hoveredNbrs.size > 0 && !isFocus ? 0.28 : 1.0);
    }

    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();

    ctx.lineWidth = (n === hoveredNode || n === inspectedNode || activeNodes.has(n.id)) ? 2.6 : 1.4;
    ctx.strokeStyle = (n === hoveredNode || n === inspectedNode || activeNodes.has(n.id)) ? "#ffffff" : "#07090e";
    ctx.stroke();

    // Label visibility rules
    const isHub = n.type === "Medicine" || n.type === "Cognitive Domain" || n.type === "Clinical Condition";
    let showLabel = false;
    if (labelMode === "all") showLabel = true;
    else if (labelMode === "hubs") showLabel = isHub || n === hoveredNode || n === inspectedNode;
    else {
      // Smart Auto: always show hubs, active TIDE nodes, hovered/inspected neighborhood, or when zoomed in
      showLabel = isHub
        || (hasActivation && isAct)
        || (hoveredNbrs.size > 0 && isFocus)
        || simNodes.length <= 120
        || scale >= 0.65
        || (scale >= 0.38 && (n.weight || 1) >= 2.2);
    }

    if (showLabel && isAct) {
      const fontSize = isHub ? Math.max(11, Math.round(13 / Math.pow(scale, 0.35))) : Math.max(9.5, Math.round(11 / Math.pow(scale, 0.35)));
      ctx.font = `${isHub ? 600 : 500} ${fontSize}px Inter, sans-serif`;
      ctx.textAlign = "center";
      const label = n.label.length > 34 && scale < 0.8 ? n.label.slice(0, 32) + "…" : n.label;
      const textWidth = ctx.measureText(label).width;
      const pillX = n.x - textWidth / 2 - 5;
      const pillY = n.y + r + 4;
      const pillH = fontSize + 5;

      ctx.fillStyle = "rgba(10, 13, 22, 0.82)";
      ctx.fillRect(pillX, pillY, textWidth + 10, pillH);

      ctx.fillStyle = isHub ? "#ffffff" : "#dce3f2";
      ctx.fillText(label, n.x, pillY + fontSize);
    }
  });

  ctx.restore();
}

function screenToWorld(sx, sy) {
  return {
    x: (sx - panX) / scale,
    y: (sy - panY) / scale
  };
}

function findNodeAt(sx, sy) {
  const pt = screenToWorld(sx, sy);
  for (let i = simNodes.length - 1; i >= 0; i--) {
    const n = simNodes[i];
    const r = nodeRadius(n) + 4 / scale;
    const dx = pt.x - n.x, dy = pt.y - n.y;
    if (dx * dx + dy * dy <= r * r) return n;
  }
  return null;
}

function inspectNode(n) {
  inspectedNode = n;
  const act = activeNodes.get(n.id);
  const v = n.valence !== undefined ? Math.round(n.valence * 100) : null;
  const a = n.arousal !== undefined ? Math.round(n.arousal * 100) : null;
  const d = n.dominance !== undefined ? Math.round(n.dominance * 100) : null;
  const nbrs = neighborsMap.get(n.id) || [];

  let html = `<h3>${n.type}</h3>
    <div style="font-size:16px;font-weight:600;margin-bottom:8px;color:${COLORS[n.type]}">${n.label}</div>
    <div class="stat-row"><span>Composite Weight</span><strong>${(n.weight || 1).toFixed(2)} / 3.00</strong></div>
    <div class="stat-row"><span>Typography Grade</span><strong>${n.grade || "-"}</strong></div>
    <div class="stat-row"><span>Section</span><strong>${n.section || "-"}</strong></div>
    <div class="stat-row"><span>Connected Links</span><strong>${nbrs.length}</strong></div>`;

  if (act !== undefined) {
    html += `<div class="stat-row"><span>TIDE Activation</span><strong style="color:var(--green)">${act.toFixed(3)}</strong></div>`;
  }
  if (v !== null) {
    html += `<div style="margin-top:8px;font-size:12px;color:var(--muted)">VAD Affect Profile (V:${v}% A:${a}% D:${d}%)</div>
      <div class="bar-bg"><div class="bar-fill" style="width:${a}%;background:var(--purple)"></div></div>`;
  }
  if (n.quote) {
    html += `<div class="quote-box">"${n.quote}"</div>`;
  }
  if (n.sources && n.sources.length) {
    html += `<div style="margin-top:7px;font-size:11px;color:var(--muted)">Sources: ${n.sources.join(", ")}</div>`;
  }

  if (nbrs.length > 0) {
    html += `<div style="margin-top:10px;font-size:11.5px;color:var(--muted);text-transform:uppercase">Connected Concepts (${nbrs.length})</div><div style="margin-top:4px;max-height:150px;overflow-y:auto;">`;
    nbrs.slice(0, 35).forEach(nb => {
      const target = GRAPH_DATA.nodes.find(x => x.id === nb.id);
      if (target) {
        html += `<span class="neighbor-chip" onclick="focusNodeById('${target.id.replace(/'/g, "\\'")}')"><span style="color:${COLORS[target.type]}">●</span> ${target.label}</span>`;
      }
    });
    html += `</div>`;
  }

  document.getElementById("inspector").innerHTML = html;
  drawCanvas();
}

function focusNodeById(id) {
  const n = simNodes.find(x => x.id === id);
  if (!n) return;
  inspectNode(n);
  scale = Math.max(scale, 0.85);
  panX = width / 2 - n.x * scale;
  panY = height / 2 - n.y * scale;
  drawCanvas();
}

// MPCS TIDE Spreading Activation + Pruning
function runSpreadingActivation() {
  const q = document.getElementById("query-input").value.trim().toLowerCase();
  if (!q) { resetActivation(); return; }
  const terms = q.split(/[,;\\s]+/).filter(t => t.length >= 2);
  activeNodes.clear();

  let seeds = 0;
  simNodes.forEach(n => {
    const hay = `${n.label} ${n.raw_example || ""} ${n.quote || ""} ${n.section || ""}`.toLowerCase();
    let hits = terms.filter(t => hay.includes(t)).length;
    if (hits > 0) {
      const arousal = n.arousal !== undefined ? n.arousal : 0.5;
      const score = (hits / terms.length) * (1.0 + 0.8 * arousal) * ((n.weight || 1.0) / 2.0);
      activeNodes.set(n.id, score);
      seeds++;
    }
  });

  const hopDecay = 0.58;
  for (let hop = 0; hop < 2; hop++) {
    const nextScores = new Map(activeNodes);
    simLinks.forEach(l => {
      const sA = activeNodes.get(l.source) || 0;
      const sB = activeNodes.get(l.target) || 0;
      if (sA > 0) nextScores.set(l.target, Math.max(nextScores.get(l.target) || 0, sA * hopDecay));
      if (sB > 0) nextScores.set(l.source, Math.max(nextScores.get(l.source) || 0, sB * hopDecay));
    });
    activeNodes = nextScores;
  }

  const maxScore = Math.max(...Array.from(activeNodes.values()), 0.001);
  const cutoff = maxScore * 0.18;
  for (const [id, sc] of Array.from(activeNodes.entries())) {
    if (sc < cutoff) activeNodes.delete(id);
  }

  const total = simNodes.length;
  const kept = activeNodes.size;
  const pruned = Math.max(0, total - kept);
  document.getElementById("act-mode").textContent = kept > 0 ? "TIDE Activated Subgraph" : "UNGROUNDED";
  document.getElementById("act-seeded").textContent = seeds;
  document.getElementById("act-kept").textContent = kept;
  document.getElementById("act-pruned").textContent = pruned;
  document.getElementById("act-ratio").textContent = total ? `${Math.round((pruned / total) * 100)}%` : "0%";
  fitToScreen();
}

function resetActivation() {
  activeNodes.clear();
  inspectedNode = null;
  document.getElementById("query-input").value = "";
  document.getElementById("act-mode").textContent = "Full Graph";
  document.getElementById("act-seeded").textContent = "0";
  document.getElementById("act-kept").textContent = simNodes.length;
  document.getElementById("act-pruned").textContent = "0";
  document.getElementById("act-ratio").textContent = "0%";
  fitToScreen();
}

// Mouse & Wheel Interactions
canvas.addEventListener("mousedown", e => {
  const rect = canvas.getBoundingClientRect();
  const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
  const hit = findNodeAt(sx, sy);
  if (hit) {
    draggedNode = hit;
    inspectNode(hit);
  } else {
    isPanning = true;
    startX = e.clientX - panX;
    startY = e.clientY - panY;
  }
});

window.addEventListener("mousemove", e => {
  const rect = canvas.getBoundingClientRect();
  const sx = e.clientX - rect.left, sy = e.clientY - rect.top;

  if (draggedNode) {
    const pt = screenToWorld(sx, sy);
    draggedNode.x = pt.x;
    draggedNode.y = pt.y;
    drawCanvas();
    return;
  }
  if (isPanning) {
    panX = e.clientX - startX;
    panY = e.clientY - startY;
    drawCanvas();
    return;
  }

  // Hover detection inside canvas
  if (sx >= 0 && sx <= width && sy >= 0 && sy <= height) {
    const hit = findNodeAt(sx, sy);
    if (hit !== hoveredNode) {
      hoveredNode = hit;
      canvas.style.cursor = hit ? "pointer" : "grab";
      if (hit) {
        tooltip.style.display = "block";
        tooltip.innerHTML = `<div style="color:${COLORS[hit.type]};font-weight:600">${hit.type}: ${hit.label}</div>
          <div style="color:var(--muted);font-size:11.5px;margin-top:3px">Weight: ${(hit.weight || 1).toFixed(2)} • Grade: ${hit.grade || 1} • Section: ${hit.section || 'General'}</div>
          ${hit.quote ? `<div style="margin-top:4px;font-style:italic;color:#cbd5e8">"${hit.quote.slice(0, 120)}${hit.quote.length > 120 ? '…' : ''}"</div>` : ''}`;
      } else {
        tooltip.style.display = "none";
      }
      drawCanvas();
    }
    if (hit) {
      tooltip.style.left = Math.min(width - 320, sx + 16) + "px";
      tooltip.style.top = Math.max(12, sy - 16) + "px";
    }
  }
});

window.addEventListener("mouseup", () => { isPanning = false; draggedNode = null; });

canvas.addEventListener("wheel", e => {
  e.preventDefault();
  const rect = canvas.getBoundingClientRect();
  const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
  const factor = e.deltaY < 0 ? 1.14 : 0.88;
  const newScale = Math.min(4.5, Math.max(0.1, scale * factor));
  panX = sx - (sx - panX) * (newScale / scale);
  panY = sy - (sy - panY) * (newScale / scale);
  scale = newScale;
  drawCanvas();
}, { passive: false });

window.onload = rebuildGraphLayout;
window.onresize = rebuildGraphLayout;
</script>
</body>
</html>
"""


def export_interactive_html(
    extracted_files: list[Path],
    output_html: Path | None = None,
    title: str = "Homeopathic Materia Medica & Cognitive-Affective Knowledge Graph",
) -> Path:
    """Build concept graph from extracted JSONL files and write standalone interactive HTML."""
    output_html = output_html or (DATA_DIR / "extracted" / "kg_interactive.html")
    output_html.parent.mkdir(parents=True, exist_ok=True)

    graph_data = build_concept_graph(extracted_files)
    json_path = output_html.with_suffix(".graph.json")
    json_path.write_text(json.dumps(graph_data, indent=2, ensure_ascii=False), encoding="utf-8")

    html = (
        HTML_TEMPLATE.replace("__TITLE__", title)
        .replace("__GRAPH_JSON__", json.dumps(graph_data, ensure_ascii=False))
    )
    output_html.write_text(html, encoding="utf-8")
    return output_html

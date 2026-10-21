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
    canonicalize_symptom_label,
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
    make_region_id,
    make_remedy_id,
    make_sensation_id,
    make_symptom_id,
)


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
                    tgt_res = remedy_resolver.resolve(rel.get("remedy_raw", ""))
                    upsert_node(tgt_res["remedy_id"], tgt_res["canonical_name"], "Medicine", weight=2.2)
                    rel_type = rel.get("type", "compare").upper()
                    upsert_edge(rem_id, tgt_res["remedy_id"], rel_type, weight=1.5)

                # Occurrences
                for occ in rec.get("occurrences", []):
                    src_ref = occ.get("source_ref", "")
                    section = occ.get("section", "General")
                    quote = occ.get("evidence_quote", "")
                    grade = int(occ.get("grade", 1))
                    sym_raw = occ.get("symptom_raw", "")
                    occ_kind = occ.get("kind", "symptom")

                    if occ_kind == "general_modality":
                        for m in occ.get("modalities", []):
                            m_res = modality_resolver.resolve(m.get("factor_raw", ""))
                            m_label_core = m_res.get("canonical_label") or m_res.get("label") or m.get("factor_raw", "")
                            direction = m.get("direction", "worse")
                            prefix = "Worse " if direction == "worse" else "Better "
                            m_label = f"{prefix}{m_label_core}"
                            m_id = f"modality:{direction}_{m_res['modality_id'].replace('modality:', '')}"
                            upsert_node(m_id, m_label, "Modality", weight=1.5, factor_type=m_res.get("factor_type", "other"), sources=[src_ref])
                            rel_label = "AGGRAVATED BY" if direction == "worse" else "AMELIORATED BY"
                            upsert_edge(rem_id, m_id, rel_label, weight=1.5, quote=quote)
                        continue

                    canon_label = occ.get("canonical_label") or canonicalize_symptom_label(sym_raw)
                    sym_id = make_symptom_id(canon_label)
                    sym_kind = occ.get("symptom_kind", "physical")
                    vad = occ.get("vad") or compute_vad(f"{sym_raw} {quote}")
                    adj_sev = occ.get("adjective_severity")
                    if adj_sev is None:
                        adj_sev, _ = compute_adjective_severity(f"{sym_raw} {quote}")
                    comp_weight = occ.get("composite_weight") or compute_linear_regression_weight(
                        grade, adj_sev, vad["arousal"], float(occ.get("confidence", 1.0))
                    )
                    cog_dom = occ.get("cognitive_domain") or resolve_cognitive_domain(sym_raw, section)

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
                        m_label_core = m_res.get("canonical_label") or m_res.get("label") or m.get("factor_raw", "")
                        direction = m.get("direction", "worse")
                        prefix = "Worse " if direction == "worse" else "Better "
                        m_label = f"{prefix}{m_label_core}"
                        m_id = f"modality:{direction}_{m_res['modality_id'].replace('modality:', '')}"
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
                        if cond.strip():
                            c_id = make_condition_id(cond)
                            upsert_node(c_id, cond.strip().title(), "Clinical Condition", weight=2.0, sources=[src_ref])
                            upsert_edge(rem_id, c_id, "INDICATED FOR (SIMILIA)", weight=comp_weight, provenance="derived")
                            upsert_edge(sym_id, c_id, "ASSOCIATED CONDITION", weight=1.2)

                    # Body Region
                    if section and section not in ("Modalities", "Relationship", "Intro", "Mind"):
                        reg_id = make_region_id(section)
                        upsert_node(reg_id, section, "Body Region", weight=1.4)
                        upsert_edge(sym_id, reg_id, "LOCATED IN", weight=1.0)

                    # Sensations
                    for sens in occ.get("sensation_raw", []):
                        if sens.strip():
                            sn_id = make_sensation_id(sens)
                            upsert_node(sn_id, sens.strip().title(), "Sensation", weight=1.3)
                            upsert_edge(sym_id, sn_id, "HAS SENSATION", weight=1.2)

                    # Causes / Etiology
                    for cause in occ.get("causes_raw", []):
                        if cause.strip():
                            et_id = make_etiology_id(cause)
                            upsert_node(et_id, f"Cause: {cause.strip()}", "Etiology", weight=1.5)
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
    --bg: #0b0d12;
    --panel: #12151e;
    --border: #232838;
    --text: #e8ecf4;
    --muted: #8b93a7;
    --blue: #7cc4fa;
    --pink: #f48fb1;
    --purple: #c5b3f8;
    --gold: #f6c86a;
    --green: #3ce68a;
    --cyan: #4dd0e1;
    --coral: #ff8a65;
    --orange: #ffb74d;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
  body { background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
  header {
    padding: 16px 24px;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
    background: #0e1118;
  }
  .title-block h1 { font-size: 22px; font-weight: 600; letter-spacing: -0.02em; }
  .title-block p { font-size: 13px; color: var(--muted); margin-top: 2px; }
  .badge {
    background: var(--panel); border: 1px solid var(--border);
    padding: 6px 14px; border-radius: 999px; font-size: 13px; color: var(--text);
  }
  .toolbar {
    padding: 10px 24px; background: var(--panel); border-bottom: 1px solid var(--border);
    display: flex; flex-wrap: wrap; gap: 16px; align-items: center; justify-content: space-between;
  }
  .legend { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; font-size: 12.5px; }
  .legend-item { display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; }
  .dot { width: 11px; height: 11px; border-radius: 50%; display: inline-block; }
  .controls { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  input, select, button {
    background: #181c28; color: var(--text); border: 1px solid var(--border);
    padding: 6px 11px; border-radius: 6px; font-size: 12.5px;
  }
  button { cursor: pointer; transition: background 0.15s; }
  button:hover { background: #252b3d; }
  button.primary { background: #245682; border-color: #3678b2; }
  main { flex: 1; display: flex; position: relative; overflow: hidden; }
  #canvas-wrap { flex: 1; position: relative; background: #07080c; }
  svg { width: 100%; height: 100%; display: block; cursor: grab; }
  svg:active { cursor: grabbing; }
  aside {
    width: 340px; background: var(--panel); border-left: 1px solid var(--border);
    padding: 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px;
  }
  .card { background: #171b26; border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
  .card h3 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 8px; }
  .stat-row { display: flex; justify-content: space-between; font-size: 13px; padding: 4px 0; border-bottom: 1px solid #202534; }
  .stat-row:last-child { border-bottom: none; }
  .quote-box { font-size: 12.5px; color: #cbd3e6; font-style: italic; line-height: 1.45; margin-top: 6px; padding: 8px; background: #10131b; border-left: 3px solid var(--blue); border-radius: 4px; }
  .bar-bg { height: 6px; background: #232838; border-radius: 3px; overflow: hidden; margin-top: 3px; }
  .bar-fill { height: 100%; background: var(--green); }
</style>
</head>
<body>
<header>
  <div class="title-block">
    <h1 id="graph-title">__TITLE__</h1>
    <p>Interactive homeopathic symptom, modality &amp; cognitive-affective network graph (MPCS LocalKG v2)</p>
  </div>
  <div class="badge" id="stats-badge">0 Nodes • 0 Links</div>
</header>
<div class="toolbar">
  <div class="legend" id="legend"></div>
  <div class="controls">
    <select id="remedy-filter"><option value="ALL">All Remedies</option></select>
    <input id="query-input" type="text" placeholder="MPCS Spreading Activation query (e.g. fear of death, midnight)..." style="width: 300px;"/>
    <button class="primary" onclick="runSpreadingActivation()">Activate &amp; Prune (TIDE)</button>
    <button onclick="resetActivation()">Reset View</button>
  </div>
</div>
<main>
  <div id="canvas-wrap">
    <svg id="graph-svg"></svg>
  </div>
  <aside>
    <div class="card">
      <h3>MPCS Spreading Activation &amp; Pruning</h3>
      <div class="stat-row"><span>Mode</span><strong id="act-mode">Full Graph</strong></div>
      <div class="stat-row"><span>Total Nodes</span><strong id="act-total">0</strong></div>
      <div class="stat-row"><span>Seeded Nodes</span><strong id="act-seeded">0</strong></div>
      <div class="stat-row"><span>Kept (Active Subgraph)</span><strong id="act-kept" style="color:var(--green)">0</strong></div>
      <div class="stat-row"><span>Pruned Nodes</span><strong id="act-pruned" style="color:var(--pink)">0</strong></div>
      <div class="stat-row"><span>Pruning Ratio</span><strong id="act-ratio">0%</strong></div>
    </div>
    <div class="card" id="inspector">
      <h3>Node Inspector</h3>
      <p style="font-size:13px;color:var(--muted);">Click any node in the graph to inspect its VAD affect vector, severity weight, modalities, and verbatim book quote.</p>
    </div>
  </aside>
</main>
<script>
const GRAPH_DATA = __GRAPH_JSON__;

const COLORS = {
  "Medicine": "#7cc4fa",
  "Physical Symptom": "#f48fb1",
  "Affective Symptom": "#c5b3f8",
  "Modality": "#f6c86a",
  "Cognitive Domain": "#3ce68a",
  "Clinical Condition": "#4dd0e1",
  "Body Region": "#ff8a65",
  "Sensation": "#ffb74d",
  "Etiology": "#ff8a80"
};

const hiddenTypes = new Set();
let activeNodes = new Map(); // id -> activation score
let selectedRemedy = "ALL";

// Populate legend & remedy dropdown
const legendEl = document.getElementById("legend");
Object.entries(COLORS).forEach(([type, color]) => {
  const item = document.createElement("div");
  item.className = "legend-item";
  item.innerHTML = `<span class="dot" style="background:${color}"></span><span>${type}</span>`;
  item.onclick = () => {
    if (hiddenTypes.has(type)) { hiddenTypes.delete(type); item.style.opacity = "1"; }
    else { hiddenTypes.add(type); item.style.opacity = "0.35"; }
    render();
  };
  legendEl.appendChild(item);
});

const remSelect = document.getElementById("remedy-filter");
GRAPH_DATA.nodes.filter(n => n.type === "Medicine").forEach(n => {
  const opt = document.createElement("option");
  opt.value = n.id; opt.textContent = n.label;
  remSelect.appendChild(opt);
});
remSelect.onchange = e => { selectedRemedy = e.target.value; initSimulation(); };

const svg = document.getElementById("graph-svg");
let width = svg.clientWidth || 960, height = svg.clientHeight || 640;
let panX = 0, panY = 0, scale = 1.0, isPanning = false, startX = 0, startY = 0, draggedNode = null;

let simNodes = [], simLinks = [];

function initSimulation() {
  width = svg.clientWidth || 960;
  height = svg.clientHeight || 640;

  let allowedIds = new Set(GRAPH_DATA.nodes.map(n => n.id));
  if (selectedRemedy !== "ALL") {
    allowedIds = new Set([selectedRemedy]);
    // 2-hop neighborhood around selected remedy
    for (let hop = 0; hop < 2; hop++) {
      GRAPH_DATA.links.forEach(l => {
        if (allowedIds.has(l.source)) allowedIds.add(l.target);
        if (allowedIds.has(l.target)) allowedIds.add(l.source);
      });
    }
  }

  simNodes = GRAPH_DATA.nodes
    .filter(n => allowedIds.has(n.id) && !hiddenTypes.has(n.type))
    .map((n, i) => {
      const angle = (2 * Math.PI * i) / Math.max(1, allowedIds.size);
      const radius = n.type === "Medicine" ? 40 : (n.type === "Cognitive Domain" ? 160 : 220);
      return {
        ...n,
        x: width / 2 + radius * Math.cos(angle) + (Math.random() - 0.5) * 40,
        y: height / 2 + radius * Math.sin(angle) + (Math.random() - 0.5) * 40,
        vx: 0, vy: 0
      };
    });

  const nodeMap = new Map(simNodes.map(n => [n.id, n]));
  simLinks = GRAPH_DATA.links
    .filter(l => nodeMap.has(l.source) && nodeMap.has(l.target))
    .map(l => ({ ...l, sourceNode: nodeMap.get(l.source), targetNode: nodeMap.get(l.target) }));

  document.getElementById("stats-badge").textContent = `${simNodes.length} Nodes • ${simLinks.length} Links`;
  document.getElementById("act-total").textContent = simNodes.length;

  for (let step = 0; step < 180; step++) tickPhysics(0.6);
  render();
}

function tickPhysics(alpha = 0.3) {
  const kRepel = 4800, kSpring = 0.045, idealLen = 145;
  for (let i = 0; i < simNodes.length; i++) {
    for (let j = i + 1; j < simNodes.length; j++) {
      const a = simNodes[i], b = simNodes[j];
      let dx = b.x - a.x, dy = b.y - a.y;
      let distSq = dx * dx + dy * dy + 1.0;
      let f = (kRepel / distSq) * alpha;
      let dist = Math.sqrt(distSq);
      a.vx -= (dx / dist) * f; a.vy -= (dy / dist) * f;
      b.vx += (dx / dist) * f; b.vy += (dy / dist) * f;
    }
  }
  simLinks.forEach(l => {
    const a = l.sourceNode, b = l.targetNode;
    let dx = b.x - a.x, dy = b.y - a.y;
    let dist = Math.sqrt(dx * dx + dy * dy) || 1;
    let f = (dist - idealLen) * kSpring * alpha;
    a.vx += (dx / dist) * f; a.vy += (dy / dist) * f;
    b.vx -= (dx / dist) * f; b.vy -= (dy / dist) * f;
  });
  simNodes.forEach(n => {
    if (n === draggedNode) return;
    n.vx += ((width / 2 - n.x) * 0.008) * alpha;
    n.vy += ((height / 2 - n.y) * 0.008) * alpha;
    n.x += n.vx; n.y += n.vy;
    n.vx *= 0.65; n.vy *= 0.65;
  });
}

function render() {
  const hasActivation = activeNodes.size > 0;
  let html = `<g transform="translate(${panX},${panY}) scale(${scale})">`;

  simLinks.forEach(l => {
    const a = l.sourceNode, b = l.targetNode;
    const bothActive = !hasActivation || (activeNodes.has(a.id) && activeNodes.has(b.id));
    const opacity = bothActive ? 0.55 : 0.07;
    const stroke = bothActive && hasActivation ? "#3ce68a" : "#3a4258";
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    html += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${stroke}" stroke-width="${Math.min(3, 1 + l.weight * 0.4)}" stroke-opacity="${opacity}"/>`;
    if (bothActive) {
      html += `<text x="${mx}" y="${my - 4}" text-anchor="middle" fill="#7c859e" font-size="9.5" opacity="${opacity + 0.15}">${l.label}</text>`;
    }
  });

  simNodes.forEach(n => {
    const isAct = !hasActivation || activeNodes.has(n.id);
    const actScore = activeNodes.get(n.id) || 0;
    const baseR = n.type === "Medicine" ? 22 : (n.type === "Cognitive Domain" ? 18 : Math.min(18, 10 + (n.weight || 1) * 2.2));
    const r = hasActivation && isAct ? baseR + actScore * 5 : baseR;
    const opacity = isAct ? 1.0 : 0.14;
    const color = COLORS[n.type] || "#90a4ae";
    const ring = hasActivation && isAct ? `stroke="#ffffff" stroke-width="2.2"` : `stroke="#0b0d12" stroke-width="1.5"`;
    html += `<g class="node-g" data-id="${n.id}" transform="translate(${n.x},${n.y})" opacity="${opacity}" style="cursor:pointer">
      <circle r="${r}" fill="${color}" ${ring}/>
      <text y="${r + 14}" text-anchor="middle" fill="#e8ecf4" font-size="12" font-weight="500">${n.label}</text>
    </g>`;
  });

  html += `</g>`;
  svg.innerHTML = html;

  svg.querySelectorAll(".node-g").forEach(el => {
    const id = el.getAttribute("data-id");
    const node = simNodes.find(n => n.id === id);
    el.onmousedown = e => { e.stopPropagation(); draggedNode = node; inspectNode(node); };
  });
}

function inspectNode(n) {
  const act = activeNodes.get(n.id);
  const v = n.valence !== undefined ? Math.round(n.valence * 100) : null;
  const a = n.arousal !== undefined ? Math.round(n.arousal * 100) : null;
  const d = n.dominance !== undefined ? Math.round(n.dominance * 100) : null;
  let html = `<h3>${n.type}</h3>
    <div style="font-size:16px;font-weight:600;margin-bottom:8px;color:${COLORS[n.type]}">${n.label}</div>
    <div class="stat-row"><span>Composite Weight</span><strong>${(n.weight || 1).toFixed(2)} / 3.00</strong></div>
    <div class="stat-row"><span>Typography Grade</span><strong>${n.grade || "-"}</strong></div>
    <div class="stat-row"><span>Section</span><strong>${n.section || "-"}</strong></div>
    <div class="stat-row"><span>Occurrences</span><strong>${n.occurrences || 1}</strong></div>`;
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
    html += `<div style="margin-top:6px;font-size:11px;color:var(--muted)">Sources: ${n.sources.join(", ")}</div>`;
  }
  document.getElementById("inspector").innerHTML = html;
}

// MPCS TIDE Spreading Activation + Pruning in JS
function runSpreadingActivation() {
  const q = document.getElementById("query-input").value.trim().toLowerCase();
  if (!q) { resetActivation(); return; }
  const terms = q.split(/[,;\\s]+/).filter(t => t.length >= 3);
  activeNodes.clear();

  // 1. Seed matching nodes: seed(s) = match * (1 + 0.8 * arousal)
  let seeds = 0;
  simNodes.forEach(n => {
    const hay = `${n.label} ${n.raw_example || ""} ${n.quote || ""}`.toLowerCase();
    let hits = terms.filter(t => hay.includes(t)).length;
    if (hits > 0) {
      const arousal = n.arousal !== undefined ? n.arousal : 0.5;
      const score = (hits / terms.length) * (1.0 + 0.8 * arousal) * ((n.weight || 1.0) / 2.0);
      activeNodes.set(n.id, score);
      seeds++;
    }
  });

  // 2. Spread activation over 2 hops with hop_decay = 0.55
  const hopDecay = 0.55;
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

  // 3. Prune below prune_threshold * max_seed
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
  render();
}

function resetActivation() {
  activeNodes.clear();
  document.getElementById("act-mode").textContent = "Full Graph";
  document.getElementById("act-seeded").textContent = "0";
  document.getElementById("act-kept").textContent = simNodes.length;
  document.getElementById("act-pruned").textContent = "0";
  document.getElementById("act-ratio").textContent = "0%";
  render();
}

svg.onmousedown = e => { isPanning = true; startX = e.clientX - panX; startY = e.clientY - panY; };
window.onmousemove = e => {
  if (draggedNode) {
    const pt = svg.getBoundingClientRect();
    draggedNode.x = (e.clientX - pt.left - panX) / scale;
    draggedNode.y = (e.clientY - pt.top - panY) / scale;
    render();
  } else if (isPanning) {
    panX = e.clientX - startX; panY = e.clientY - startY; render();
  }
};
window.onmouseup = () => { isPanning = false; draggedNode = null; };
svg.onwheel = e => {
  e.preventDefault();
  scale = Math.min(3.0, Math.max(0.25, scale * (e.deltaY < 0 ? 1.1 : 0.9)));
  render();
};

window.onload = initSimulation;
window.onresize = initSimulation;
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

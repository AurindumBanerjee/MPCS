"""Generate pure Knowledge Graph Showcase HTML files for Arnica montana and Atropa belladonna.
No model integration, no TIDE spreading activation, no search box.
Purely showcases the Knowledge Graph, its entities, relationships, quotes, and topology.
"""

import json
from pathlib import Path

DATA_DIR = Path(r"D:\MyStuff\GitHub\MPCS\LocalKG\data\extracted")
DOCS_DIR = Path(r"D:\MyStuff\GitHub\MPCS\docs")

def build_pure_kg_html(graph_data: dict, remedy_title: str, remedy_subtitle: str) -> str:
    # Ensure remedy node metadata is clean
    for n in graph_data.get("nodes", []):
        if n.get("id") == "remedy:arnica_montana":
            n["kingdom"] = "plant"
            n["latin_name"] = "Arnica montana"

    nodes_json = json.dumps(graph_data, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{remedy_title} — Knowledge Graph Showcase</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
  :root {{
    --bg: #07090e;
    --panel: #10141f;
    --panel-alt: #161b2a;
    --border: #22293d;
    --border-light: #2d3752;
    --text: #eef2f9;
    --text-muted: #8b95ab;
    --blue: #58b8ff;
    --purple: #c5b3f8;
    --pink: #f48fb1;
    --gold: #ffd166;
    --green: #06d6a0;
    --cyan: #4dd0e1;
    --coral: #ff8a65;
    --orange: #ffb74d;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
  body {{ background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}

  /* Header */
  header {{
    padding: 12px 24px;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
    background: #0b0e17;
    flex-shrink: 0;
  }}
  .title-block h1 {{
    font-size: 19px; font-weight: 600; letter-spacing: -0.02em; color: #fff;
    display: flex; align-items: center; gap: 10px;
  }}
  .title-block .tag {{
    font-size: 10.5px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em;
    padding: 2px 8px; border-radius: 99px; background: rgba(88, 184, 255, 0.12);
    border: 1px solid rgba(88, 184, 255, 0.3); color: var(--blue);
  }}
  .title-block p {{ font-size: 12px; color: var(--text-muted); margin-top: 3px; }}
  .header-right {{ display: flex; align-items: center; gap: 12px; }}
  .badge {{
    background: var(--panel-alt); border: 1px solid var(--border);
    padding: 5px 14px; border-radius: 999px; font-size: 12.5px; color: var(--text); font-weight: 500;
  }}

  /* Toolbar */
  .toolbar {{
    padding: 9px 24px; background: var(--panel); border-bottom: 1px solid var(--border);
    display: flex; flex-wrap: wrap; gap: 16px; align-items: center; justify-content: space-between;
    flex-shrink: 0;
  }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 12px; }}
  .legend-item {{
    display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none;
    padding: 4px 10px; border-radius: 6px; background: var(--panel-alt); border: 1px solid var(--border);
    transition: all 0.15s; font-size: 11.5px;
  }}
  .legend-item:hover {{ border-color: var(--blue); }}
  .legend-item.dimmed {{ opacity: 0.32; }}
  .dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; box-shadow: 0 0 6px currentColor; }}
  
  .controls {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
  button, select {{
    background: var(--panel-alt); color: var(--text); border: 1px solid var(--border);
    padding: 6px 12px; border-radius: 6px; font-size: 12px; outline: none; cursor: pointer;
    transition: all 0.15s; font-weight: 500;
  }}
  button:hover, select:hover {{ background: #232b42; border-color: #364263; }}
  button.active-toggle {{ background: #143554; border-color: var(--blue); color: #fff; }}

  /* Main Workspace */
  main {{ flex: 1; display: flex; position: relative; overflow: hidden; }}

  /* Left Sidebar: Concept Directory */
  #left-sidebar {{
    width: 270px; background: var(--panel); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; overflow: hidden; flex-shrink: 0;
  }}
  .sidebar-header {{
    padding: 12px 14px; border-bottom: 1px solid var(--border);
    display: flex; flex-direction: column; gap: 8px;
  }}
  .sidebar-header h3 {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); }}
  .search-input {{
    background: var(--panel-alt); color: var(--text); border: 1px solid var(--border);
    padding: 6px 10px; border-radius: 6px; font-size: 12px; outline: none; width: 100%;
  }}
  .search-input:focus {{ border-color: var(--blue); }}
  #concept-list {{ flex: 1; overflow-y: auto; padding: 8px; display: flex; flex-direction: column; gap: 4px; }}
  .concept-group-title {{
    font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.08em;
    color: var(--text-muted); padding: 8px 6px 4px; font-weight: 600;
  }}
  .concept-item {{
    padding: 6px 9px; border-radius: 6px; cursor: pointer; font-size: 12px;
    display: flex; align-items: center; justify-content: space-between;
    color: #cbd5e8; transition: background 0.12s; border-left: 2px solid transparent;
  }}
  .concept-item:hover {{ background: var(--panel-alt); color: #fff; }}
  .concept-item.selected {{ background: #1c334d; color: #fff; border-left-color: var(--blue); font-weight: 600; }}
  .concept-type-dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; margin-right: 6px; }}

  /* Center Interactive Canvas */
  #canvas-wrap {{ flex: 1; position: relative; background: radial-gradient(circle at center, #0e1320 0%, #06080d 100%); overflow: hidden; }}
  canvas {{ width: 100%; height: 100%; display: block; cursor: grab; }}
  canvas:active {{ cursor: grabbing; }}
  .canvas-overlay {{
    position: absolute; bottom: 16px; left: 16px; display: flex; gap: 8px; align-items: center;
    background: rgba(16, 20, 31, 0.9); backdrop-filter: blur(8px);
    padding: 7px 13px; border-radius: 8px; border: 1px solid var(--border); font-size: 12px;
  }}
  .hover-tooltip {{
    position: absolute; pointer-events: none; display: none;
    background: rgba(14, 18, 28, 0.96); border: 1px solid #394566;
    padding: 9px 12px; border-radius: 8px; font-size: 12px; color: #fff;
    box-shadow: 0 8px 24px rgba(0,0,0,0.65); max-width: 320px; z-index: 20;
  }}

  /* Right Sidebar: Node & Topology Inspector */
  aside {{
    width: 360px; background: var(--panel); border-left: 1px solid var(--border);
    padding: 14px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; flex-shrink: 0;
  }}
  .card {{ background: var(--panel-alt); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }}
  .card h3 {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 10px; }}
  .stat-row {{ display: flex; justify-content: space-between; font-size: 12px; padding: 5px 0; border-bottom: 1px solid #1f263a; }}
  .stat-row:last-child {{ border-bottom: none; }}
  .quote-box {{
    font-size: 12px; color: #d5def0; font-style: italic; line-height: 1.5;
    margin-top: 10px; padding: 10px 12px; background: #0c0f18; border-left: 3px solid var(--blue); border-radius: 5px;
  }}
  .bar-bg {{ height: 6px; background: #232a3e; border-radius: 3px; overflow: hidden; margin-top: 4px; }}
  .bar-fill {{ height: 100%; background: var(--green); }}
  .neighbor-chip {{
    display: inline-flex; align-items: center; gap: 5px; padding: 4px 8px; margin: 3px 4px 0 0; border-radius: 5px;
    font-size: 11px; background: #101420; border: 1px solid var(--border); cursor: pointer; transition: all 0.12s;
  }}
  .neighbor-chip:hover {{ border-color: var(--blue); color: var(--blue); }}
  .empty-state {{ font-size: 12px; color: var(--text-muted); line-height: 1.5; }}
</style>
</head>
<body>

<header>
  <div class="title-block">
    <h1>
      <span>{remedy_title}</span>
      <span class="tag">Knowledge Graph Showcase</span>
    </h1>
    <p>{remedy_subtitle}</p>
  </div>
  <div class="header-right">
    <div class="badge" id="stats-badge">Loading Knowledge Graph...</div>
  </div>
</header>

<div class="toolbar">
  <div class="legend" id="legend"></div>
  <div class="controls">
    <button id="layout-btn" class="active-toggle" onclick="toggleLayoutMode()">Layout: Radial Mandala</button>
    <button id="hover-mode-btn" onclick="toggleHoverEdgeMode()">Hover: Subgraph + Outside</button>
    <button id="edge-style-btn" onclick="toggleEdgeStyle()">Edge: Straight</button>
    <button id="labels-btn" onclick="toggleAllLabels()">Labels: Smart Auto</button>
    <button onclick="fitToScreen()">Fit to Screen</button>
    <button onclick="resetView()">Reset View</button>
  </div>
</div>

<main>
  <!-- Left Concept Directory -->
  <div id="left-sidebar">
    <div class="sidebar-header">
      <h3>Entity Directory (<span id="concept-total-count">0</span>)</h3>
    </div>
    <div id="concept-list"></div>
  </div>

  <!-- Center Canvas -->
  <div id="canvas-wrap">
    <canvas id="graph-canvas"></canvas>
    <div id="tooltip" class="hover-tooltip"></div>
    <div class="canvas-overlay">
      <button onclick="zoomBy(1.28)">Zoom +</button>
      <button onclick="zoomBy(0.78)">Zoom −</button>
      <span style="color:var(--text-muted);margin-left:6px;">Min Weight: <strong id="weight-val">1.0</strong></span>
      <input id="weight-slider" type="range" min="1.0" max="2.8" step="0.1" value="1.0" style="width:85px" oninput="updateWeightFilter(this.value)"/>
    </div>
  </div>

  <!-- Right Inspector & Graph Summary -->
  <aside>
    <!-- Node Inspector -->
    <div class="card" id="inspector">
      <h3>Entity Inspector</h3>
      <div class="empty-state">
        Click any node on the canvas or select an entity from the left directory to inspect its clinical severity weight, repertory typography grade, verbatim proving quote, literature sources, and connected concepts.
      </div>
    </div>

    <!-- Graph Topology Summary Card -->
    <div class="card" id="summary-card">
      <h3>Knowledge Graph Summary</h3>
      <div class="stat-row"><span>Primary Medicine</span><strong>{remedy_title}</strong></div>
      <div class="stat-row"><span>Hover Highlight</span><strong id="showcase-hover-mode" style="color:var(--blue)">Subgraph + Outside</strong></div>
      <div class="stat-row"><span>Edge Style</span><strong id="showcase-edge-style" style="color:var(--gold)">Straight Vectors</strong></div>
      <div class="stat-row"><span>Total Entities (Nodes)</span><strong id="summary-nodes">0</strong></div>
      <div class="stat-row"><span>Relationships (Edges)</span><strong id="summary-links">0</strong></div>
      <div class="stat-row"><span>Affective Symptoms</span><strong id="summary-affective">0</strong></div>
      <div class="stat-row"><span>Physical Symptoms</span><strong id="summary-physical">0</strong></div>
      <div class="stat-row"><span>Modalities (Agg / Amel)</span><strong id="summary-modalities">0</strong></div>
      <div class="stat-row"><span>Clinical Literature</span><strong id="summary-clinical">0</strong></div>
      <div style="margin-top:10px;font-size:11px;color:var(--text-muted);display:flex;align-items:center;justify-content:space-between;border-top:1px solid var(--border);padding-top:6px;">
        <span style="color:#06d6a0;">● Subgraph Link</span>
        <span style="color:#ff79c6;">┄ External Bridge</span>
      </div>
    </div>
  </aside>
</main>

<script>
const GRAPH_DATA = {nodes_json};

const COLORS = {{
  "Medicine": "#58b8ff",
  "Affective Symptom": "#c5b3f8",
  "Cognitive Domain": "#06d6a0",
  "Physical Symptom": "#f48fb1",
  "Modality": "#ffd166",
  "Clinical Condition": "#4dd0e1",
  "Body Region": "#ff8a65",
  "Sensation": "#ffb74d",
  "Etiology": "#ff8a80"
}};

const hiddenTypes = new Set();
let inspectedNode = null;
let hoveredNode = null;
let minWeight = 1.0;
let layoutMode = "mandala"; // "mandala" | "clusters" | "rings"
let labelMode = "smart";     // "smart" | "all" | "hubs"
let hoverEdgeMode = "subgraph_all"; // "subgraph_all" | "subgraph_only" | "all_unified"
let edgeStyle = "straight"; // "straight" | "curved" | "glow"

function toggleHoverEdgeMode() {{
  const modes = ["subgraph_all", "subgraph_only", "all_unified"];
  hoverEdgeMode = modes[(modes.indexOf(hoverEdgeMode) + 1) % modes.length];
  const btn = document.getElementById("hover-mode-btn");
  const titles = {{
    subgraph_all: "Hover: Subgraph + Outside",
    subgraph_only: "Hover: Subgraph Only",
    all_unified: "Hover: Classic Focus"
  }};
  btn.textContent = titles[hoverEdgeMode];
  btn.classList.toggle("active-toggle", hoverEdgeMode !== "all_unified");
  const el = document.getElementById("showcase-hover-mode");
  if (el) {{
    const desc = {{
      subgraph_all: "Subgraph + Outside",
      subgraph_only: "Subgraph Only (Strict)",
      all_unified: "Classic Unified"
    }};
    el.textContent = desc[hoverEdgeMode];
    el.style.color = hoverEdgeMode === "subgraph_only" ? "var(--green)" : (hoverEdgeMode === "subgraph_all" ? "var(--blue)" : "var(--text-muted)");
  }}
  drawCanvas();
}}

function toggleEdgeStyle() {{
  const styles = ["straight", "curved", "glow"];
  edgeStyle = styles[(styles.indexOf(edgeStyle) + 1) % styles.length];
  const btn = document.getElementById("edge-style-btn");
  const titles = {{
    straight: "Edge: Straight",
    curved: "Edge: Curved Arcs",
    glow: "Edge: Neon Glow"
  }};
  btn.textContent = titles[edgeStyle];
  btn.classList.toggle("active-toggle", edgeStyle !== "straight");
  const el = document.getElementById("showcase-edge-style");
  if (el) {{
    const desc = {{
      straight: "Straight Vectors",
      curved: "Curved Arcs",
      glow: "Neon Glow (Bloom)"
    }};
    el.textContent = desc[edgeStyle];
    el.style.color = edgeStyle === "glow" ? "var(--gold)" : (edgeStyle === "curved" ? "var(--blue)" : "var(--text-muted)");
  }}
  drawCanvas();
}}

// Build adjacency lookup
const neighborsMap = new Map();
const nodeDegree = new Map();
GRAPH_DATA.nodes.forEach(n => {{ neighborsMap.set(n.id, []); nodeDegree.set(n.id, 0); }});
GRAPH_DATA.links.forEach(l => {{
  if (neighborsMap.has(l.source) && neighborsMap.has(l.target)) {{
    neighborsMap.get(l.source).push({{ id: l.target, rel: l.label }});
    neighborsMap.get(l.target).push({{ id: l.source, rel: l.label }});
    nodeDegree.set(l.source, (nodeDegree.get(l.source) || 0) + 1);
    nodeDegree.set(l.target, (nodeDegree.get(l.target) || 0) + 1);
  }}
}});

// Populate Graph Topology Summary Card
document.getElementById("summary-nodes").textContent = GRAPH_DATA.nodes.length;
document.getElementById("summary-links").textContent = GRAPH_DATA.links.length;
document.getElementById("summary-affective").textContent = GRAPH_DATA.nodes.filter(n => n.type === "Affective Symptom").length;
document.getElementById("summary-physical").textContent = GRAPH_DATA.nodes.filter(n => n.type === "Physical Symptom").length;
document.getElementById("summary-modalities").textContent = GRAPH_DATA.nodes.filter(n => n.type === "Modality").length;
document.getElementById("summary-clinical").textContent = GRAPH_DATA.nodes.filter(n => n.type === "Clinical Condition").length;
document.getElementById("concept-total-count").textContent = GRAPH_DATA.nodes.length;

// Populate Legend
const legendEl = document.getElementById("legend");
const typeCounts = {{}};
GRAPH_DATA.nodes.forEach(n => {{ typeCounts[n.type] = (typeCounts[n.type] || 0) + 1; }});
Object.entries(COLORS).forEach(([type, color]) => {{
  if (!typeCounts[type]) return;
  const item = document.createElement("div");
  item.className = "legend-item";
  item.innerHTML = `<span class="dot" style="background:${{color}};color:${{color}}"></span><span>${{type}} (${{typeCounts[type]}})</span>`;
  item.onclick = () => {{
    if (hiddenTypes.has(type)) {{
      hiddenTypes.delete(type);
      item.classList.remove("dimmed");
    }} else {{
      hiddenTypes.add(type);
      item.classList.add("dimmed");
    }}
    rebuildGraphLayout();
  }};
  legendEl.appendChild(item);
}});

// Populate Left Entity Directory
function renderConceptSidebar() {{
  const listEl = document.getElementById("concept-list");
  
  // Group by category
  const groups = [
    {{ title: "Primary Medicine", types: ["Medicine"] }},
    {{ title: "Cognitive Domains", types: ["Cognitive Domain"] }},
    {{ title: "Affective Symptoms", types: ["Affective Symptom"] }},
    {{ title: "Physical Symptoms", types: ["Physical Symptom"] }},
    {{ title: "Modalities", types: ["Modality"] }},
    {{ title: "Clinical Literature", types: ["Clinical Condition"] }},
    {{ title: "Body Regions & Sensations", types: ["Body Region", "Sensation", "Etiology"] }}
  ];

  let html = "";
  groups.forEach(g => {{
    const items = GRAPH_DATA.nodes
      .filter(n => g.types.includes(n.type))
      .sort((a, b) => (b.weight || 1) - (a.weight || 1));
    
    if (items.length === 0) return;
    html += `<div class="concept-group-title">${{g.title}} (${{items.length}})</div>`;
    items.forEach(n => {{
      const sel = inspectedNode && inspectedNode.id === n.id ? "selected" : "";
      const dotColor = COLORS[n.type] || "#888";
      html += `<div class="concept-item ${{sel}}" onclick="focusNodeById('${{n.id.replace(/'/g, "\\\\'")}}')">
        <span><span class="concept-type-dot" style="background:${{dotColor}}"></span>${{n.label}}</span>
        <span style="font-size:10.5px;color:var(--text-muted)">${{(n.weight || 1).toFixed(1)}}</span>
      </div>`;
    }});
  }});

  listEl.innerHTML = html;
}}
renderConceptSidebar();

function updateWeightFilter(val) {{
  minWeight = parseFloat(val);
  document.getElementById("weight-val").textContent = minWeight.toFixed(1);
  rebuildGraphLayout();
}}

function toggleLayoutMode() {{
  const modes = ["mandala", "clusters", "rings"];
  layoutMode = modes[(modes.indexOf(layoutMode) + 1) % modes.length];
  const labels = {{
    mandala: "Layout: Radial Mandala",
    clusters: "Layout: Galaxy Clusters",
    rings: "Layout: Concentric Rings"
  }};
  document.getElementById("layout-btn").textContent = labels[layoutMode];
  rebuildGraphLayout();
}}

function toggleAllLabels() {{
  const order = ["smart", "all", "hubs"];
  labelMode = order[(order.indexOf(labelMode) + 1) % order.length];
  const labels = {{ smart: "Labels: Smart Auto", all: "Labels: Always Show All", hubs: "Labels: Hubs Only" }};
  document.getElementById("labels-btn").textContent = labels[labelMode];
  drawCanvas();
}}

// Canvas Setup
const canvas = document.getElementById("graph-canvas");
const ctx = canvas.getContext("2d");
const tooltip = document.getElementById("tooltip");
let width = 960, height = 680, dpr = window.devicePixelRatio || 1;
let panX = 0, panY = 0, scale = 1.0;
let isPanning = false, startX = 0, startY = 0, draggedNode = null;
let simNodes = [], simLinks = [];

function resizeCanvas() {{
  const rect = canvas.parentElement.getBoundingClientRect();
  width = rect.width || 960;
  height = rect.height || 680;
  dpr = window.devicePixelRatio || 1;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
}}

function hashStr(str) {{
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) {{
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }}
  return (h >>> 0) / 4294967295;
}}

function rebuildGraphLayout() {{
  resizeCanvas();

  // Filter allowed nodes based on legend toggles & min weight
  simNodes = GRAPH_DATA.nodes
    .filter(n => !hiddenTypes.has(n.type) && (n.type === "Medicine" || n.type === "Cognitive Domain" || (n.weight || 1.0) >= minWeight))
    .map(n => ({{ ...n, x: 0, y: 0 }}));

  const nodeMap = new Map(simNodes.map(n => [n.id, n]));
  simLinks = GRAPH_DATA.links
    .filter(l => nodeMap.has(l.source) && nodeMap.has(l.target))
    .map(l => ({{ ...l, sourceNode: nodeMap.get(l.source), targetNode: nodeMap.get(l.target) }}));

  const meds = simNodes.filter(n => n.type === "Medicine");
  const domains = simNodes.filter(n => n.type === "Cognitive Domain");
  const regions = simNodes.filter(n => n.type === "Body Region" || n.type === "Clinical Condition");
  const others = simNodes.filter(n => !["Medicine", "Cognitive Domain", "Body Region", "Clinical Condition"].includes(n.type));

  if (layoutMode === "mandala") {{
    // Radial Mandala: Primary remedy pinned at origin (0, 0)
    const center = meds[0];
    if (center) {{ center.x = 0; center.y = 0; center.pinned = true; }}

    domains.forEach((d, i) => {{
      const a = (2 * Math.PI * i) / Math.max(1, domains.length);
      d.x = 240 * Math.cos(a);
      d.y = 240 * Math.sin(a);
    }});

    regions.forEach((r, i) => {{
      const a = (2 * Math.PI * i) / Math.max(1, regions.length) + 0.35;
      r.x = 360 * Math.cos(a);
      r.y = 360 * Math.sin(a);
    }});

    others.forEach((n, i) => {{
      const ring = n.type === "Affective Symptom" ? 520 : (n.type === "Modality" ? 680 : 840);
      const spread = (i % 3 - 1) * 55;
      const a = (2 * Math.PI * i) / Math.max(1, others.length);
      n.x = (ring + spread) * Math.cos(a);
      n.y = (ring + spread) * Math.sin(a);
    }});
  }} else if (layoutMode === "clusters") {{
    // Clustered around connected hubs
    domains.forEach((d, i) => {{
      const a = (2 * Math.PI * i) / Math.max(1, domains.length);
      d.x = 320 * Math.cos(a);
      d.y = 320 * Math.sin(a);
    }});
    regions.forEach((r, i) => {{
      const a = (2 * Math.PI * i) / Math.max(1, regions.length);
      r.x = 580 * Math.cos(a);
      r.y = 580 * Math.sin(a);
    }});
    if (meds[0]) {{ meds[0].x = 0; meds[0].y = 0; }}

    others.forEach((n, i) => {{
      const hubs = [];
      (neighborsMap.get(n.id) || []).forEach(nb => {{
        const target = nodeMap.get(nb.id);
        if (target && ["Medicine", "Cognitive Domain", "Body Region"].includes(target.type)) hubs.push(target);
      }});
      let cx = 0, cy = 0;
      if (hubs.length > 0) {{
        hubs.forEach(h => {{ cx += h.x; cy += h.y; }});
        cx /= hubs.length; cy /= hubs.length;
      }} else {{
        const a = 2 * Math.PI * hashStr(n.id);
        cx = 900 * Math.cos(a); cy = 900 * Math.sin(a);
      }}
      const r = 100 + (i % 4) * 40;
      const a = 2 * Math.PI * hashStr(n.id + ":" + i);
      n.x = cx + r * Math.cos(a);
      n.y = cy + r * Math.sin(a);
    }});
  }} else {{
    // Concentric semantic rings
    const rings = [
      {{ list: meds, r: 0 }},
      {{ list: domains, r: 240 }},
      {{ list: regions, r: 420 }},
      {{ list: others.filter(n => n.type === "Affective Symptom"), r: 620 }},
      {{ list: others.filter(n => n.type === "Modality"), r: 800 }},
      {{ list: others.filter(n => n.type !== "Affective Symptom" && n.type !== "Modality"), r: 980 }}
    ];
    rings.forEach(rg => {{
      rg.list.forEach((n, i) => {{
        if (rg.r === 0) {{ n.x = 0; n.y = 0; return; }}
        const a = (2 * Math.PI * i) / Math.max(1, rg.list.length);
        const j = (i % 2 === 0 ? 1 : -1) * 35;
        n.x = (rg.r + j) * Math.cos(a);
        n.y = (rg.r + j) * Math.sin(a);
      }});
    }});
  }}

  // Fast collision relaxation
  resolveNodeCollisions(simNodes, 8);

  document.getElementById("stats-badge").textContent = `${{simNodes.length}} Nodes • ${{simLinks.length}} Links`;
  fitToScreen();
}}

function resolveNodeCollisions(nodes, iterations = 8) {{
  const minSep = 56;
  const cellSize = minSep * 1.5;

  for (let iter = 0; iter < iterations; iter++) {{
    const grid = new Map();
    nodes.forEach((n, idx) => {{
      const gx = Math.floor(n.x / cellSize), gy = Math.floor(n.y / cellSize);
      const key = `${{gx}},${{gy}}`;
      if (!grid.has(key)) grid.set(key, []);
      grid.get(key).push(idx);
    }});

    nodes.forEach((a, i) => {{
      if (a.pinned) return;
      const gx = Math.floor(a.x / cellSize), gy = Math.floor(a.y / cellSize);
      for (let dx = -1; dx <= 1; dx++) {{
        for (let dy = -1; dy <= 1; dy++) {{
          const cell = grid.get(`${{gx + dx}},${{gy + dy}}`);
          if (!cell) continue;
          for (let k = 0; k < cell.length; k++) {{
            const j = cell[k];
            if (j <= i) continue;
            const b = nodes[j];
            let vx = b.x - a.x, vy = b.y - a.y;
            let distSq = vx * vx + vy * vy;
            const req = (a.type === "Medicine" || b.type === "Medicine") ? minSep * 1.5 : minSep;
            if (distSq < req * req) {{
              let dist = Math.sqrt(distSq) || 0.1;
              let overlap = (req - dist) * 0.5;
              let nx = vx / dist, ny = vy / dist;
              a.x -= nx * overlap; a.y -= ny * overlap;
              if (!b.pinned) {{ b.x += nx * overlap; b.y += ny * overlap; }}
            }}
          }}
        }}
      }}
    }});
  }}
}}

function fitToScreen() {{
  if (simNodes.length === 0) {{ drawCanvas(); return; }}
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  simNodes.forEach(n => {{
    if (n.x < minX) minX = n.x;
    if (n.x > maxX) maxX = n.x;
    if (n.y < minY) minY = n.y;
    if (n.y > maxY) maxY = n.y;
  }});

  const pad = 120;
  const spanX = Math.max(300, (maxX - minX) + pad * 2);
  const spanY = Math.max(300, (maxY - minY) + pad * 2);
  scale = Math.min(2.4, Math.max(0.18, Math.min(width / spanX, height / spanY)));
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  panX = width / 2 - cx * scale;
  panY = height / 2 - cy * scale;
  drawCanvas();
}}

function resetView() {{
  inspectedNode = null;
  hoveredNode = null;
  document.getElementById("inspector").innerHTML = `<h3>Entity Inspector</h3><div class="empty-state">Click any node on the canvas or select an entity from the left directory to inspect its clinical severity weight, repertory typography grade, verbatim proving quote, literature sources, and connected concepts.</div>`;
  fitToScreen();
}}

function zoomBy(factor) {{
  const newScale = Math.min(4.5, Math.max(0.12, scale * factor));
  panX = width / 2 - (width / 2 - panX) * (newScale / scale);
  panY = height / 2 - (height / 2 - panY) * (newScale / scale);
  scale = newScale;
  drawCanvas();
}}

function nodeRadius(n) {{
  if (n.type === "Medicine") return 22;
  if (n.type === "Cognitive Domain") return 17;
  if (n.type === "Clinical Condition" || n.type === "Body Region") return 13;
  return Math.min(14, 7 + (n.weight || 1.0) * 2.1);
}}

function drawCanvas() {{
  ctx.save();
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  ctx.translate(panX, panY);
  ctx.scale(scale, scale);

  const hoveredNbrs = new Set();
  if (hoveredNode) {{
    hoveredNbrs.add(hoveredNode.id);
    (neighborsMap.get(hoveredNode.id) || []).forEach(nb => hoveredNbrs.add(nb.id));
  }} else if (inspectedNode) {{
    hoveredNbrs.add(inspectedNode.id);
    (neighborsMap.get(inspectedNode.id) || []).forEach(nb => hoveredNbrs.add(nb.id));
  }}

  const pickedSubgraph = new Set();
  if (inspectedNode) {{
    pickedSubgraph.add(inspectedNode.id);
    (neighborsMap.get(inspectedNode.id) || []).forEach(nb => pickedSubgraph.add(nb.id));
  }}

  // 1. Draw Links
  simLinks.forEach(l => {{
    const a = l.sourceNode, b = l.targetNode;
    const isHovered = hoveredNode && (a.id === hoveredNode.id || b.id === hoveredNode.id);
    const isInspected = !hoveredNode && inspectedNode && (a.id === inspectedNode.id || b.id === inspectedNode.id);
    const hasPickedSubgraph = pickedSubgraph.size > 0;
    const bothInSubgraph = pickedSubgraph.has(a.id) && pickedSubgraph.has(b.id);

    ctx.setLineDash([]);
    let isGlowing = false;
    let strokeColor = "#333e5c";
    let strokeAlpha = 0.42;
    let strokeWidth = 1.1 / Math.max(0.6, Math.sqrt(scale));
    let showLabel = false;
    let labelColor = "#b0c4de";
    let labelPrefix = "";

    if (hasPickedSubgraph && isHovered) {{
      if (bothInSubgraph) {{
        // [COLOR 1: Subgraph Internal Link] - Connects within picked active subgraph
        strokeColor = "#06d6a0"; // Intense Emerald Green
        strokeAlpha = 0.96;
        strokeWidth = 2.6 / Math.max(0.6, Math.sqrt(scale));
        showLabel = true;
        labelColor = "#06d6a0";
        if (edgeStyle === "glow") isGlowing = true;
      }} else {{
        // Incident link connecting from subgraph outward
        if (hoverEdgeMode === "subgraph_only") {{
          // Suppress external bridging edges in subgraph-only mode
          strokeColor = "#252c40";
          strokeAlpha = 0.04;
          strokeWidth = 1.0 / Math.max(0.6, Math.sqrt(scale));
          showLabel = false;
        }} else if (hoverEdgeMode === "all_unified") {{
          // Unified focus highlight
          strokeColor = "#58b8ff";
          strokeAlpha = 0.90;
          strokeWidth = 2.0 / Math.max(0.6, Math.sqrt(scale));
          showLabel = true;
          labelColor = "#58b8ff";
          if (edgeStyle === "glow") isGlowing = true;
        }} else {{
          // Subgraph + Outside: [COLOR 2: Subgraph External Bridging Link]
          strokeColor = "#ff79c6"; // Electric Pink
          strokeAlpha = 0.92;
          strokeWidth = 2.2 / Math.max(0.6, Math.sqrt(scale));
          ctx.setLineDash([5, 3]);
          showLabel = true;
          labelColor = "#ff79c6";
          labelPrefix = "[EXTERNAL] ";
          if (edgeStyle === "glow") isGlowing = true;
        }}
      }}
    }} else if (isHovered || isInspected) {{
      strokeColor = "#58b8ff";
      strokeAlpha = 0.88;
      strokeWidth = 2.0 / Math.max(0.6, Math.sqrt(scale));
      showLabel = true;
      labelColor = "#58b8ff";
      if (edgeStyle === "glow") isGlowing = true;
    }} else if (hasPickedSubgraph && bothInSubgraph) {{
      strokeColor = "#06d6a0";
      strokeAlpha = 0.55;
      strokeWidth = 1.5 / Math.max(0.6, Math.sqrt(scale));
      if (edgeStyle === "glow") isGlowing = true;
    }} else if (hoveredNbrs.size > 0 || hasPickedSubgraph) {{
      strokeColor = "#252c40";
      strokeAlpha = 0.08;
      strokeWidth = 1.0 / Math.max(0.6, Math.sqrt(scale));
    }} else {{
      strokeColor = "#333e5c";
      strokeAlpha = 0.42;
      strokeWidth = 1.1 / Math.max(0.6, Math.sqrt(scale));
    }}

    ctx.strokeStyle = strokeColor;
    ctx.globalAlpha = strokeAlpha;
    ctx.lineWidth = strokeWidth;

    let midX = (a.x + b.x) / 2, midY = (a.y + b.y) / 2;

    if (edgeStyle === "curved") {{
      const dx = b.x - a.x, dy = b.y - a.y;
      const dist = Math.hypot(dx, dy) || 1;
      const nx = -dy / dist, ny = dx / dist;
      const bend = Math.min(50, Math.max(16, dist * 0.12)) * (hashStr(a.id + b.id) > 0.5 ? 1 : -1);
      const cx = midX + nx * bend, cy = midY + ny * bend;
      midX = (midX + cx) / 2;
      midY = (midY + cy) / 2;

      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.quadraticCurveTo(cx, cy, b.x, b.y);
      ctx.stroke();
    }} else {{
      if (isGlowing) {{
        ctx.save();
        ctx.lineWidth = strokeWidth * 2.8;
        ctx.globalAlpha = strokeAlpha * 0.32;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
        ctx.restore();
      }}
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }}
    ctx.setLineDash([]);

    // Relationship Label on highlighted links or zoomed in
    if ((showLabel || ((isHovered || isInspected || scale > 0.7) && scale > 0.4))) {{
      ctx.fillStyle = labelColor;
      ctx.globalAlpha = (isHovered || isInspected) ? 0.95 : 0.65;
      ctx.font = `${{Math.max(9, Math.round(9.5 / Math.sqrt(scale)))}}px Inter, sans-serif`;
      ctx.textAlign = "center";
      const edgeText = labelPrefix ? `${{labelPrefix}}${{l.label}}` : l.label;
      ctx.fillText(edgeText, midX, midY - 3);
    }}
  }});

  // 2. Draw Nodes & Labels
  simNodes.forEach(n => {{
    const isFocus = hoveredNbrs.size === 0 || hoveredNbrs.has(n.id);
    const r = nodeRadius(n);
    const color = COLORS[n.type] || "#90a4ae";

    ctx.globalAlpha = hoveredNbrs.size > 0 && !isFocus ? 0.22 : 1.0;

    // Soft outer glow for Medicine & Domains
    if (n.type === "Medicine" || n.type === "Cognitive Domain" || n === hoveredNode || n === inspectedNode) {{
      ctx.beginPath();
      ctx.arc(n.x, n.y, r + 5, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.globalAlpha *= 0.24;
      ctx.fill();
      ctx.globalAlpha = hoveredNbrs.size > 0 && !isFocus ? 0.22 : 1.0;
    }}

    // Core circle
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();

    // White outline for focus
    ctx.lineWidth = (n === hoveredNode || n === inspectedNode) ? 2.6 : 1.4;
    ctx.strokeStyle = (n === hoveredNode || n === inspectedNode) ? "#ffffff" : "#07090e";
    ctx.stroke();

    // Label display rules
    const isHub = n.type === "Medicine" || n.type === "Cognitive Domain" || n.type === "Clinical Condition";
    let showLabel = false;
    if (labelMode === "all") showLabel = true;
    else if (labelMode === "hubs") showLabel = isHub || n === hoveredNode || n === inspectedNode;
    else {{
      // Smart auto
      showLabel = isHub
        || (hoveredNbrs.size > 0 && isFocus)
        || simNodes.length <= 80
        || scale >= 0.65
        || (scale >= 0.4 && (n.weight || 1) >= 2.0);
    }}

    if (showLabel) {{
      const fontSize = isHub ? Math.max(11, Math.round(13 / Math.pow(scale, 0.35))) : Math.max(9.5, Math.round(11 / Math.pow(scale, 0.35)));
      ctx.font = `${{isHub ? 600 : 500}} ${{fontSize}}px Inter, sans-serif`;
      ctx.textAlign = "center";
      const label = n.label.length > 35 && scale < 0.8 ? n.label.slice(0, 33) + "…" : n.label;
      const textWidth = ctx.measureText(label).width;
      const pillX = n.x - textWidth / 2 - 5;
      const pillY = n.y + r + 4;
      const pillH = fontSize + 5;

      ctx.fillStyle = "rgba(10, 13, 22, 0.85)";
      ctx.fillRect(pillX, pillY, textWidth + 10, pillH);

      ctx.fillStyle = isHub ? "#ffffff" : "#dce3f2";
      ctx.fillText(label, n.x, pillY + fontSize);
    }}
  }});

  ctx.restore();
}}

function screenToWorld(sx, sy) {{
  return {{ x: (sx - panX) / scale, y: (sy - panY) / scale }};
}}

function findNodeAt(sx, sy) {{
  const pt = screenToWorld(sx, sy);
  for (let i = simNodes.length - 1; i >= 0; i--) {{
    const n = simNodes[i];
    const r = nodeRadius(n) + 5 / scale;
    const dx = pt.x - n.x, dy = pt.y - n.y;
    if (dx * dx + dy * dy <= r * r) return n;
  }}
  return null;
}}

function inspectNode(n) {{
  inspectedNode = n;
  renderConceptSidebar();
  const nbrs = neighborsMap.get(n.id) || [];
  const v = n.valence !== undefined ? Math.round(n.valence * 100) : null;
  const a = n.arousal !== undefined ? Math.round(n.arousal * 100) : null;
  const d = n.dominance !== undefined ? Math.round(n.dominance * 100) : null;

  let html = `<h3>${{n.type}}</h3>
    <div style="font-size:16px;font-weight:600;margin-bottom:8px;color:${{COLORS[n.type] || '#fff'}}">${{n.label}}</div>
    <div class="stat-row"><span>Composite Severity Weight</span><strong>${{(n.weight || 1).toFixed(2)}} / 3.00</strong></div>
    <div class="stat-row"><span>Typography Grade</span><strong>${{n.grade || "-"}}</strong></div>
    <div class="stat-row"><span>Section / Context</span><strong>${{n.section || "-"}}</strong></div>
    <div class="stat-row"><span>Connected Relationships</span><strong>${{nbrs.length}}</strong></div>`;

  if (v !== null) {{
    html += `<div style="margin-top:10px;font-size:11.5px;color:var(--text-muted)">VAD Affect Profile (Valence: ${{v}}%, Arousal: ${{a}}%, Dominance: ${{d}}%)</div>
      <div class="bar-bg"><div class="bar-fill" style="width:${{a}}%;background:var(--purple)"></div></div>`;
  }}
  if (n.quote) {{
    html += `<div class="quote-box">"${{n.quote}}"</div>`;
  }}
  if (n.sources && n.sources.length) {{
    html += `<div style="margin-top:8px;font-size:11px;color:var(--text-muted)">Provenance: ${{n.sources.join(", ")}}</div>`;
  }}

  if (nbrs.length > 0) {{
    html += `<div style="margin-top:12px;font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.06em">Connected Entities (${{nbrs.length}})</div><div style="margin-top:5px;max-height:160px;overflow-y:auto;">`;
    nbrs.forEach(nb => {{
      const target = GRAPH_DATA.nodes.find(x => x.id === nb.id);
      if (target) {{
        const dotColor = COLORS[target.type] || "#888";
        html += `<span class="neighbor-chip" onclick="focusNodeById('${{target.id.replace(/'/g, "\\\\'")}}')">
          <span style="color:${{dotColor}}">●</span> <strong>${{nb.rel}}:</strong> ${{target.label}}
        </span>`;
      }}
    }});
    html += `</div>`;
  }}

  document.getElementById("inspector").innerHTML = html;
  drawCanvas();
}}

function focusNodeById(id) {{
  const n = simNodes.find(x => x.id === id);
  if (!n) return;
  inspectNode(n);
  scale = Math.max(scale, 0.9);
  panX = width / 2 - n.x * scale;
  panY = height / 2 - n.y * scale;
  drawCanvas();
}}

// Mouse and Touch Interaction
canvas.addEventListener("mousedown", e => {{
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left, y = e.clientY - rect.top;
  const n = findNodeAt(x, y);
  if (n) {{
    draggedNode = n;
    inspectNode(n);
  }} else {{
    isPanning = true;
    startX = x - panX;
    startY = y - panY;
  }}
}});

window.addEventListener("mousemove", e => {{
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left, y = e.clientY - rect.top;

  if (draggedNode) {{
    const pt = screenToWorld(x, y);
    draggedNode.x = pt.x;
    draggedNode.y = pt.y;
    drawCanvas();
    return;
  }}

  if (isPanning) {{
    panX = x - startX;
    panY = y - startY;
    drawCanvas();
    return;
  }}

  // Hover detection
  if (x >= 0 && x <= width && y >= 0 && y <= height) {{
    const n = findNodeAt(x, y);
    if (n !== hoveredNode) {{
      hoveredNode = n;
      drawCanvas();
    }}
    if (n) {{
      canvas.style.cursor = "pointer";
      tooltip.style.display = "block";
      tooltip.style.left = `${{Math.min(width - 240, x + 14)}}px`;
      tooltip.style.top = `${{Math.min(height - 100, y + 14)}}px`;
      tooltip.innerHTML = `<strong style="color:${{COLORS[n.type] || '#fff'}}">${{n.label}}</strong><div style="font-size:11px;color:#a0aec0;margin-top:2px;">Type: ${{n.type}} • Weight: ${{(n.weight || 1).toFixed(2)}}</div>`;
    }} else {{
      canvas.style.cursor = isPanning ? "grabbing" : "grab";
      tooltip.style.display = "none";
    }}
  }}
}});

window.addEventListener("mouseup", () => {{
  draggedNode = null;
  isPanning = false;
}});

canvas.addEventListener("wheel", e => {{
  e.preventDefault();
  const factor = e.deltaY < 0 ? 1.15 : 0.87;
  const rect = canvas.getBoundingClientRect();
  const mouseX = e.clientX - rect.left;
  const mouseY = e.clientY - rect.top;
  const newScale = Math.min(4.5, Math.max(0.12, scale * factor));

  panX = mouseX - (mouseX - panX) * (newScale / scale);
  panY = mouseY - (mouseY - panY) * (newScale / scale);
  scale = newScale;
  drawCanvas();
}}, {{ passive: false }});

window.addEventListener("resize", () => {{
  rebuildGraphLayout();
}});

// Initialize
rebuildGraphLayout();
</script>
</body>
</html>
"""

def generate_showcases():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Arnica montana
    arnica_data = json.loads((DATA_DIR / "kg_arnica_montana_cleaned.graph.json").read_text(encoding="utf-8"))
    arnica_html = build_pure_kg_html(
        arnica_data,
        remedy_title="Arnica montana",
        remedy_subtitle="Cognitive-Affective, Proving Modality & Clinical Knowledge Graph (Hahnemann, Boericke & PubMed)"
    )
    (DOCS_DIR / "kg_arnica_montana_showcase.html").write_text(arnica_html, encoding="utf-8")
    (DATA_DIR / "kg_arnica_montana_showcase.html").write_text(arnica_html, encoding="utf-8")
    print(f"Generated Arnica showcase ({len(arnica_html):,} bytes)")

    # 2. Atropa belladonna
    belladonna_data = json.loads((DATA_DIR / "kg_belladonna_cleaned.graph.json").read_text(encoding="utf-8"))
    belladonna_html = build_pure_kg_html(
        belladonna_data,
        remedy_title="Atropa belladonna",
        remedy_subtitle="Cognitive-Affective, Proving Modality & Anticholinergic Toxidrome Knowledge Graph (Hahnemann, Boericke & PubMed)"
    )
    (DOCS_DIR / "kg_belladonna_showcase.html").write_text(belladonna_html, encoding="utf-8")
    (DATA_DIR / "kg_belladonna_showcase.html").write_text(belladonna_html, encoding="utf-8")
    print(f"Generated Belladonna showcase ({len(belladonna_html):,} bytes)")

if __name__ == "__main__":
    generate_showcases()

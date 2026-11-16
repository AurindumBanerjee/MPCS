/**
 * MPCS-LocalRAG Unified Cognitive Studio — Frontend Controller
 * ============================================================
 * Implements:
 * 1. Continuous high-DPI HTML5 Canvas Knowledge Graph visualization
 * 2. Complete node class numbering & legend with Sensation at top
 * 3. Minimized icon rail sidebars (expandable / collapsible like screenshot)
 * 4. Scrollable page addition for Cognitive Loop Output (Stages 1-4)
 * 5. Learning loop commented out for now
 */

// Global Application State
let GRAPH_DATA = { nodes: [], links: [] };
let nodeDegree = new Map();
let neighborsMap = new Map();
let hiddenTypes = new Set();
let selectedRemedy = "ALL";
let minWeight = 1.0;
let layoutMode = "galaxy"; // "galaxy" | "spiral" | "force"
let hoverEdgeMode = "subgraph_and_outside"; // "subgraph_and_outside" | "subgraph_only" | "all_unified"
let edgeStyle = "straight"; // "straight" | "curved" | "glow"
let labelMode = "smart"; // "smart" | "all" | "hubs"
let activeNodes = new Map(); // id -> activationScore
let hoveredNode = null;
let inspectedNode = null;
let draggedNode = null;
let isPanning = false;
let startX = 0, startY = 0;
let panX = 0, panY = 0, scale = 1.0;
let simNodes = [], simLinks = [];

const state = {
  activePersona: "doctor",
  lastResponse: null,
};

// Entity Color Palette with Sensation included
const COLORS = {
  "Medicine": "#58b8ff",
  "Affective Symptom": "#c5b3f8",
  "Physical Symptom": "#f48fb1",
  "Sensation": "#ffb74d",
  "Modality": "#ffd166",
  "Cognitive Domain": "#06d6a0",
  "Body Region": "#4dd0e1",
  "Clinical Condition": "#ff8a65",
  "Literature Citation": "#ff8a80",
  "default": "#8b95ab"
};

// Canvas Setup
const canvas = document.getElementById("graph-canvas");
const ctx = canvas.getContext("2d");
const tooltip = document.getElementById("tooltip");
let width = 960, height = 680, dpr = window.devicePixelRatio || 1;

/**
 * Initialize Application
 */
async function initApp() {
  setupSidebarToggles();
  setupCognitiveControls();
  resizeCanvas();

  // 1. Fetch System Health & Status
  try {
    const healthRes = await fetch("/api/health");
    if (healthRes.ok) {
      const health = await healthRes.json();
      const badge = document.getElementById("safety-badge") || document.getElementById("dlcbf-badge");
      if (badge) badge.textContent = `Stage 1 Safety Guard: ${health.stage1_rules_count} Rules Active`;
    }
  } catch (err) {
    console.warn("Health check error:", err);
  }

  // 2. Fetch Sample Archetype Scenarios
  try {
    const samplesRes = await fetch("/api/sample_queries");
    if (samplesRes.ok) {
      const samples = await samplesRes.json();
      renderSampleScenarios(samples);
    }
  } catch (err) {
    console.warn("Failed to load sample scenarios:", err);
  }

  // 3. Fetch Full Knowledge Graph for Continuous Visualizer
  try {
    const graphRes = await fetch("/api/graph");
    if (graphRes.ok) {
      GRAPH_DATA = await graphRes.json();
      initGraphDataStructures();
      renderLegendWithCounts();
      renderRemedySidebar();
      rebuildGraphLayout();
    }
  } catch (err) {
    console.error("Failed to load graph data:", err);
    const statsBadge = document.getElementById("stats-badge");
    if (statsBadge) statsBadge.textContent = "Error Loading Graph";
  }
}

/**
 * Initialize Neighbor Adjacency and Degree Counts
 */
function initGraphDataStructures() {
  nodeDegree.clear();
  neighborsMap.clear();

  GRAPH_DATA.links.forEach(l => {
    nodeDegree.set(l.source, (nodeDegree.get(l.source) || 0) + 1);
    nodeDegree.set(l.target, (nodeDegree.get(l.target) || 0) + 1);

    if (!neighborsMap.has(l.source)) neighborsMap.set(l.source, []);
    if (!neighborsMap.has(l.target)) neighborsMap.set(l.target, []);
    neighborsMap.get(l.source).push({ id: l.target, label: l.label, weight: l.weight });
    neighborsMap.get(l.target).push({ id: l.source, label: l.label, weight: l.weight });
  });

  const statsBadge = document.getElementById("stats-badge");
  if (statsBadge) {
    statsBadge.textContent =
      `${GRAPH_DATA.nodes.length.toLocaleString()} Nodes · ${GRAPH_DATA.links.length.toLocaleString()} Links`;
  }

  const medicines = GRAPH_DATA.nodes.filter(n => n.type === "Medicine");
  const remBadge = document.getElementById("rail-rem-badge");
  if (remBadge) remBadge.textContent = medicines.length;

  const keptBadge = document.getElementById("rail-kept-badge");
  if (keptBadge) keptBadge.textContent = `${(GRAPH_DATA.nodes.length / 1000).toFixed(1)}k`;
}

/**
 * Setup Sidebar Toggles: Minimized Rail vs Expanded
 */
function setupSidebarToggles() {
  document.getElementById("toggle-left-btn").addEventListener("click", () => toggleSidebar("left"));
  document.getElementById("toggle-right1-btn").addEventListener("click", () => toggleSidebar("right1"));
  document.getElementById("toggle-right2-btn").addEventListener("click", () => toggleSidebar("right2"));
  
  const scrollResultsBtn = document.getElementById("btn-scroll-results");
  if (scrollResultsBtn) {
    scrollResultsBtn.addEventListener("click", scrollToResults);
  }
}

function toggleSidebar(which) {
  let panel, toggleBtn;
  if (which === "left") {
    panel = document.getElementById("left-sidebar");
    toggleBtn = document.getElementById("toggle-left-btn");
  } else if (which === "right1") {
    panel = document.getElementById("right-sidebar-inspector");
    toggleBtn = document.getElementById("toggle-right1-btn");
  } else if (which === "right2") {
    panel = document.getElementById("right-sidebar-cognitive");
    toggleBtn = document.getElementById("toggle-right2-btn");
  }

  if (panel) {
    // Toggle minimized rail state (thin rail vs expanded)
    panel.classList.toggle("minimized");
    const isMinimized = panel.classList.contains("minimized");
    if (toggleBtn) {
      toggleBtn.classList.toggle("active", !isMinimized);
    }
    // Resize canvas to adapt to new available width
    setTimeout(() => {
      resizeCanvas();
      rebuildGraphLayout();
      fitToScreen();
    }, 220);
  }
}

function scrollToResults() {
  const section = document.getElementById("results-section");
  if (section) {
    section.classList.remove("hidden");
    section.scrollIntoView({ behavior: "smooth" });
  }
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/**
 * Render Interactive Legend with Node Class Numbering and Sensation Included
 */
function renderLegendWithCounts() {
  const container = document.getElementById("legend");
  container.innerHTML = "";

  // Count instances of each node type in GRAPH_DATA
  const typeCounts = {};
  GRAPH_DATA.nodes.forEach(n => {
    const t = n.type || "Other";
    typeCounts[t] = (typeCounts[t] || 0) + 1;
  });

  // Ordered list of classes prioritizing clinical importance
  const orderedClasses = [
    "Medicine",
    "Physical Symptom",
    "Affective Symptom",
    "Sensation",
    "Modality",
    "Clinical Condition",
    "Cognitive Domain",
    "Body Region"
  ];

  orderedClasses.forEach(type => {
    const count = typeCounts[type] || 0;
    if (count === 0 && !typeCounts[type]) return;

    const col = COLORS[type] || COLORS.default;
    const item = document.createElement("div");
    item.className = "legend-item";
    item.setAttribute("data-type", type);
    item.title = `Click to toggle visibility of all ${count} ${type} nodes`;
    item.innerHTML = `
      <span class="dot" style="background:${col};color:${col}"></span>
      <span>${type}</span>
      <span class="legend-count">${count}</span>
    `;

    item.addEventListener("click", () => toggleType(type));
    container.appendChild(item);
  });
}

function toggleType(type) {
  if (hiddenTypes.has(type)) {
    hiddenTypes.delete(type);
  } else {
    hiddenTypes.add(type);
  }
  document.querySelectorAll(".legend-item").forEach(el => {
    if (el.getAttribute("data-type") === type) {
      el.classList.toggle("hidden-type", hiddenTypes.has(type));
    }
  });
  rebuildGraphLayout();
}

/**
 * Render Left Remedy Explorer
 */
function renderRemedySidebar(filterText = "") {
  const listEl = document.getElementById("remedy-list");
  const q = filterText.trim().toLowerCase();
  const medicines = GRAPH_DATA.nodes
    .filter(n => n.type === "Medicine")
    .sort((a, b) => (nodeDegree.get(b.id) || 0) - (nodeDegree.get(a.id) || 0));

  document.getElementById("rem-total-count").textContent = medicines.length;
  const railBadge = document.getElementById("rail-rem-badge");
  if (railBadge) railBadge.textContent = medicines.length;

  let html = `<div class="rem-item ${selectedRemedy === 'ALL' ? 'selected' : ''}" onclick="selectRemedy('ALL')">
    <span>All Remedies (Full Graph)</span>
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
    if (found) {
      inspectNode(found);
      activeNodes.clear();
      simNodes.forEach(n => activeNodes.set(n.id, 1.0));
      updatePruningStats(`Subgraph: ${found.label}`, 1, simNodes.length, GRAPH_DATA.nodes.length - simNodes.length);
      drawCanvas();
    }
  } else {
    resetActivation();
  }
}

/**
 * Setup Cognitive Controls & Modalities
 */
function setupCognitiveControls() {
  const btnDoc = document.getElementById("btn-persona-doctor");
  const btnPat = document.getElementById("btn-persona-patient");

  btnDoc.addEventListener("click", () => setPersona("doctor"));
  btnPat.addEventListener("click", () => setPersona("patient"));

  // Query Input Enter shortcut
  const inputEl = document.getElementById("query-input");
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      executeCognitiveLoop();
    }
  });
}

function setPersona(persona) {
  state.activePersona = persona;
  const btnDoc = document.getElementById("btn-persona-doctor");
  const btnPat = document.getElementById("btn-persona-patient");
  const railBadge = document.getElementById("rail-persona-badge");

  if (persona === "doctor") {
    btnDoc.classList.add("active");
    btnPat.classList.remove("active");
    if (railBadge) {
      railBadge.textContent = "DOC";
      railBadge.className = "rail-badge persona-rail-badge";
    }
  } else {
    btnPat.classList.add("active");
    btnDoc.classList.remove("active");
    if (railBadge) {
      railBadge.textContent = "PT";
      railBadge.className = "rail-badge persona-rail-badge patient-tag";
    }
  }
}

/**
 * Render Sample Archetype Scenarios into categorized <select> dropdown
 */
function renderSampleScenarios(samples) {
  const select = document.getElementById("archetype-select");
  if (!select) return;
  select.innerHTML = `<option value="">-- Select Archetype Scenario --</option>`;

  const groups = {
    doctor: { label: "Doctor / Clinician Cases", items: [] },
    patient: { label: "Patient / End-User Cases", items: [] },
    emergency: { label: "Emergency Red-Flag Cases", items: [] },
  };

  samples.forEach((sample, idx) => {
    const isEmerg = sample.id && sample.id.startsWith("emergency");
    if (isEmerg) {
      groups.emergency.items.push({ sample, idx });
    } else if (sample.persona === "patient") {
      groups.patient.items.push({ sample, idx });
    } else {
      groups.doctor.items.push({ sample, idx });
    }
  });

  Object.values(groups).forEach(group => {
    if (group.items.length === 0) return;
    const optgroup = document.createElement("optgroup");
    optgroup.label = group.label;
    group.items.forEach(({ sample, idx }) => {
      const opt = document.createElement("option");
      opt.value = String(idx);
      opt.textContent = sample.title;
      optgroup.appendChild(opt);
    });
    select.appendChild(optgroup);
  });

  select.onchange = () => {
    if (select.value === "") return;
    const chosen = samples[Number(select.value)];
    if (!chosen) return;
    document.getElementById("query-input").value = chosen.query;
    setPersona(chosen.persona);
    executeCognitiveLoop();
  };
}

/**
 * Canvas Layout Rebuild Engine (Galaxy Clusters + Concentric Rings)
 */
function resizeCanvas() {
  const rect = canvas.parentElement.getBoundingClientRect();
  width = rect.width || 960;
  height = rect.height || 680;
  dpr = window.devicePixelRatio || 1;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
}

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

  // 1. Filter allowed nodes
  let allowedIds = new Set();
  if (selectedRemedy === "ALL") {
    GRAPH_DATA.nodes.forEach(n => {
      if (n.type === "Medicine" || n.type === "Cognitive Domain" || (n.weight || 1.0) >= minWeight) {
        allowedIds.add(n.id);
      }
    });
  } else {
    allowedIds.add(selectedRemedy);
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

  // 2. Compute Layout Coordinates
  const meds = simNodes.filter(n => n.type === "Medicine");
  const domains = simNodes.filter(n => n.type === "Cognitive Domain");
  const regions = simNodes.filter(n => n.type === "Body Region" || n.type === "Clinical Condition");
  const others = simNodes.filter(n => !["Medicine", "Cognitive Domain", "Body Region", "Clinical Condition"].includes(n.type));
  const isSingleRemedy = (selectedRemedy !== "ALL" || meds.length <= 2);

  if (layoutMode === "galaxy") {
    if (isSingleRemedy) {
      const centerRem = simNodes.find(n => n.id === selectedRemedy) || meds[0];
      if (centerRem) { centerRem.x = 0; centerRem.y = 0; centerRem.pinned = true; }

      const hubList = [...domains, ...regions];
      hubList.forEach((h, idx) => {
        const ang = (2 * Math.PI * idx) / Math.max(1, hubList.length);
        const r = h.type === "Cognitive Domain" ? 360 : 540;
        h.x = r * Math.cos(ang);
        h.y = r * Math.sin(ang);
      });

      others.forEach((n, idx) => {
        const connectedHubs = [];
        const nbrs = neighborsMap.get(n.id) || [];
        nbrs.forEach(nb => {
          const target = nodeMap.get(nb.id);
          if (target && target !== centerRem && (target.type === "Cognitive Domain" || target.type === "Body Region" || target.type === "Clinical Condition")) {
            connectedHubs.push(target);
          }
        });

        let cx = 0, cy = 0;
        if (connectedHubs.length > 0) {
          connectedHubs.forEach(h => { cx += h.x; cy += h.y; });
          cx /= connectedHubs.length;
          cy /= connectedHubs.length;
        } else {
          const ang = (2 * Math.PI * idx) / Math.max(1, others.length);
          cx = 450 * Math.cos(ang);
          cy = 450 * Math.sin(ang);
        }

        const orbitRadius = 85 + (idx % 4) * 35;
        const orbitAngle = 2 * Math.PI * hashStr(n.id + ":" + idx);
        n.x = cx + orbitRadius * Math.cos(orbitAngle);
        n.y = cy + orbitRadius * Math.sin(orbitAngle);
      });
    } else {
      // Multi-Remedy Galaxy Layout
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
    }
  } else if (layoutMode === "spiral") {
    // Golden-Angle Phyllotaxis Spiral Layout (following kg_full_materia_medica.html)
    const goldenAngle = Math.PI * (3 - Math.sqrt(5));
    const byDegreeDesc = (a, b) => (nodeDegree.get(b.id) || 0) - (nodeDegree.get(a.id) || 0);

    if (isSingleRemedy) {
      const centerRem = simNodes.find(n => n.id === selectedRemedy) || meds[0];
      if (centerRem) { centerRem.x = 0; centerRem.y = 0; centerRem.pinned = true; }

      const spiralNodes = [
        ...domains.slice().sort(byDegreeDesc),
        ...regions.slice().sort(byDegreeDesc),
        ...others.slice().sort((a, b) => a.type.localeCompare(b.type) || byDegreeDesc(a, b))
      ].filter(n => n !== centerRem);

      spiralNodes.forEach((n, idx) => {
        const r = 210 + 95 * Math.sqrt(idx + 1);
        const theta = idx * goldenAngle;
        n.x = r * Math.cos(theta);
        n.y = r * Math.sin(theta);
      });
    } else {
      const sortedDomains = domains.slice().sort(byDegreeDesc);
      const sortedMeds = meds.slice().sort(byDegreeDesc);
      const sortedRegions = regions.slice().sort((a, b) => a.type.localeCompare(b.type) || byDegreeDesc(a, b));
      const sortedOthers = others.slice().sort((a, b) => a.type.localeCompare(b.type) || byDegreeDesc(a, b));

      sortedDomains.forEach((d, idx) => {
        const r = 140 + 80 * Math.sqrt(idx + 1);
        const theta = idx * goldenAngle;
        d.x = r * Math.cos(theta);
        d.y = r * Math.sin(theta);
      });

      const medOffset = sortedDomains.length;
      sortedMeds.forEach((m, idx) => {
        const r = 380 + 135 * Math.sqrt(idx + 1);
        const theta = (idx + medOffset) * goldenAngle;
        m.x = r * Math.cos(theta);
        m.y = r * Math.sin(theta);
      });

      const outerNodes = [...sortedRegions, ...sortedOthers];
      const outerOffset = medOffset + sortedMeds.length;
      outerNodes.forEach((n, idx) => {
        const r = 820 + 78 * Math.sqrt(idx + 1);
        const theta = (idx + outerOffset) * goldenAngle;
        n.x = r * Math.cos(theta);
        n.y = r * Math.sin(theta);
      });
    }
  } else if (layoutMode === "galaxy_spiral") {
    // Multi-Arm Swirling Galaxy Spiral Layout
    const numArms = 4;
    const byDegreeDesc = (a, b) => (nodeDegree.get(b.id) || 0) - (nodeDegree.get(a.id) || 0);

    if (isSingleRemedy) {
      const centerRem = simNodes.find(n => n.id === selectedRemedy) || meds[0];
      if (centerRem) { centerRem.x = 0; centerRem.y = 0; centerRem.pinned = true; }

      const hubs = [...domains, ...regions].filter(n => n !== centerRem);
      const arms = Math.min(4, Math.max(2, hubs.length || 2));
      const hubArmMap = new Map();

      hubs.forEach((h, idx) => {
        const arm = idx % arms;
        hubArmMap.set(h.id, arm);
        const t = (Math.floor(idx / arms) + 1) / Math.max(1, Math.ceil(hubs.length / arms));
        const r = 240 + t * 320;
        const theta = (2 * Math.PI * arm) / arms + t * 1.9;
        h.x = r * Math.cos(theta);
        h.y = r * Math.sin(theta);
      });

      others.forEach((n, idx) => {
        const nbrs = neighborsMap.get(n.id) || [];
        let arm = idx % arms;
        for (const nb of nbrs) {
          if (hubArmMap.has(nb.id)) { arm = hubArmMap.get(nb.id); break; }
        }
        const t = (Math.floor(idx / arms) + 1) / Math.max(1, Math.ceil(others.length / arms));
        const r = 420 + t * 620;
        const spread = (hashStr(n.id) - 0.5) * 0.28;
        const theta = (2 * Math.PI * arm) / arms + (r / 650) * 1.9 + spread;
        n.x = r * Math.cos(theta);
        n.y = r * Math.sin(theta);
      });
    } else {
      // Galactic Core: Cognitive Domains
      domains.forEach((d, idx) => {
        const ang = (2 * Math.PI * idx) / Math.max(1, domains.length);
        d.x = 220 * Math.cos(ang);
        d.y = 220 * Math.sin(ang);
      });

      // 4 Sweeping Spiral Arms: Medicines lead the arms, Regions & Symptoms trail outward
      const sortedMeds = meds.slice().sort(byDegreeDesc);
      const medArmMap = new Map();
      const armSteps = new Array(numArms).fill(0);

      sortedMeds.forEach((m, idx) => {
        const arm = idx % numArms;
        medArmMap.set(m.id, arm);
        const t = (Math.floor(idx / numArms) + 1) / Math.max(1, Math.ceil(sortedMeds.length / numArms));
        const r = 360 + t * 1050;
        const theta = (2 * Math.PI * arm) / numArms + t * 2.5;
        m.x = r * Math.cos(theta);
        m.y = r * Math.sin(theta);
      });

      const trailingNodes = [...regions, ...others].sort((a, b) => a.type.localeCompare(b.type) || byDegreeDesc(a, b));
      trailingNodes.forEach((n, idx) => {
        const nbrs = neighborsMap.get(n.id) || [];
        let arm = idx % numArms;
        for (const nb of nbrs) {
          if (medArmMap.has(nb.id)) { arm = medArmMap.get(nb.id); break; }
        }
        const step = armSteps[arm]++;
        const t = step / Math.max(1, Math.ceil(trailingNodes.length / numArms));
        const r = 480 + t * 1950;
        const spread = (hashStr(n.id + ":" + idx) - 0.5) * 0.24;
        const theta = (2 * Math.PI * arm) / numArms + (r / 1500) * 2.5 + spread;
        n.x = r * Math.cos(theta);
        n.y = r * Math.sin(theta);
      });
    }
  } else if (layoutMode === "mandala") {
    // Radial Mandala Layout (following kg_arnica_montana_showcase.html)
    if (isSingleRemedy) {
      const center = simNodes.find(n => n.id === selectedRemedy) || meds[0];
      if (center) { center.x = 0; center.y = 0; center.pinned = true; }

      domains.forEach((d, i) => {
        const a = (2 * Math.PI * i) / Math.max(1, domains.length);
        d.x = 240 * Math.cos(a);
        d.y = 240 * Math.sin(a);
      });

      regions.forEach((r, i) => {
        const a = (2 * Math.PI * i) / Math.max(1, regions.length) + 0.35;
        r.x = 360 * Math.cos(a);
        r.y = 360 * Math.sin(a);
      });

      others.forEach((n, i) => {
        const ring = n.type === "Affective Symptom" ? 520 : (n.type === "Modality" ? 680 : 840);
        const spread = (i % 3 - 1) * 55;
        const a = (2 * Math.PI * i) / Math.max(1, others.length);
        n.x = (ring + spread) * Math.cos(a);
        n.y = (ring + spread) * Math.sin(a);
      });
    } else {
      domains.forEach((d, i) => {
        const a = (2 * Math.PI * i) / Math.max(1, domains.length);
        d.x = 240 * Math.cos(a);
        d.y = 240 * Math.sin(a);
      });

      meds.forEach((m, i) => {
        const a = (2 * Math.PI * i) / Math.max(1, meds.length);
        const r = 520 + (i % 2) * 90;
        m.x = r * Math.cos(a);
        m.y = r * Math.sin(a);
      });

      regions.forEach((r, i) => {
        const a = (2 * Math.PI * i) / Math.max(1, regions.length) + 0.35;
        r.x = 840 * Math.cos(a);
        r.y = 840 * Math.sin(a);
      });

      others.forEach((n, i) => {
        const ring = n.type === "Affective Symptom" ? 1140 : (n.type === "Modality" ? 1440 : 1760);
        const spread = (i % 3 - 1) * 70;
        const a = (2 * Math.PI * i) / Math.max(1, others.length);
        n.x = (ring + spread) * Math.cos(a);
        n.y = (ring + spread) * Math.sin(a);
      });
    }
  } else {
    // Concentric Semantic Rings Layout
    const rings = [
      { list: domains, r: 280 },
      { list: meds, r: 720 },
      { list: regions, r: 1120 },
      { list: others.filter(n => n.type === "Affective Symptom"), r: 1520 },
      { list: others.filter(n => n.type === "Sensation"), r: 1720 },
      { list: others.filter(n => n.type === "Modality"), r: 1950 },
      { list: others.filter(n => !["Affective Symptom", "Sensation", "Modality"].includes(n.type)), r: 2400 }
    ];
    rings.forEach(g => {
      g.list.forEach((n, i) => {
        const ang = (2 * Math.PI * i) / Math.max(1, g.list.length);
        const jitter = (i % 2 === 0 ? 1 : -1) * 40;
        n.x = (g.r + jitter) * Math.cos(ang);
        n.y = (g.r + jitter) * Math.sin(ang);
      });
    });
  }

  // Fast Spatial-Grid Collision Relaxation
  resolveNodeCollisions(simNodes, 6);

  document.getElementById("act-total").textContent = simNodes.length;
  if (activeNodes.size === 0) {
    document.getElementById("act-kept").textContent = simNodes.length;
    document.getElementById("act-pruned").textContent = "0";
    document.getElementById("act-ratio").textContent = "0%";
  }

  fitToScreen();
}

function resolveNodeCollisions(nodes, iterations = 6) {
  const minSep = 54;
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

/**
 * Screen & Canvas Coordinate Utilities
 */
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

function updateWeightFilter(val) {
  minWeight = parseFloat(val);
  document.getElementById("weight-val").textContent = minWeight.toFixed(1);
  rebuildGraphLayout();
}

function toggleLayoutMode() {
  const order = ["galaxy", "spiral", "galaxy_spiral", "mandala", "force"];
  layoutMode = order[(order.indexOf(layoutMode) + 1) % order.length];
  const titles = {
    galaxy: "Layout: Galaxy Clusters",
    spiral: "Layout: Golden Spiral",
    galaxy_spiral: "Layout: Galaxy Spiral",
    mandala: "Layout: Radial Mandala",
    force: "Layout: Concentric Rings"
  };
  const btn = document.getElementById("layout-btn");
  btn.textContent = titles[layoutMode];
  btn.classList.toggle("active-toggle", layoutMode !== "force");
  rebuildGraphLayout();
}

function toggleHoverEdgeMode() {
  const modes = ["subgraph_and_outside", "subgraph_only", "all_unified"];
  hoverEdgeMode = modes[(modes.indexOf(hoverEdgeMode) + 1) % modes.length];
  const titles = {
    subgraph_and_outside: "Hover: Subgraph + Outside",
    subgraph_only: "Hover: Subgraph Only",
    all_unified: "Hover: All Unified"
  };
  document.getElementById("hover-mode-btn").textContent = titles[hoverEdgeMode];
  document.getElementById("act-hover-mode").textContent = titles[hoverEdgeMode].replace("Hover: ", "");
  drawCanvas();
}

function toggleEdgeStyle() {
  const styles = ["straight", "curved", "glow"];
  edgeStyle = styles[(styles.indexOf(edgeStyle) + 1) % styles.length];
  const titles = { straight: "Edge: Straight", curved: "Edge: Curved", glow: "Edge: Glow" };
  document.getElementById("edge-style-btn").textContent = titles[edgeStyle];
  document.getElementById("act-edge-style").textContent = titles[edgeStyle].replace("Edge: ", "");
  drawCanvas();
}

function toggleAllLabels() {
  const order = ["smart", "all", "hubs"];
  labelMode = order[(order.indexOf(labelMode) + 1) % order.length];
  const labels = { smart: "Labels: Smart Auto", all: "Labels: Always Show All", hubs: "Labels: Hubs Only" };
  document.getElementById("labels-btn").textContent = labels[labelMode];
  drawCanvas();
}

function nodeRadius(n) {
  if (n.type === "Medicine") return 20;
  if (n.type === "Cognitive Domain") return 17;
  if (n.type === "Clinical Condition" || n.type === "Body Region") return 13;
  if (n.type === "Sensation") return 12;
  return Math.min(14, 7 + (n.weight || 1.0) * 2.1);
}

/**
 * Canvas Rendering Loop
 */
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
  simLinks.forEach(l => {
    const a = l.sourceNode, b = l.targetNode;
    if (!a || !b) return;

    const isIncident = (hoveredNode && (a.id === hoveredNode.id || b.id === hoveredNode.id))
                    || (!hoveredNode && inspectedNode && (a.id === inspectedNode.id || b.id === inspectedNode.id));
    const bothActive = !hasActivation || (activeNodes.has(a.id) && activeNodes.has(b.id));

    ctx.setLineDash([]);
    let isGlowing = false;
    let strokeColor = "#333e5c";
    let strokeAlpha = simNodes.length > 400 ? 0.28 : 0.48;
    let strokeWidth = 1.1 / Math.max(0.6, Math.sqrt(scale));
    let showLabel = false;
    let labelColor = "#98a6c4";
    let labelPrefix = "";

    if (hasActivation && isIncident) {
      if (bothActive) {
        strokeColor = "#06d6a0"; // Subgraph Internal Link (Emerald Green)
        strokeAlpha = 0.96;
        strokeWidth = 2.6 / Math.max(0.6, Math.sqrt(scale));
        showLabel = true;
        labelColor = "#06d6a0";
        if (edgeStyle === "glow") isGlowing = true;
      } else {
        if (hoverEdgeMode === "subgraph_only") {
          strokeColor = "#252c40";
          strokeAlpha = 0.04;
          strokeWidth = 1.0 / Math.max(0.6, Math.sqrt(scale));
          showLabel = false;
        } else if (hoverEdgeMode === "all_unified") {
          strokeColor = "#58b8ff";
          strokeAlpha = 0.90;
          strokeWidth = 2.0 / Math.max(0.6, Math.sqrt(scale));
          showLabel = true;
          labelColor = "#58b8ff";
          if (edgeStyle === "glow") isGlowing = true;
        } else {
          strokeColor = "#ff79c6"; // Subgraph External Bridge (Pink)
          strokeAlpha = 0.92;
          strokeWidth = 2.2 / Math.max(0.6, Math.sqrt(scale));
          ctx.setLineDash([5, 3]);
          showLabel = true;
          labelColor = "#ff79c6";
          labelPrefix = "[EXTERNAL] ";
          if (edgeStyle === "glow") isGlowing = true;
        }
      }
    } else if (isIncident) {
      strokeColor = "#58b8ff";
      strokeAlpha = 0.88;
      strokeWidth = 2.0 / Math.max(0.6, Math.sqrt(scale));
      showLabel = true;
      labelColor = "#58b8ff";
      if (edgeStyle === "glow") isGlowing = true;
    } else if (hasActivation && bothActive) {
      strokeColor = "#06d6a0";
      strokeAlpha = 0.65;
      strokeWidth = 1.6 / Math.max(0.6, Math.sqrt(scale));
      if (edgeStyle === "glow") isGlowing = true;
    } else if (hasActivation && !bothActive) {
      strokeColor = "#2e3750";
      strokeAlpha = 0.15;
      strokeWidth = 1.0 / Math.max(0.6, Math.sqrt(scale));
    } else {
      strokeColor = "#333e5c";
      strokeAlpha = simNodes.length > 400 ? 0.28 : 0.48;
      strokeWidth = 1.1 / Math.max(0.6, Math.sqrt(scale));
    }

    ctx.strokeStyle = strokeColor;
    ctx.globalAlpha = strokeAlpha;
    ctx.lineWidth = strokeWidth;

    let midX = (a.x + b.x) / 2, midY = (a.y + b.y) / 2;

    if (edgeStyle === "curved") {
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
    } else {
      if (isGlowing) {
        ctx.save();
        ctx.lineWidth = strokeWidth * 2.8;
        ctx.globalAlpha = strokeAlpha * 0.32;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
        ctx.restore();
      }
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }
    ctx.setLineDash([]);

    if (showLabel && scale > 0.4) {
      ctx.fillStyle = labelColor;
      ctx.globalAlpha = 0.95;
      ctx.font = `${Math.max(9, Math.round(10 / Math.sqrt(scale)))}px Inter, sans-serif`;
      ctx.textAlign = "center";
      const edgeText = labelPrefix ? `${labelPrefix}${l.label}` : l.label;
      ctx.fillText(edgeText, midX, midY - 4);
    }
  });

  // 2. Draw Nodes
  simNodes.forEach(n => {
    const isAct = !hasActivation || activeNodes.has(n.id);
    const isFocus = hoveredNbrs.size === 0 || hoveredNbrs.has(n.id);
    const r = nodeRadius(n) + (activeNodes.has(n.id) ? (activeNodes.get(n.id) || 1) * 3 : 0);
    const color = COLORS[n.type] || COLORS.default;

    ctx.globalAlpha = !isAct ? 0.25 : (hoveredNbrs.size > 0 && !isFocus ? 0.28 : 1.0);

    // Outer glow for key nodes
    if ((n.type === "Medicine" || n.type === "Cognitive Domain" || activeNodes.has(n.id)) && isAct) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, r + 5, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.globalAlpha *= 0.22;
      ctx.fill();
      ctx.globalAlpha = !isAct ? 0.25 : (hoveredNbrs.size > 0 && !isFocus ? 0.28 : 1.0);
    }

    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();

    ctx.lineWidth = (n === hoveredNode || n === inspectedNode || activeNodes.has(n.id)) ? 2.5 : 1.4;
    ctx.strokeStyle = (n === hoveredNode || n === inspectedNode || activeNodes.has(n.id)) ? "#ffffff" : "#07090e";
    ctx.stroke();

    // Labels
    const isHub = n.type === "Medicine" || n.type === "Cognitive Domain";
    let showLabel = false;
    if (labelMode === "all") showLabel = true;
    else if (labelMode === "hubs") showLabel = isHub || n === hoveredNode || n === inspectedNode;
    else {
      showLabel = isHub
        || n === hoveredNode
        || n === inspectedNode
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

/**
 * Node Inspector Card Population
 */
function inspectNode(n) {
  inspectedNode = n;
  const act = activeNodes.get(n.id);
  const v = n.valence !== undefined ? Math.round(n.valence * 100) : null;
  const a = n.arousal !== undefined ? Math.round(n.arousal * 100) : null;
  const d = n.dominance !== undefined ? Math.round(n.dominance * 100) : null;
  const nbrs = neighborsMap.get(n.id) || [];

  let html = `<h3>${n.type}</h3>
    <div style="font-size:15px;font-weight:600;margin-bottom:8px;color:${COLORS[n.type] || '#fff'}">${n.label}</div>
    <div class="stat-row"><span>Composite Weight</span><strong>${(n.weight || 1).toFixed(2)} / 3.00</strong></div>
    <div class="stat-row"><span>Typography Grade</span><strong>${n.grade || "-"}</strong></div>
    <div class="stat-row"><span>Section</span><strong>${n.section || "-"}</strong></div>
    <div class="stat-row"><span>Connected Links</span><strong>${nbrs.length}</strong></div>`;

  if (act !== undefined) {
    html += `<div class="stat-row"><span>TIDE Activation</span><strong style="color:var(--green)">${act.toFixed(3)}</strong></div>`;
  }
  if (v !== null) {
    html += `<div style="margin-top:8px;font-size:11.5px;color:var(--muted)">VAD Affect Profile (V:${v}% A:${a}% D:${d}%)</div>
      <div class="bar-bg"><div class="bar-fill" style="width:${a}%;background:var(--purple)"></div></div>`;
  }
  if (n.quote) {
    html += `<div class="quote-box">"${escapeHtml(n.quote)}"</div>`;
  }
  if (n.sources && n.sources.length) {
    html += `<div style="margin-top:7px;font-size:11px;color:var(--muted)">Sources: ${escapeHtml(n.sources.join(", "))}</div>`;
  }

  if (nbrs.length > 0) {
    html += `<div style="margin-top:9px;font-size:11px;color:var(--muted);text-transform:uppercase">Connected Concepts (${nbrs.length})</div>
      <div style="margin-top:4px;max-height:140px;overflow-y:auto;">`;
    nbrs.slice(0, 35).forEach(nb => {
      const target = GRAPH_DATA.nodes.find(x => x.id === nb.id);
      if (target) {
        html += `<span class="neighbor-chip" onclick="focusNodeById('${target.id.replace(/'/g, "\\'")}')">
          <span style="color:${COLORS[target.type] || '#fff'}">&bull;</span> ${target.label}
        </span>`;
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

/**
 * Execute Cognitive Loop Pipeline
 * - Runs /api/query
 * - Prunes graph visualizer down to active subgraph
 * - Unhides and displays Stages 1 - 4 in the document flow section below canvas
 * - Smoothly scrolls to the output
 */
async function executeCognitiveLoop() {
  const queryText = document.getElementById("query-input").value.trim();
  if (!queryText) {
    alert("Please enter a clinical symptom query or select an archetype scenario.");
    return;
  }

  const runBtn = document.getElementById("run-btn");
  runBtn.disabled = true;
  runBtn.innerHTML = `<span>Deliberating Cognitive Loop...</span>`;
  document.getElementById("emergency-banner").classList.add("hidden");

  try {
    const payload = {
      query: queryText,
      persona: state.activePersona,
    };

    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`Server returned error: ${res.statusText}`);
    }

    const data = await res.json();
    state.lastResponse = data;

    // 1. Prune Knowledge Graph to Active Subgraph
    pruneGraphToResponse(data);

    // 2. Render and Display Stages 1 - 4
    renderPipelineResults(data);

    // 3. Smoothly scroll to results section
    setTimeout(() => {
      scrollToResults();
    }, 280);

  } catch (err) {
    console.error("Cognitive loop execution failed:", err);
    alert(`Cognitive execution error: ${err.message}`);
  } finally {
    runBtn.disabled = false;
    runBtn.innerHTML = `<span class="btn-text">Execute Cognitive Loop</span>`;
  }
}

/**
 * Prune Canvas Graph Based on API Response
 */
function pruneGraphToResponse(data) {
  if (selectedRemedy !== "ALL") {
    selectedRemedy = "ALL";
    const searchEl = document.getElementById("rem-search");
    renderRemedySidebar(searchEl ? searchEl.value : "");
    rebuildGraphLayout();
  }

  activeNodes.clear();

  (data.subgraph_nodes || []).forEach(n => {
    activeNodes.set(n.id, n.score || 1.0);
  });

  const total = simNodes.length;
  const kept = activeNodes.size;
  const pruned = Math.max(0, total - kept);
  const ratio = total > 0 ? ((pruned / total) * 100).toFixed(1) : "0";

  updatePruningStats(`TIDE Subgraph (${data.persona.toUpperCase()})`, data.subgraph_nodes.length, kept, pruned, ratio);

  // Focus and fit to active subgraph
  fitToScreen();
}

function updatePruningStats(mode, seeded, kept, pruned, ratio = null) {
  document.getElementById("act-mode").textContent = mode;
  document.getElementById("act-seeded").textContent = seeded;
  document.getElementById("act-kept").textContent = kept;
  document.getElementById("act-pruned").textContent = pruned;

  const total = kept + pruned;
  const r = ratio !== null ? ratio : (total ? `${Math.round((pruned / total) * 100)}%` : "0%");
  document.getElementById("act-ratio").textContent = r.toString().includes("%") ? r : `${r}%`;

  let internalCount = 0, externalCount = 0;
  simLinks.forEach(l => {
    const inA = activeNodes.has(l.source);
    const inB = activeNodes.has(l.target);
    if (inA && inB) internalCount++;
    else if (inA || inB) externalCount++;
  });
  document.getElementById("act-internal-edges").textContent = internalCount;
  document.getElementById("act-external-edges").textContent = externalCount;

  const keptBadge = document.getElementById("rail-kept-badge");
  if (keptBadge) keptBadge.textContent = kept > 0 ? kept : `${(simNodes.length / 1000).toFixed(1)}k`;
}

/**
 * Reset Graph Activation to Full Graph
 */
function resetActivation() {
  activeNodes.clear();
  inspectedNode = null;
  if (selectedRemedy !== "ALL") {
    selectedRemedy = "ALL";
    const searchEl = document.getElementById("rem-search");
    renderRemedySidebar(searchEl ? searchEl.value : "");
    rebuildGraphLayout();
  }
  document.getElementById("act-mode").textContent = "Full Graph";
  document.getElementById("act-seeded").textContent = "0";
  document.getElementById("act-kept").textContent = simNodes.length;
  document.getElementById("act-pruned").textContent = "0";
  document.getElementById("act-ratio").textContent = "0%";
  document.getElementById("act-internal-edges").textContent = "0";
  document.getElementById("act-external-edges").textContent = "0";

  const keptBadge = document.getElementById("rail-kept-badge");
  if (keptBadge) keptBadge.textContent = `${(GRAPH_DATA.nodes.length / 1000).toFixed(1)}k`;

  fitToScreen();
}

/**
 * Render Unified Two-Column Clinical Dashboard below canvas
 */
function renderPipelineResults(data) {
  const section = document.getElementById("results-section");
  const scrollBtn = document.getElementById("btn-scroll-results");
  const floatBtn = document.getElementById("float-scroll-btn");

  // Emergency Banner Check (Visible only when data.is_emergency === true)
  const banner = document.getElementById("emergency-banner");
  const st1Badge = document.getElementById("stage1-status");
  if (data.is_emergency === true) {
    banner.classList.remove("hidden");
    document.getElementById("emergency-title").textContent = "CRITICAL RED-FLAG DETECTED";
    document.getElementById("emergency-message").textContent = data.emergency_warning || "";
    if (st1Badge) {
      st1Badge.textContent = "REFLEX BLOCKED";
      st1Badge.className = "badge badge-danger";
    }
  } else {
    banner.classList.add("hidden");
    if (st1Badge) {
      st1Badge.textContent = "SAFE DELIBERATION";
      st1Badge.className = "badge badge-success";
    }
  }

  // Latency directly beneath #run-btn in Cognitive Studio sidebar
  const execMeta = document.getElementById("execution-meta");
  const latText = document.getElementById("latency-text");
  if (execMeta && latText) {
    execMeta.classList.remove("hidden");
    latText.textContent = `\u26A1 Latency: ${data.total_latency_ms} ms`;
  }

  // Header Bar Meta (Action Pill + Compact TIDE Route Badge)
  const actPill = document.getElementById("action-pill");
  actPill.textContent = data.action.toUpperCase();
  actPill.className = `action-pill ${data.action.toLowerCase()}`;
  const routeBadge = document.getElementById("tide-route-badge");
  if (routeBadge) {
    routeBadge.textContent = `${data.tide_route} ROUTE`;
  }
  const subMeta = document.getElementById("subgraph-meta");
  if (subMeta) {
    subMeta.textContent = `${data.subgraph_nodes.length} Nodes \u00B7 ${data.pruning_ratio_pct.toFixed(1)}% Ambient Cut`;
  }

  // Differential Synthesis, Click-to-Expand Remedies, and Top 5 Citations
  document.getElementById("diff-analysis").innerHTML = formatMarkdown(data.differential_analysis);
  renderTopRemedies(data.top_remedies);
  renderEvidence(data.grounded_evidence);

  // Unhide results section & scroll triggers
  section.classList.remove("hidden");
  if (scrollBtn) scrollBtn.classList.remove("hidden");
  if (floatBtn) floatBtn.classList.remove("hidden");
}

function toggleRemedyAccordion(cardEl, remedyId) {
  const isExpanded = cardEl.classList.contains("expanded");
  document.querySelectorAll("#top-remedies-container .remedy-accordion.expanded").forEach(el => {
    if (el !== cardEl) el.classList.remove("expanded");
  });
  cardEl.classList.toggle("expanded", !isExpanded);
  if (remedyId) {
    selectRemedy(remedyId);
  }
}

function renderTopRemedies(remedies) {
  const container = document.getElementById("top-remedies-container");
  if (!remedies || remedies.length === 0) {
    container.innerHTML = `<div class="empty-hint">No remedies exceeded threshold for this query.</div>`;
    return;
  }

  container.innerHTML = remedies.map(r => {
    const safeId = escapeHtml(r.id).replace(/'/g, "\\'");
    const symText = r.linked_symptoms && r.linked_symptoms.length > 0
      ? escapeHtml(r.linked_symptoms.join(", "))
      : "General constitutional rubric match";
    const srcCount = Array.isArray(r.sources) ? r.sources.length : 0;
    return `
      <div class="remedy-accordion" data-id="${escapeHtml(r.id)}" onclick="toggleRemedyAccordion(this, '${safeId}')">
        <div class="remedy-summary-row">
          <div class="rem-title-group">
            <span class="rem-name">${escapeHtml(r.name)}</span>
            <span class="rem-grade-badge">Grade ${r.grade}</span>
          </div>
          <div class="rem-meta-group">
            <span class="rem-score-pill">W = ${r.score.toFixed(2)}</span>
            <span class="rem-chevron">\u25BE</span>
          </div>
        </div>
        <div class="remedy-drawer">
          <div class="drawer-row"><strong>Classification:</strong> <span>${escapeHtml(r.classification)}</span></div>
          <div class="drawer-row"><strong>Proving Sources:</strong> <span>${srcCount} source(s)</span></div>
          <div class="drawer-row"><strong>Linked Rubrics:</strong> <span>${symText}</span></div>
        </div>
      </div>
    `;
  }).join("");
}

function formatCitationBadge(src) {
  const s = String(src || "Materia Medica");
  const lower = s.toLowerCase();
  if (lower.includes("boericke")) {
    const m = s.match(/p\.?\s*\d+/i);
    return `[Boericke ${m ? m[0].replace(/\s+/g, "") : "MM"}]`;
  }
  if (lower.includes("hahnemann")) {
    const m = s.match(/p\.?\s*\d+/i);
    return `[Hahnemann ${m ? m[0].replace(/\s+/g, "") : "MMP"}]`;
  }
  if (lower.includes("pubmed") || /pmid/i.test(s)) {
    const m = s.match(/\d{5,}/);
    return `[PubMed ${m ? "PMID:" + m[0] : "PMID"}]`;
  }
  return `[${s}]`;
}

function renderEvidence(evidence) {
  const container = document.getElementById("evidence-container");
  const topFive = (evidence || []).slice(0, 5);
  if (topFive.length === 0) {
    container.innerHTML = `<div class="empty-hint">No occurrence quotes attached to active nodes.</div>`;
    return;
  }

  container.innerHTML = topFive.map(e => {
    const badges = (e.sources && e.sources.length ? e.sources : ["Materia Medica"])
      .slice(0, 2)
      .map(s => `<span class="citation-badge">${escapeHtml(formatCitationBadge(s))}</span>`)
      .join(" ");
    return `
      <div class="evidence-item">
        <div class="evidence-quote">"${escapeHtml(e.quote)}"</div>
        <div class="evidence-meta">
          <strong>${escapeHtml(e.label)}</strong> (${escapeHtml(e.section)}) &middot; Grade ${e.grade} ${badges}
        </div>
      </div>
    `;
  }).join("");
}

/**
 * Canvas Mouse & Wheel Interaction Listeners
 */
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

  if (sx >= 0 && sx <= width && sy >= 0 && sy <= height) {
    const hit = findNodeAt(sx, sy);
    if (hit !== hoveredNode) {
      hoveredNode = hit;
      canvas.style.cursor = hit ? "pointer" : "grab";
      if (hit) {
        tooltip.style.display = "block";
        tooltip.innerHTML = `
          <div style="color:${COLORS[hit.type] || '#fff'};font-weight:600">${hit.type}: ${escapeHtml(hit.label)}</div>
          <div style="color:var(--muted);font-size:11px;margin-top:2px">Weight: ${(hit.weight || 1).toFixed(2)} &middot; Grade: ${hit.grade || 1} &middot; Section: ${escapeHtml(hit.section || 'General')}</div>
          ${hit.quote ? `<div style="margin-top:4px;font-style:italic;color:#cbd5e8">"${escapeHtml(hit.quote.slice(0, 120))}${hit.quote.length > 120 ? '…' : ''}"</div>` : ''}
        `;
      } else {
        tooltip.style.display = "none";
      }
      drawCanvas();
    }
    if (hit) {
      tooltip.style.left = Math.min(width - 310, sx + 14) + "px";
      tooltip.style.top = Math.max(10, sy - 14) + "px";
    }
  }
});

window.addEventListener("mouseup", () => {
  isPanning = false;
  draggedNode = null;
});

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

window.addEventListener("resize", () => {
  resizeCanvas();
  rebuildGraphLayout();
});

/**
 * Text Utilities
 */
function escapeHtml(text) {
  if (!text) return "";
  return String(text).replace(/[&<>"']/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[m]);
}

function formatMarkdown(text) {
  if (!text) return "";
  return escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.*?)`/g, "<code class='mono'>$1</code>")
    .replace(/\n\n/g, "<br/><br/>");
}

/**
 * Submit Expert Action: RED_FLAG_URGENT_REFERRAL
 * Registers current query into Stage 1 Emergency Guard
 */
async function submitExpertRedFlag() {
  const expertAction = document.getElementById("expert-action-select").value;
  if (!expertAction) {
    alert("Please select an expert action.");
    return;
  }

  const queryText = (state.lastResponse && state.lastResponse.query) || document.getElementById("query-input").value.trim();
  if (!queryText) {
    alert("Please enter a query or run a scenario first before registering a red flag.");
    return;
  }

  const btn = document.getElementById("btn-teach");
  btn.disabled = true;
  btn.textContent = "Registering...";

  try {
    const res = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        step: state.lastResponse ? state.lastResponse.step_index : 1,
        expert_action: expertAction,
        query: queryText
      })
    });

    if (res.ok) {
      const resp = await res.json();
      alert(`[SAFETY GUARD UPDATED]\n${resp.message}\nTotal Stage 1 Registered Rules: ${resp.total_learned_flags}`);
      // Refresh health badge
      const healthRes = await fetch("/api/health");
      if (healthRes.ok) {
        const health = await healthRes.json();
        const badge = document.getElementById("safety-badge") || document.getElementById("dlcbf-badge");
        if (badge) badge.textContent = `Stage 1 Safety Guard: ${health.stage1_rules_count} Rules Active`;
      }
    } else {
      alert("Failed to register red flag feedback.");
    }
  } catch (err) {
    console.error("Feedback submission error:", err);
    alert(`Error: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "Register Red Flag";
  }
}

// Start application on DOM ready
document.addEventListener("DOMContentLoaded", initApp);

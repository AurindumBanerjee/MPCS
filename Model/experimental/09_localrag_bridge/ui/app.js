/**
 * MPCS-LocalRAG Unified Cognitive Studio — Frontend Controller
 * ============================================================
 * Handles real-time query dispatch, 4-stage pipeline visualization,
 * interactive 60 FPS HTML5 Canvas graph rendering, and reinforcement loop.
 */

// Application State
const state = {
  activePersona: "doctor",
  selectedModalities: {
    thermal: "",
    motion: "",
    contact: "",
  },
  lastResponse: null,
  activeNodes: [],
  activeEdges: [],
  canvasTransform: { x: 0, y: 0, k: 1 },
  hoveredNode: null,
};

// DOM Element References
const elements = {
  btnDoctor: document.getElementById("btn-persona-doctor"),
  btnPatient: document.getElementById("btn-persona-patient"),
  archetypePills: document.getElementById("archetype-pills"),
  queryInput: document.getElementById("query-input"),
  runBtn: document.getElementById("run-btn"),
  emergencyBanner: document.getElementById("emergency-banner"),
  emergencyTitle: document.getElementById("emergency-title"),
  emergencyMessage: document.getElementById("emergency-message"),
  dlcbfStatus: document.getElementById("dlcbf-status"),
  kgStats: document.getElementById("kg-stats"),
  stage1Status: document.getElementById("stage1-status"),
  stage1Dlcbf: document.getElementById("stage1-dlcbf"),
  stage1DlcbfLat: document.getElementById("stage1-dlcbf-lat"),
  stage1TotalLat: document.getElementById("stage1-total-lat"),
  stage2Pruning: document.getElementById("stage2-pruning"),
  stage2Nodecount: document.getElementById("stage2-nodecount"),
  topRemediesContainer: document.getElementById("top-remedies-container"),
  actionPill: document.getElementById("action-pill"),
  policySub: document.getElementById("policy-sub"),
  tideRouteBadge: document.getElementById("tide-route-badge"),
  valValence: document.getElementById("val-valence"),
  fillValence: document.getElementById("fill-valence"),
  valArousal: document.getElementById("val-arousal"),
  fillArousal: document.getElementById("fill-arousal"),
  valDominance: document.getElementById("val-dominance"),
  fillDominance: document.getElementById("fill-dominance"),
  diffAnalysis: document.getElementById("diff-analysis"),
  evidenceContainer: document.getElementById("evidence-container"),
  canvas: document.getElementById("subgraph-canvas"),
  tooltip: document.getElementById("node-tooltip"),
  btnValidate: document.getElementById("btn-validate"),
  btnPenalize: document.getElementById("btn-penalize"),
  expertSelect: document.getElementById("expert-action-select"),
  btnTeach: document.getElementById("btn-teach"),
};

// Canvas 2D Context
const ctx = elements.canvas.getContext("2d");

// Entity Color Palette
const COLORS = {
  remedy: "#4a90e2",
  medicine: "#4a90e2",
  physical: "#e94e77",
  affective: "#9013fe",
  modality: "#f5a623",
  domain: "#10b981",
  condition: "#06b6d4",
  default: "#94a3b8",
};

/**
 * Initialize application and load server endpoints
 */
async function initApp() {
  setupEventListeners();
  resizeCanvas();
  window.addEventListener("resize", resizeCanvas);

  try {
    // 1. Fetch Health & Stats
    const healthRes = await fetch("/api/health");
    if (healthRes.ok) {
      const health = await healthRes.json();
      elements.kgStats.textContent = `${health.graph_nodes.toLocaleString()} Nodes · ${health.graph_links.toLocaleString()} Edges`;
      elements.dlcbfStatus.textContent = `${health.dlcbf_capacity} Fingerprints`;
    }

    // 2. Fetch Sample Queries
    const samplesRes = await fetch("/api/sample_queries");
    if (samplesRes.ok) {
      const samples = await samplesRes.json();
      renderSamplePills(samples);
    }
  } catch (err) {
    console.error("Failed to connect to bridge backend:", err);
  }
}

/**
 * Setup Event Listeners
 */
function setupEventListeners() {
  // Persona Toggle
  elements.btnDoctor.addEventListener("click", () => setPersona("doctor"));
  elements.btnPatient.addEventListener("click", () => setPersona("patient"));

  // Modality Chips
  document.querySelectorAll(".chip-group").forEach((group) => {
    const groupName = group.getAttribute("data-group");
    group.querySelectorAll(".mod-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        group.querySelectorAll(".mod-chip").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        state.selectedModalities[groupName] = chip.getAttribute("data-val") || "";
      });
    });
  });

  // Execute Query Button
  elements.runBtn.addEventListener("click", executeQuery);
  elements.queryInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      executeQuery();
    }
  });

  // Canvas Mouse Interactions
  elements.canvas.addEventListener("mousemove", handleCanvasMouseMove);
  elements.canvas.addEventListener("mouseleave", () => {
    state.hoveredNode = null;
    elements.tooltip.classList.add("hidden");
    drawGraph();
  });

  // Reinforcement Learning Loop
  elements.btnValidate.addEventListener("click", () => submitFeedback(1.0));
  elements.btnPenalize.addEventListener("click", () => submitFeedback(0.0));
  elements.btnTeach.addEventListener("click", () => {
    const expertAction = elements.expertSelect.value;
    if (!expertAction) {
      alert("Please choose an expert action from the dropdown first.");
      return;
    }
    submitFeedback(1.0, expertAction);
  });
}

/**
 * Set Active Persona
 */
function setPersona(persona) {
  state.activePersona = persona;
  if (persona === "doctor") {
    elements.btnDoctor.classList.add("active");
    elements.btnPatient.classList.remove("active");
  } else {
    elements.btnPatient.classList.add("active");
    elements.btnDoctor.classList.remove("active");
  }
}

/**
 * Render Sample Archetype Buttons
 */
function renderSamplePills(samples) {
  elements.archetypePills.innerHTML = "";
  samples.forEach((sample) => {
    const btn = document.createElement("button");
    btn.className = `pill-btn ${sample.id.startsWith("emergency") ? "pill-emergency" : ""}`;
    btn.textContent = `${sample.id.startsWith("emergency") ? "🚨 " : ""}${sample.title}`;
    btn.addEventListener("click", () => {
      elements.queryInput.value = sample.query;
      setPersona(sample.persona);
      if (sample.modalities) {
        applyModalities(sample.modalities);
      }
      executeQuery();
    });
    elements.archetypePills.appendChild(btn);
  });
}

function applyModalities(mods) {
  Object.keys(mods).forEach((grp) => {
    state.selectedModalities[grp] = mods[grp];
    const groupEl = document.querySelector(`.chip-group[data-group="${grp}"]`);
    if (groupEl) {
      groupEl.querySelectorAll(".mod-chip").forEach((chip) => {
        if (chip.getAttribute("data-val") === mods[grp]) {
          chip.classList.add("active");
        } else {
          chip.classList.remove("active");
        }
      });
    }
  });
}

/**
 * Execute Query Pipeline
 */
async function executeQuery() {
  const queryText = elements.queryInput.value.trim();
  if (!queryText) {
    alert("Please enter a query or select an archetype scenario.");
    return;
  }

  // Set Loading State
  elements.runBtn.disabled = true;
  elements.runBtn.innerHTML = `<span>Deliberating...</span>`;
  elements.emergencyBanner.classList.add("hidden");

  try {
    const payload = {
      query: queryText,
      persona: state.activePersona,
      modalities: state.selectedModalities,
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
    renderResponse(data);
  } catch (err) {
    console.error("Query execution failed:", err);
    alert(`Cognitive execution error: ${err.message}`);
  } finally {
    elements.runBtn.disabled = false;
    elements.runBtn.innerHTML = `<span class="btn-icon">⚡</span><span>Execute Cognitive Loop</span>`;
  }
}

/**
 * Render Complete 4-Stage Response
 */
function renderResponse(data) {
  // 1. Emergency Red-Flag Banner Check
  if (data.is_emergency) {
    elements.emergencyBanner.classList.remove("hidden");
    elements.emergencyTitle.textContent = "🚨 CRITICAL EMERGENCY RED-FLAG DETECTED";
    elements.emergencyMessage.textContent = data.emergency_warning;
    elements.stage1Status.textContent = "REFLEX BLOCKED";
    elements.stage1Status.className = "badge badge-danger";
  } else {
    elements.emergencyBanner.classList.add("hidden");
    elements.stage1Status.textContent = "SAFE DELIBERATION";
    elements.stage1Status.className = "badge badge-success";
  }

  // 2. Stage 1 Metrics (Safety & dlCBF)
  elements.stage1Dlcbf.textContent = data.dlcbf_hit ? "SEEN VERBATIM" : "NOVEL ENCOUNTER";
  elements.stage1DlcbfLat.textContent = `${data.dlcbf_latency_us} µs`;
  elements.stage1TotalLat.textContent = `${data.total_latency_ms} ms`;

  // 3. Stage 2 Metrics (LocalRAG)
  elements.stage2Pruning.textContent = `${data.pruning_ratio_pct.toFixed(1)}% Noise Cut`;
  elements.stage2Nodecount.textContent = `${data.subgraph_nodes.length} Nodes · ${data.subgraph_edges.length} Edges`;
  renderTopRemedies(data.top_remedies);

  // 4. Stage 3 Metrics (MPCS Deliberation & Somatic Markers)
  elements.actionPill.textContent = data.action.toUpperCase();
  elements.actionPill.className = `action-pill ${data.action.toLowerCase()}`;
  elements.policySub.textContent = `Policy: ${data.policy} · Step: ${data.step_index}`;
  elements.tideRouteBadge.textContent = `${data.tide_route} ROUTE`;

  // VAD Gauges
  const vad = data.somatic_vad || { valence: 0.5, arousal: 0.5, dominance: 0.5 };
  elements.valValence.textContent = vad.valence.toFixed(2);
  elements.fillValence.style.width = `${Math.max(0, Math.min(100, (vad.valence + 1.0) * 50))}%`;

  elements.valArousal.textContent = vad.arousal.toFixed(2);
  elements.fillArousal.style.width = `${Math.max(0, Math.min(100, vad.arousal * 100))}%`;

  elements.valDominance.textContent = vad.dominance.toFixed(2);
  elements.fillDominance.style.width = `${Math.max(0, Math.min(100, vad.dominance * 100))}%`;

  // 5. Stage 4 Grounded Output
  elements.diffAnalysis.innerHTML = formatMarkdown(data.differential_analysis);
  renderEvidence(data.grounded_evidence);

  // 6. Subgraph Canvas Setup
  setupCanvasGraph(data.subgraph_nodes, data.subgraph_edges);
}

/**
 * Render Top Remedy Cards
 */
function renderTopRemedies(remedies) {
  if (!remedies || remedies.length === 0) {
    elements.topRemediesContainer.innerHTML = `<div class="empty-hint">No remedies exceeded threshold for this query.</div>`;
    return;
  }

  elements.topRemediesContainer.innerHTML = remedies
    .map(
      (r) => `
    <div class="remedy-item" data-id="${r.id}">
      <div class="rem-top">
        <span class="rem-name">${r.name}</span>
        <span class="rem-score">W = ${r.score.toFixed(3)}</span>
      </div>
      <div class="rem-sub">
        <span>Grade ${r.grade}</span>
        <span>•</span>
        <span>${r.classification.replace("_", " ")}</span>
        <span>•</span>
        <span>VAD: (${r.valence}, ${r.arousal}, ${r.dominance})</span>
      </div>
      ${
        r.linked_symptoms && r.linked_symptoms.length > 0
          ? `<div class="rem-rubrics" title="${r.linked_symptoms.join(', ')}">Rubrics: ${r.linked_symptoms.join(', ')}</div>`
          : ""
      }
    </div>
  `
    )
    .join("");
}

/**
 * Render Materia Medica Proving Quotes
 */
function renderEvidence(evidence) {
  if (!evidence || evidence.length === 0) {
    elements.evidenceContainer.innerHTML = `<div class="empty-hint">No occurrence quotes attached to active nodes.</div>`;
    return;
  }

  elements.evidenceContainer.innerHTML = evidence
    .map(
      (e) => `
    <div class="evidence-item">
      <div class="evidence-quote">"${escapeHtml(e.quote)}"</div>
      <div class="evidence-meta">
        <strong>${e.label}</strong> (${e.section}) · Grade ${e.grade} · <em>${e.sources.join(', ')}</em>
      </div>
    </div>
  `
    )
    .join("");
}

/**
 * Setup and Layout the Active Subgraph in HTML5 Canvas
 */
function setupCanvasGraph(nodes, edges) {
  state.activeNodes = [];
  state.activeEdges = edges || [];

  if (!nodes || nodes.length === 0) {
    drawGraph();
    return;
  }

  const W = elements.canvas.width;
  const H = elements.canvas.height;
  const cx = W / 2;
  const cy = H / 2;

  // Layout Algorithm: Concentric Radial Mandala
  // Layer 0: Center Percept Seed
  // Layer 1: Remedies / Medicines (R = 150)
  // Layer 2: Symptoms & Modalities (R = 240 - 280)
  const remedies = nodes.filter(
    (n) => n.type.toLowerCase() === "medicine" || n.id.startsWith("remedy:")
  );
  const others = nodes.filter(
    (n) => n.type.toLowerCase() !== "medicine" && !n.id.startsWith("remedy:")
  );

  // Position Remedies in inner circle
  remedies.forEach((rem, i) => {
    const angle = (2 * Math.PI * i) / Math.max(1, remedies.length) - Math.PI / 2;
    const r = remedies.length === 1 ? 0 : 130;
    state.activeNodes.push({
      ...rem,
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
      radius: 18 + rem.score * 12,
      color: COLORS.remedy,
    });
  });

  // Position Symptoms in outer circle with golden angle distribution
  others.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / Math.max(1, others.length) + 0.3;
    const r = 240 + (i % 2) * 35;
    let nodeColor = COLORS.default;
    const t = node.type.toLowerCase();
    if (t.includes("physical")) nodeColor = COLORS.physical;
    else if (t.includes("affective")) nodeColor = COLORS.affective;
    else if (t.includes("modality")) nodeColor = COLORS.modality;
    else if (t.includes("condition")) nodeColor = COLORS.condition;
    else if (t.includes("domain")) nodeColor = COLORS.domain;

    state.activeNodes.push({
      ...node,
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
      radius: 8 + node.score * 8,
      color: nodeColor,
    });
  });

  drawGraph();
}

/**
 * Draw 60 FPS Canvas Graph
 */
function drawGraph() {
  const W = elements.canvas.width;
  const H = elements.canvas.height;
  ctx.clearRect(0, 0, W, H);

  // Draw Background Grid
  ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
  ctx.lineWidth = 1;
  const gridSize = 40;
  for (let x = 0; x < W; x += gridSize) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, H);
    ctx.stroke();
  }
  for (let y = 0; y < H; y += gridSize) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(W, y);
    ctx.stroke();
  }

  const nodeMap = new Map(state.activeNodes.map((n) => [n.id, n]));

  // Draw Edges
  state.activeEdges.forEach((edge) => {
    const src = nodeMap.get(edge.source);
    const tgt = nodeMap.get(edge.target);
    if (!src || !tgt) return;

    ctx.beginPath();
    ctx.moveTo(src.x, src.y);
    ctx.lineTo(tgt.x, tgt.y);

    if (edge.classification === "internal") {
      ctx.strokeStyle = "rgba(16, 185, 129, 0.4)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([]);
    } else {
      ctx.strokeStyle = "rgba(236, 72, 153, 0.35)";
      ctx.lineWidth = 1.2;
      ctx.setLineDash([4, 4]);
    }
    ctx.stroke();
    ctx.setLineDash([]);
  });

  // Draw Nodes
  state.activeNodes.forEach((node) => {
    const isHovered = state.hoveredNode && state.hoveredNode.id === node.id;

    // Glowing Halo
    if (isHovered || node.score > 0.7) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius + 6, 0, Math.PI * 2);
      ctx.fillStyle = `${node.color}33`;
      ctx.fill();
    }

    // Node Circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
    ctx.fillStyle = node.color;
    ctx.fill();
    ctx.lineWidth = isHovered ? 2.5 : 1.5;
    ctx.strokeStyle = isHovered ? "#ffffff" : "rgba(255, 255, 255, 0.3)";
    ctx.stroke();

    // Node Text Label
    ctx.font = node.radius > 16 ? "600 11px Inter" : "500 9px Inter";
    ctx.fillStyle = "#f8fafc";
    ctx.textAlign = "center";
    ctx.fillText(truncate(node.label, 20), node.x, node.y + node.radius + 12);
  });
}

/**
 * Handle Canvas Mouse Hover Detection
 */
function handleCanvasMouseMove(e) {
  const rect = elements.canvas.getBoundingClientRect();
  const mouseX = ((e.clientX - rect.left) / rect.width) * elements.canvas.width;
  const mouseY = ((e.clientY - rect.top) / rect.height) * elements.canvas.height;

  let found = null;
  for (let i = state.activeNodes.length - 1; i >= 0; i--) {
    const n = state.activeNodes[i];
    const dx = mouseX - n.x;
    const dy = mouseY - n.y;
    if (dx * dx + dy * dy <= (n.radius + 6) * (n.radius + 6)) {
      found = n;
      break;
    }
  }

  if (found !== state.hoveredNode) {
    state.hoveredNode = found;
    drawGraph();

    if (found) {
      elements.tooltip.classList.remove("hidden");
      elements.tooltip.style.left = `${e.clientX - rect.left + 15}px`;
      elements.tooltip.style.top = `${e.clientY - rect.top + 10}px`;
      elements.tooltip.innerHTML = `
        <div style="font-weight:700;color:#93c5fd;margin-bottom:2px;">${found.label}</div>
        <div style="font-size:0.7rem;color:#94a3b8;">${found.type} · Score: ${found.score.toFixed(3)}</div>
        ${found.grade ? `<div style="font-size:0.7rem;color:#fbbf24;">Typographic Grade: ${found.grade}</div>` : ""}
        ${found.section ? `<div style="font-size:0.7rem;color:#a78bfa;">Section: ${found.section}</div>` : ""}
        ${found.quote ? `<div style="font-style:italic;font-size:0.68rem;color:#cbd5e1;margin-top:4px;">"${found.quote.slice(0, 120)}..."</div>` : ""}
      `;
    } else {
      elements.tooltip.classList.add("hidden");
    }
  }
}

/**
 * Submit Feedback / Reinforcement
 */
async function submitFeedback(reward, expertAction = null) {
  if (!state.lastResponse) {
    alert("Please execute a query first before submitting feedback.");
    return;
  }

  try {
    const payload = {
      step: state.lastResponse.step_index,
      reward: reward,
      expert_action: expertAction,
    };

    const res = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const data = await res.json();
      alert(`Feedback recorded! Status: ${data.status}. Adaptive action threshold adjusted.`);
    }
  } catch (err) {
    console.error("Feedback submission error:", err);
  }
}

/**
 * Resize Canvas for HiDPI
 */
function resizeCanvas() {
  const rect = elements.canvas.parentElement.getBoundingClientRect();
  elements.canvas.width = rect.width || 1200;
  elements.canvas.height = rect.height || 520;
  if (state.activeNodes.length > 0) {
    drawGraph();
  }
}

/**
 * Utilities
 */
function truncate(str, max) {
  return str.length > max ? str.slice(0, max - 1) + "…" : str;
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[m]);
}

function formatMarkdown(text) {
  if (!text) return "";
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.*?)`/g, "<code class='mono'>$1</code>");
}

// Boot application on DOM ready
document.addEventListener("DOMContentLoaded", initApp);


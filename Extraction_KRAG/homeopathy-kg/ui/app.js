// Homeopathy Knowledge Graph Interactive Studio
document.addEventListener("DOMContentLoaded", () => {
  const schemaTitle = document.getElementById("schema-title");
  const schemaSubtitle = document.getElementById("schema-subtitle");
  const statsPill = document.getElementById("stats-pill");
  const remedySelect = document.getElementById("remedy-select");
  const svgElement = document.getElementById("graph-svg");
  const container = document.getElementById("canvas-container");
  const resetBtn = document.getElementById("reset-btn");
  const zoomInBtn = document.getElementById("zoom-in");
  const zoomOutBtn = document.getElementById("zoom-out");
  const zoomFitBtn = document.getElementById("zoom-fit");
  const drawer = document.getElementById("inspector-drawer");
  const drawerContent = document.getElementById("drawer-content");
  const drawerCloseBtn = document.getElementById("drawer-close-btn");
  const legendItems = document.querySelectorAll(".legend-item");
  const guideToggleBtn = document.getElementById("guide-toggle-btn");
  const guideModalBackdrop = document.getElementById("guide-modal-backdrop");
  const modalCloseBtn = document.getElementById("modal-close-btn");
  const modalDismissBtn = document.getElementById("modal-dismiss-btn");
  const runSelect = document.getElementById("run-select");

  const allRuns = window.ALL_RUNS || { "hybrid": window.GRAPH_DATA || {} };
  let currentRunKey = allRuns["hybrid"] ? "hybrid" : (Object.keys(allRuns)[0] || "hybrid");
  let graphData = allRuns[currentRunKey] || window.GRAPH_DATA || {};

  if (runSelect) {
    runSelect.value = currentRunKey;
    runSelect.addEventListener("change", (e) => {
      currentRunKey = e.target.value;
      graphData = allRuns[currentRunKey] || {};
      initSelector();
      const firstSchema = remedySelect.value || Object.keys(graphData)[0];
      if (firstSchema) {
        loadSchema(firstSchema);
      }
    });
  }

  let currentSchema = null;
  let simulation = null;
  let svg = d3.select("#graph-svg");
  let g = svg.append("g");
  let zoom = null;

  // Category Color Map strictly from screenshot
  const colorMap = {
    "Medicine": "#70b5ff",
    "Physical Symptom": "#f7a1c4",
    "Affective Symptom": "#caa9f7",
    "Modality": "#f3d266",
    "Cognitive Domain": "#55d99b"
  };

  const radiusMap = {
    "Medicine": 24,
    "Physical Symptom": 15,
    "Affective Symptom": 16,
    "Modality": 12,
    "Cognitive Domain": 16
  };

  function getNodeRadius(d) {
    return radiusMap[d.type] || 14;
  }

  function getNodeColor(d) {
    return colorMap[d.type] || "#a0aec0";
  }

  // Populate Remedy Select
  function initSelector() {
    const keys = Object.keys(graphData);
    if (keys.length === 0) {
      console.warn("No graph data found.");
      return;
    }

    remedySelect.innerHTML = "";
    keys.forEach(k => {
      const opt = document.createElement("option");
      opt.value = k;
      opt.textContent = k;
      if (k.startsWith("Combined") || k.includes("Combined Knowledge Graph")) {
        opt.selected = true;
      }
      remedySelect.appendChild(opt);
    });

    remedySelect.addEventListener("change", (e) => {
      loadSchema(e.target.value);
    });

    const defaultKey = remedySelect.value || keys[0];
    loadSchema(defaultKey);
  }

  // Zoom Setup
  function initZoom() {
    zoom = d3.zoom()
      .scaleExtent([0.1, 5])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });

    svg.call(zoom);

    resetBtn.addEventListener("click", () => {
      resetView();
    });

    zoomInBtn.addEventListener("click", () => {
      svg.transition().duration(300).call(zoom.scaleBy, 1.3);
    });

    zoomOutBtn.addEventListener("click", () => {
      svg.transition().duration(300).call(zoom.scaleBy, 0.7);
    });

    zoomFitBtn.addEventListener("click", () => {
      resetView();
    });
  }

  function resetView() {
    const width = container.clientWidth || 1000;
    const height = container.clientHeight || 650;
    const isLarge = currentSchema && currentSchema.nodes.length > 80;
    const initialScale = isLarge ? 0.32 : 1.0;
    const tx = isLarge ? (width / 2) * (1 - initialScale) : 0;
    const ty = isLarge ? (height / 2) * (1 - initialScale) : 0;

    svg.transition().duration(750).call(
      zoom.transform,
      d3.zoomIdentity.translate(tx, ty).scale(initialScale)
    );
    if (simulation) {
      simulation.alpha(0.8).restart();
    }
  }

  // Load and Render Schema
  function loadSchema(schemaKey) {
    currentSchema = graphData[schemaKey];
    if (!currentSchema) return;

    // Update Header Text
    schemaTitle.textContent = currentSchema.title || `${schemaKey} Schema`;
    schemaSubtitle.textContent = currentSchema.subtitle || "Interactive homeopathic symptom & modality network graph";
    statsPill.textContent = `${currentSchema.nodes.length} Nodes · ${currentSchema.links.length} Links`;

    // Clone data to avoid mutating original
    const nodes = currentSchema.nodes.map(d => ({ ...d }));
    const links = currentSchema.links.map(d => ({ ...d }));

    renderGraph(nodes, links);
  }

  function renderGraph(nodes, links) {
    const rect = container.getBoundingClientRect();
    const width = rect.width > 100 ? rect.width : 1000;
    const height = rect.height > 100 ? rect.height : 650;
    const isLarge = nodes.length > 80;

    svg.attr("viewBox", [0, 0, width, height]);

    // Clear previous elements
    g.selectAll("*").remove();

    if (simulation) simulation.stop();

    // Initialize node positions
    const medNodes = nodes.filter(x => x.type === "Medicine");
    if (medNodes.length === 1) {
      medNodes[0].x = width / 2;
      medNodes[0].y = height / 2;
      const nonMed = nodes.filter(x => x.type !== "Medicine");
      nonMed.forEach((n, idx) => {
        const angle = (idx / Math.max(nonMed.length, 1)) * 2 * Math.PI;
        const dist = n.type === "Modality" ? 220 : (n.type === "Cognitive Domain" ? 170 : 130);
        n.x = width / 2 + dist * Math.cos(angle);
        n.y = height / 2 + dist * Math.sin(angle);
      });
    } else {
      // Multi-remedy / Combined Graph: distribute medicines in outer ring
      medNodes.forEach((n, idx) => {
        const angle = (idx / Math.max(medNodes.length, 1)) * 2 * Math.PI;
        const r = 520;
        n.x = width / 2 + r * Math.cos(angle);
        n.y = height / 2 + r * Math.sin(angle);
      });
      // Cognitive Domain hubs in inner ring
      const domNodes = nodes.filter(x => x.type === "Cognitive Domain");
      domNodes.forEach((n, idx) => {
        const angle = (idx / Math.max(domNodes.length, 1)) * 2 * Math.PI;
        const r = 160;
        n.x = width / 2 + r * Math.cos(angle);
        n.y = height / 2 + r * Math.sin(angle);
      });
      // Other nodes (Symptoms, Modalities)
      const otherNodes = nodes.filter(x => x.type !== "Medicine" && x.type !== "Cognitive Domain");
      otherNodes.forEach((n, idx) => {
        const angle = (idx / Math.max(otherNodes.length, 1)) * 2 * Math.PI;
        const r = 320 + (idx % 7) * 40;
        n.x = width / 2 + r * Math.cos(angle);
        n.y = height / 2 + r * Math.sin(angle);
      });
    }

    // Force simulation parameters tuned for scale
    simulation = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id(d => d.id).distance(isLarge ? 75 : 140))
      .force("charge", d3.forceManyBody().strength(isLarge ? -110 : -450))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(d => getNodeRadius(d) + (isLarge ? 10 : 26)))
      .force("x", d3.forceX(width / 2).strength(isLarge ? 0.04 : 0.06))
      .force("y", d3.forceY(height / 2).strength(isLarge ? 0.04 : 0.06));

    // Arrow markers
    const defs = svg.selectAll("defs").data([0]).join("defs");
    defs.selectAll("marker").remove();

    defs.append("marker")
      .attr("id", "arrow")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 26)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-4L8,0L0,4")
      .attr("fill", "#4a5568");

    // Links container
    const linkGroup = g.append("g").attr("class", "links");
    const link = linkGroup.selectAll("line")
      .data(links)
      .join("line")
      .attr("class", "graph-link")
      .attr("marker-end", "url(#arrow)");

    // Link Labels
    const linkLabelGroup = g.append("g").attr("class", "link-labels");
    const linkLabel = linkLabelGroup.selectAll("text")
      .data(links)
      .join("text")
      .attr("class", "graph-link-label")
      .text(d => d.label || "");

    // Nodes container
    const nodeGroup = g.append("g").attr("class", "nodes");
    const node = nodeGroup.selectAll("g")
      .data(nodes)
      .join("g")
      .attr("class", "graph-node")
      .call(drag(simulation));

    // Node Circles with border and glow
    node.append("circle")
      .attr("class", "graph-node-circle")
      .attr("r", d => getNodeRadius(d))
      .attr("fill", d => getNodeColor(d))
      .attr("stroke", "#ffffff")
      .attr("stroke-opacity", 0.4);

    // Node Labels
    node.append("text")
      .attr("class", "graph-node-text")
      .attr("dy", d => getNodeRadius(d) + 14)
      .attr("text-anchor", "middle")
      .text(d => d.name);

    // Interaction Events
    node.on("click", (event, d) => {
      event.stopPropagation();
      openInspector(d);
    });

    node.on("mouseenter", (event, d) => {
      highlightConnections(d, nodes, links, node, link, linkLabel);
    });

    node.on("mouseleave", () => {
      clearHighlights(node, link, linkLabel);
    });

    // Tick update
    simulation.on("tick", () => {
      link
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);

      linkLabel
        .attr("x", d => (d.source.x + d.target.x) / 2)
        .attr("y", d => (d.source.y + d.target.y) / 2 - 3);

      node.attr("transform", d => `translate(${d.x},${d.y})`);
    });

    // Reset view transform on schema switch
    resetView();
  }

  // Highlight network neighborhood
  function highlightConnections(activeNode, nodes, links, nodeSel, linkSel, labelSel) {
    const connectedIds = new Set([activeNode.id]);

    links.forEach(l => {
      const sId = typeof l.source === "object" ? l.source.id : l.source;
      const tId = typeof l.target === "object" ? l.target.id : l.target;
      if (sId === activeNode.id) connectedIds.add(tId);
      if (tId === activeNode.id) connectedIds.add(sId);
    });

    nodeSel.style("opacity", d => connectedIds.has(d.id) ? 1 : 0.2);
    linkSel
      .style("opacity", l => {
        const sId = typeof l.source === "object" ? l.source.id : l.source;
        const tId = typeof l.target === "object" ? l.target.id : l.target;
        return (sId === activeNode.id || tId === activeNode.id) ? 1 : 0.1;
      })
      .classed("highlighted", l => {
        const sId = typeof l.source === "object" ? l.source.id : l.source;
        const tId = typeof l.target === "object" ? l.target.id : l.target;
        return (sId === activeNode.id || tId === activeNode.id);
      });

    labelSel.style("opacity", l => {
      const sId = typeof l.source === "object" ? l.source.id : l.source;
      const tId = typeof l.target === "object" ? l.target.id : l.target;
      return (sId === activeNode.id || tId === activeNode.id) ? 1 : 0.1;
    });
  }

  function clearHighlights(nodeSel, linkSel, labelSel) {
    nodeSel.style("opacity", 1);
    linkSel.style("opacity", 0.7).classed("highlighted", false);
    labelSel.style("opacity", 1);
  }

  // Drag Behaviors
  function drag(sim) {
    function dragstarted(event) {
      if (!event.active) sim.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }

    function dragended(event) {
      if (!event.active) sim.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }

    return d3.drag()
      .on("start", dragstarted)
      .on("drag", dragged)
      .on("end", dragended);
  }

  // Open Inspector Drawer
  function openInspector(d) {
    const color = getNodeColor(d);
    drawerContent.innerHTML = `
      <div>
        <span class="info-badge-type" style="background: ${color}25; color: ${color}; border: 1px solid ${color}60;">
          ${d.type}
        </span>
        <h2 style="font-size: 20px; font-weight: 600; margin-top: 10px; color: #ffffff;">${d.name}</h2>
      </div>

      ${d.quote ? `
        <div>
          <div class="info-label">Verbatim Evidence Quote</div>
          <div class="info-box info-quote">"${d.quote}"</div>
        </div>
      ` : ""}

      ${d.details ? `
        <div>
          <div class="info-label">Clinical / Affective Notes</div>
          <div class="info-box">${d.details}</div>
        </div>
      ` : ""}

      ${d.remedy ? `
        <div>
          <div class="info-label">Associated Remedy</div>
          <div class="info-box" style="color: #70b5ff; font-weight: 500;">${d.remedy}</div>
        </div>
      ` : ""}

      ${d.remedies && d.remedies.length > 0 ? `
        <div>
          <div class="info-label">Associated Remedies (${d.remedies.length})</div>
          <div class="info-box" style="color: #70b5ff; font-weight: 500;">${d.remedies.join(', ')}</div>
        </div>
      ` : ""}

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
        ${d.confidence ? `
          <div class="info-box" style="text-align: center;">
            <div class="info-label">Confidence</div>
            <div style="font-size: 18px; font-weight: bold; color: #70b5ff;">${Math.round(d.confidence * 100)}%</div>
          </div>
        ` : ""}
        ${d.grade ? `
          <div class="info-box" style="text-align: center;">
            <div class="info-label">Clinical Grade</div>
            <div style="font-size: 18px; font-weight: bold; color: #f3d266;">Grade ${d.grade} ${'★'.repeat(d.grade)}</div>
          </div>
        ` : ""}
      </div>

      ${d.source_ref ? `
        <div>
          <div class="info-label">Source Citation</div>
          <div class="info-box" style="font-family: monospace; font-size: 12px; color: #8b949e;">${d.source_ref}</div>
        </div>
      ` : ""}
    `;

    drawer.classList.add("open");
  }

  drawerCloseBtn.addEventListener("click", () => {
    drawer.classList.remove("open");
  });

  // Close inspector when clicking on canvas background
  svg.on("click", () => {
    drawer.classList.remove("open");
  });

  // Guide Modal Controls
  function openGuide() {
    if (guideModalBackdrop) guideModalBackdrop.classList.add("open");
  }

  function closeGuide() {
    if (guideModalBackdrop) guideModalBackdrop.classList.remove("open");
  }

  if (guideToggleBtn) guideToggleBtn.addEventListener("click", openGuide);
  if (modalCloseBtn) modalCloseBtn.addEventListener("click", closeGuide);
  if (modalDismissBtn) modalDismissBtn.addEventListener("click", closeGuide);

  if (guideModalBackdrop) {
    guideModalBackdrop.addEventListener("click", (e) => {
      if (e.target === guideModalBackdrop) {
        closeGuide();
      }
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeGuide();
      drawer.classList.remove("open");
    }
  });

  // Legend filter clicks
  legendItems.forEach(item => {
    item.addEventListener("click", () => {
      const type = item.getAttribute("data-type");
      g.selectAll(".graph-node").style("opacity", d => d.type === type ? 1 : 0.25);
      setTimeout(() => {
        g.selectAll(".graph-node").style("opacity", 1);
      }, 1800);
    });
  });

  // Initialize
  initZoom();
  initSelector();

  // Responsive resize
  window.addEventListener("resize", () => {
    if (currentSchema) {
      loadSchema(remedySelect.value);
    }
  });
});

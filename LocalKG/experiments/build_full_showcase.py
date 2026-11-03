import json
from pathlib import Path
import sys

sys.path.insert(0, "LocalKG/src")
from lkg.viz.graph_viz import HTML_TEMPLATE

data_dir = Path("LocalKG/data/extracted")
docs_dir = Path("docs")

full_graph = json.loads((data_dir / "kg_full_materia_medica_cleaned.graph.json").read_text(encoding="utf-8"))
full_json_str = json.dumps(full_graph, ensure_ascii=False)

# 1. Simple TIDE WITHOUT Persona Profiles -> kg_full_materia_medica.html
simple_tide_html = (
    HTML_TEMPLATE.replace("__TITLE__", "Full Materia Medica Knowledge Graph (TIDE Spreading Activation)")
    .replace("__GRAPH_JSON__", full_json_str)
    .replace('    <button id="persona-btn" class="active-toggle" onclick="togglePersonaMode()">Persona: Exploratory</button>\n', '')
    .replace('      <div class="stat-row"><span>Query Persona</span><strong id="act-persona" style="color:var(--cyan)">Exploratory (Broad)</strong></div>\n', '')
    .replace('const btn = document.getElementById("persona-btn");', 'const btn = document.getElementById("persona-btn"); if(!btn) return;')
    .replace('personaMode === "confident" ? "Confident Core Subgraph" : "Exploratory Subgraph"', '"TIDE Active Subgraph"')
)
(data_dir / "kg_full_materia_medica.html").write_text(simple_tide_html, encoding="utf-8")
print("Wrote Simple TIDE (without profiles) -> kg_full_materia_medica.html")

# 2. Full TIDE WITH Persona Profiles -> kg_full_materia_medica_cleaned.html
full_personas_html = (
    HTML_TEMPLATE.replace("__TITLE__", "Full Materia Medica Knowledge Graph (TIDE + Dual Persona Profiles)")
    .replace("__GRAPH_JSON__", full_json_str)
)
(data_dir / "kg_full_materia_medica_cleaned.html").write_text(full_personas_html, encoding="utf-8")
print("Wrote TIDE + Persona Profiles -> kg_full_materia_medica_cleaned.html")

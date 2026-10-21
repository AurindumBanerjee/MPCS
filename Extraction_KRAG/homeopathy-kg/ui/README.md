# Homeopathy Knowledge Graph Studio — Architecture & Execution Guide

This document explains the architecture of the **Homeopathy Knowledge Graph (HKG) Interactive Studio**, how the data pipeline transforms raw extracted homeopathic literature into a structured network, and step-by-step instructions on **how to run the pipeline and render the interactive graph**.

---

## 1. Overview & Conceptual Architecture

The Homeopathy Knowledge Graph Studio visualizes multi-layered clinical networks extracted from digitized classical homeopathic literature (*Boericke's Pocket Manual of Homeopathic Materia Medica*).

Each remedy's graph is an interconnected schema linking clinical substances to symptoms, environmental modalities, and psychological cognitive domains with textual provenance.

```
                  ┌──────────────────────┐
                  │       Medicine       │  (Blue, center hub)
                  │   e.g. Belladonna    │
                  └──────────┬───────────┘
         ┌───────────────────┼────────────────────┬────────────────────┐
         │ TREATS            │ HAS AFFECTIVE SYM  │ AGGRAVATED BY      │ AMELIORATED BY
         ▼                   ▼                    ▼                    ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Physical Symptom │ │Affective Symptom │ │     Modality     │ │     Modality     │
│  (Pink nodes)    │ │ (Purple nodes)   │ │  (Yellow nodes)  │ │  (Yellow nodes)  │
└──────────────────┘ └────────┬─────────┘ └──────────────────┘ └──────────────────┘
                              │ MAPS TO
                              ▼
                     ┌──────────────────┐
                     │ Cognitive Domain │
                     │  (Green nodes)   │
                     └──────────────────┘
```

---

## 2. Graph Schema & Visual Grammar

### A. Node Types & Color Coding
The visual grammar matches clinical and neuropsychological ontologies:

| Entity Type | Color | Radius | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| **Medicine** | `#70b5ff` (Blue) | `24px` | Central homeopathic remedy entity | *Belladonna*, *Arsenicum Album* |
| **Physical Symptom** | `#f7a1c4` (Pink) | `15px` | Somatic symptoms organized by anatomical section | *Throbbing headache*, *Burning in stomach* |
| **Affective Symptom** | `#caa9f7` (Purple) | `16px` | Psychological, emotional, or behavioral symptoms | *Anguish and restlessness*, *Delirium with fury* |
| **Modality** | `#f3d266` (Yellow) | `12px` | Factors that aggravate or ameliorate conditions | *Worse Cold Air*, *Better Warm Drinks* |
| **Cognitive Domain** | `#55d99b` (Green) | `16px` | High-level neuropsychological construct mapped from affect | *Anxiety / Threat Processing*, *Hyperarousal* |

### B. Relationship Types (Directed Edges)
| Edge Label | Source Entity | Target Entity | Semantics |
| :--- | :--- | :--- | :--- |
| `TREATS` | Medicine | Physical Symptom | Remedy is clinically indicated for the physical condition |
| `HAS AFFECTIVE SYMPTOM` | Medicine | Affective Symptom | Remedy manifests specific emotional/mental states |
| `AGGRAVATED BY` | Medicine or Symptom | Modality | Condition or remedy worsens under this factor |
| `AMELIORATED BY` | Medicine or Symptom | Modality | Condition or remedy improves under this factor |
| `MAPS TO` | Affective Symptom | Cognitive Domain | Links emotional symptom to psychological domain |

---

## 3. Cognitive Domain & Modality Mapping

### Cognitive Domain Extraction
Affective symptoms are mapped to Research Domain Criteria (RDoC)-inspired cognitive domains via keyword taxonomy in `export_graph_data.py`:
1. **Anxiety / Threat Processing**: `fear`, `anxiety`, `anguish`, `dread`, `fright`, `panic`, `phobia`, `terror`
2. **Hyperarousal**: `restless`, `tossing`, `agitation`, `startle`, `hypervigilance`, `insomnia`, `wakefulness`
3. **Mood / Affect Regulation**: `melancholy`, `despair`, `sad`, `weeping`, `grief`, `suicidal`, `hopeless`, `apathy`
4. **Impulse Control / Aggression**: `rage`, `fury`, `violence`, `destructive`, `anger`, `quarrelsome`, `irritability`
5. **Cognitive Processing**: `delirium`, `hallucinations`, `confusion`, `stupor`, `absent-minded`, `concentration`
6. **Social Cognition**: `alone`, `company`, `suspicious`, `mistrustful`, `aversion to company`

### Dynamic Modality Parsing
Modality factors are extracted from both:
- **General Modality occurrences**: Text blocks containing `Worse... Better...` (e.g., *after midnight*, *wet weather*, *heat*) parsed into individual factors with directional polarity (`worse` vs `better`).
- **Per-symptom modalities**: Local aggravating/ameliorating conditions attached to specific anatomical symptoms.

---

## 4. How to Run and Get the Graph (Step-by-Step)

### Prerequisites
- Python 3.10+ installed
- Conda environment or virtualenv (e.g. `et_hack` or standard Python environment)
- A modern web browser (Chrome, Edge, Firefox, Safari)

### Step 1: Verify Extracted Data
The pipeline relies on structured JSONL extraction from Boericke's Materia Medica located at:
```
data/extracted/run_manual_baseline.jsonl
```
*(Contains 115 records spanning 20 classical homeopathic remedies)*.

### Step 2: Run the Graph Data Exporter
Run the export script from the project root (`homeopathy-kg`):

```powershell
python ui/export_graph_data.py
```

**What this script does:**
1. Ingests `data/extracted/run_manual_baseline.jsonl`.
2. Groups chunks by remedy name across all 20 remedies.
3. Dynamically extracts `Medicine`, `Physical Symptom`, `Affective Symptom`, `Modality`, and `Cognitive Domain` nodes.
4. Generates two synchronized files:
   - `ui/graph_data.json` (Structured JSON representation for API or programmatic use)
   - `ui/data.js` (Exposes `window.GRAPH_DATA = { ... }` for zero-CORS browser loading)

**Console Output:**
```
Generated 20 schemas -> ui\graph_data.json
  Also wrote UI data -> ui\data.js
  Aconitum napellus: 10 nodes, 11 edges
  Arsenicum album: 10 nodes, 10 edges
  Belladonna: 13 nodes, 14 edges
  Nux vomica: 12 nodes, 13 edges
  ...
```

### Step 3: Launch the UI Server
Run the local HTTP server:

```powershell
python serve_ui.py
```

The server binds to port `8080` serving the static assets in `ui/`:
```
========================================================
  ✨ Homeopathy Knowledge Graph Studio is Running!
  🌐 Open URL: http://localhost:8080
========================================================
```

### Step 4: Open and Explore in the Browser
Navigate to:
```
http://localhost:8080/
```

---

## 5. UI Features & Controls

1. **Remedy Schema Selector (Top Navbar)**:
   - Dropdown menu dynamically lists all 20 extracted remedies.
   - Selecting any remedy instantly transitions the force-directed graph to that remedy's network.

2. **Force-Directed Physics Simulation**:
   - D3.js force simulation (`d3.forceSimulation`) dynamically arranges nodes with charge repulsion, collision avoidance, and centered link springs.
   - **Interactive Dragging**: Click and drag any node to pin or reposition it. Double-clicking unpins the node.
   - **Zoom & Pan**: Use the mouse scroll wheel or drag on empty canvas to zoom/pan. Use controls (+, −, ⛶) at bottom right.

3. **Entity Provenance Inspector (Click Drawer)**:
   - Clicking any node opens a right-side inspector panel showing:
     - Entity label & category tag
     - Anatomical / text section (e.g. *Mind*, *Head*, *Modalities*)
     - Clinical extraction grade (Grade 1-3)
     - Extraction confidence score (e.g. 95%)
     - Verbatim evidence quote from Boericke's original text

4. **Legend & Interactive Highlight**:
   - Legend bar displays the 5 node types.
   - Hovering over a legend item highlights nodes of that category and dims other nodes.

---

## 6. Directory Structure

```
homeopathy-kg/
├── data/
│   ├── raw/
│   │   └── boericke.html            # Digitized raw source text
│   └── extracted/
│       └── run_manual_baseline.jsonl       # Extracted JSONL entities & modalities (mock/manual baseline)
├── serve_ui.py                      # Local web server runner (Port 8080)
└── ui/
    ├── README.md                    # This architecture and execution guide
    ├── index.html                   # UI layout and structure
    ├── style.css                    # Dark glassmorphism styling
    ├── app.js                       # D3.js force graph, zoom, inspector drawer
    ├── export_graph_data.py         # Pipeline data transformer (JSONL -> graph)
    ├── graph_data.json              # Programmatic graph dataset
    └── data.js                      # Browser-ready window.GRAPH_DATA
```

# MPCS Monograph & Technical Report Workspace

This directory is the dedicated workspace for the comprehensive, publication-grade, two-column technical report covering the entire **MPCS (Memory-Perceptual Cognitive System) & LocalKG** repository.

---

## Directory Layout

```
report/
├── README.md                   # Directory overview and build instructions
├── MPCS_TECHNICAL_REPORT.md    # Primary exhaustive two-column monograph
├── figures/                    # Dedicated storage for figures, diagrams, and flowcharts
│   ├── arch_pipeline.svg       # End-to-end extraction and ingestion architecture
│   ├── memory_hierarchy.svg    # 3-tier memory hierarchy (dlCBF -> HyST -> TIDE)
│   ├── query_flowchart.svg     # Dual-Persona Query & Subgraph routing flow
│   └── viz_canvas_shaders.svg  # High-DPI Canvas shader & edge classification pipeline
└── tables/                     # (Optional) Exported benchmark datasets in CSV / JSON format
```

---

## Formatting Specifications

- **Style**: Dual-Column Scientific Format (IEEE / ACM style).
- **Typography**: Responsive CSS dual-column grid (`column-count: 2`) with full-width breaks (`column-span: all`) for comprehensive benchmark tables and landscape architecture flowcharts.
- **Formulas**: LaTeX / KaTeX mathematical rigor ($...$ inline, $$...$$ display).
- **Figures**: High-resolution vector diagrams (Mermaid, SVG, or crisp standalone graphics) stored directly under `report/figures/` and referenced via relative links (`./figures/<name>.svg`).

"""Build docs/Materia_Medica_Literature_PubMed.md from Materia_Medica_PubMed_Records.json."""

import json
from pathlib import Path

docs_dir = Path("docs")
records = json.loads((docs_dir / "Materia_Medica_PubMed_Records.json").read_text(encoding="utf-8"))

remedy_groups = {}
for r in records:
    rem = r["remedy"]
    remedy_groups.setdefault(rem, []).append(r)

lines = [
    "# Curated Materia Medica PubMed Literature & MeSH Index",
    "",
    "Authoritative medical literature, clinical trials, toxicological evaluations, and MeSH descriptor mappings.",
    "Integrated into the **MPCS Knowledge Graph** across 12 major remedies.",
    "",
    "---",
    "",
]

for rem, recs in remedy_groups.items():
    lines.append(f"## {rem}")
    lines.append("")
    for idx, r in enumerate(recs, start=1):
        lines.append(f"### Reference {idx}: {r['title']}")
        lines.append(f"* **Identifier**: `pmid:{r['pmid']}`")
        if r.get("authors"):
            lines.append(f"* **Authors**: {r['authors']}")
        lines.append(f"* **Source**: *{r['journal']}*, {r['year']}.")
        lines.append(f"* **Evidence Type**: {r['evidence_type'].title()} Study / Review")
        lines.append("* **MeSH Descriptors**: " + ", ".join(f"`{m}`" for m in r.get("mesh_terms", [])))
        lines.append("* **Extracted Clinical & Affective Symptoms**:")
        for s in r.get("extracted_symptoms", []):
            lines.append(f"  - **{s['canonical_label']}** ({s['kind'].capitalize()}, Severity Grade: {s['grade']}, Composite Weight: {s['composite_weight']})")
            if s.get("clinical_conditions"):
                lines.append("    * *Clinical Conditions (MeSH)*: " + ", ".join(s["clinical_conditions"]))
            if s.get("modalities"):
                mods = [f"{m['direction']} {m['factor_raw']}" for m in s["modalities"]]
                lines.append("    * *Modalities*: " + ", ".join(mods))
            if s.get("cognitive_domain") and s["cognitive_domain"] != "None":
                lines.append(f"    * *Cognitive/Affective Domain*: {s['cognitive_domain']}")
            eq = s.get("evidence_quote", "")
            if eq:
                lines.append(f'    * *Literature Quote*: "{eq}"')
        lines.append("")
    lines.append("---")
    lines.append("")

out_path = docs_dir / "Materia_Medica_Literature_PubMed.md"
out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {len(remedy_groups)} remedies to {out_path} ({out_path.stat().st_size:,} bytes)")

import json
from pathlib import Path

p = Path(r"LocalKG/data/extracted/kg_full_materia_medica.graph.json")
with open(p, "r", encoding="utf-8") as f:
    d = json.load(f)

nodes = d["nodes"]
links = d["links"]

bad_labels = [n for n in nodes if any(c in n["label"] for c in ["<", ">", "&", '"'])]
print(f"Nodes with XML special chars in label: {len(bad_labels)}")
for n in bad_labels[:10]:
    print("  ", n["id"], repr(n["label"]))

bad_link_labels = [l for l in links if any(c in l["label"] for c in ["<", ">", "&", '"'])]
print(f"Links with XML special chars in label: {len(bad_link_labels)}")
for l in bad_link_labels[:5]:
    print("  ", l["source"], repr(l["label"]), l["target"])

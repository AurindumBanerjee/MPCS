import re
from pathlib import Path

text = Path("docs/kg_full_materia_medica_showcase.html").read_text(encoding="utf-8")
el_ids = re.findall(r'document\.getElementById\(["\']([^"\']+)["\']\)', text)
missing = []
for eid in set(el_ids):
    if f'id="{eid}"' not in text and f"id='{eid}'" not in text:
        missing.append(eid)
print("Missing DOM IDs referenced by JS:", missing)

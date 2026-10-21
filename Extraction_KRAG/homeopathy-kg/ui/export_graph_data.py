import json
import re
from pathlib import Path

# ── Cognitive domain mapping ──────────────────────────────────────────────
# Maps keywords found in mental/affective symptoms to cognitive domain labels.
# A single symptom can map to multiple domains.
COGNITIVE_DOMAIN_MAP = {
    "Anxiety / Threat Processing": [
        "fear", "anxiety", "anguish", "dread", "fright", "apprehension",
        "panic", "worry", "phobia", "terror"
    ],
    "Hyperarousal": [
        "restless", "tossing", "agitation", "startl", "hypervig",
        "insomnia", "sleepless", "wakefulness"
    ],
    "Mood / Affect Regulation": [
        "melanchol", "despair", "sad", "weep", "tearful", "grief",
        "lamenting", "suicid", "hopeless", "indifferent", "apathy"
    ],
    "Impulse Control / Aggression": [
        "rage", "fury", "furious", "violen", "strike", "bite",
        "destructive", "anger", "irascib", "quarrel", "morose",
        "irritab"
    ],
    "Cognitive Processing": [
        "delirium", "hallucin", "confus", "stupor", "forget",
        "absent-mind", "concentrat", "dull", "slow", "wander"
    ],
    "Social Cognition": [
        "alone", "company", "jealous", "suspicio", "mistrustful",
        "antisocial", "aversion to company"
    ],
}


def _classify_cognitive_domains(symptom_text: str) -> list[str]:
    """Return list of cognitive domain names that match the symptom text."""
    text_lower = symptom_text.lower()
    domains = []
    for domain, keywords in COGNITIVE_DOMAIN_MAP.items():
        if any(kw in text_lower for kw in keywords):
            domains.append(domain)
    return domains


def _parse_modality_factors(raw_text: str) -> list[dict]:
    """
    Parse a raw modality string like:
      'wet weather, after midnight, cold drinks, cold food. Better, from heat, warm drinks, head elevated.'
    into individual factor dicts with direction and clean labels.
    """
    factors = []
    raw_text = raw_text.strip()
    if not raw_text or "###" in raw_text:
        return factors

    # Split into worse / better halves
    # The raw text from the pipeline looks like:
    #   "wet weather, after midnight, cold drinks. Better, from heat, warm drinks."
    # The direction for the chunk comes from the modality object's "direction" field,
    # but the text itself may also embed "Better," as a separator.
    parts = re.split(r"\.\s*Better\b[,.]?\s*", raw_text, flags=re.IGNORECASE)
    worse_part = parts[0].strip() if parts else ""
    better_part = parts[1].strip() if len(parts) > 1 else ""

    # Split each part on commas / semicolons to get individual factors
    for factor_str in re.split(r"[,;]+", worse_part):
        f = factor_str.strip().rstrip(".")
        f = re.sub(r"^(worse\s+)", "", f, flags=re.IGNORECASE).strip()
        if f and len(f) > 2:
            label = f[0].upper() + f[1:]
            factors.append({"direction": "worse", "label": f"Worse {label}"})

    for factor_str in re.split(r"[,;]+", better_part):
        f = factor_str.strip().rstrip(".")
        f = re.sub(r"^(from\s+|by\s+)", "", f, flags=re.IGNORECASE).strip()
        if f and len(f) > 2:
            label = f[0].upper() + f[1:]
            factors.append({"direction": "better", "label": f"Better {label}"})

    return factors


def generate_graph_data(extracted_file: Path, output_file: Path):
    remedy_graphs = {}

    # ── First pass: collect all chunks grouped by remedy ──────────────
    remedy_chunks: dict[str, list[dict]] = {}
    with open(extracted_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            remedy_name = rec.get("remedy_name", "").strip()
            if not remedy_name or remedy_name.lower() in ("introduction", "intro"):
                continue
            remedy_chunks.setdefault(remedy_name, []).append(rec)

    # ── Second pass: build graph per remedy ───────────────────────────
    for remedy_name, chunks in remedy_chunks.items():
        graph = {
            "id": remedy_name,
            "title": f"{remedy_name} Schema",
            "subtitle": "Interactive homeopathic symptom & modality network graph",
            "nodes": [],
            "links": []
        }
        med_node_id = f"med:{remedy_name}"
        graph["nodes"].append({
            "id": med_node_id,
            "name": remedy_name,
            "type": "Medicine",
            "details": f"Homeopathic remedy: {remedy_name}"
        })

        node_ids: set[str] = {med_node_id}
        link_keys: set[tuple] = set()
        mental_symptom_ids: list[str] = []   # track for cognitive domain linking

        for rec in chunks:
            section = rec.get("section", "General")

            for occ in rec.get("occurrences", []):
                kind = occ.get("kind", "symptom")

                # ── Handle general_modality occurrences ───────────
                if kind == "general_modality":
                    mods = occ.get("modalities", [])
                    for mod in mods:
                        raw_factor = mod.get("factor_raw", "")
                        parsed_factors = _parse_modality_factors(raw_factor)
                        for pf in parsed_factors:
                            mod_node_id = f"mod:{remedy_name}:{pf['label'].lower().replace(' ', '_')}"
                            if mod_node_id not in node_ids:
                                direction_text = (
                                    "Aggravation" if pf["direction"] == "worse"
                                    else "Amelioration"
                                )
                                graph["nodes"].append({
                                    "id": mod_node_id,
                                    "name": pf["label"],
                                    "type": "Modality",
                                    "details": f"{direction_text}: {pf['label']}"
                                })
                                node_ids.add(mod_node_id)

                            # Link medicine → modality
                            rel_label = (
                                "AGGRAVATED BY" if pf["direction"] == "worse"
                                else "AMELIORATED BY"
                            )
                            l_key = (med_node_id, mod_node_id, rel_label)
                            if l_key not in link_keys:
                                graph["links"].append({
                                    "source": med_node_id,
                                    "target": mod_node_id,
                                    "label": rel_label
                                })
                                link_keys.add(l_key)
                    continue

                # ── Handle symptom occurrences ────────────────────
                raw_sym = occ.get("symptom_raw", "").strip()
                if not raw_sym or raw_sym.startswith("###"):
                    continue

                short_label = raw_sym.split(".")[0].split(";")[0].strip()
                short_label = re.sub(r"[\*_]", "", short_label)
                if len(short_label) > 34:
                    short_label = short_label[:31] + "..."

                s_kind = occ.get("symptom_kind", "physical")
                is_mental = (
                    s_kind == "mental"
                    or (
                        section.lower() in ("mind", "head", "sensorium")
                        and any(
                            k in raw_sym.lower()
                            for k in ("fear", "restless", "anguish", "anxiety",
                                      "delirium", "rage", "sad", "despair",
                                      "melanchol", "suicid", "hallucin")
                        )
                    )
                )

                node_type = "Affective Symptom" if is_mental else "Physical Symptom"
                symptom_node_id = f"sym:{remedy_name}:{short_label.lower()}"

                if symptom_node_id not in node_ids:
                    graph["nodes"].append({
                        "id": symptom_node_id,
                        "name": short_label,
                        "type": node_type,
                        "section": section,
                        "quote": occ.get("evidence_quote", ""),
                        "confidence": occ.get("confidence", 0.95),
                        "grade": occ.get("grade", 1),
                        "source_ref": occ.get("source_ref", "")
                    })
                    node_ids.add(symptom_node_id)

                    rel_label = "HAS AFFECTIVE SYMPTOM" if is_mental else "TREATS"
                    l_key = (med_node_id, symptom_node_id, rel_label)
                    if l_key not in link_keys:
                        graph["links"].append({
                            "source": med_node_id,
                            "target": symptom_node_id,
                            "label": rel_label
                        })
                        link_keys.add(l_key)

                    if is_mental:
                        mental_symptom_ids.append(symptom_node_id)

                # ── Per-symptom modalities (if present) ───────────
                occ_mods = occ.get("modalities", [])
                for mod in occ_mods:
                    factor_raw = mod.get("factor_raw", "").strip()
                    if not factor_raw or "###" in factor_raw:
                        continue
                    direction = mod.get("direction", "worse")
                    factor_label = factor_raw.split(".")[0].split(";")[0].strip()
                    factor_label = re.sub(r"[\*_]", "", factor_label)
                    if len(factor_label) > 34:
                        factor_label = factor_label[:31] + "..."
                    prefix = "Worse" if direction == "worse" else "Better"
                    mod_name = f"{prefix} {factor_label}"
                    mod_node_id = f"mod:{remedy_name}:{mod_name.lower().replace(' ', '_')}"

                    if mod_node_id not in node_ids:
                        graph["nodes"].append({
                            "id": mod_node_id,
                            "name": mod_name,
                            "type": "Modality",
                            "details": f"{'Aggravation' if direction == 'worse' else 'Amelioration'}: {mod_name}"
                        })
                        node_ids.add(mod_node_id)

                    rel_label = "AGGRAVATED BY" if direction == "worse" else "AMELIORATED BY"
                    if symptom_node_id in node_ids:
                        l_key = (symptom_node_id, mod_node_id, rel_label)
                        if l_key not in link_keys:
                            graph["links"].append({
                                "source": symptom_node_id,
                                "target": mod_node_id,
                                "label": rel_label
                            })
                            link_keys.add(l_key)

        # ── Cognitive domain mapping ──────────────────────────────
        # For each mental symptom, check if it maps to known cognitive domains
        for node in list(graph["nodes"]):
            if node["type"] != "Affective Symptom":
                continue
            # Combine name + quote for richer keyword matching
            search_text = f"{node.get('name', '')} {node.get('quote', '')}"
            domains = _classify_cognitive_domains(search_text)
            for domain in domains:
                dom_node_id = f"dom:{remedy_name}:{domain.lower().replace(' ', '_').replace('/', '_')}"
                if dom_node_id not in node_ids:
                    graph["nodes"].append({
                        "id": dom_node_id,
                        "name": domain,
                        "type": "Cognitive Domain",
                        "details": f"Cognitive/psychological domain: {domain}"
                    })
                    node_ids.add(dom_node_id)

                l_key = (node["id"], dom_node_id, "MAPS TO")
                if l_key not in link_keys:
                    graph["links"].append({
                        "source": node["id"],
                        "target": dom_node_id,
                        "label": "MAPS TO"
                    })
                    link_keys.add(l_key)

        remedy_graphs[remedy_name] = graph

    # ── Write output ──────────────────────────────────────────────────
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON (for programmatic consumers)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(remedy_graphs, f, indent=2, ensure_ascii=False)

    # Write data.js (for the UI — sets window.GRAPH_DATA)
    data_js_path = output_file.parent / "data.js"
    with open(data_js_path, "w", encoding="utf-8") as f:
        f.write("window.GRAPH_DATA = ")
        json.dump(remedy_graphs, f, ensure_ascii=False)
        f.write(";\n")

    # Summary
    print(f"Generated {len(remedy_graphs)} schemas -> {output_file}")
    print(f"  Also wrote UI data -> {data_js_path}")
    for name, g in remedy_graphs.items():
        types = {}
        for n in g["nodes"]:
            types[n["type"]] = types.get(n["type"], 0) + 1
        print(f"  {name}: {len(g['nodes'])} nodes {dict(types)}, {len(g['links'])} edges")


if __name__ == "__main__":
    src = Path("data/extracted/run_pilot_01.jsonl")
    dst = Path("ui/graph_data.json")
    generate_graph_data(src, dst)

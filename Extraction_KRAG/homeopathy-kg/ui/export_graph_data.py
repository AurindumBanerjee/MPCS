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


def _clean_symptom_label(raw_sym: str) -> str:
    """Extract clean concise symptom label, avoiding truncation on abbreviations like St."""
    cleaned = re.sub(r"[\*_]", "", raw_sym).strip()
    parts = re.split(r"(?<!\bSt)(?<!\bDr)(?<!\bMr)(?<!\bNo)\.\s+", cleaned)
    first_clause = parts[0].split(";")[0].strip()
    if first_clause.lower() in ("st", "dr", "no") and len(parts) > 1:
        first_clause = f"{first_clause}. {parts[1].split(';')[0].strip()}"
    if len(first_clause) > 34:
        return first_clause[:31] + "..."
    return first_clause


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

                short_label = _clean_symptom_label(raw_sym)

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

    # ── Third pass: build unified multi-remedy combined graph ─────────
    # Load abbreviations for inter-remedy relationship resolution
    import yaml
    abbr_map = {}
    abbr_file = Path("config/remedy_abbreviations.yaml")
    if abbr_file.exists():
        try:
            with open(abbr_file, encoding="utf-8") as af:
                abbr_map = (yaml.safe_load(af) or {}).get("abbreviations", {})
        except Exception:
            pass

    combined_graph = {
        "id": "all_remedies_combined",
        "title": "Combined Knowledge Graph (All 20 Remedies)",
        "subtitle": "Unified multi-remedy symptom, modality, cognitive domain & relationship network",
        "nodes": [],
        "links": []
    }

    combined_nodes = {}
    combined_links = set()
    all_remedy_names = set(remedy_chunks.keys())

    # 1. Add all 20 Medicine nodes
    for rem in sorted(all_remedy_names):
        m_id = f"med:{rem}"
        combined_nodes[m_id] = {
            "id": m_id,
            "name": rem,
            "type": "Medicine",
            "details": f"Classical Homeopathic remedy: {rem}"
        }

    # 2. Add 6 global shared Cognitive Domain hubs
    for domain in COGNITIVE_DOMAIN_MAP.keys():
        d_id = f"dom:{domain.lower().replace(' ', '_').replace('/', '_')}"
        combined_nodes[d_id] = {
            "id": d_id,
            "name": domain,
            "type": "Cognitive Domain",
            "details": f"Psychological & cognitive domain: {domain}"
        }

    # 3. Process all chunks for combined network
    for rem, chunks in remedy_chunks.items():
        m_id = f"med:{rem}"

        for rec in chunks:
            section = rec.get("section", "General")

            # Inter-remedy comparative relationships (Medicine -> Medicine)
            for rel in rec.get("relationships", []):
                target_raw = rel.get("remedy_raw", "").strip()
                if not target_raw or target_raw.lower() in ("relationship", "relations"):
                    continue
                target_canonical = abbr_map.get(target_raw, target_raw)
                matched_rem = None
                for cand in all_remedy_names:
                    if cand.lower() == target_canonical.lower() or target_canonical.lower() in cand.lower():
                        matched_rem = cand
                        break
                if matched_rem and matched_rem != rem:
                    target_id = f"med:{matched_rem}"
                    rel_type = rel.get("type", "compare").upper().replace("_", " ")
                    l_key = (m_id, target_id, rel_type)
                    if l_key not in combined_links:
                        combined_graph["links"].append({
                            "source": m_id,
                            "target": target_id,
                            "label": rel_type
                        })
                        combined_links.add(l_key)

            # General modalities (shared hubs across remedies)
            for occ in rec.get("occurrences", []):
                kind = occ.get("kind", "symptom")
                if kind == "general_modality":
                    for mod in occ.get("modalities", []):
                        raw_factor = mod.get("factor_raw", "")
                        for pf in _parse_modality_factors(raw_factor):
                            mod_node_id = f"mod:{pf['label'].lower().replace(' ', '_')}"
                            if mod_node_id not in combined_nodes:
                                combined_nodes[mod_node_id] = {
                                    "id": mod_node_id,
                                    "name": pf["label"],
                                    "type": "Modality",
                                    "details": f"{'Aggravation' if pf['direction'] == 'worse' else 'Amelioration'}: {pf['label']}",
                                    "remedies": [rem]
                                }
                            else:
                                if rem not in combined_nodes[mod_node_id].get("remedies", []):
                                    combined_nodes[mod_node_id].setdefault("remedies", []).append(rem)

                            rel_label = "AGGRAVATED BY" if pf["direction"] == "worse" else "AMELIORATED BY"
                            l_key = (m_id, mod_node_id, rel_label)
                            if l_key not in combined_links:
                                combined_graph["links"].append({
                                    "source": m_id,
                                    "target": mod_node_id,
                                    "label": rel_label
                                })
                                combined_links.add(l_key)
                    continue

                # Symptoms
                raw_sym = occ.get("symptom_raw", "").strip()
                if not raw_sym or raw_sym.startswith("###"):
                    continue

                short_label = _clean_symptom_label(raw_sym)

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
                symptom_node_id = f"sym:{rem}:{short_label.lower()}"

                if symptom_node_id not in combined_nodes:
                    combined_nodes[symptom_node_id] = {
                        "id": symptom_node_id,
                        "name": short_label,
                        "type": node_type,
                        "section": section,
                        "quote": occ.get("evidence_quote", ""),
                        "confidence": occ.get("confidence", 0.95),
                        "grade": occ.get("grade", 1),
                        "source_ref": occ.get("source_ref", ""),
                        "remedy": rem
                    }

                    rel_label = "HAS AFFECTIVE SYMPTOM" if is_mental else "TREATS"
                    l_key = (m_id, symptom_node_id, rel_label)
                    if l_key not in combined_links:
                        combined_graph["links"].append({
                            "source": m_id,
                            "target": symptom_node_id,
                            "label": rel_label
                        })
                        combined_links.add(l_key)

                    # Link affective symptom -> shared cognitive domain
                    if is_mental:
                        search_text = f"{short_label} {occ.get('evidence_quote', '')}"
                        domains = _classify_cognitive_domains(search_text)
                        for domain in domains:
                            dom_node_id = f"dom:{domain.lower().replace(' ', '_').replace('/', '_')}"
                            l_key = (symptom_node_id, dom_node_id, "MAPS TO")
                            if l_key not in combined_links:
                                combined_graph["links"].append({
                                    "source": symptom_node_id,
                                    "target": dom_node_id,
                                    "label": "MAPS TO"
                                })
                                combined_links.add(l_key)

    combined_graph["nodes"] = list(combined_nodes.values())

    # Build final dictionary with Combined Graph first, followed by individual remedies
    final_graphs = {
        "Combined Knowledge Graph (All 20 Remedies)": combined_graph,
        **remedy_graphs
    }

    # ── Write output ──────────────────────────────────────────────────
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_graphs, f, indent=2, ensure_ascii=False)
        print(f"Generated {len(final_graphs)} schemas (including Combined Graph) -> {output_file}")
        print(f"  [Combined Graph]: {len(combined_graph['nodes'])} nodes, {len(combined_graph['links'])} edges")

    return final_graphs


def export_all_runs(ui_dir: Path = Path("ui")):
    """Export graphs for all 3 runs (hybrid, groq, baseline) into unified data.js."""
    all_runs = {}

    runs = [
        ("hybrid", Path("data/extracted/run_hybrid_01.jsonl"), ui_dir / "graph_data_hybrid.json"),
        ("groq", Path("data/extracted/run_groq_01.jsonl"), ui_dir / "graph_data_groq.json"),
        ("baseline", Path("data/extracted/run_manual_baseline.jsonl"), ui_dir / "graph_data.json"),
    ]

    for key, src_file, out_json in runs:
        if src_file.exists():
            print(f"\nProcessing run [{key}] from {src_file}...")
            all_runs[key] = generate_graph_data(src_file, out_json)

    # Write unified data.js
    data_js_path = ui_dir / "data.js"
    with open(data_js_path, "w", encoding="utf-8") as f:
        f.write("window.ALL_RUNS = ")
        json.dump(all_runs, f, ensure_ascii=False)
        f.write(";\n")
        # Default to hybrid if available, else first run
        default_key = "hybrid" if "hybrid" in all_runs else list(all_runs.keys())[0]
        f.write(f"window.GRAPH_DATA = window.ALL_RUNS['{default_key}'];\n")

    print(f"\nSuccessfully wrote unified multi-run bundle -> {data_js_path}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] != "--all":
        src = Path(sys.argv[1])
        dst = Path("ui/graph_data.json")
        print(f"Loading single extraction source: {src}")
        generate_graph_data(src, dst)
    else:
        export_all_runs(Path("ui"))

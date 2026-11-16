"""Comparison study: LocalKG vs Extraction_KRAG knowledge graphs.

Restricted to remedies present in both graphs and, within each remedy,
to sections populated in both. Writes metrics to
docs/kg_comparison/comparison_metrics.json and figures to docs/kg_comparison/.

Run from the repository root:
    python LocalKG/experiments/compare_localkg_vs_krag.py
"""
from __future__ import annotations

import collections
import json
import re
import subprocess
from pathlib import Path

from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parents[2]
KRAG = ROOT / "Extraction_KRAG" / "homeopathy-kg"
LKG_GRAPH = ROOT / "LocalKG" / "data" / "extracted" / "kg_full_materia_medica_cleaned.graph.json"
LKG_CHUNKS = ROOT / "LocalKG" / "data" / "chunks"
OUT = ROOT / "docs" / "kg_comparison"
RUNS = {"Rule-based": "run_manual_baseline", "Model-only": "run_groq_01", "Hybrid": "run_hybrid_01"}

# KRAG name -> LocalKG remedy id
ALIASES = {"Lachesis muta": "lachesis_muta", "Pulsatilla pratensis": "pulsatilla_nigricans"}
MENTAL_KINDS = {"mental"}
MATCH_T = 75.0  # same threshold as hkg.eval.metrics


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def similar(a: str, b: str) -> float:
    """Best of plain ratio and token-set ratio on normalised text."""
    a, b = norm(a), norm(b)
    return max(fuzz.ratio(a, b), fuzz.token_set_ratio(a, b) if min(len(a), len(b)) >= 6 else 0)


def greedy_match(xs: list[str], ys: list[str], t: float = MATCH_T) -> int:
    pairs = sorted(((similar(x, y), i, j) for i, x in enumerate(xs) for j, y in enumerate(ys)), reverse=True)
    ui, uj, n = set(), set(), 0
    for s, i, j in pairs:
        if s < t:
            break
        if i in ui or j in uj:
            continue
        ui.add(i); uj.add(j); n += 1
    return n


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------------------------------------------------------------- KRAG
def krag_run(run: str) -> dict:
    """remedy -> section -> list of symptom dicts; also modalities and relationships per remedy."""
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    mods = collections.Counter(); rels = collections.Counter(); header_artifacts = 0
    for c in load_jsonl(KRAG / "data" / "extracted" / f"{run}.jsonl"):
        r = c["remedy_name"]
        for o in c.get("occurrences", []):
            if o.get("kind") != "symptom":
                mods[r] += 1
                continue
            raw = o.get("symptom_raw", "")
            if raw.startswith("###"):
                header_artifacts += 1
                continue
            out[r][c["section"]].append({"text": raw, "kind": o.get("symptom_kind"), "grade": o.get("grade", 1),
                                         "verbatim": norm(raw) in norm(o.get("evidence_quote", "")),
                                         "n_mod": len(o.get("modalities") or [])})
            mods[r] += len(o.get("modalities") or [])
        rels[r] += len(c.get("relationships") or [])
    return {"sym": out, "mods": mods, "rels": rels, "header_artifacts": header_artifacts}


# ---------------------------------------------------------------- LocalKG
def localkg() -> dict:
    g = json.loads(LKG_GRAPH.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in g["nodes"]}
    deg = collections.Counter()
    rem_links = collections.defaultdict(list)
    for e in g["links"]:
        s, t = e["source"], e["target"]
        if nodes[s]["type"] == "Medicine" and nodes[t]["type"] != "Medicine":
            rem_links[s].append((e["label"], t))
            deg[t] += 1
    sym = collections.defaultdict(lambda: collections.defaultdict(list))
    mods = collections.Counter(); prov = collections.defaultdict(collections.Counter)
    for rid, lst in rem_links.items():
        for lab, nid in lst:
            n = nodes[nid]
            if "SYMPTOM" in lab:
                srcs = n.get("sources", [])
                kind = "mental" if n["type"] == "Affective Symptom" else "physical"
                origin = ("PubMed" if any("PMID" in s for s in srcs) and not any("source:" in s for s in srcs)
                          else "Hahnemann" if any("hahnemann" in s for s in srcs) and not any("boericke" in s for s in srcs)
                          else "Boericke" if any("boericke" in s for s in srcs) and not any("hahnemann" in s for s in srcs)
                          else "Mixed")
                prov[rid][origin] += 1
                sym[rid][n.get("section") or "None"].append({
                    "text": n["label"], "kind": kind, "grade": n.get("grade", 1), "origin": origin,
                    "shared": deg[nid] > 1, "words": len(n["label"].split())})
            elif lab in ("AGGRAVATED BY", "AMELIORATED BY"):
                mods[rid] += 1
    shared_nodes = sum(1 for nid, d in deg.items() if d > 1 and "Symptom" in nodes[nid]["type"])
    all_sym_nodes = sum(1 for nid in deg if "Symptom" in nodes[nid]["type"])
    chunks = collections.defaultdict(list)
    for f in LKG_CHUNKS.glob("chunks_*.jsonl"):
        for c in load_jsonl(f):
            chunks[slug(c["remedy_name"]).replace("lachesis_mutus", "lachesis_muta")].append(
                (c["source_id"].split(":")[1], c["section"], c["page"]))
    return {"sym": sym, "mods": mods, "prov": prov, "shared": shared_nodes, "sym_nodes": all_sym_nodes, "chunks": chunks}


BOERICKE_PDF = KRAG / "data" / "Materia_medica.pdf"


def audit_boericke_page(remedy: str, page: int) -> str:
    """Check which remedy headings are printed on the page LocalKG used (and the page before).

    Returns 'correct' if the remedy's heading appears, 'other' if only other remedies'
    headings appear, 'none' if no heading is printed (page inside a long entry).
    """
    txt = subprocess.run(["pdftotext", "-f", str(page - 1), "-l", str(page), str(BOERICKE_PDF), "-"],
                         capture_output=True, text=True).stdout
    heads = [h.strip(" .") for h in re.findall(r"^([A-Z][A-Z]{3,}(?: [A-Z]{3,})?)\.?\s*$", txt, re.M)]
    if not heads:
        return "none"
    first, *rest = remedy.split()
    keys = [first.upper()[:5]] + [w.upper()[:4] for w in rest if len(w) >= 4]
    words = [w for h in heads for w in h.split()]
    return "correct" if any(w.startswith(k) for w in words for k in keys) else "other"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    L = localkg()
    K = {k: krag_run(v) for k, v in RUNS.items()}
    gold = load_jsonl(KRAG / "data" / "gold" / "gold_annotations.jsonl")

    krag_remedies = sorted(K["Hybrid"]["sym"].keys())
    rmap = {r: "remedy:" + ALIASES.get(r, slug(r)) for r in krag_remedies}
    common = [r for r in krag_remedies if rmap[r] in L["sym"]]

    res = {"common_remedies": common, "krag_only": [r for r in krag_remedies if r not in common],
           "per_remedy": {}, "per_section": [], "gold": {}, "global": {}}

    # --- section coverage
    for r in common:
        lid = rmap[r]
        ks = {s for run in K.values() for s, v in run["sym"][r].items() if v}
        ls = {s for s, v in L["sym"][lid].items() if v}
        inter = sorted(ks & ls)
        res["per_remedy"][r] = {
            "krag_sections": sorted(ks), "localkg_sections": sorted(ls), "shared_sections": inter,
            "localkg_provenance": dict(L["prov"][lid]),
            "localkg_chunks": sorted(L["chunks"].get(lid.split(":")[1], [])),
            "modalities": {"LocalKG": L["mods"][lid], **{k: K[k]["mods"][r] for k in K}},
            "relationships": {k: K[k]["rels"][r] for k in K},
        }
        for s in inter:
            lsym = L["sym"][lid][s]
            row = {"remedy": r, "section": s, "LocalKG_n": len(lsym),
                   "LocalKG_mental_pct": round(100 * sum(x["kind"] == "mental" for x in lsym) / len(lsym), 1),
                   "LocalKG_origin": dict(collections.Counter(x["origin"] for x in lsym))}
            for k, run in K.items():
                ksym = run["sym"][r].get(s, [])
                m = greedy_match([x["text"] for x in ksym], [x["text"] for x in lsym]) if ksym else 0
                row[f"{k}_n"] = len(ksym)
                row[f"{k}_matched"] = m
                row[f"{k}_mental_pct"] = round(100 * sum(x["kind"] in MENTAL_KINDS for x in ksym) / len(ksym), 1) if ksym else None
            res["per_section"].append(row)

    # --- remedy attribution audit of LocalKG's Boericke chunks
    audit = {}
    for r in common:
        pages = sorted({pg for src, _, pg in L["chunks"].get(rmap[r].split(":")[1], []) if src.startswith("boericke")})
        audit[r] = {pg: audit_boericke_page(r, pg) for pg in pages}
        res["per_remedy"][r]["boericke_page_audit"] = audit[r]
    res["global"]["boericke_audit_counts"] = dict(collections.Counter(v for a in audit.values() for v in a.values()))

    # --- totals over shared sections
    tot = collections.Counter()
    for row in res["per_section"]:
        tot["LocalKG_n"] += row["LocalKG_n"]
        for k in K:
            tot[f"{k}_n"] += row[f"{k}_n"]; tot[f"{k}_matched"] += row[f"{k}_matched"]
    res["global"]["shared_section_totals"] = dict(tot)
    res["global"]["n_shared_pairs"] = len(res["per_section"])

    # --- whole-remedy symptom overlap (all sections), to separate section-label effects
    whole = {}
    for k, run in K.items():
        m = nk = nl = 0
        for r in common:
            ks = [x["text"] for v in run["sym"][r].values() for x in v]
            ls = [x["text"] for v in L["sym"][rmap[r]].values() for x in v if x["origin"] != "PubMed"]
            m += greedy_match(ks, ls); nk += len(ks); nl += len(ls)
        whole[k] = {"krag_n": nk, "localkg_n": nl, "matched": m}
    res["global"]["whole_remedy_overlap"] = whole

    # --- gold keynote recall, intersecting remedies only (same fuzz.ratio >= 75 rule as hkg)
    def recall(preds: list[str], gl: list[str]) -> int:
        hit = 0
        for gtext in gl:
            if any(fuzz.ratio(norm(p), norm(gtext)) >= MATCH_T for p in preds):
                hit += 1
        return hit
    gtot = collections.Counter()
    for g in gold:
        r = g["remedy_name"]
        if r not in common:
            continue
        gl = [s["symptom_raw"] for s in g["symptoms"]]
        gtot["gold"] += len(gl)
        preds_l = [x["text"] for v in L["sym"][rmap[r]].values() for x in v]
        gtot["LocalKG"] += recall(preds_l, gl)
        for k, run in K.items():
            gtot[k] += recall([x["text"] for v in run["sym"][r].values() for x in v], gl)
    res["gold"] = dict(gtot)

    # --- structural / quality properties
    lall = [x for r in common for v in L["sym"][rmap[r]].values() for x in v]
    res["global"]["localkg_quality"] = {
        "symptom_links": len(lall),
        "single_word_labels": sum(x["words"] == 1 for x in lall),
        "shared_symptom_nodes_pct_graph": round(100 * L["shared"] / L["sym_nodes"], 1),
        "links_to_shared_nodes": sum(x["shared"] for x in lall),
        "grade_dist": dict(collections.Counter(x["grade"] for x in lall)),
        "origin": dict(collections.Counter(x["origin"] for x in lall)),
    }
    for k, run in K.items():
        kall = [x for r in common for v in run["sym"][r].values() for x in v]
        res["global"][f"{k}_quality"] = {
            "symptoms": len(kall), "header_artifacts": run["header_artifacts"],
            "single_word_labels": sum(len(x["text"].split()) == 1 for x in kall),
            "verbatim_pct": round(100 * sum(x["verbatim"] for x in kall) / max(1, len(kall)), 1),
            "grade_dist": dict(collections.Counter(x["grade"] for x in kall)),
            "mental_pct": round(100 * sum(x["kind"] in MENTAL_KINDS for x in kall) / max(1, len(kall)), 1),
        }
    res["global"]["localkg_mental_pct"] = round(100 * sum(x["kind"] == "mental" for x in lall) / len(lall), 1)

    # --- Mind-section purity: share of "Mind" symptoms that name a body part or physical complaint
    body = re.compile(r"\b(pains?|colic|abdom\w*|stomach|nausea|vomit\w*|eructat\w*|flatul\w*|navel|ribs?|head\w*|eyes?|eyeball|ears?|"
                      r"tooth\w*|teeth|jaws?|throat|cough\w*|stools?|urine|chill\w*|fever|sweat\w*|perspir\w*|skin|itch\w*|swell\w*|"
                      r"pressure|ache|aching|cramps?|vertigo|dizz\w*|nose|mouth|tongue|chest|limbs?|arms?|legs?|satiety|fulness|"
                      r"windpipe|phlegm|expector\w*|nipple|epigastr\w*|hypogastr\w*)\b")
    mind_rem = [r for r in common if "Mind" in res["per_remedy"][r]["shared_sections"]]
    lm = [x["text"] for r in mind_rem for x in L["sym"][rmap[r]].get("Mind", [])]
    purity = {"remedies": len(mind_rem), "LocalKG": {"n": len(lm), "bodily": sum(bool(body.search(t.lower())) for t in lm)}}
    for k, run in K.items():
        km = [x["text"] for r in mind_rem for x in run["sym"][r].get("Mind", [])]
        purity[k] = {"n": len(km), "bodily": sum(bool(body.search(t.lower())) for t in km)}
    res["global"]["mind_section_purity"] = purity

    (OUT / "comparison_metrics.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("common_remedies", "krag_only", "gold")}, indent=1))
    print(json.dumps(res["global"], indent=1))
    make_figures(res)


# ---------------------------------------------------------------- figures
def make_figures(res: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.edgecolor": "#222222",
                         "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False})
    NAVY, OCHRE, GREY, LIGHT, RUST = "#2F4B6E", "#A8742A", "#6B6B6B", "#D9D9D9", "#8E3B2E"
    rems = res["common_remedies"]
    short = [r.split()[0] for r in rems]

    # 1. section coverage matrix
    secs = sorted({s for r in rems for s in res["per_remedy"][r]["krag_sections"] + res["per_remedy"][r]["localkg_sections"]
                   if s not in ("None",)}, key=lambda x: (x == "Clinical Literature (PubMed)", x))
    M = []
    for r in rems:
        pr = res["per_remedy"][r]; row = []
        for s in secs:
            k, l = s in pr["krag_sections"], s in pr["localkg_sections"]
            row.append(3 if k and l else 1 if k else 2 if l else 0)
        M.append(row)
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.imshow(M, cmap=ListedColormap(["#FFFFFF", "#C9D3DF", "#EBDCC4", NAVY]), vmin=0, vmax=3, aspect="auto")
    ax.set_xticks(range(len(secs))); ax.set_xticklabels([s.replace("Clinical Literature (PubMed)", "PubMed") for s in secs], rotation=45, ha="right")
    ax.set_yticks(range(len(rems))); ax.set_yticklabels(rems)
    ax.set_xticks([x - .5 for x in range(1, len(secs))], minor=True); ax.set_yticks([y - .5 for y in range(1, len(rems))], minor=True)
    ax.grid(which="minor", color="white", linewidth=1.2); ax.tick_params(which="minor", length=0)
    for sp in ax.spines.values(): sp.set_visible(False)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color="#C9D3DF", label="Extraction_KRAG only"), Patch(color="#EBDCC4", label="LocalKG only"),
                       Patch(color=NAVY, label="Both (compared)")], loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, frameon=False)
    fig.tight_layout(); fig.savefig(OUT / "fig_section_coverage.png", dpi=220); plt.close(fig)

    # 2. gold keynote recall
    g = res["gold"]; names = ["LocalKG", "Rule-based", "Model-only", "Hybrid"]
    vals = [100 * g[n] / g["gold"] for n in names]
    fig, ax = plt.subplots(figsize=(4.6, 2.8))
    bars = ax.bar(["LocalKG", "KRAG\nrule-based", "KRAG\nmodel-only", "KRAG\nhybrid"], vals, color=[OCHRE, NAVY, NAVY, NAVY], width=0.6)
    for b, n in zip(bars, names): ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, f"{g[n]}/{g['gold']}", ha="center", fontsize=8)
    ax.set_ylabel("Keynote recall (%)"); ax.set_ylim(0, 100); ax.yaxis.grid(True, color=LIGHT, linewidth=0.5); ax.set_axisbelow(True)
    fig.tight_layout(); fig.savefig(OUT / "fig_gold_recall.png", dpi=220); plt.close(fig)

    # 3. shared (remedy, section) pairs: sizes and matches
    rows = res["per_section"]
    lab = [f"{r['remedy'].split()[0]} / {r['section']}" for r in rows]
    import numpy as np
    x = np.arange(len(rows)); w = 0.38
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.bar(x - w / 2, [r["LocalKG_n"] for r in rows], w, color=OCHRE, label="LocalKG symptoms")
    ax.bar(x + w / 2, [r["Hybrid_n"] for r in rows], w, color=NAVY, label="KRAG hybrid symptoms")
    ax.scatter(x, [r["Hybrid_matched"] for r in rows], marker="D", s=14, color=RUST, zorder=3, label="Matched pairs")
    ax.set_xticks(x); ax.set_xticklabels(lab, rotation=55, ha="right", fontsize=7.5)
    ax.set_ylabel("Symptoms"); ax.yaxis.grid(True, color=LIGHT, linewidth=0.5); ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(OUT / "fig_shared_sections.png", dpi=220); plt.close(fig)

    # 4. LocalKG provenance per remedy
    cats = [("Boericke", NAVY), ("Hahnemann", OCHRE), ("Mixed", GREY), ("PubMed", LIGHT)]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    bottom = np.zeros(len(rems))
    for c, col in cats:
        v = np.array([res["per_remedy"][r]["localkg_provenance"].get(c, 0) for r in rems])
        ax.bar(short, v, bottom=bottom, color=col, label=c, width=0.65); bottom += v
    for i, r in enumerate(rems):
        a = res["per_remedy"][r]["boericke_page_audit"]
        bad = sum(v == "other" for v in a.values()); tot = len(a)
        if tot: ax.text(i, bottom[i] + 1, f"{bad}/{tot}", ha="center", fontsize=7, color=RUST)
    ax.set_ylabel("Symptom links in LocalKG"); ax.legend(frameon=False, ncol=4, fontsize=8, loc="upper right")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right"); ax.yaxis.grid(True, color=LIGHT, linewidth=0.5); ax.set_axisbelow(True)
    fig.tight_layout(); fig.savefig(OUT / "fig_localkg_provenance.png", dpi=220); plt.close(fig)


if __name__ == "__main__":
    main()

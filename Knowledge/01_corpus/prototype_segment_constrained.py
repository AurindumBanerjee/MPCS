import re, sys, json
from collections import Counter

SRC = sys.argv[1]
lines = open(SRC, encoding="utf-8", errors="ignore").read().split("\n")

REMEDIES = ["ACONITUM","AMBRA GRISEA","ARGENTUM","ARNICA MONTANA","ARSENICUM","ASARUM",
 "BELLADONNA","BRYONIA","CAMPHORA","CARBO VEGETABILIS","CHAMOMILLA","CONIUM","DROSERA",
 "FERRUM","HYOSCYAMUS","IGNATIA","IPECACUANHA"]

def indent(l): return len(l) - len(l.lstrip(" "))
NUM      = re.compile(r'^\s{0,14}(\d{1,4})\.\s+(?=\S)')
BARE_NUM = re.compile(r'^\s*\d{1,4}\.?\s*$')
JUNK     = re.compile(r'^\s*[^A-Za-z]*\s*$')
# running head: page no. and/or ALL-CAPS remedy name, in either order
HEAD     = re.compile(r'^\s*(\d{1,3}\s+)?[A-Z][A-Z .\-]{4,}\.?(\s+\d{1,3})?\s*$')
ENDPUNCT = re.compile(r'[.!?)\]]\s*$')

def chapter_bounds():
    pos = {}
    for i, l in enumerate(lines):
        s = l.strip().rstrip(".")
        s = re.sub(r'^\d{1,3}\s+', '', s)          # leading page number
        s = re.sub(r'\s+\d{1,3}$', '', s).strip()  # trailing page number
        if s in REMEDIES and s not in pos: pos[s] = i
    o = sorted(pos.items(), key=lambda kv: kv[1])
    return [(n, st, (o[k+1][1] if k+1 < len(o) else len(lines))) for k,(n,st) in enumerate(o)]

def rows_of(chap):
    out = []
    for l in chap:
        if JUNK.match(l) or HEAD.match(l) or BARE_NUM.match(l): continue
        m = NUM.match(l)
        if m: out.append({"n": int(m.group(1)), "t": l[m.end():].rstrip(), "i": indent(l)})
        else: out.append({"n": None, "t": l.strip(), "i": indent(l)})
    return out

def break_score(prev, cur, med):
    """How likely is `cur` the first line of a new entry?"""
    s = 0.0
    s += 2.0 * (cur["i"] - med) / 4.0          # indented more than body text
    if ENDPUNCT.search(prev["t"]): s += 2.0    # previous line closed a sentence
    if len(prev["t"]) < 55: s += 1.0           # previous line ran short (ragged right)
    if re.match(r'^[("(]?[A-Z]', cur["t"]): s += 1.0
    if re.match(r'^(and|or|of|the|in|with|to|as|that|which|from)\b', cur["t"]): s -= 2.5
    return s

def segment(rows):
    anchors = [k for k,r in enumerate(rows) if r["n"] is not None]
    if len(anchors) < 2: return [], 0, 0
    rows = rows[anchors[0]:]                   # drop the chapter's prose preamble
    anchors = [k for k,r in enumerate(rows) if r["n"] is not None]
    med = Counter(r["i"] for r in rows if r["n"] is None).most_common(1)[0][0]

    entries, ok, bad = [], 0, 0
    for a, b in zip(anchors, anchors[1:] + [len(rows)]):
        n1 = rows[a]["n"]
        n2 = rows[b]["n"] if b < len(rows) else None
        want = (n2 - n1) if (n2 is not None and 0 < n2 - n1 <= 40) else None
        block = rows[a:b]
        if want is None:                       # no usable checksum: fall back to indent
            cuts = [j for j in range(1, len(block)) if block[j]["i"] > med]
        else:
            ok += 1
            scored = sorted(range(1, len(block)),
                            key=lambda j: -break_score(block[j-1], block[j], med))
            cuts = sorted(scored[:want-1])     # exactly `want` entries, by construction
            if len(cuts) != want - 1: bad += 1; ok -= 1
        bounds = [0] + cuts + [len(block)]
        for k in range(len(bounds)-1):
            seg = block[bounds[k]:bounds[k+1]]
            if not seg: continue
            entries.append({
                "number": n1 + k,
                "number_source": "printed" if k == 0 else "constrained",
                "text": re.sub(r'\s+',' '," ".join(x["t"] for x in seg)).strip(),
            })
    return entries, ok, bad

print(f"{'remedy':20}{'entries':>9}{'blocks':>8}{'solved':>8}{'max no.':>9}{'highest printed':>17}")
allent = {}
for name, st, en in chapter_bounds():
    ents, ok, bad = segment(rows_of(lines[st:en]))
    if not ents: print(f"{name:20}{'— no anchors':>25}"); continue
    allent[name] = ents
    mx = max(e["number"] for e in ents)
    hp = max((e["number"] for e in ents if e["number_source"]=="printed"), default=0)
    print(f"{name:20}{len(ents):>9}{ok+bad:>8}{ok:>8}{mx:>9}{hp:>17}")

json.dump(allent, open(f"{sys.argv[2]}", "w"), indent=1)
print(f"\nwrote {sum(len(v) for v in allent.values())} entries across {len(allent)} chapters")

# --- spot-check: Arnica 313-331, against the printed page 102 ---
import json as _j
e = _j.load(open(sys.argv[2]))["ARNICA MONTANA"]
print("\n--- ARNICA MONTANA 313-331 (compare to printed p.102) ---")
for x in e:
    if 313 <= x["number"] <= 331:
        tag = "P" if x["number_source"]=="printed" else " "
        print(f'{tag} {x["number"]:>4}  {x["text"][:96]}')

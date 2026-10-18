import re, sys, statistics, json
from collections import Counter

SRC = sys.argv[1]
lines = open(SRC, encoding="utf-8", errors="ignore").read().split("\n")

REMEDIES = ["ACONITUM","AMBRA GRISEA","ARGENTUM","ARNICA MONTANA","ARSENICUM","ASARUM",
 "BELLADONNA","BRYONIA","CAMPHORA","CARBO VEGETABILIS","CHAMOMILLA","CONIUM","DROSERA",
 "FERRUM","HYOSCYAMUS","IGNATIA","IPECACUANHA"]

def indent(l): return len(l) - len(l.lstrip(" "))

NUM = re.compile(r'^\s{0,12}(\d{1,4})\.\s+(?=\S)')
RUNHEAD = re.compile(r'^\s*\d{1,3}\s{2,}[A-Z][A-Z .]{4,}\.?\s*$|^\s*[A-Z][A-Z .]{4,}\.?\s{2,}\d{1,3}\s*$')
BARE_CAPS = re.compile(r'^\s*[A-Z][A-Z .\-]{4,}\.?\s*$')
BARE_NUM  = re.compile(r'^\s*\d{1,4}\.?\s*$')
JUNK = re.compile(r'^\s*[^A-Za-z]*\s*$')

def chapter_bounds():
    pos = {}
    for i, l in enumerate(lines):
        s = l.strip().rstrip(".")
        if s in REMEDIES and s not in pos: pos[s] = i
    o = sorted(pos.items(), key=lambda kv: kv[1])
    return [(n, st, (o[k+1][1] if k+1 < len(o) else len(lines))) for k,(n,st) in enumerate(o)]

def segment(chap_lines):
    # keep only content lines, remembering printed numbers
    rows = []
    for l in chap_lines:
        if JUNK.match(l) or RUNHEAD.match(l) or BARE_CAPS.match(l): continue
        m = NUM.match(l)
        if m:
            rows.append((int(m.group(1)), l[m.end():], indent(l), True)); continue
        if BARE_NUM.match(l): continue
        rows.append((None, l.strip(), indent(l), False))

    # adaptive indent split: two clusters of indents among non-numbered lines
    ind = [r[2] for r in rows if not r[3]]
    if not ind: return []
    c = Counter(ind)
    common = sorted(c.items(), key=lambda kv: -kv[1])[:6]
    vals = sorted(v for v,_ in common)
    split = statistics.median(ind)

    entries = []
    for num, text, ii, printed in rows:
        new = printed or ii > split
        if new or not entries:
            entries.append({"num": num, "printed": printed, "parts": [text]})
        else:
            entries[-1]["parts"].append(text)
    for e in entries:
        e["text"] = re.sub(r'\s+', ' ', " ".join(e["parts"])).strip()
        del e["parts"]
    return entries

def validate(entries):
    """Printed every-5th numbers are a checksum: count between anchors must be 5."""
    anchors = [(i, e["num"]) for i, e in enumerate(entries) if e["printed"]]
    ok = bad = 0; errs = []
    for (i1,n1),(i2,n2) in zip(anchors, anchors[1:]):
        expected = n2 - n1
        actual = i2 - i1
        if expected == actual: ok += 1
        else:
            bad += 1
            if len(errs) < 4: errs.append((n1, n2, expected, actual))
    return ok, bad, errs, len(anchors)

print(f"{'remedy':20}{'entries':>9}{'anchors':>9}{'gaps ok':>9}{'bad':>6}{'agree%':>8}   sample errors")
tot_ok = tot_bad = 0
for name, st, en in chapter_bounds():
    ents = segment(lines[st:en])
    ok, bad, errs, na = validate(ents)
    tot_ok += ok; tot_bad += bad
    pct = 100*ok/max(1,ok+bad)
    es = "  ".join(f"{a}->{b}:exp{e}got{g}" for a,b,e,g in errs)
    print(f"{name:20}{len(ents):>9}{na:>9}{ok:>9}{bad:>6}{pct:>7.1f}%   {es}")
print(f"\nTOTAL gaps: {tot_ok} correct, {tot_bad} wrong  ->  {100*tot_ok/max(1,tot_ok+tot_bad):.1f}% agreement")

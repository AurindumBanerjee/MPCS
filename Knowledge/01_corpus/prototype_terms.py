import json, re, sys
from collections import Counter
E = json.load(open(f'{sys.argv[1]}'))["ARNICA MONTANA"]

STOP = set("""a an the of in on at to for with as from by and or but if is are was were be been
his her him he she it its they them their this that these those which who whom what when where
had has have not no nor so than then there here too very can will would could should may might
one two three four five after before during between upon into out up down over under again all
both each few more most other some such only own same s t just don now i me my we us you your""".split())

def norm(t):
    t = re.sub(r'\[[^\]]*\]', ' ', t)                  # prover attributions
    t = re.sub(r'\(aft\.?[^)]*\)', ' ', t, flags=re.I) # onset parentheses
    t = re.sub(r'(\w)-\s+(\w)', r'\1\2', t)            # rejoin hyphenation
    return t.lower()

def toks(t): return [w for w in re.findall(r"[a-z]+", norm(t)) if len(w) > 2 and w not in STOP]

uni, bi, tri = Counter(), Counter(), Counter()
onset, modal, paren = 0, Counter(), 0
MODAL = re.compile(r'\b(morning|evening|night|midday|afternoon|lying|rising|walking|sitting|'
                   r'standing|stooping|motion|rest|touch|pressure|open air|warmth|cold)\b', re.I)
for e in E:
    ws = toks(e["text"])
    uni.update(ws)
    bi.update(" ".join(ws[i:i+2]) for i in range(len(ws)-1))
    tri.update(" ".join(ws[i:i+3]) for i in range(len(ws)-2))
    if re.search(r'\baft\.?\s*\d', e["text"], re.I): onset += 1
    modal.update(m.group(1).lower() for m in MODAL.finditer(e["text"]))
    if e["text"].strip().startswith("("): paren += 1

print(f"{len(E)} Arnica entries · {sum(uni.values())} content tokens · {len(uni)} distinct\n")
print("top unigrams :", ", ".join(f"{w}({c})" for w,c in uni.most_common(14)))
print("top bigrams  :", ", ".join(f"{w}({c})" for w,c in bi.most_common(9)))
print("top trigrams :", ", ".join(f"{w}({c})" for w,c in tri.most_common(6)))
print(f"\nstructured fields recovered")
print(f"  entries with an onset '(aft. N h.)' : {onset} ({100*onset/len(E):.0f}%)")
print(f"  entries bracketed by Hahnemann       : {paren} ({100*paren/len(E):.0f}%)")
print(f"  modality words                       :", ", ".join(f"{w}({c})" for w,c in modal.most_common(10)))
hapax = sum(1 for w,c in uni.items() if c == 1)
print(f"\nvocabulary shape · hapax (seen once): {hapax} of {len(uni)} = {100*hapax/len(uni):.0f}%"
      f"  ← candidates for OCR junk + genuinely rare clinical terms")
print("sample hapax:", ", ".join(list(w for w,c in uni.items() if c==1)[:16]))

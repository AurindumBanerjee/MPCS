# 01_corpus — extraction notes

Prototypes, not the final extractor. Run against a `pdftotext -layout` dump of
`BTP/Meet5/Materia Medica Samuel Hahnemann.pdf` (vol. 2, 742 pp.).

    pdftotext -layout "Materia Medica Samuel Hahnemann.pdf" mmp2_layout.txt
    python prototype_segment_constrained.py mmp2_layout.txt entries.json
    python prototype_terms.py entries.json

## Two findings that shape the design

**1. `-layout` is required, not optional.** Plain `pdftotext` discards the
indentation, and the indentation is the only thing marking where one symptom
entry ends and the next begins. The edition sets each entry with its first
line indented ~9 columns and continuation lines outdented to ~5.

**2. The printed numbers are a constraint, not just a checksum.** Entry
numbers are printed only every fifth entry. Segmenting on indent alone and
*checking* against those markers gives **45%** agreement (see
`prototype_segment_indent.py`). Using them as a constraint instead — between
marker *n* and marker *n+5* there are exactly five entries, so pick the four
best break points — removes the counting error by construction and leaves only
the question of break *placement*.

Spot-checked against printed page 102: entries 315–331 segment **17/17**
correctly.

## Per-chapter state

`entries` ≈ `max number` means the chapter segmented cleanly. `entries` much
greater than `max number` means the chapter contains long non-list prose
(essays, clinical commentary, footnote blocks) being chopped into false
entries.

| Remedy | Entries | Max no. | State |
|---|---|---|---|
| Arnica montana | 636 | 640 | clean |
| Carbo vegetabilis | 716 | 720 | clean |
| Ignatia | 804 | 798 | clean |
| Aconitum | 557 | 548 | clean |
| Ipecacuanha | 240 | 235 | clean |
| Argentum | 241 | 225 | clean |
| Hyoscyamus | 627 | 585 | ~7% over |
| Arsenicum | 1214 | 1086 | ~12% over |
| Belladonna | 1657 | 1456 | ~14% over |
| Bryonia | 1057 | 795 | prose bleed |
| Drosera | 855 | 415 | prose bleed |
| Asarum | 698 | 370 | prose bleed |
| Conium | 1096 | 442 | prose bleed |
| Ambra grisea | 839 | 544 | prose bleed |
| Chamomilla | 3244 | 1959 | prose bleed |
| Ferrum | 1095 | 311 | prose bleed |
| Camphora | 1277 | 368 | mostly prose chapter |

## Known defects, in priority order

1. **Prose bleed.** Blocks with no usable marker pair fall back to the indent
   heuristic and over-segment. Fix: emit nothing past the chapter's highest
   printed number, and drop runs longer than ~12 lines that contain no marker.
2. **Footnote bleed.** Arnica 313–314 are footnote fragments
   ("Curative effect. See note to S. 20,"). Footnotes sit at a distinct
   indent and font size; `pdftotext -bbox` exposes the size and would separate
   them properly.
3. **Hyphenation.** "pos- terior" is rejoined in `prototype_terms.py` but not
   in the segmenter, so stored text keeps the break.
4. **Prover attributions.** `[Kr.]` OCRs as `[Zr.]`, `[Z%.]`, `\_Kr.~]`. The
   set of provers is small and closed, so fuzzy-match each bracket against a
   known list rather than parsing it. The token `hbg` currently leaks into the
   term counts from `[Hbg.]`.
5. **OCR word errors.** "from the month" for "mouth". Needs a spell pass
   against a medical + affect lexicon, with every correction logged.

## Term layer — Arnica, measured

636 entries · 4,195 content tokens · 1,339 distinct types.

- **Mean 6.6 content words per entry.** These are very short documents.
- **53% of the vocabulary is hapax** (714 of 1,339) — seen exactly once. Part
  OCR junk, part genuinely rare clinical terms.
- Top unigrams are the sensation vocabulary: pain 111, aching 45, shooting 42,
  stitches 39, tearing 28, heat 29.
- Multiword terms matter: "scrobiculus cordis" 11, "obtuse stitches" 10,
  "open air" 9 — so phrase extraction, not just unigrams.
- Modality words extract cleanly: morning 21, walking 21, evening 18,
  pressure 16, rest 9, open air 9, lying 9, cold 9.
- 23% of entries carry an `(aft. N h.)` onset; 3% are bracketed by Hahnemann
  as less certain.

**Design consequence.** Six-word documents with a half-hapax vocabulary are
the worst case for pure lexical matching — two entries describing the same
thing often share no term at all. This is the argument for the dense channel,
and the argument for MeSH: a controlled vocabulary collapses those 714 one-off
surface forms onto shared descriptors.

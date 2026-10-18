# Graph schema

Every edge records where it came from. Attested edges are read off the book;
linked edges come from a matcher and carry a confidence; derived edges are
inferred by a rule and name the edges they were inferred from. Nothing in the
graph is allowed to be of unknown origin.

| Provenance | Meaning | Trust |
|---|---|---|
| `attested` | Read directly from the text's own structure. | Wrong only if the parser is wrong. |
| `linked` | Produced by a matcher against an external vocabulary. | Carries `confidence` and `surface`; auditable. |
| `derived` | Inferred by a stated rule from other edges. | Carries `rule` and `from`; never presented as attested. |

---

## Nodes

### `remedy`
```json
{
  "id": "remedy:arnica_montana",
  "type": "remedy",
  "name": "Arnica montana",
  "volume": 2,
  "chapter_lines": [8439, 10832],
  "symptom_count": 712
}
```

### `symptom`
One numbered entry. The atomic unit of the corpus.
```json
{
  "id": "symptom:arn-320",
  "type": "symptom",
  "remedy": "remedy:arnica_montana",
  "number": 320,
  "number_source": "printed",
  "text": "Dry tussiculation as from a tickle in the lower part of the trachea, every morning after rising.",
  "text_raw": "Dry tussiculation as from a tickle in the lower part\nof the trachea, every morning after rising. [Zr.]",
  "region_path": "respiration/trachea",
  "onset_hours": null,
  "modality": ["morning", "after rising"],
  "prover": "Kr.",
  "affect": { "valence": 0.31, "arousal": 0.44, "dominance": 0.29, "coverage": 0.55 },
  "terms": ["dry", "tussiculation", "tickle", "trachea", "morning", "rising"],
  "parenthesised": false
}
```

- `number_source` is `printed` or `interpolated`. Markers appear only every
  fifth entry, so most numbers are interpolated and the field makes that
  visible rather than silently assumed.
- `text_raw` is kept so cleaning can be revisited without re-parsing the PDF.
- `affect.coverage` is the share of content words found in the VAD lexicon. A
  low coverage means the affect vector is weakly supported and should be
  discounted — the same role per-modality confidence plays in the engine.
- `parenthesised`: Hahnemann bracketed symptoms he regarded as less certain.
  That is his own confidence annotation and it should survive into the graph.

### `region`
A node of the head-to-toe schema, which is a hierarchy.
```json
{ "id": "region:respiration/trachea", "type": "region",
  "label": "trachea", "parent": "region:respiration", "depth": 2 }
```
Top level, in the book's order: `mind`, `head`, `eyes`, `ears`, `nose`,
`face`, `mouth`, `throat`, `stomach`, `abdomen`, `stool`, `urine`, `genitals`,
`respiration`, `chest`, `back`, `extremities`, `sleep`, `fever`, `skin`.

### `mesh`
A MeSH descriptor, keeping MeSH's own tree numbers so depth and ancestry come
for free.
```json
{ "id": "mesh:D003371", "type": "mesh", "label": "Cough",
  "tree_numbers": ["C08.618.248"], "depth": 3 }
```

### `prover`
```json
{ "id": "prover:Kr", "type": "prover", "initials": "Kr.", "entries": 97 }
```
Worth having: a symptom observed by one prover once is weaker evidence than
one reported by several, and that is measurable from the graph.

### `paper`
Supplementary literature, for the two chosen remedies only.
```json
{ "id": "paper:pmid-12345678", "type": "paper",
  "title": "...", "year": 2019, "pmid": "12345678",
  "mesh_terms": ["D003371", "D001158"], "source": "pubmed" }
```
PubMed records come pre-indexed with MeSH descriptors by human indexers, so a
paper's `discusses` edges are attested rather than linked.

---

## Edges

### Tier 1 — attested

| Edge | From → To | How |
|---|---|---|
| `produces` | `remedy → symptom` | The entry sits in that remedy's chapter. |
| `in_region` | `symptom → region` | Position in the head-to-toe ordering. |
| `observed_by` | `symptom → prover` | The `[Kr.]`-style attribution. |
| `subregion_of` | `region → region` | The schema's own nesting. |
| `broader` | `mesh → mesh` | MeSH tree numbers. |
| `discusses` | `paper → mesh` | The record's own MeSH indexing. |
| `about_remedy` | `paper → remedy` | Chosen when the paper was collected. |

```json
{ "from": "remedy:arnica_montana", "to": "symptom:arn-320",
  "type": "produces", "provenance": "attested" }
```

### Tier 2 — linked

| Edge | From → To | How | Carries |
|---|---|---|---|
| `about` | `symptom → mesh` | Matcher over MeSH terms and synonyms | `confidence`, `surface`, `method` |
| `precedes` | `symptom → symptom` | Cause clause in the entry text | `pattern`, `confidence` |
| `similar_to` | `symptom → symptom` | Cosine over entry embeddings, top-k | `score` |

```json
{ "from": "symptom:arn-320", "to": "mesh:D003371",
  "type": "about", "provenance": "linked",
  "confidence": 0.82, "surface": "tussiculation", "method": "embed+synonym" }
```

```json
{ "from": "symptom:arn-325a", "to": "symptom:arn-325b",
  "type": "precedes", "provenance": "linked",
  "pattern": "after X, Y", "confidence": 0.7,
  "note": "\"After weeping and whining, cough, in children.\"" }
```

`similar_to` is the graph's record of what the dense index found, so the
visualisation and the retrieval agree with each other. It is regenerated from
the index, never hand-edited.

### Tier 3 — derived

| Edge | From → To | Rule |
|---|---|---|
| `indicated_for` | `remedy → mesh` | Similia: a remedy that produces symptoms about descriptor *D* is indicated for *D*. **Not a claim the text makes.** |
| `co_produced_with` | `symptom → symptom` | Both produced by the same remedy, within *n* entries of each other. |
| `shares_region` | `remedy → remedy` | Both produce symptoms in the same region, weighted by count. |

```json
{ "from": "remedy:arnica_montana", "to": "mesh:D003371",
  "type": "indicated_for", "provenance": "derived",
  "rule": "similia:produces->about",
  "from_edges": ["symptom:arn-320", "symptom:arn-321", "symptom:arn-329"],
  "support": 3, "mean_confidence": 0.79 }
```

**The one rule to keep.** `indicated_for` must never be serialised,
visualised, or reported without its `provenance: derived` and its `rule`. The
*Materia Medica* records what a substance produced in healthy provers. The
therapeutic reading is a separate inference, and flattening the two would put
a clinical claim in the graph that the source never made. Keeping them apart
also makes the graph honest about something genuinely interesting: it can show
exactly which recorded symptoms a therapeutic suggestion rests on, which is
the same explanation contract the engine already holds itself to.

---

## Traversal, as the retrieval path

A free-text complaint enters through the index and leaves through the graph.

```
query text
  │
  ├─ BM25 over postings          ──┐
  └─ dense top-k over symptoms   ──┴─→ rank fusion → seed symptom nodes
                                                        │
                        seed(s) = sim(q,s) · (1 + salience_gain · arousal(s))
                                                        │
                           spread over (produces, about, in_region,
                                        precedes, similar_to), decay per hop
                                                        │
                      prune below prune_threshold × strongest seed,
                                        keep ≤ max_active
                                                        │
                    ┌───────────────────┬───────────────┴──────────┐
                 DIRECT             SUBGRAPH                  UNGROUNDED
         one remedy clearly      the activated structure    nothing activated;
         ahead, with the         returned for inspection    say so, recommend
         symptoms behind it                                 nothing
```

`seed`, `spread`, the pruning parameters and the three-way routing are
`08_tide/tide_layer.py` as written. The change is the edge vocabulary and the
source of `arousal`, which now comes from the VAD lexicon rather than derived
percept channels.

## Serialisation

`03_graph/graph.jsonl` — one JSON object per line, nodes first then edges,
each tagged with `type` and `provenance`. Line-oriented so that stages can
append and so a `git diff` stays readable. A `networkx` loader and a
`graph.graphml` export for external viewers are built from it, not instead of
it.

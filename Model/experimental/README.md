# Model/experimental

Active development trunk. New mechanisms are built here first.

Each folder carries its own `instructions.txt` with setup, run commands, a
walkthrough and troubleshooting.

```
core/                  The engine. No UI. Everything else imports this.
dashboard_web/         Dashboard A — local web app, no dependencies
dashboard_streamlit/   Dashboard B — Streamlit
dashboard_plotly/      Dashboard C — Dash / Plotly
dashboard_tk/          Dashboard D — Tkinter desktop app, no dependencies
baseline_z/            The previous two-modality version, unchanged
```

## Quick start

No installation required — pick a browser or a desktop window:

```
python dashboard_web/MPCS_Test.py     # opens http://127.0.0.1:8756/
python dashboard_tk/mpcs_dash_tk.py   # native window, instant start
```

Both open with the 70-experience preset bank loaded. The other two dashboards
show the same thing through different technology — see their
`instructions.txt`.

Verify the engine without any UI:

```
python core/engine_smoke.py
```

## MPCS v2 — what changed

Cognition is separate from presentation: one engine in `core/`, three
interchangeable front-ends. Behaviour is identical whichever you run.

**Four modalities.** Vision and audio are joined by **touch** (contact,
texture, thermal, intensity) and **smell** (odor type, intensity,
pleasantness), behind a generic `MODALITIES` registry rather than hard-coded
slots. Any modality may be switched off; the system reasons from what remains,
and reflexes on a missing channel cannot fire.

**Reflexes for the new channels.** Hot surfaces and impacts trigger
`withdraw`, a fifth action; smoke and strong chemical odours trigger `alert`.
Touch pain outranks the older audio and vision rules.

**Per-modality confidence.** Z-numbers previously all carried `conf=1.0`,
making confidence-weighted similarity arithmetically identical to plain
feature counting. Each channel now has its own reliability (smell lowest at
0.70), so the Z layer affects retrieval.

**Reward comes from memory, not `random.uniform(0, 1)`.** The reward for an
action is the similarity- and decay-weighted **mean of relevant past rewards,
plus sampled variance**. With no relevant memory it falls back to a weak
neutral prior and says so. On the reflex path the same logic applies, with
reflex-origin memories weighted more heavily.

**Acting against memory's advice costs something.** When similar memories
exist but the action taken is not the one they recommend, reward is scaled
down by how much better the recommendation looked and how well-evidenced it
was. A marginally worse choice barely stings; overriding a strong,
well-supported recommendation does.

**`action_threshold` finally does something.** It was written by the learning
update but read by no decision code, leaving the reward loop inert. It now
gates commitment: when even the best option scores below it, the system falls
back to `observe` and reports `HESITATE`.

**Explanation payload.** Every step returns the memories that contributed and
each one's arithmetic (similarity × decay × boost = weight). The dashboards
draw this as a percept-centred node-link graph, so a decision's provenance is
visible rather than inferred.

**A larger preset bank.** 70 experiences (50 novel contexts + 20
near-repetitions), every one carrying all four modalities, covering all five
actions. It deliberately mixes coherent cases (smoke + hot + alarm) with
conflicting ones (pleasant smell, sharp texture) so retrieved memories
genuinely disagree, and includes low-reward records of actions that
contradicted advice.

## Dashboard comparison

| | A: web | B: Streamlit | C: Dash/Plotly | D: Tk |
|---|---|---|---|---|
| Install | nothing | `streamlit pandas` | `dash plotly` | nothing |
| Launch | `python MPCS_Test.py` | `streamlit run …` | `python …` | `python …` |
| Surface | browser | browser | browser | desktop window |
| Startup | server + browser | server + browser | server, no browser | instant |
| Graph | inline SVG | inline SVG | Plotly traces | Tk Canvas |
| Hover detail | title tooltips | title tooltips | full hover cards | none |

All three expose the same controls: sidebar parameters, memory source
(scratch / preset / import), export, per-modality toggles, manual reward and
expert teaching.

# MPCS
Malleable Perceptual-Cognitive System

MPCS is a compact cognitive-architecture simulation with a full loop:
perception -> reflex or deliberation -> action -> reward -> memory -> state update.

## Repository layout

```
Model/
  reference/     Frozen baselines: mpcs.py, BloomMPCS.py, their preset launchers, MPCS_Test.py
  experimental/  Active trunk — MPCS v2, one folder per implementation:
      core/                  the engine (four modalities, memory-derived reward)
      dashboard_web/         local web dashboard, no dependencies
      dashboard_tk/          Tkinter desktop dashboard, no dependencies
      dashboard_streamlit/   Streamlit dashboard
      dashboard_plotly/      Dash / Plotly dashboard
      baseline_z/            MPCS_Z.py, the previous two-modality version
  data/          PresetMemory.txt, PresetMemory_v2.txt and other data artifacts
docs/            MPCS_Report.html, CurrentStatus.md, Checklist.md
Reading/         Background PDFs
```

Each `Model/` subfolder has a README; every `experimental/` implementation
folder also carries an `instructions.txt` with setup, run commands, a
walkthrough and troubleshooting.

## Run

Current version — a dashboard showing which memories produced each decision.
Both of these need nothing installed:

- `python Model/experimental/dashboard_web/MPCS_Test.py` (browser)
- `python Model/experimental/dashboard_tk/mpcs_dash_tk.py` (desktop window)

The same system through other front-ends (`pip install -r requirements.txt`,
or `pip install streamlit pandas dash plotly`):

- `streamlit run Model/experimental/dashboard_streamlit/mpcs_dash_streamlit.py`
- `python Model/experimental/dashboard_plotly/mpcs_dash_plotly.py`

Verify the engine with no UI involved:

- `python Model/experimental/core/engine_smoke.py`

Earlier versions, kept for comparison. Install optional BloomMPCS dependency:
- `pip install bloom-filter`

- Previous Z-number Tk UI (two modalities, expert teaching):
	- `python Model/experimental/baseline_z/MPCS_Z.py`
- Standard reference UI:
	- `python Model/reference/mpcs.py`
- Preset-memory reference UI (starts with ready-made experience):
	- `python Model/reference/mpcs_preset_memory.py`
	- `python Model/reference/mpcs_preset_memory.py --profile cautious`
	- `python Model/reference/mpcs_preset_memory.py --profile exploratory --seed 99`
- Bloom-filter reference UI:
	- `python Model/reference/BloomMPCS.py`
- Bloom-filter preset-memory reference UI:
	- `python Model/reference/BloomMPCS_preset_memory.py --profile cautious`

Note: the preset launchers import their sibling modules, so run them from
within `Model/reference/` (or with that directory on `PYTHONPATH`).

In the UI, use `Run Step` to execute an action, then enter a reward and click `Apply Reward` to attach that reward to the most recently executed action.

## Current Architecture

MPCS v2 (`Model/experimental/`) separates cognition from presentation: one
engine, three interchangeable dashboards.

- Multimodal afferent binding across **vision, audio, touch and smell**, with
  any channel omissible at run time
- Per-modality confidence weighting matched retrieval (Z-numbers)
- Reflexive fast-path rules including touch pain and smoke, driving a fifth
  action, `withdraw`
- Deliberative scoring over candidate actions, with hesitation when the best
  option falls below the learned threshold
- Experience memory with top-k retrieval and time decay
- **Reward derived from relevant past memory** — weighted mean plus sampled
  variance — with a penalty for acting against what memory recommends
- Internal state adaptation from reward, now actually consulted by decisions
- Per-step explanation of which memories produced the decision, drawn as a
  contribution graph

Earlier versions (`Model/reference/`, `Model/experimental/baseline_z/`) keep
the two-modality Tk implementations for comparison.

## Research-Aligned Improvement Roadmap

This roadmap is organized by impact-to-effort ratio, with explicit ties to
cognitive behavior realism.

### 1. Immediate High-Impact Improvements

These produce the largest behavioral gains with minimal complexity increase.

1. Similarity-weighted memory influence
- Why: all past memories should not contribute equally.
- Effect: decisions are shaped by truly relevant precedents.
- Status: implemented.

2. Exploration vs exploitation
- Why: deterministic argmax is unrealistically rigid.
- Effect: epsilon-style stochastic behavior with controlled risk.
- Status: implemented.

3. Explicit novelty detection
- Why: novelty is a key driver for curiosity and learning intensity.
- Effect: computes familiarity gap versus stored experience.
- Status: implemented.

4. Time decay over memory
- Why: old events should gradually lose influence.
- Effect: natural forgetting and adaptation to non-stationary contexts.
- Status: implemented.

### 2. Cognitive-Depth Improvements

5. Emotion / valence layer
- Add confidence/stress signals from running reward trends.
- Use these as secondary decision biases.

6. Goal / intent layer
- Add explicit operating modes such as maximize_reward vs explore.
- Let intent modulate action policy and novelty weighting.

7. Attention filtering
- Prioritize salient channels (for example alarms over low-value visual detail).
- Reduce noisy input burden before deliberation.

### 3. Reasoning Improvements

8. Multi-step counterfactual planning
- Replace one-step expected reward with short-horizon rollout.
- Introduce gamma-discounted future utility estimates.

9. Contradiction detection
- Detect mismatch between reflex recommendation and memory-based risk.
- Trigger deliberate override when conflict is high.

10. Uncertainty-aware policy
- Track reward variance per action in similar contexts.
- High uncertainty increases exploration pressure.

### 4. Structural Improvements

11. Indexed memory
- Move beyond flat list scans to indexed retrieval.
- Enables faster scaling and richer retrieval heuristics.

12. Episodic memory sequences
- Store trajectories, not only single transitions.
- Supports temporal pattern recall and sequence reasoning.

13. Decision traceability
- Log chosen action, alternatives, scores, and policy mode.
- Status: partially implemented (expanded internal decision logging).

### 5. UI and Experimentation Improvements

14. Manual reward slider
- Replace text entry with a bounded slider for cleaner experiments.

15. Visualization panel
- Add action-score bars, similarity heat, and memory influence display.

16. Seed control
- Expose deterministic run seed in UI for reproducibility studies.

17. Step replay
- Persist per-step state and allow timeline replay.

### 6. Experimental Extensions

18. Same input, multiple seeds
- Run fixed stimuli over N seeds and quantify behavioral divergence.

19. Learning-curve tracking
- Plot step vs reward and step vs thresholds.

20. Behavior clustering
- Cluster action traces to identify stable policy phenotypes.

### 7. Advanced Research Layer

21. Efficient novelty cache / bloom-like seen-before signal
22. Structured thought objects (context, belief, affect)
23. Minimal commonsense rule base for semantic priors

## Recommended Next Build Sequence

1. Emotion and uncertainty layer
2. Attention mechanism
3. UI controls (reward slider + seed + replay)
4. Multi-step planning

This sequence keeps implementation cost moderate while significantly increasing
observed cognitive realism.

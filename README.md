# MPCS
Malleable Perceptual-Cognitive System

MPCS is a compact cognitive-architecture simulation with a full loop:
perception -> reflex or deliberation -> action -> reward -> memory -> state update.

## Run

- Standard UI:
	- `python mpcs.py`
- Preset-memory test UI (starts with ready-made experience):
	- `python mpcs_preset_memory.py`
	- `python mpcs_preset_memory.py --profile balanced`
	- `python mpcs_preset_memory.py --profile cautious`
	- `python mpcs_preset_memory.py --profile exploratory --seed 99`

## Current Architecture

- Multimodal afferent binding (vision + audio)
- Reflexive fast-path rules
- Deliberative scoring over candidate actions
- Experience memory with top-k retrieval
- Internal state adaptation from reward
- Interactive Tk UI for controlled experiments

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

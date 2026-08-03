# MPCS Implementation Checklist

## Main Points (Important)

- [x] Dual-path processing is implemented (reflex path + deliberative path).
- [x] Experience encoding is implemented after each step (memory updates each cycle).
- [x] Deliberative decision scoring is implemented (similarity-based retrieval + counterfactual action scoring).
- [x] Exploration vs exploitation behavior is implemented (epsilon-style decision policy).
- [x] Novelty signal and memory time-decay are implemented.
- [ ] Full salience formula (4-component scoring) is implemented.
- [ ] Learned salience-threshold routing (formal theta-based route decision) is implemented.
- [ ] Two-layer memory architecture is implemented (fast membership layer + structured experience layer).
- [ ] Emotion as a first-class routing signal is implemented.
- [ ] Full triple-update learning loop is implemented (memory + salience weights + routing threshold).

## Minor Points

| Area | Minor Point | Status | Note |
|---|---|---|---|
| Deliberative Pathway | Emotional alignment step | Not yet | No explicit emotional alignment stage in deliberation flow. |
| Deliberative Pathway | Full contextual reasoning chain | Partial | Simplified reasoning via score aggregation and epsilon policy. |
| Learning | Formal salience-weight updates (w1-w4) | Not yet | No explicit variables or update rule for salience weights. |
| Learning | Formal theta adaptation from routing outcomes | Partial | Action threshold updates exist, but not report-level theta formulation. |
| Memory | Bloom-style fast membership lookup | Not yet | Novelty currently uses scan/similarity over stored memories. |
| UI | Manual reward slider control | Not yet | Reward is text entry currently, not bounded slider. |
| UI | Visualization panel (scores/influence) | Not yet | Text history exists; no chart or heat/influence panel. |
| UI | Seed control in main UI | Not yet | Seed is available in preset launcher, not exposed in main UI panel. |
| UI | Step replay controls | Not yet | Decision history log exists, no replay timeline controls. |
| Future Extension | Multi-modal deep learning encoders | Not yet | Still symbolic/handcrafted feature pipeline. |
| Future Extension | RL-based policy optimization | Not yet | Heuristic scoring is used instead of RL training. |
| Future Extension | Attention-based memory filtering | Not yet | No attention mechanism in retrieval/scoring. |
| Future Extension | Extended emotional dimensions (PAD/Plutchik) | Not yet | No rich affect model beyond current simplified signals. |

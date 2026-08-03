"""
MPCS — Z-number variant
-----------------------
Lightweight variant of the MPCS reference implementation that represents
feature values as Z-numbers: a (value, confidence) pair. Similarity and
novelty are computed using confidence-weighted matching.

This file is intentionally self-contained and mirrors the original
`mpcs.py` pipeline but replaces symbolic summaries with Z-number summaries.

Run:
    python mpcs_z.py

"""

import tkinter as tk
from tkinter import ttk
import random
from typing import Optional

# Keep feature schemas the same for UI compatibility
VISION_FEATURES = {
    "object_type": ["human", "animal", "vehicle", "unknown"],
    "motion":       ["static", "slow", "fast"],
    "color":        ["red", "blue", "dark", "bright"],
}

AUDIO_FEATURES = {
    "sound_type": ["none", "speech", "noise", "alarm"],
    "intensity":  ["low", "medium", "high"],
}

ACTIONS = ["ignore", "observe", "approach", "alert"]

REFLEX_RULES = [
    ({"sound_type": "alarm"}, "alert"),
    ({"motion": "fast"},      "observe"),
]

LEARNING_RATE = 0.01
TOP_K_MEMORIES = 5
TIME_DECAY_BASE = 0.99

PROFILE_CONFIGS = {
    "balanced": {"state": {}, "description": "No bias."},
    "cautious": {"state": {"risk_bias": 0.20, "action_threshold": 0.62}, "description": "Conservative."},
    "exploratory": {"state": {"risk_bias": 0.82, "action_threshold": 0.40}, "description": "Adventurous."},
}


# ----------------------
# Z-number helpers
# ----------------------
class ZNumber:
    """Simple Z-number: (value, confidence).

    - value: categorical value (string)
    - conf: reliability/confidence in [0.0, 1.0]
    """

    def __init__(self, value: str, conf: float = 1.0):
        self.value = value
        self.conf = max(0.0, min(1.0, float(conf)))

    def as_tuple(self):
        return (self.value, self.conf)

    def __repr__(self):
        return f"ZNumber({self.value!r}, {self.conf:.2f})"


# ----------------------
#  Afferent (Z) object
# ----------------------
class AfferentZObject:
    """Multimodal input where each feature is a Z-number."""

    def __init__(self, vision: dict, audio: dict, time: int, state: dict):
        # convert plain values into ZNumbers with default conf=1.0
        self.vision = {k: ZNumber(v) for k, v in vision.items()}
        self.audio = {k: ZNumber(v) for k, v in audio.items()}
        self.time = time
        self.state = state
        self.summary = self._create_summary()

    def _create_summary(self):
        # produce stable, hashable tuple-of-tuples: ((k,v,conf), ...), ((...))
        vis = tuple(sorted((k, z.value, z.conf) for k, z in self.vision.items()))
        aud = tuple(sorted((k, z.value, z.conf) for k, z in self.audio.items()))
        return (vis, aud)


# ----------------------
# Memory (Z) system
# ----------------------
class MemorySystemZ:
    def __init__(self):
        self._store: list[dict] = []

    def store(self, summary: tuple, action: str, reward: float, step: int, confidence: float = 1.0) -> None:
        self._store.append({
            "summary": summary,
            "action": action,
            "reward": reward,
            "step": step,
            "conf": max(0.0, min(1.0, float(confidence)))
        })

    def retrieve(self, summary: tuple, k: int = TOP_K_MEMORIES) -> list[dict]:
        ranked = sorted(
            self._store,
            key=lambda m: similarity_z(summary, m["summary"]),
            reverse=True,
        )
        return ranked[:k]

    def __len__(self):
        return len(self._store)


# ----------------------
# Similarity (Z-aware)
# ----------------------
def similarity_z(s1: tuple, s2: tuple) -> float:
    """Compute confidence-weighted matching score between two Z-summaries.

    For each feature: if values match, contribute the product of confidences;
    otherwise contribute zero. Sum across vision+audio.
    """
    score = 0.0
    for (k1, v1, c1), (k2, v2, c2) in zip(s1[0], s2[0]):
        if v1 == v2:
            score += (c1 * c2)
    for (k1, v1, c1), (k2, v2, c2) in zip(s1[1], s2[1]):
        if v1 == v2:
            score += (c1 * c2)
    return score

def total_confidence(s: tuple) -> float:
    # sum of confidences across all features (vision+audio)
    return sum(c for _, _, c in s[0]) + sum(c for _, _, c in s[1])

def normalized_similarity_z(s1: tuple, s2: tuple) -> float:
    denom = total_confidence(s1)
    return (similarity_z(s1, s2) / denom) if denom else 0.0

def compute_novelty_z(summary: tuple, memory: MemorySystemZ) -> float:
    if len(memory) == 0:
        return 1.0
    max_sim = max(normalized_similarity_z(summary, m["summary"]) for m in memory._store)
    return 1.0 - max_sim


# ----------------------
# Reflex & Deliberative (reuse ideas from mpcs)
# ----------------------
def reflexive_decision_z(afferent: AfferentZObject) -> Optional[str]:
    combined = {**{k: z.value for k, z in afferent.vision.items()}, **{k: z.value for k, z in afferent.audio.items()}}
    for condition, action in REFLEX_RULES:
        if all(combined.get(k) == v for k, v in condition.items()):
            return action
    return None

def simulate_action_z(action: str, past_cases: list[dict], summary: tuple, current_step: int) -> float:
    if not past_cases:
        return random.uniform(0.4, 0.6)

    weighted_sum = 0.0
    total_weight = 0.0
    for m in past_cases:
        if m["action"] != action:
            continue
        sim_w = normalized_similarity_z(summary, m["summary"])
        age = max(0, current_step - m.get("step", current_step))
        decay_w = TIME_DECAY_BASE ** age
        w = sim_w * decay_w
        weighted_sum += w * m["reward"]
        total_weight += w

    return (weighted_sum / total_weight) if total_weight else 0.5

def deliberate_z(afferent: AfferentZObject, memory: MemorySystemZ, novelty: float):
    cases = memory.retrieve(afferent.summary)
    scores = {action: simulate_action_z(action, cases, afferent.summary, afferent.time) for action in ACTIONS}
    best = max(scores, key=scores.get)
    epsilon = max(0.0, min(1.0, afferent.state.get("risk_bias", 0.5) * (0.6 + 0.4 * novelty)))
    if random.random() < epsilon:
        chosen = random.choice(ACTIONS)
        policy = "EXPLORE"
    else:
        chosen = best
        policy = "EXPLOIT"
    return chosen, scores, cases, policy, best, epsilon


# ----------------------
# Learning update
# ----------------------
def clamp_reward(value: float) -> float:
    return max(0.0, min(1.0, value))

def update_state(state: dict, reward: float, novelty: float) -> None:
    novelty_gain = 0.5 + novelty
    state["action_threshold"] = clamp_reward(state.get("action_threshold", 0.5) + LEARNING_RATE * novelty_gain * (reward - 0.5))


# ----------------------
# Cognitive step (Z)
# ----------------------
def cognitive_step_z(vision: dict, audio: dict, step: int, state: dict, memory: MemorySystemZ, manual_reward: Optional[float] = None) -> dict:
    aff = AfferentZObject(vision, audio, time=step, state=state)
    novelty = compute_novelty_z(aff.summary, memory)
    reflex_action = reflexive_decision_z(aff)

    if reflex_action is not None:
        action = reflex_action
        mode = "REFLEXIVE"
        scores = {a: "—" for a in ACTIONS}
        scores[action] = "triggered"
        cases = []
        policy = "REFLEX"
        best_action = action
        epsilon = 0.0
    else:
        action, scores, cases, policy, best_action, epsilon = deliberate_z(aff, memory, novelty)
        mode = "DELIBERATIVE"

    if manual_reward is not None:
        reward = clamp_reward(manual_reward)
    else:
        reward = random.uniform(0.0, 1.0)

    memory.store(aff.summary, action, reward, step, confidence=1.0)
    update_state(state, reward, novelty)

    return {
        "step": step,
        "action": action,
        "mode": mode,
        "policy": policy,
        "best_action": best_action,
        "epsilon": epsilon,
        "novelty": novelty,
        "reward": reward,
        "memory_size": len(memory),
        "scores": scores,
        "state": dict(state),
    }


# ----------------------
# Minimal UI launcher
# ----------------------
class CognitiveZUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("MPCS — Z-number variant")
        self.state = {"novelty_threshold": 0.5, "action_threshold": 0.5, "risk_bias": 0.5}
        self.memory = MemorySystemZ()
        self.step = 0
        self._vars = {}
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 6, "pady": 3}
        input_frame = ttk.LabelFrame(self.root, text="Input")
        input_frame.grid(row=0, column=0, sticky="nsew", **pad)

        row = 0
        ttk.Label(input_frame, text="── Vision ──", font=("", 9, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1
        for key, options in VISION_FEATURES.items():
            self._add_dropdown(input_frame, row, key, options)
            row += 1

        ttk.Label(input_frame, text="── Audio ──", font=("", 9, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1
        for key, options in AUDIO_FEATURES.items():
            self._add_dropdown(input_frame, row, key, options)
            row += 1

        ctrl = ttk.Frame(self.root)
        ctrl.grid(row=1, column=0, sticky="ew", **pad)
        ttk.Button(ctrl, text="▶ Run Step", command=self._run_step).pack(side="left", **pad)
        ttk.Button(ctrl, text="⟳ Reset", command=self._reset).pack(side="left", **pad)

        out = ttk.LabelFrame(self.root, text="Output")
        out.grid(row=0, column=1, rowspan=2, sticky="nsew", **pad)
        self.action_label = ttk.Label(out, text="Action: —", font=("", 12, "bold"))
        self.action_label.grid(row=0, column=0, sticky="w", **pad)
        self.state_label = ttk.Label(out, text="—")
        self.state_label.grid(row=1, column=0, sticky="w", **pad)

    def _add_dropdown(self, parent, row, key, options):
        ttk.Label(parent, text=key.replace("_"," ").title()).grid(row=row, column=0, sticky="w", padx=6, pady=2)
        var = tk.StringVar(value=options[0])
        self._vars[key] = var
        cb = ttk.Combobox(parent, textvariable=var, values=options, state="readonly", width=12)
        cb.grid(row=row, column=1, sticky="w", padx=6, pady=2)

    def _run_step(self):
        self.step += 1
        vision = {k: self._vars[k].get() for k in VISION_FEATURES}
        audio = {k: self._vars[k].get() for k in AUDIO_FEATURES}
        result = cognitive_step_z(vision, audio, self.step, self.state, self.memory)
        self.action_label.config(text=f"Action: {result['action'].upper()}")
        s = result['state']
        self.state_label.config(text=f"novelty_thr={s.get('novelty_threshold',0.0):.2f}  action_thr={s.get('action_threshold',0.0):.2f} risk_bias={s.get('risk_bias',0.0):.2f}")

    def _reset(self):
        self.state = {"novelty_threshold": 0.5, "action_threshold": 0.5, "risk_bias": 0.5}
        self.memory = MemorySystemZ()
        self.step = 0
        self.action_label.config(text="Action: —")
        self.state_label.config(text="—")


def main():
    root = tk.Tk()
    ui = CognitiveZUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

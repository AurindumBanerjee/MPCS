"""
MPCS — Z-number variant
-----------------------
Lightweight variant of the MPCS reference implementation that represents
feature values as Z-numbers: a (value, confidence) pair. Similarity and
novelty are computed using confidence-weighted matching.

Run:
    python mpcs_z.py

"""

import tkinter as tk
from tkinter import ttk
import hashlib
import random
from dataclasses import dataclass
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

# Expert-in-the-loop tuning
EXPERT_REWARD_DEFAULT = 0.95   # reward attached to a taught expert action
EXPERT_WEIGHT_BOOST = 3.0      # multiplier on expert cases during action scoring
EXPERT_DEMOTE_REWARD = 0.05    # reward the model's wrong original choice is demoted to

# dlCBF tuning: d subtables, each with its own bucket array.
# The default sizes are intentionally modest for the UI workload.
DLCBF_SUBTABLES = 4
DLCBF_BUCKETS_PER_SUBTABLE = 1024
DLCBF_FINGERPRINT_BITS = 16

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
@dataclass(slots=True)
class DLBucket:
    fingerprint: int = 0
    count: int = 0


class DLeftCountingBloomFilter:
    """d-left counting Bloom filter with per-bucket fingerprints and counters."""

    def __init__(
        self,
        subtables: int = DLCBF_SUBTABLES,
        buckets_per_subtable: int = DLCBF_BUCKETS_PER_SUBTABLE,
        fingerprint_bits: int = DLCBF_FINGERPRINT_BITS,
    ):
        self.subtables = max(2, int(subtables))
        self.buckets_per_subtable = max(8, int(buckets_per_subtable))
        self.fingerprint_bits = max(4, int(fingerprint_bits))
        self._fingerprint_mask = (1 << self.fingerprint_bits) - 1
        self._tables = [
            [DLBucket() for _ in range(self.buckets_per_subtable)]
            for _ in range(self.subtables)
        ]
        self._item_count = 0

    @staticmethod
    def _key_bytes(item: str) -> bytes:
        return item.encode("utf-8")

    def _digest(self, item: str) -> bytes:
        return hashlib.blake2b(self._key_bytes(item), digest_size=32).digest()

    def _fingerprint(self, digest: bytes) -> int:
        fp = int.from_bytes(digest[:8], "big") & self._fingerprint_mask
        return fp or 1

    def _bucket_index(self, digest: bytes, table_index: int) -> int:
        offset = 8 + (table_index * 4)
        chunk = digest[offset:offset + 4]
        if len(chunk) < 4:
            chunk = (chunk + digest)[:4]
        return int.from_bytes(chunk, "big") % self.buckets_per_subtable

    def _candidates(self, item: str) -> tuple[int, list[tuple[int, int, DLBucket]]]:
        digest = self._digest(item)
        fingerprint = self._fingerprint(digest)
        choices = []
        for table_index in range(self.subtables):
            bucket_index = self._bucket_index(digest, table_index)
            choices.append((table_index, bucket_index, self._tables[table_index][bucket_index]))
        return fingerprint, choices

    def insert(self, item: str) -> None:
        fingerprint, choices = self._candidates(item)

        for _, _, bucket in choices:
            if bucket.count > 0 and bucket.fingerprint == fingerprint:
                bucket.count += 1
                self._item_count += 1
                return

        table_index, bucket_index, bucket = min(choices, key=lambda choice: (choice[2].count, choice[0], choice[1]))
        if bucket.count == 0:
            bucket.fingerprint = fingerprint
        bucket.count += 1
        self._item_count += 1

    def query(self, item: str) -> bool:
        fingerprint, choices = self._candidates(item)
        return any(bucket.count > 0 and bucket.fingerprint == fingerprint for _, _, bucket in choices)

    def delete(self, item: str) -> bool:
        fingerprint, choices = self._candidates(item)
        for _, _, bucket in choices:
            if bucket.count > 0 and bucket.fingerprint == fingerprint:
                bucket.count -= 1
                self._item_count = max(0, self._item_count - 1)
                if bucket.count == 0:
                    bucket.fingerprint = 0
                return True
        return False

    def __len__(self) -> int:
        return self._item_count


class MemorySystemZ:
    def __init__(self):
        self._store: list[dict] = []
        self._dlcbf = DLeftCountingBloomFilter()

    @staticmethod
    def _summary_key(summary: tuple) -> str:
        return repr(summary)

    def store(self, summary: tuple, action: str, reward: float, step: int, confidence: float = 1.0, is_expert: bool = False) -> None:
        self._dlcbf.insert(self._summary_key(summary))
        self._store.append({
            "summary": summary,
            "action": action,
            "reward": reward,
            "step": step,
            "conf": max(0.0, min(1.0, float(confidence))),
            "is_expert": bool(is_expert),
        })

    def retrieve(self, summary: tuple, k: int = TOP_K_MEMORIES) -> list[dict]:
        if not self._dlcbf.query(self._summary_key(summary)):
            return []

        ranked = sorted(
            self._store,
            key=lambda m: similarity_z(summary, m["summary"]),
            reverse=True,
        )
        return ranked[:k]

    def delete(self, summary: tuple, step: Optional[int] = None) -> bool:
        """Remove the first matching record and decrement the dlCBF counter."""
        summary_key = self._summary_key(summary)
        for index in range(len(self._store) - 1, -1, -1):
            record = self._store[index]
            if record["summary"] != summary:
                continue
            if step is not None and record["step"] != step:
                continue
            self._store.pop(index)
            self._dlcbf.delete(summary_key)
            return True
        return False

    def update_reward(self, step: int, reward: float) -> bool:
        for record in reversed(self._store):
            if record["step"] == step:
                record["reward"] = reward
                return True
        return False

    def demote(self, step: int, reward: float = EXPERT_DEMOTE_REWARD) -> bool:
        """Lower the reward on the model's original record at *step* (expert correction)."""
        for record in reversed(self._store):
            if record["step"] == step and not record.get("is_expert"):
                record["reward"] = min(record["reward"], reward)
                record["demoted"] = True
                return True
        return False

    def teach_expert(self, summary: tuple, action: str, step: int, reward: float = EXPERT_REWARD_DEFAULT) -> None:
        """Store a high-confidence, expert-flagged experience for *action*."""
        self.store(summary, action, reward, step, confidence=1.0, is_expert=True)

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
    if not memory._dlcbf.query(memory._summary_key(summary)):
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
        expert_w = EXPERT_WEIGHT_BOOST if m.get("is_expert") else 1.0
        w = sim_w * decay_w * expert_w
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
        "summary": aff.summary,
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
        self.root.title("MPCS - Z-number variant")
        self.root.resizable(False, False)
        self.state = {"novelty_threshold": 0.5, "action_threshold": 0.5, "risk_bias": 0.5}
        self.memory = MemorySystemZ()
        self.step = 0
        self.last_result: Optional[dict] = None
        self._vars = {}
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
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
        ttk.Button(ctrl, text="Run Step", command=self._run_step).pack(side="left", **pad)
        ttk.Button(ctrl, text="Apply Reward", command=self._apply_reward_to_last_action).pack(side="left", **pad)
        ttk.Button(ctrl, text="Reset", command=self._reset).pack(side="left", **pad)

        ttk.Label(ctrl, text="Expert action:").pack(side="left", padx=(12, 2))
        self._expert_var = tk.StringVar(value=ACTIONS[0])
        ttk.Combobox(
            ctrl,
            textvariable=self._expert_var,
            values=tuple(ACTIONS),
            state="readonly",
            width=10,
        ).pack(side="left", padx=(0, 4))
        ttk.Button(ctrl, text="Teach Expert", command=self._teach_expert).pack(side="left", **pad)

        ttk.Label(ctrl, text="Profile:").pack(side="left", padx=(12, 2))
        self._profile_var = tk.StringVar(value="balanced")
        profile_cb = ttk.Combobox(
            ctrl,
            textvariable=self._profile_var,
            values=tuple(PROFILE_CONFIGS.keys()),
            state="readonly",
            width=12,
        )
        profile_cb.pack(side="left", padx=(0, 8))
        profile_cb.bind("<<ComboboxSelected>>", lambda e: self._apply_profile())

        ttk.Label(ctrl, text="Reward (0-1):").pack(side="left", padx=(12, 2))
        self._reward_var = tk.StringVar(value="")
        ttk.Entry(ctrl, textvariable=self._reward_var, width=6).pack(side="left", padx=(0, 8))
        ttk.Label(ctrl, text="(blank = random)", foreground="gray").pack(side="left")

        out = ttk.LabelFrame(self.root, text="Output")
        out.grid(row=0, column=1, rowspan=2, sticky="nsew", **pad)
        self.action_label = ttk.Label(out, text="Action: -", font=("", 12, "bold"))
        self.action_label.grid(row=0, column=0, columnspan=2, sticky="w", **pad)

        self.mode_label = ttk.Label(out, text="Mode: -")
        self.mode_label.grid(row=1, column=0, columnspan=2, sticky="w", **pad)

        self.reward_label = ttk.Label(out, text="Reward: -")
        self.reward_label.grid(row=2, column=0, columnspan=2, sticky="w", **pad)

        self.memory_label = ttk.Label(out, text="Memory size: 0")
        self.memory_label.grid(row=3, column=0, columnspan=2, sticky="w", **pad)

        ttk.Separator(out, orient="horizontal").grid(row=4, column=0, columnspan=2, sticky="ew", pady=4)

        ttk.Label(out, text="Action scores:", font=("", 9, "bold")).grid(row=5, column=0, columnspan=2, sticky="w", **pad)
        self.scores_label = ttk.Label(out, text="-", foreground="navy")
        self.scores_label.grid(row=6, column=0, columnspan=2, sticky="w", **pad)

        ttk.Label(out, text="Internal state:", font=("", 9, "bold")).grid(row=7, column=0, columnspan=2, sticky="w", **pad)
        self.state_label = ttk.Label(out, text="-", foreground="darkgreen")
        self.state_label.grid(row=8, column=0, columnspan=2, sticky="w", **pad)

        log_frame = ttk.LabelFrame(self.root, text="Decision History")
        log_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", **pad)

        self.log_text = tk.Text(
            log_frame,
            height=14,
            width=74,
            state="disabled",
            font=("Courier", 9),
            bg="#f9f9f9",
        )
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _add_dropdown(self, parent, row, key, options):
        ttk.Label(parent, text=key.replace("_", " ").title()).grid(row=row, column=0, sticky="w", padx=8, pady=2)
        var = tk.StringVar(value=options[0])
        self._vars[key] = var
        cb = ttk.Combobox(parent, textvariable=var, values=options, state="readonly", width=12)
        cb.grid(row=row, column=1, sticky="w", padx=8, pady=2)

    def _apply_profile(self):
        profile_name = self._profile_var.get()
        profile_cfg = PROFILE_CONFIGS[profile_name]
        for key, value in profile_cfg["state"].items():
            self.state[key] = value

        self._refresh_state_label()
        self._log(f"Profile changed: {profile_name} - {profile_cfg['description']}\n")

    def _run_step(self):
        self.step += 1
        vision = {k: self._vars[k].get() for k in VISION_FEATURES}
        audio = {k: self._vars[k].get() for k in AUDIO_FEATURES}
        manual_reward: Optional[float] = None
        raw = self._reward_var.get().strip()
        if raw:
            try:
                manual_reward = float(raw)
            except ValueError:
                manual_reward = None

        result = cognitive_step_z(vision, audio, self.step, self.state, self.memory, manual_reward=manual_reward)
        self.last_result = result

        self.action_label.config(text=f"Action: {result['action'].upper()}")
        self.mode_label.config(text=f"Mode: {result['mode']}  [{result['policy']}]")
        self.reward_label.config(text=f"Reward: {result['reward']:.3f}{'  (manual)' if manual_reward is not None else '  (random)'}")
        self.memory_label.config(text=f"Memory size: {result['memory_size']}")
        self.scores_label.config(text=self._format_scores(result['scores'], result['mode']))
        self._refresh_state_label()
        self._log_step(result)

    def _apply_reward_to_last_action(self):
        if self.last_result is None:
            self._log("No prior action to reward yet. Run a step first.\n")
            return

        raw = self._reward_var.get().strip()
        if not raw:
            self._log("Enter a reward value before applying it to the last action.\n")
            return

        try:
            reward = clamp_reward(float(raw))
        except ValueError:
            self._log("Reward must be a number between 0 and 1.\n")
            return

        previous_reward = self.last_result["reward"]
        step = self.last_result["step"]
        novelty = self.last_result["novelty"]

        if not self.memory.update_reward(step, reward):
            self._log(f"Could not find step {step} in memory to update reward.\n")
            return

        novelty_gain = 0.5 + novelty
        delta = LEARNING_RATE * novelty_gain * (reward - previous_reward)
        self.state["action_threshold"] = clamp_reward(self.state["action_threshold"] + delta)

        self.last_result["reward"] = reward
        self.last_result["reward_manual"] = True

        self.reward_label.config(text=f"Reward: {reward:.3f}  (applied to last action)")
        self._refresh_state_label()
        self._log(f"Applied reward {reward:.3f} to step {step} (replaced {previous_reward:.3f}).\n")

    def _teach_expert(self):
        if self.last_result is None:
            self._log("No prior action to correct yet. Run a step first.\n")
            return

        expert_action = self._expert_var.get()
        if expert_action not in ACTIONS:
            self._log(f"Unknown expert action: {expert_action!r}.\n")
            return

        # Optional custom expert reward from the reward field; default high.
        raw = self._reward_var.get().strip()
        if raw:
            try:
                expert_reward = clamp_reward(float(raw))
            except ValueError:
                self._log("Expert reward must be a number between 0 and 1.\n")
                return
        else:
            expert_reward = EXPERT_REWARD_DEFAULT

        summary = self.last_result["summary"]
        original_step = self.last_result["step"]
        original_action = self.last_result["action"]

        # 1) Store the expert's action as a new high-confidence, flagged experience.
        self.step += 1
        self.memory.teach_expert(summary, expert_action, self.step, reward=expert_reward)

        # 2) Demote the model's original (wrong) choice, unless it already matched.
        demoted = False
        if expert_action != original_action:
            demoted = self.memory.demote(original_step)

        # 3) Nudge routing threshold toward the expert signal (reuse set-reward math).
        novelty = self.last_result["novelty"]
        novelty_gain = 0.5 + novelty
        delta = LEARNING_RATE * novelty_gain * (expert_reward - 0.5)
        self.state["action_threshold"] = clamp_reward(self.state["action_threshold"] + delta)

        self.memory_label.config(text=f"Memory size: {len(self.memory)}")
        self._refresh_state_label()
        note = (
            f"Taught EXPERT action '{expert_action}' (reward {expert_reward:.2f}, conf=1.00) "
            f"for step {original_step}'s context."
        )
        if demoted:
            note += f" Demoted model's original '{original_action}' to {EXPERT_DEMOTE_REWARD:.2f}."
        elif expert_action == original_action:
            note += " Model already agreed; reinforced only."
        self._log(note + "\n")

    def _format_scores(self, scores: dict, mode: str) -> str:
        if mode == "REFLEXIVE":
            return "N/A (reflex fired)"
        return "  ".join(f"{a}: {v:.2f}" for a, v in scores.items())

    def _refresh_state_label(self):
        self.state_label.config(
            text=(
                f"novelty_thr={self.state['novelty_threshold']:.3f}  "
                f"action_thr={self.state['action_threshold']:.3f}  "
                f"risk_bias={self.state['risk_bias']:.3f}"
            )
        )

    def _log_step(self, result: dict):
        lines = [
            f"─── Step {result['step']} ───────────────────────────────────────",
            f"  Action : {result['action'].upper()}  [{result['mode']}]",
            f"  Reward : {result['reward']:.3f}   Memory size: {result['memory_size']}",
            (
                f"  Policy : {result['policy']}  "
                f"best={result['best_action']}  "
                f"eps={result['epsilon']:.2f}  novelty={result['novelty']:.2f}"
            ),
            f"  Scores : {self._scores_line(result['scores'])}",
            "",
        ]
        self._log("\n".join(lines) + "\n")

    def _scores_line(self, scores: dict) -> str:
        if not scores:
            return "-"
        return ", ".join(f"{a}={v}" for a, v in scores.items())

    def _log(self, text: str):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _reset(self):
        self.state = {"novelty_threshold": 0.5, "action_threshold": 0.5, "risk_bias": 0.5}
        self.memory = MemorySystemZ()
        self.step = 0
        self.last_result = None
        self.action_label.config(text="Action: -")
        self.mode_label.config(text="Mode: -")
        self.reward_label.config(text="Reward: -")
        self.memory_label.config(text="Memory size: 0")
        self.scores_label.config(text="-")
        self.state_label.config(text="-")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")
        self._log("System reset - new internal state initialized.\n")


def main():
    root = tk.Tk()
    ui = CognitiveZUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

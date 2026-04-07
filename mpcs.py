"""
MPCS — Malleable Perceptual-Cognitive System
=============================================
A minimal cognitive architecture simulation that mimics core aspects of
cognition: perception → reasoning → action → learning.

Pipeline:
    Manual Input (UI)
        ↓
    Afferent Structure (multimodal binding)
        ↓
    Reflexive Layer (fast rules)
        ↓ (if not triggered)
    Deliberative Layer
        → Retrieve similar memories
        → Simulate actions (counterfactuals)
        → Score actions
        → Choose best
        ↓
    Action Output → Reward → Memory Update → Internal State Update
"""

import tkinter as tk
from tkinter import ttk
import random
from typing import Optional

# ---------------------------------------------------------------------------
# 1. Feature Definitions
# ---------------------------------------------------------------------------
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

# Reflexive rules: list of (condition_dict, action) pairs.
# Conditions can reference keys from either vision OR audio dicts.
REFLEX_RULES = [
    ({"sound_type": "alarm"}, "alert"),
    ({"motion": "fast"},      "observe"),
]

LEARNING_RATE = 0.01
TOP_K_MEMORIES = 5
PRIOR_MIN = 0.4   # lower bound for weak action-reward prior (no memory)
PRIOR_MAX = 0.6   # upper bound for weak action-reward prior (no memory)

# ---------------------------------------------------------------------------
# 2. Afferent Structure
# ---------------------------------------------------------------------------
class AfferentObject:
    """Unified multimodal input binding."""

    def __init__(self, vision: dict, audio: dict, time: int, state: dict):
        self.vision = vision
        self.audio = audio
        self.time = time
        self.state = state
        self.summary = self._create_summary()

    def _create_summary(self) -> tuple:
        """Compressed, hashable representation used for similarity matching."""
        return (
            tuple(sorted(self.vision.items())),
            tuple(sorted(self.audio.items())),
        )

# ---------------------------------------------------------------------------
# 3. Internal State (self-made parameters)
# ---------------------------------------------------------------------------
def init_state(seed: Optional[int] = None) -> dict:
    """Return a fresh internal state, optionally seeded for reproducibility."""
    rng = random.Random(seed)
    return {
        "novelty_threshold": rng.uniform(0.3, 0.7),
        "action_threshold":  rng.uniform(0.3, 0.7),
        "risk_bias":         rng.uniform(0.0, 1.0),
    }

# ---------------------------------------------------------------------------
# 4. Memory System
# ---------------------------------------------------------------------------
class MemorySystem:
    """Stores and retrieves experiences."""

    def __init__(self):
        self._store: list[dict] = []

    def store(self, summary: tuple, action: str, reward: float) -> None:
        self._store.append({
            "summary": summary,
            "action":  action,
            "reward":  reward,
        })

    def retrieve(self, summary: tuple, k: int = TOP_K_MEMORIES) -> list[dict]:
        """Return top-k most similar past experiences."""
        ranked = sorted(
            self._store,
            key=lambda m: similarity(summary, m["summary"]),
            reverse=True,
        )
        return ranked[:k]

    def __len__(self) -> int:
        return len(self._store)

# ---------------------------------------------------------------------------
# 5. Similarity Function (symbolic, no ML)
# ---------------------------------------------------------------------------
def similarity(s1: tuple, s2: tuple) -> int:
    """
    Count matching feature values between two summaries.

    Both summaries must originate from the same feature schema
    (same keys in the same sorted order) as produced by
    ``AfferentObject._create_summary()``.  ``zip`` is used intentionally:
    if the schemas ever differ the shorter sequence limits the score,
    which is safe because all summaries are built from the global
    ``VISION_FEATURES`` / ``AUDIO_FEATURES`` dictionaries.
    """
    score = 0
    for (_, v1), (_, v2) in zip(s1[0], s2[0]):  # vision
        if v1 == v2:
            score += 1
    for (_, v1), (_, v2) in zip(s1[1], s2[1]):  # audio
        if v1 == v2:
            score += 1
    return score

# ---------------------------------------------------------------------------
# 6. Reflexive Layer (fast thinking)
# ---------------------------------------------------------------------------
def reflexive_decision(afferent: AfferentObject) -> Optional[str]:
    """
    Evaluate reflex rules and return an action immediately if triggered.
    Returns None when no rule fires (→ deliberation required).
    """
    combined = {**afferent.vision, **afferent.audio}
    for condition, action in REFLEX_RULES:
        if all(combined.get(k) == v for k, v in condition.items()):
            return action
    return None

# ---------------------------------------------------------------------------
# 7. Deliberative Layer (slow thinking + counterfactuals)
# ---------------------------------------------------------------------------
def simulate_action(action: str, past_cases: list[dict]) -> float:
    """
    Counterfactual simulation: estimate expected reward for *action*
    given the retrieved memory cases.
    """
    if not past_cases:
        return random.uniform(PRIOR_MIN, PRIOR_MAX)  # weak prior when no history
    rewards = [m["reward"] for m in past_cases if m["action"] == action]
    return sum(rewards) / len(rewards) if rewards else 0.5

def deliberate(afferent: AfferentObject, memory: MemorySystem) -> tuple:
    """
    Retrieve similar memories, simulate each action, return best action.

    Returns:
        (chosen_action, score_per_action, retrieved_cases)
    """
    cases = memory.retrieve(afferent.summary)
    scores = {action: simulate_action(action, cases) for action in ACTIONS}
    if not scores:
        return ACTIONS[0], scores, cases
    best = max(scores, key=scores.get)
    return best, scores, cases

# ---------------------------------------------------------------------------
# 8. Learning Update
# ---------------------------------------------------------------------------
def update_state(state: dict, reward: float) -> None:
    """Adapt internal parameters based on reward signal."""
    state["action_threshold"] = max(
        0.0, min(1.0, state["action_threshold"] + LEARNING_RATE * (reward - 0.5))
    )

# ---------------------------------------------------------------------------
# 9. Cognitive Step (full pipeline)
# ---------------------------------------------------------------------------
def cognitive_step(
    vision: dict,
    audio: dict,
    step: int,
    state: dict,
    memory: MemorySystem,
    manual_reward: Optional[float] = None,
) -> dict:
    """
    Execute one full cognitive cycle and return a result dict for display.

    Args:
        vision: vision feature dict.
        audio: audio feature dict.
        step: current step count.
        state: mutable internal state dict (updated in-place).
        memory: MemorySystem instance (updated in-place).
        manual_reward: explicit reward value in [0, 1].  When *None* a random
            reward is sampled (autonomous operation).
    """
    aff = AfferentObject(vision, audio, time=step, state=state)

    # --- Reflexive layer ---
    reflex_action = reflexive_decision(aff)

    if reflex_action is not None:
        action      = reflex_action
        mode        = "REFLEXIVE"
        scores      = {a: "—" for a in ACTIONS}
        scores[action] = "triggered"
        cases       = []
        sim_scores_str = "N/A (reflex triggered)"
    else:
        # --- Deliberative layer ---
        action, scores, cases = deliberate(aff, memory)
        mode = "DELIBERATIVE"
        sim_scores_str = ", ".join(f"{a}={v:.2f}" for a, v in scores.items())

    # --- Assign reward (manual override or random for autonomous operation) ---
    if manual_reward is not None:
        reward = max(0.0, min(1.0, manual_reward))
    else:
        reward = random.uniform(0.0, 1.0)

    # --- Memory & state update ---
    memory.store(aff.summary, action, reward)
    update_state(state, reward)

    # Build similarity details for top cases
    case_details = []
    for c in cases:
        sim = similarity(aff.summary, c["summary"])
        case_details.append(
            f"  sim={sim}  action={c['action']}  reward={c['reward']:.2f}"
        )

    return {
        "step":         step,
        "action":       action,
        "mode":         mode,
        "reward":       reward,
        "reward_manual": manual_reward is not None,
        "memory_size":  len(memory),
        "scores":       scores,
        "sim_scores_str": sim_scores_str,
        "case_details": case_details,
        "state":        dict(state),
    }

# ---------------------------------------------------------------------------
# 10. UI
# ---------------------------------------------------------------------------
class CognitiveUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("MPCS — Malleable Perceptual-Cognitive System")
        self.root.resizable(False, False)

        self.state  = init_state()
        self.memory = MemorySystem()
        self.step   = 0

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # ── Input frame ────────────────────────────────────────────────
        input_frame = ttk.LabelFrame(self.root, text="Input")
        input_frame.grid(row=0, column=0, sticky="nsew", **pad)

        self._vars: dict[str, tk.StringVar] = {}

        row = 0
        ttk.Label(input_frame, text="── Vision ──", font=("", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad
        )
        row += 1
        for key, options in VISION_FEATURES.items():
            self._add_dropdown(input_frame, row, key, options)
            row += 1

        ttk.Label(input_frame, text="── Audio ──", font=("", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad
        )
        row += 1
        for key, options in AUDIO_FEATURES.items():
            self._add_dropdown(input_frame, row, key, options)
            row += 1

        # ── Control frame ──────────────────────────────────────────────
        ctrl_frame = ttk.Frame(self.root)
        ctrl_frame.grid(row=1, column=0, sticky="ew", **pad)

        ttk.Button(ctrl_frame, text="▶  Run Step", command=self._run_step).pack(
            side="left", **pad
        )
        ttk.Button(ctrl_frame, text="⟳  Reset", command=self._reset).pack(
            side="left", **pad
        )

        # Manual reward entry (optional; leave blank for random)
        ttk.Label(ctrl_frame, text="Reward (0–1):").pack(side="left", padx=(12, 2))
        self._reward_var = tk.StringVar(value="")
        ttk.Entry(ctrl_frame, textvariable=self._reward_var, width=6).pack(
            side="left", padx=(0, 8)
        )
        ttk.Label(ctrl_frame, text="(blank = random)", foreground="gray").pack(
            side="left"
        )

        # ── Output frame ───────────────────────────────────────────────
        out_frame = ttk.LabelFrame(self.root, text="Output")
        out_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", **pad)

        self.action_label = ttk.Label(
            out_frame, text="Action: —", font=("", 12, "bold")
        )
        self.action_label.grid(row=0, column=0, columnspan=2, sticky="w", **pad)

        self.mode_label = ttk.Label(out_frame, text="Mode: —")
        self.mode_label.grid(row=1, column=0, columnspan=2, sticky="w", **pad)

        self.reward_label = ttk.Label(out_frame, text="Reward: —")
        self.reward_label.grid(row=2, column=0, columnspan=2, sticky="w", **pad)

        self.memory_label = ttk.Label(out_frame, text="Memory size: 0")
        self.memory_label.grid(row=3, column=0, columnspan=2, sticky="w", **pad)

        ttk.Separator(out_frame, orient="horizontal").grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=4
        )

        ttk.Label(out_frame, text="Action scores:", font=("", 9, "bold")).grid(
            row=5, column=0, columnspan=2, sticky="w", **pad
        )
        self.scores_label = ttk.Label(out_frame, text="—", foreground="navy")
        self.scores_label.grid(row=6, column=0, columnspan=2, sticky="w", **pad)

        ttk.Label(out_frame, text="Internal state:", font=("", 9, "bold")).grid(
            row=7, column=0, columnspan=2, sticky="w", **pad
        )
        self.state_label = ttk.Label(out_frame, text="—", foreground="darkgreen")
        self.state_label.grid(row=8, column=0, columnspan=2, sticky="w", **pad)

        # ── History log ───────────────────────────────────────────────
        log_frame = ttk.LabelFrame(self.root, text="Decision History")
        log_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", **pad)

        self.log_text = tk.Text(
            log_frame, height=14, width=74, state="disabled",
            font=("Courier", 9), bg="#f9f9f9",
        )
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _add_dropdown(self, parent, row, key, options):
        label_text = key.replace("_", " ").title()
        ttk.Label(parent, text=label_text).grid(
            row=row, column=0, sticky="w", padx=8, pady=2
        )
        var = tk.StringVar(value=options[0])
        self._vars[key] = var
        cb = ttk.Combobox(
            parent, textvariable=var, values=options, state="readonly", width=12
        )
        cb.grid(row=row, column=1, sticky="w", padx=8, pady=2)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------
    def _run_step(self):
        self.step += 1

        vision = {k: self._vars[k].get() for k in VISION_FEATURES}
        audio  = {k: self._vars[k].get() for k in AUDIO_FEATURES}

        # Parse manual reward if provided
        manual_reward: Optional[float] = None
        raw = self._reward_var.get().strip()
        if raw:
            try:
                manual_reward = float(raw)
            except ValueError:
                pass  # invalid input → fall back to random

        result = cognitive_step(
            vision, audio, self.step, self.state, self.memory,
            manual_reward=manual_reward,
        )

        # Update summary labels
        self.action_label.config(text=f"Action: {result['action'].upper()}")
        self.mode_label.config(
            text=f"Mode: {result['mode']}",
            foreground=("firebrick" if result["mode"] == "REFLEXIVE" else "darkblue"),
        )
        self.reward_label.config(
            text=f"Reward: {result['reward']:.3f}"
                 f"{'  (manual)' if result['reward_manual'] else '  (random)'}"
        )
        self.memory_label.config(text=f"Memory size: {result['memory_size']}")

        # Action scores
        if result["mode"] == "REFLEXIVE":
            scores_text = "N/A (reflex fired)"
        else:
            scores_text = "  ".join(
                f"{a}: {v:.2f}" for a, v in result["scores"].items()
            )
        self.scores_label.config(text=scores_text)

        # Internal state
        s = result["state"]
        state_text = (
            f"novelty_thr={s['novelty_threshold']:.3f}  "
            f"action_thr={s['action_threshold']:.3f}  "
            f"risk_bias={s['risk_bias']:.3f}"
        )
        self.state_label.config(text=state_text)

        # Append to history log
        self._log_step(result)

    def _reset(self):
        self.state  = init_state()
        self.memory = MemorySystem()
        self.step   = 0
        self.action_label.config(text="Action: —")
        self.mode_label.config(text="Mode: —", foreground="black")
        self.reward_label.config(text="Reward: —")
        self.memory_label.config(text="Memory size: 0")
        self.scores_label.config(text="—")
        self.state_label.config(text="—")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")
        self._log("System reset — new internal state initialized.\n")

    def _log_step(self, result: dict):
        lines = [
            f"─── Step {result['step']} ───────────────────────────────────────",
            f"  Action : {result['action'].upper()}  [{result['mode']}]",
            f"  Reward : {result['reward']:.3f}   Memory size: {result['memory_size']}",
            f"  Scores : {result['sim_scores_str']}",
        ]
        if result["case_details"]:
            lines.append("  Top memories used:")
            lines.extend(result["case_details"])
        lines.append("")
        self._log("\n".join(lines) + "\n")

    def _log(self, text: str):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    root = tk.Tk()
    app = CognitiveUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

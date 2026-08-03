"""
Preset-memory launcher for MPCS.

This script boots the existing Tk UI with a ready-made memory bank so you can
test decision making against known prior experiences.

Workflow:
    1) Click Run Step to execute an action.
    2) Enter reward value.
    3) Click Apply Reward to attach it to that last executed action.

Run:
    python mpcs_preset_memory.py
    python mpcs_preset_memory.py --profile cautious
    python mpcs_preset_memory.py --profile exploratory --seed 99
"""

import argparse
import tkinter as tk

from mpcs import AfferentObject, CognitiveUI, MemorySystem, init_state


PROFILE_CONFIGS = {
    "balanced": {
        "state": {},
        "reward_delta": {
            "ignore": 0.00,
            "observe": 0.00,
            "approach": 0.00,
            "alert": 0.00,
        },
    },
    "cautious": {
        "state": {
            "risk_bias": 0.20,
            "action_threshold": 0.62,
        },
        "reward_delta": {
            "ignore": 0.06,
            "observe": 0.04,
            "approach": -0.06,
            "alert": -0.02,
        },
    },
    "exploratory": {
        "state": {
            "risk_bias": 0.82,
            "action_threshold": 0.40,
        },
        "reward_delta": {
            "ignore": -0.05,
            "observe": 0.05,
            "approach": 0.07,
            "alert": 0.03,
        },
    },
}


def clamp_reward(value: float) -> float:
    """Clamp rewards to [0.0, 1.0] after profile shaping."""
    return max(0.0, min(1.0, value))


def make_summary(vision: dict, audio: dict) -> tuple:
    """Build a canonical summary tuple using MPCS' afferent encoding."""
    return AfferentObject(vision=vision, audio=audio, time=0, state={}).summary


def build_preset_memory(profile: str = "balanced") -> MemorySystem:
    """Return MemorySystem preloaded with hand-crafted experiences."""
    memory = MemorySystem()
    profile_cfg = PROFILE_CONFIGS[profile]

    # 20 novel contexts + 10 repeated variants with slight changes.
    # Step values intentionally span time to make decay effects visible.
    novel_entries = [
        ({"object_type": "human", "motion": "static", "color": "blue"}, {"sound_type": "alarm", "intensity": "high"}, "alert", 0.95, 1),
        ({"object_type": "vehicle", "motion": "slow", "color": "dark"}, {"sound_type": "alarm", "intensity": "medium"}, "alert", 0.90, 2),
        ({"object_type": "animal", "motion": "fast", "color": "red"}, {"sound_type": "noise", "intensity": "medium"}, "observe", 0.82, 3),
        ({"object_type": "unknown", "motion": "fast", "color": "bright"}, {"sound_type": "none", "intensity": "low"}, "observe", 0.78, 4),
        ({"object_type": "human", "motion": "slow", "color": "bright"}, {"sound_type": "speech", "intensity": "low"}, "approach", 0.88, 5),
        ({"object_type": "human", "motion": "slow", "color": "blue"}, {"sound_type": "speech", "intensity": "medium"}, "approach", 0.84, 6),
        ({"object_type": "animal", "motion": "slow", "color": "dark"}, {"sound_type": "noise", "intensity": "high"}, "ignore", 0.62, 7),
        ({"object_type": "vehicle", "motion": "static", "color": "red"}, {"sound_type": "none", "intensity": "low"}, "ignore", 0.75, 8),
        ({"object_type": "unknown", "motion": "slow", "color": "dark"}, {"sound_type": "noise", "intensity": "medium"}, "observe", 0.70, 9),
        ({"object_type": "human", "motion": "fast", "color": "red"}, {"sound_type": "speech", "intensity": "high"}, "alert", 0.86, 10),
        ({"object_type": "animal", "motion": "static", "color": "bright"}, {"sound_type": "none", "intensity": "low"}, "ignore", 0.68, 11),
        ({"object_type": "vehicle", "motion": "fast", "color": "dark"}, {"sound_type": "noise", "intensity": "high"}, "observe", 0.83, 12),
        ({"object_type": "unknown", "motion": "static", "color": "blue"}, {"sound_type": "speech", "intensity": "low"}, "observe", 0.64, 13),
        ({"object_type": "human", "motion": "static", "color": "bright"}, {"sound_type": "none", "intensity": "medium"}, "approach", 0.73, 14),
        ({"object_type": "animal", "motion": "slow", "color": "red"}, {"sound_type": "speech", "intensity": "low"}, "approach", 0.77, 15),
        ({"object_type": "vehicle", "motion": "slow", "color": "blue"}, {"sound_type": "noise", "intensity": "medium"}, "observe", 0.66, 16),
        ({"object_type": "unknown", "motion": "fast", "color": "red"}, {"sound_type": "alarm", "intensity": "high"}, "alert", 0.93, 17),
        ({"object_type": "human", "motion": "slow", "color": "dark"}, {"sound_type": "none", "intensity": "low"}, "ignore", 0.72, 18),
        ({"object_type": "animal", "motion": "fast", "color": "bright"}, {"sound_type": "alarm", "intensity": "medium"}, "alert", 0.89, 19),
        ({"object_type": "vehicle", "motion": "static", "color": "bright"}, {"sound_type": "speech", "intensity": "medium"}, "approach", 0.74, 20),
    ]

    repeated_variant_entries = [
        # Slight changes from earlier contexts to improve local contextual density.
        ({"object_type": "human", "motion": "static", "color": "red"}, {"sound_type": "alarm", "intensity": "high"}, "alert", 0.92, 21),
        ({"object_type": "vehicle", "motion": "slow", "color": "dark"}, {"sound_type": "alarm", "intensity": "high"}, "alert", 0.91, 22),
        ({"object_type": "animal", "motion": "fast", "color": "red"}, {"sound_type": "noise", "intensity": "high"}, "observe", 0.80, 23),
        ({"object_type": "unknown", "motion": "fast", "color": "dark"}, {"sound_type": "none", "intensity": "low"}, "observe", 0.76, 24),
        ({"object_type": "human", "motion": "slow", "color": "bright"}, {"sound_type": "speech", "intensity": "medium"}, "approach", 0.85, 25),
        ({"object_type": "human", "motion": "slow", "color": "blue"}, {"sound_type": "speech", "intensity": "low"}, "approach", 0.82, 26),
        ({"object_type": "animal", "motion": "slow", "color": "dark"}, {"sound_type": "noise", "intensity": "medium"}, "ignore", 0.60, 27),
        ({"object_type": "vehicle", "motion": "static", "color": "red"}, {"sound_type": "none", "intensity": "medium"}, "ignore", 0.71, 28),
        ({"object_type": "unknown", "motion": "slow", "color": "dark"}, {"sound_type": "noise", "intensity": "high"}, "observe", 0.68, 29),
        ({"object_type": "animal", "motion": "slow", "color": "dark"}, {"sound_type": "noise", "intensity": "high"}, "approach", 0.42, 30),
    ]

    entries = novel_entries + repeated_variant_entries

    for vision, audio, action, reward, step in entries:
        reward = clamp_reward(reward + profile_cfg["reward_delta"][action])
        summary = make_summary(vision, audio)
        memory.store(summary=summary, action=action, reward=reward, step=step)

    return memory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Launch MPCS UI with a preset memory bank and selectable behavior profile."
        )
    )
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILE_CONFIGS.keys()),
        default="balanced",
        help="Behavior profile to apply to state and reward priors.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed used for initial internal state.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = tk.Tk()
    ui = CognitiveUI(root)

    # Reinitialize with deterministic state and selected profile.
    ui.state = init_state(seed=args.seed)
    for key, value in PROFILE_CONFIGS[args.profile]["state"].items():
        ui.state[key] = value

    ui.memory = build_preset_memory(profile=args.profile)
    ui.step = len(ui.memory)

    ui.memory_label.config(text=f"Memory size: {len(ui.memory)}")
    ui.state_label.config(
        text=(
            f"novelty_thr={ui.state['novelty_threshold']:.3f}  "
            f"action_thr={ui.state['action_threshold']:.3f}  "
            f"risk_bias={ui.state['risk_bias']:.3f}"
        )
    )

    ui._log(
        "Loaded preset memory bank with 30 experiences "
        "(20 novel + 10 repeated variants). "
        f"Profile={args.profile}, seed={args.seed}. "
        "Use Run Step, then Apply Reward to label the last executed action.\n"
    )

    root.mainloop()


if __name__ == "__main__":
    main()

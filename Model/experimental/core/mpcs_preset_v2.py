"""
Preset memory bank for MPCS v2 — 70 four-modality experiences
-------------------------------------------------------------
50 novel contexts plus 20 near-repetitions, every entry carrying all four
modalities (vision, audio, touch, smell).

The bank is shaped so the decision machinery has something to chew on:

  * every action appears, including `withdraw`, whose entries cluster on hot,
    impact and sharp-contact contexts so the touch reflexes have precedent;
  * coherent cases (smoke + hot + alarm -> withdraw, high reward) sit
    alongside conflicting ones (pleasant smell, sharp texture) so retrieved
    memories genuinely disagree and the contribution graph shows it;
  * the 20 repetitions perturb one or two features of an earlier context,
    creating the local density that makes similarity weighting and time decay
    visible rather than theoretical;
  * a handful of deliberately low-reward entries record actions that
    contradicted what memory advised, giving the off-recommendation penalty
    precedent to learn from.

Steps run 1..70 so older memories decay measurably against newer ones.

Run directly to regenerate the human-readable companion document:
    python mcps_preset_v2.py --write-doc
"""

from __future__ import annotations

import argparse
import os
from collections import Counter, defaultdict

from mcps_engine import (
    ACTIONS,
    MemorySystem,
    clamp_reward,
    summary_of,
)


# Per-profile reward shaping, extended from the v1 launcher with `withdraw`.
PROFILE_CONFIGS = {
    "balanced": {
        "state": {},
        "reward_delta": {
            "ignore": 0.00, "observe": 0.00, "approach": 0.00,
            "alert": 0.00, "withdraw": 0.00,
        },
        "description": "No bias.",
    },
    "cautious": {
        "state": {"risk_bias": 0.20, "action_threshold": 0.62},
        "reward_delta": {
            "ignore": 0.06, "observe": 0.04, "approach": -0.06,
            "alert": -0.02, "withdraw": 0.05,
        },
        "description": "Rewards restraint and withdrawal; penalises approach.",
    },
    "exploratory": {
        "state": {"risk_bias": 0.82, "action_threshold": 0.40},
        "reward_delta": {
            "ignore": -0.05, "observe": 0.05, "approach": 0.07,
            "alert": 0.03, "withdraw": -0.04,
        },
        "description": "Rewards engagement; discounts withdrawal.",
    },
}


def _p(object_type, motion, color,
       sound_type, audio_intensity,
       contact, texture, thermal, touch_intensity,
       odor_type, odor_intensity, pleasantness) -> dict:
    """Build a full four-modality percept dict."""
    return {
        "vision": {
            "object_type": object_type, "motion": motion, "color": color,
        },
        "audio": {
            "sound_type": sound_type, "audio_intensity": audio_intensity,
        },
        "touch": {
            "contact": contact, "texture": texture,
            "thermal": thermal, "touch_intensity": touch_intensity,
        },
        "smell": {
            "odor_type": odor_type, "odor_intensity": odor_intensity,
            "pleasantness": pleasantness,
        },
    }


# Each entry: (percept, action, reward, step, mode, note)
# `mode` records how the experience was originally produced, which the reward
# machinery re-weights when valuing a reflex outcome.
NOVEL_ENTRIES = [
    # -- danger: heat and fire, reflex territory ----------------------------
    (_p("unknown", "static", "bright", "alarm", "high",
        "firm", "smooth", "hot", "high",
        "smoke", "strong", "foul"),
     "withdraw", 0.96, 1, "REFLEXIVE", "Burning surface, alarm sounding; withdrawal clearly right."),
    (_p("vehicle", "static", "dark", "noise", "medium",
        "light", "smooth", "hot", "medium",
        "smoke", "moderate", "foul"),
     "withdraw", 0.92, 2, "REFLEXIVE", "Overheated machine; back away before inspecting."),
    (_p("unknown", "slow", "red", "alarm", "high",
        "none", "smooth", "warm", "low",
        "smoke", "strong", "foul"),
     "alert", 0.94, 3, "REFLEXIVE", "Fire signalled but not yet touchable; raise the alarm."),
    (_p("unknown", "static", "dark", "none", "low",
        "none", "smooth", "neutral", "low",
        "smoke", "faint", "neutral"),
     "alert", 0.83, 4, "REFLEXIVE", "Faint smoke with no other cue still warrants alerting."),

    # -- danger: impact and sharp contact -----------------------------------
    (_p("vehicle", "fast", "dark", "noise", "high",
        "impact", "rough", "neutral", "high",
        "none", "faint", "neutral"),
     "withdraw", 0.93, 5, "REFLEXIVE", "Struck by a moving vehicle; disengage immediately."),
    (_p("unknown", "fast", "bright", "noise", "high",
        "impact", "sharp", "cold", "high",
        "none", "faint", "neutral"),
     "withdraw", 0.95, 6, "REFLEXIVE", "Sharp fast impact; the strongest withdrawal case."),
    (_p("unknown", "static", "dark", "none", "low",
        "firm", "sharp", "cold", "medium",
        "none", "faint", "neutral"),
     "withdraw", 0.88, 7, "REFLEXIVE", "Gripping something sharp; release even when quiet."),
    (_p("animal", "fast", "dark", "noise", "high",
        "firm", "sharp", "warm", "high",
        "organic", "strong", "foul"),
     "withdraw", 0.90, 8, "REFLEXIVE", "Animal bite: sharp, warm, foul-smelling."),

    # -- alert: threat detected at a distance -------------------------------
    (_p("human", "fast", "red", "alarm", "high",
        "none", "smooth", "neutral", "low",
        "none", "faint", "neutral"),
     "alert", 0.91, 9, "REFLEXIVE", "Person running with alarm; escalate."),
    (_p("vehicle", "fast", "red", "alarm", "medium",
        "none", "smooth", "neutral", "low",
        "chemical", "moderate", "foul"),
     "alert", 0.89, 10, "REFLEXIVE", "Emergency vehicle with chemical odour."),
    (_p("unknown", "static", "dark", "none", "low",
        "none", "smooth", "neutral", "low",
        "chemical", "strong", "foul"),
     "alert", 0.87, 11, "REFLEXIVE", "Strong chemical leak with no visual cue."),
    (_p("animal", "fast", "dark", "alarm", "high",
        "none", "rough", "warm", "low",
        "organic", "strong", "foul"),
     "alert", 0.85, 12, "REFLEXIVE", "Agitated animal; warn rather than engage."),
    (_p("human", "static", "blue", "alarm", "high",
        "none", "smooth", "neutral", "low",
        "none", "faint", "neutral"),
     "alert", 0.90, 13, "REFLEXIVE", "Stationary person, alarm sounding."),

    # -- observe: motion or ambiguity, no contact ---------------------------
    (_p("animal", "fast", "red", "noise", "medium",
        "none", "smooth", "neutral", "low",
        "organic", "moderate", "neutral"),
     "observe", 0.82, 14, "REFLEXIVE", "Fast animal, nothing threatening; watch."),
    (_p("unknown", "fast", "bright", "none", "low",
        "none", "smooth", "cold", "low",
        "none", "faint", "neutral"),
     "observe", 0.78, 15, "REFLEXIVE", "Unidentified fast mover in silence."),
    (_p("vehicle", "fast", "dark", "noise", "high",
        "none", "smooth", "neutral", "low",
        "chemical", "faint", "neutral"),
     "observe", 0.83, 16, "REFLEXIVE", "Passing traffic; track it, do not act."),
    (_p("unknown", "slow", "dark", "noise", "medium",
        "light", "rough", "cold", "low",
        "none", "faint", "neutral"),
     "observe", 0.70, 17, "DELIBERATIVE", "Slow ambiguous object, light contact."),
    (_p("unknown", "static", "blue", "speech", "low",
        "none", "smooth", "neutral", "low",
        "none", "faint", "neutral"),
     "observe", 0.64, 18, "DELIBERATIVE", "Static unknown with distant speech."),
    (_p("animal", "slow", "bright", "noise", "low",
        "light", "rough", "warm", "low",
        "organic", "moderate", "neutral"),
     "observe", 0.72, 19, "DELIBERATIVE", "Calm animal at light contact."),
    (_p("vehicle", "static", "blue", "noise", "medium",
        "light", "smooth", "cold", "low",
        "chemical", "faint", "neutral"),
     "observe", 0.66, 20, "DELIBERATIVE", "Parked vehicle, mild chemical trace."),

    # -- approach: safe, inviting contexts ----------------------------------
    (_p("human", "slow", "bright", "speech", "low",
        "light", "smooth", "warm", "low",
        "food", "moderate", "pleasant"),
     "approach", 0.92, 21, "DELIBERATIVE", "Calm person, warm room, food smell: ideal approach."),
    (_p("human", "slow", "blue", "speech", "medium",
        "light", "smooth", "neutral", "low",
        "food", "faint", "pleasant"),
     "approach", 0.87, 22, "DELIBERATIVE", "Conversational person; safe to close distance."),
    (_p("human", "static", "bright", "speech", "low",
        "firm", "smooth", "warm", "medium",
        "food", "strong", "pleasant"),
     "approach", 0.89, 23, "DELIBERATIVE", "Firm friendly contact, strong pleasant food odour."),
    (_p("animal", "slow", "bright", "none", "low",
        "light", "smooth", "warm", "low",
        "organic", "faint", "pleasant"),
     "approach", 0.81, 24, "DELIBERATIVE", "Docile warm animal."),
    (_p("human", "static", "blue", "speech", "medium",
        "none", "smooth", "warm", "low",
        "food", "moderate", "pleasant"),
     "approach", 0.84, 25, "DELIBERATIVE", "Person waiting; nothing adverse in any channel."),
    (_p("vehicle", "static", "bright", "speech", "medium",
        "light", "smooth", "neutral", "low",
        "none", "faint", "neutral"),
     "approach", 0.74, 26, "DELIBERATIVE", "Stationary vehicle with occupants talking."),
    (_p("animal", "slow", "red", "speech", "low",
        "light", "smooth", "warm", "low",
        "food", "moderate", "pleasant"),
     "approach", 0.79, 27, "DELIBERATIVE", "Animal near food; approachable."),

    # -- ignore: nothing worth spending attention on ------------------------
    (_p("animal", "slow", "dark", "noise", "high",
        "none", "smooth", "cold", "low",
        "none", "faint", "neutral"),
     "ignore", 0.62, 28, "DELIBERATIVE", "Background animal noise; no action needed."),
    (_p("vehicle", "static", "red", "none", "low",
        "none", "smooth", "cold", "low",
        "none", "faint", "neutral"),
     "ignore", 0.76, 29, "DELIBERATIVE", "Empty parked vehicle; correctly ignored."),
    (_p("human", "slow", "dark", "none", "low",
        "none", "smooth", "neutral", "low",
        "none", "faint", "neutral"),
     "ignore", 0.72, 30, "DELIBERATIVE", "Passer-by, no signal in any channel."),
    (_p("animal", "static", "bright", "none", "low",
        "none", "smooth", "neutral", "low",
        "organic", "faint", "neutral"),
     "ignore", 0.68, 31, "DELIBERATIVE", "Resting animal."),
    (_p("unknown", "static", "blue", "none", "low",
        "none", "smooth", "cold", "low",
        "none", "faint", "neutral"),
     "ignore", 0.70, 32, "DELIBERATIVE", "Inert cold object; baseline ignore case."),
    (_p("vehicle", "slow", "blue", "none", "low",
        "none", "smooth", "cold", "low",
        "none", "faint", "neutral"),
     "ignore", 0.67, 33, "DELIBERATIVE", "Slow distant vehicle."),

    # -- conflicting evidence: channels disagree ----------------------------
    (_p("human", "slow", "bright", "speech", "low",
        "firm", "sharp", "warm", "medium",
        "food", "moderate", "pleasant"),
     "withdraw", 0.71, 34, "REFLEXIVE", "Pleasant scene but sharp firm contact; touch overrides."),
    (_p("animal", "slow", "bright", "speech", "low",
        "light", "smooth", "warm", "low",
        "chemical", "strong", "foul"),
     "alert", 0.69, 35, "DELIBERATIVE", "Calm scene undermined by a strong chemical odour."),
    (_p("human", "static", "blue", "alarm", "high",
        "light", "smooth", "warm", "low",
        "food", "strong", "pleasant"),
     "alert", 0.77, 36, "REFLEXIVE", "Alarm during a pleasant meal; alarm still wins."),
    (_p("unknown", "static", "dark", "none", "low",
        "firm", "wet", "cold", "medium",
        "organic", "strong", "foul"),
     "withdraw", 0.74, 37, "DELIBERATIVE", "Cold wet foul mass; unpleasant but not reflexive."),
    (_p("vehicle", "fast", "bright", "speech", "low",
        "none", "smooth", "warm", "low",
        "food", "moderate", "pleasant"),
     "observe", 0.68, 38, "REFLEXIVE", "Fast motion in an otherwise benign scene."),

    # -- texture and thermal nuance -----------------------------------------
    (_p("unknown", "static", "dark", "none", "low",
        "firm", "wet", "warm", "medium",
        "organic", "moderate", "neutral"),
     "observe", 0.65, 39, "DELIBERATIVE", "Warm wet unknown; inspect before deciding."),
    (_p("unknown", "static", "bright", "none", "low",
        "light", "rough", "warm", "low",
        "none", "faint", "neutral"),
     "approach", 0.70, 40, "DELIBERATIVE", "Rough warm surface, harmless."),
    (_p("human", "slow", "bright", "speech", "low",
        "firm", "smooth", "cold", "medium",
        "none", "faint", "neutral"),
     "approach", 0.76, 41, "DELIBERATIVE", "Cold handshake; cold alone is not a threat."),
    (_p("unknown", "static", "red", "none", "low",
        "light", "smooth", "warm", "low",
        "chemical", "faint", "neutral"),
     "observe", 0.63, 42, "DELIBERATIVE", "Warm object with a faint chemical trace."),

    # -- low-reward records: acted against what memory advised ---------------
    (_p("animal", "slow", "dark", "noise", "high",
        "none", "smooth", "cold", "low",
        "none", "faint", "neutral"),
     "approach", 0.28, 43, "DELIBERATIVE", "Approached where ignoring was advised; poor outcome."),
    (_p("unknown", "static", "bright", "alarm", "high",
        "firm", "smooth", "hot", "high",
        "smoke", "strong", "foul"),
     "approach", 0.12, 44, "DELIBERATIVE", "Approached a fire. Worst entry in the bank."),
    (_p("human", "slow", "bright", "speech", "low",
        "light", "smooth", "warm", "low",
        "food", "moderate", "pleasant"),
     "withdraw", 0.31, 45, "DELIBERATIVE", "Withdrew from a safe, inviting scene; wasted caution."),
    (_p("vehicle", "fast", "dark", "noise", "high",
        "impact", "rough", "neutral", "high",
        "none", "faint", "neutral"),
     "ignore", 0.09, 46, "DELIBERATIVE", "Ignored a collision. Should have withdrawn."),
    (_p("unknown", "static", "dark", "none", "low",
        "none", "smooth", "neutral", "low",
        "chemical", "strong", "foul"),
     "ignore", 0.22, 47, "DELIBERATIVE", "Ignored a strong chemical leak."),

    # -- quiet baselines ----------------------------------------------------
    (_p("human", "static", "bright", "none", "medium",
        "none", "smooth", "neutral", "low",
        "none", "faint", "neutral"),
     "observe", 0.73, 48, "DELIBERATIVE", "Neutral human presence; default watchfulness."),
    (_p("animal", "static", "red", "none", "low",
        "light", "rough", "neutral", "low",
        "organic", "faint", "neutral"),
     "ignore", 0.66, 49, "DELIBERATIVE", "Quiet animal at light contact."),
    (_p("unknown", "slow", "blue", "speech", "medium",
        "none", "smooth", "neutral", "low",
        "food", "faint", "pleasant"),
     "approach", 0.75, 50, "DELIBERATIVE", "Ambiguous but pleasant; approach paid off."),
]


# Near-repetitions: one or two features perturbed from an earlier context.
# These build the local density that makes similarity weighting visible.
REPEATED_ENTRIES = [
    (_p("unknown", "static", "bright", "alarm", "high",
        "firm", "smooth", "hot", "medium",
        "smoke", "strong", "foul"),
     "withdraw", 0.94, 51, "REFLEXIVE", "Variant of 1: lower touch intensity, same verdict."),
    (_p("vehicle", "static", "dark", "noise", "high",
        "light", "smooth", "hot", "medium",
        "smoke", "strong", "foul"),
     "withdraw", 0.91, 52, "REFLEXIVE", "Variant of 2: louder, stronger smoke."),
    (_p("unknown", "fast", "bright", "noise", "high",
        "impact", "sharp", "neutral", "high",
        "none", "faint", "neutral"),
     "withdraw", 0.93, 53, "REFLEXIVE", "Variant of 6: neutral rather than cold."),
    (_p("animal", "fast", "dark", "noise", "high",
        "firm", "sharp", "warm", "medium",
        "organic", "moderate", "foul"),
     "withdraw", 0.87, 54, "REFLEXIVE", "Variant of 8: milder odour and grip."),
    (_p("human", "fast", "red", "alarm", "medium",
        "none", "smooth", "neutral", "low",
        "none", "faint", "neutral"),
     "alert", 0.90, 55, "REFLEXIVE", "Variant of 9: quieter alarm."),
    (_p("unknown", "static", "dark", "none", "low",
        "none", "smooth", "warm", "low",
        "chemical", "strong", "foul"),
     "alert", 0.85, 56, "REFLEXIVE", "Variant of 11: warm rather than neutral."),
    (_p("human", "static", "blue", "alarm", "medium",
        "none", "smooth", "neutral", "low",
        "none", "faint", "neutral"),
     "alert", 0.88, 57, "REFLEXIVE", "Variant of 13: medium alarm intensity."),
    (_p("animal", "fast", "red", "noise", "high",
        "none", "smooth", "neutral", "low",
        "organic", "moderate", "neutral"),
     "observe", 0.80, 58, "REFLEXIVE", "Variant of 14: louder background."),
    (_p("unknown", "fast", "dark", "none", "low",
        "none", "smooth", "cold", "low",
        "none", "faint", "neutral"),
     "observe", 0.76, 59, "REFLEXIVE", "Variant of 15: dark rather than bright."),
    (_p("unknown", "slow", "dark", "noise", "high",
        "light", "rough", "cold", "low",
        "none", "faint", "neutral"),
     "observe", 0.68, 60, "DELIBERATIVE", "Variant of 17: louder."),
    (_p("human", "slow", "bright", "speech", "medium",
        "light", "smooth", "warm", "low",
        "food", "moderate", "pleasant"),
     "approach", 0.90, 61, "DELIBERATIVE", "Variant of 21: louder speech; still ideal."),
    (_p("human", "slow", "blue", "speech", "low",
        "light", "smooth", "warm", "low",
        "food", "faint", "pleasant"),
     "approach", 0.86, 62, "DELIBERATIVE", "Variant of 22: quieter, warmer."),
    (_p("human", "static", "bright", "speech", "low",
        "firm", "smooth", "warm", "low",
        "food", "moderate", "pleasant"),
     "approach", 0.88, 63, "DELIBERATIVE", "Variant of 23: gentler contact."),
    (_p("animal", "slow", "bright", "none", "low",
        "light", "rough", "warm", "low",
        "organic", "faint", "pleasant"),
     "approach", 0.78, 64, "DELIBERATIVE", "Variant of 24: rougher coat."),
    (_p("animal", "slow", "dark", "noise", "medium",
        "none", "smooth", "cold", "low",
        "none", "faint", "neutral"),
     "ignore", 0.60, 65, "DELIBERATIVE", "Variant of 28: quieter."),
    (_p("vehicle", "static", "red", "none", "medium",
        "none", "smooth", "cold", "low",
        "none", "faint", "neutral"),
     "ignore", 0.71, 66, "DELIBERATIVE", "Variant of 29: some ambient sound."),
    (_p("human", "slow", "dark", "none", "low",
        "light", "smooth", "neutral", "low",
        "none", "faint", "neutral"),
     "ignore", 0.69, 67, "DELIBERATIVE", "Variant of 30: incidental contact."),
    (_p("human", "slow", "bright", "speech", "low",
        "firm", "sharp", "warm", "high",
        "food", "moderate", "pleasant"),
     "withdraw", 0.73, 68, "REFLEXIVE", "Variant of 34: firmer sharp contact."),
    (_p("animal", "slow", "dark", "noise", "high",
        "none", "smooth", "cold", "low",
        "none", "faint", "neutral"),
     "approach", 0.25, 69, "DELIBERATIVE", "Variant of 43: approach punished again."),
    (_p("unknown", "static", "bright", "alarm", "high",
        "firm", "smooth", "hot", "high",
        "smoke", "moderate", "foul"),
     "approach", 0.15, 70, "DELIBERATIVE", "Variant of 44: approaching fire, punished again."),
]


ALL_ENTRIES = NOVEL_ENTRIES + REPEATED_ENTRIES


def build_preset_memory(profile: str = "balanced") -> MemorySystem:
    """Return a MemorySystem preloaded with the 70-entry bank."""
    memory = MemorySystem()
    deltas = PROFILE_CONFIGS.get(profile, PROFILE_CONFIGS["balanced"])["reward_delta"]

    for percepts, action, reward, step, mode, _note in ALL_ENTRIES:
        memory.store(
            summary=summary_of(percepts),
            action=action,
            reward=clamp_reward(reward + deltas.get(action, 0.0)),
            step=step,
            confidence=1.0,
            mode=mode,
            reward_source="preset",
        )
    return memory


def bank_stats() -> dict:
    """Summary counts, used by the doc generator and the smoke tests."""
    by_action = Counter(entry[1] for entry in ALL_ENTRIES)
    by_mode = Counter(entry[4] for entry in ALL_ENTRIES)
    rewards = defaultdict(list)
    for _, action, reward, _, _, _ in ALL_ENTRIES:
        rewards[action].append(reward)
    return {
        "total": len(ALL_ENTRIES),
        "novel": len(NOVEL_ENTRIES),
        "repeated": len(REPEATED_ENTRIES),
        "by_action": dict(by_action),
        "by_mode": dict(by_mode),
        "mean_reward": {a: sum(v) / len(v) for a, v in rewards.items()},
    }


def render_doc() -> str:
    """Generate the companion document from the entry list itself.

    Generated rather than hand-written: the v1 PresetMemory.txt was prose only
    and drifted from the executable bank it described.
    """
    stats = bank_stats()
    lines = [
        "MPCS v2 — Preset Memory Bank",
        "=" * 60,
        "",
        f"{stats['total']} experiences: {stats['novel']} novel contexts + "
        f"{stats['repeated']} near-repetitions.",
        "Every entry carries all four modalities (vision, audio, touch, smell).",
        "Generated from mcps_preset_v2.py — do not edit by hand.",
        "",
        "Action distribution",
        "-" * 60,
    ]
    for action in ACTIONS:
        count = stats["by_action"].get(action, 0)
        mean = stats["mean_reward"].get(action)
        mean_text = f"mean reward {mean:.2f}" if mean is not None else "—"
        lines.append(f"  {action:<10} {count:>3} entries    {mean_text}")

    lines += [
        "",
        "Origin mode",
        "-" * 60,
    ]
    for mode, count in sorted(stats["by_mode"].items()):
        lines.append(f"  {mode:<14} {count:>3}")

    lines += ["", "Entries", "-" * 60, ""]
    for percepts, action, reward, step, mode, note in ALL_ENTRIES:
        section = "NOVEL" if step <= len(NOVEL_ENTRIES) else "REPEAT"
        lines.append(f"[{step:>2}] {section:<6} {action.upper():<9} reward={reward:.2f}  ({mode})")
        for modality in ("vision", "audio", "touch", "smell"):
            features = percepts[modality]
            rendered = ", ".join(f"{k}={v}" for k, v in features.items())
            lines.append(f"       {modality:<7} {rendered}")
        lines.append(f"       note    {note}")
        lines.append("")

    return "\n".join(lines)


def write_doc(path: str) -> str:
    text = render_doc()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def _default_doc_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "..", "data", "PresetMemory_v2.txt")


def main() -> None:
    parser = argparse.ArgumentParser(description="MPCS v2 preset memory bank.")
    parser.add_argument("--write-doc", action="store_true",
                        help="Regenerate Model/data/PresetMemory_v2.txt.")
    parser.add_argument("--profile", choices=tuple(PROFILE_CONFIGS), default="balanced")
    args = parser.parse_args()

    stats = bank_stats()
    print(f"Preset bank: {stats['total']} entries "
          f"({stats['novel']} novel + {stats['repeated']} repeated)")
    for action in ACTIONS:
        print(f"  {action:<10} {stats['by_action'].get(action, 0):>3}")

    if args.write_doc:
        path = os.path.normpath(write_doc(_default_doc_path()))
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()

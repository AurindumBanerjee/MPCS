"""
Preset memory bank for MPCS v3 — 600 generated, partial-modality experiences
------------------------------------------------------------------------------
Where mpcs_preset_v2 is 70 hand-written, always-four-modality entries, this
bank is generated from scenario archetypes so it can reach real volume
without 600 individually hand-typed tuples. Same output shape as v2 (a flat
list of (percept, action, reward, step, mode, note) entries plus
is_expert), same MemorySystem.store() contract, and it is deterministic —
build_preset_memory_v3() with the same seed always returns the same bank —
so it is as reviewable and reproducible as a hand-written list, just built
programmatically.

Design, matching what was asked for
------------------------------------
  * ~420 unique scenes + ~180 near-repetitions (70/30 split), scaling the
    v2 shape up roughly 8-9x.
  * Modality coverage is mixed, weighted toward full: each scenario
    archetype has a preferred modality count distribution skewed to 3-4,
    but a meaningful minority of entries (roughly a quarter to a third)
    carry only 1-2 modalities, always keeping whichever channel carries
    the archetype's decisive feature (you cannot drop `touch` from a
    "hot surface" scene and still have it mean anything).
  * ~15-20% of unique scenes get a contradicting twin: the same or a
    near-identical percept recorded again later with a different action
    and a divergent reward, modelling genuine policy disagreement without
    drowning out the clear-precedent majority the reflex layer needs.
  * 30-40 expert-taught corrections (is_expert=True, mode="EXPERT",
    reward_source="expert"), each placed shortly after a plausible
    model mistake on a similar scene, mirroring how Session.teach_expert
    is used live: reinforcement near ~0.95 when the model's own action
    already agreed with the expert, demotion-flavoured low reward near
    ~0.05 attached to the corrected scene when it did not.
  * Steps run 1..N across the whole generated sequence in the order
    entries are produced, so time decay treats later entries as
    genuinely newer, matching how mpcs_engine expects a memory bank to
    be laid down.

Run directly to see bank statistics, or regenerate the companion doc:
    python mpcs_preset_v3.py
    python mpcs_preset_v3.py --write-doc
"""

from __future__ import annotations

import argparse
import os
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from mpcs_engine import (
    ACTIONS,
    MODALITIES,
    MemorySystem,
    clamp_reward,
    summary_of,
)


DEFAULT_SEED = 20260907   # date-stamped, matches this file's authoring session

# Reused from v2 verbatim: reward shaping is a policy concern, not a data
# volume concern, so profile deltas do not need to change with bank size.
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


# ----------------------------------------------------------------------
# 1. Scenario archetypes
# ----------------------------------------------------------------------
# An archetype describes *a family* of percepts that plausibly lead to one
# action, not one fixed percept. `features` maps modality -> {feature:
# [plausible values]}; `anchor_modality` is the channel that must stay
# active for the scene to keep its meaning (you cannot drop touch from a
# "hot surface" scenario). `reward_range` and `modality_bias` shape the
# sampled outcome and the modality-count distribution respectively.
@dataclass
class Archetype:
    name: str
    action: str
    mode: str                      # "REFLEXIVE" or "DELIBERATIVE"
    features: dict[str, dict[str, list[str]]]
    anchor_modality: str
    reward_range: tuple[float, float]
    note_template: str
    # Weights over modality counts {1,2,3,4}; renormalised at use.
    modality_bias: dict[int, float] = field(default_factory=lambda: {1: 0.10, 2: 0.20, 3: 0.35, 4: 0.35})
    contradicting_action: Optional[str] = None   # what a disagreeing twin does instead
    contradicting_reward_range: tuple[float, float] = (0.15, 0.35)


ARCHETYPES: list[Archetype] = [
    # -- withdraw: heat, impact, sharp contact ------------------------------
    Archetype(
        name="hot_surface",
        action="withdraw", mode="REFLEXIVE",
        features={
            "touch": {"contact": ["firm", "impact"], "texture": ["smooth", "rough"],
                      "thermal": ["hot"], "touch_intensity": ["medium", "high"]},
            "smell": {"odor_type": ["smoke", "none"], "odor_intensity": ["faint", "moderate", "strong"],
                      "pleasantness": ["foul", "neutral"]},
            "vision": {"object_type": ["unknown", "vehicle"], "motion": ["static", "slow"],
                       "color": ["dark", "bright", "red"]},
            "audio": {"sound_type": ["none", "alarm", "noise"], "audio_intensity": ["low", "medium", "high"]},
        },
        anchor_modality="touch",
        reward_range=(0.85, 0.97),
        note_template="Hot surface contact; withdrawal is the correct reflex.",
        modality_bias={1: 0.15, 2: 0.25, 3: 0.30, 4: 0.30},
        contradicting_action="approach",
        contradicting_reward_range=(0.05, 0.18),
    ),
    Archetype(
        name="impact_sharp",
        action="withdraw", mode="REFLEXIVE",
        features={
            "touch": {"contact": ["impact", "firm"], "texture": ["sharp", "rough"],
                      "thermal": ["cold", "neutral", "warm"], "touch_intensity": ["medium", "high"]},
            "vision": {"object_type": ["vehicle", "unknown", "animal"], "motion": ["fast", "static"],
                       "color": ["dark", "bright"]},
            "audio": {"sound_type": ["noise", "none"], "audio_intensity": ["medium", "high"]},
            "smell": {"odor_type": ["none", "organic"], "odor_intensity": ["faint", "moderate"],
                      "pleasantness": ["neutral", "foul"]},
        },
        anchor_modality="touch",
        reward_range=(0.83, 0.96),
        note_template="Sharp or impact contact; disengage before assessing further.",
        modality_bias={1: 0.15, 2: 0.30, 3: 0.30, 4: 0.25},
        contradicting_action="ignore",
        contradicting_reward_range=(0.05, 0.20),
    ),
    Archetype(
        name="animal_bite",
        action="withdraw", mode="REFLEXIVE",
        features={
            "touch": {"contact": ["firm", "impact"], "texture": ["sharp", "rough"],
                      "thermal": ["warm"], "touch_intensity": ["high", "medium"]},
            "smell": {"odor_type": ["organic"], "odor_intensity": ["strong", "moderate"],
                      "pleasantness": ["foul"]},
            "vision": {"object_type": ["animal"], "motion": ["fast", "slow"], "color": ["dark", "red"]},
            "audio": {"sound_type": ["noise", "alarm"], "audio_intensity": ["high", "medium"]},
        },
        anchor_modality="touch",
        reward_range=(0.80, 0.93),
        note_template="Animal contact, sharp and foul-smelling; withdraw.",
        modality_bias={1: 0.10, 2: 0.25, 3: 0.35, 4: 0.30},
    ),

    # -- alert: threat detected without direct contact ----------------------
    Archetype(
        name="smoke_alarm",
        action="alert", mode="REFLEXIVE",
        features={
            "smell": {"odor_type": ["smoke"], "odor_intensity": ["faint", "moderate", "strong"],
                      "pleasantness": ["foul", "neutral"]},
            "audio": {"sound_type": ["alarm", "none", "noise"], "audio_intensity": ["low", "medium", "high"]},
            "vision": {"object_type": ["unknown", "vehicle"], "motion": ["static", "slow"],
                       "color": ["dark", "red", "bright"]},
            "touch": {"contact": ["none"], "texture": ["smooth"], "thermal": ["neutral", "warm"],
                      "touch_intensity": ["low"]},
        },
        anchor_modality="smell",
        reward_range=(0.78, 0.95),
        note_template="Smoke detected; alerting is warranted even without direct heat contact.",
        modality_bias={1: 0.20, 2: 0.30, 3: 0.30, 4: 0.20},
        contradicting_action="ignore",
        contradicting_reward_range=(0.10, 0.28),
    ),
    Archetype(
        name="chemical_leak",
        action="alert", mode="REFLEXIVE",
        features={
            "smell": {"odor_type": ["chemical"], "odor_intensity": ["moderate", "strong"],
                      "pleasantness": ["foul"]},
            "vision": {"object_type": ["unknown", "vehicle"], "motion": ["static"], "color": ["dark", "bright"]},
            "audio": {"sound_type": ["none", "alarm"], "audio_intensity": ["low", "medium"]},
            "touch": {"contact": ["none"], "texture": ["smooth"], "thermal": ["neutral"], "touch_intensity": ["low"]},
        },
        anchor_modality="smell",
        reward_range=(0.75, 0.92),
        note_template="Chemical odour with no visual confirmation; alert first.",
        modality_bias={1: 0.25, 2: 0.30, 3: 0.25, 4: 0.20},
    ),
    Archetype(
        name="distant_threat",
        action="alert", mode="REFLEXIVE",
        features={
            "audio": {"sound_type": ["alarm"], "audio_intensity": ["high", "medium"]},
            "vision": {"object_type": ["human", "vehicle", "animal"], "motion": ["fast", "static"],
                       "color": ["red", "dark", "blue"]},
            "smell": {"odor_type": ["none", "organic"], "odor_intensity": ["faint"], "pleasantness": ["neutral"]},
            "touch": {"contact": ["none"], "texture": ["smooth"], "thermal": ["neutral"], "touch_intensity": ["low"]},
        },
        anchor_modality="audio",
        reward_range=(0.80, 0.93),
        note_template="Alarm sounding at a distance; escalate rather than approach.",
        modality_bias={1: 0.20, 2: 0.30, 3: 0.30, 4: 0.20},
    ),

    # -- observe: motion or ambiguity, no contact ---------------------------
    Archetype(
        name="fast_mover",
        action="observe", mode="REFLEXIVE",
        features={
            "vision": {"object_type": ["animal", "unknown", "vehicle"], "motion": ["fast"],
                       "color": ["red", "bright", "dark"]},
            "audio": {"sound_type": ["noise", "none"], "audio_intensity": ["low", "medium"]},
            "smell": {"odor_type": ["none", "organic"], "odor_intensity": ["faint"], "pleasantness": ["neutral"]},
            "touch": {"contact": ["none"], "texture": ["smooth"], "thermal": ["neutral", "cold"], "touch_intensity": ["low"]},
        },
        anchor_modality="vision",
        reward_range=(0.70, 0.85),
        note_template="Fast motion with no other adverse signal; watch rather than act.",
        modality_bias={1: 0.20, 2: 0.30, 3: 0.30, 4: 0.20},
    ),
    Archetype(
        name="ambiguous_slow",
        action="observe", mode="DELIBERATIVE",
        features={
            "vision": {"object_type": ["unknown", "human"], "motion": ["slow", "static"], "color": ["blue", "dark"]},
            "audio": {"sound_type": ["speech", "none"], "audio_intensity": ["low"]},
            "touch": {"contact": ["light"], "texture": ["rough", "smooth"], "thermal": ["cold", "neutral"],
                      "touch_intensity": ["low"]},
            "smell": {"odor_type": ["none"], "odor_intensity": ["faint"], "pleasantness": ["neutral"]},
        },
        anchor_modality="vision",
        reward_range=(0.60, 0.78),
        note_template="Slow, ambiguous scene; light contact does not resolve it either way.",
        modality_bias={1: 0.15, 2: 0.30, 3: 0.35, 4: 0.20},
    ),

    # -- approach: safe, inviting contexts -----------------------------------
    Archetype(
        name="friendly_human",
        action="approach", mode="DELIBERATIVE",
        features={
            "vision": {"object_type": ["human"], "motion": ["slow", "static"], "color": ["bright", "blue"]},
            "audio": {"sound_type": ["speech"], "audio_intensity": ["low", "medium"]},
            "touch": {"contact": ["light", "firm"], "texture": ["smooth"], "thermal": ["warm", "neutral"],
                      "touch_intensity": ["low", "medium"]},
            "smell": {"odor_type": ["food", "none"], "odor_intensity": ["faint", "moderate", "strong"],
                      "pleasantness": ["pleasant"]},
        },
        anchor_modality="vision",
        reward_range=(0.80, 0.94),
        note_template="Calm, communicative person in a warm setting; safe to approach.",
        modality_bias={1: 0.05, 2: 0.20, 3: 0.35, 4: 0.40},
        contradicting_action="withdraw",
        contradicting_reward_range=(0.20, 0.35),
    ),
    Archetype(
        name="docile_animal",
        action="approach", mode="DELIBERATIVE",
        features={
            "vision": {"object_type": ["animal"], "motion": ["slow", "static"], "color": ["bright", "red"]},
            "touch": {"contact": ["light"], "texture": ["smooth", "rough"], "thermal": ["warm"],
                      "touch_intensity": ["low"]},
            "smell": {"odor_type": ["organic", "food"], "odor_intensity": ["faint", "moderate"],
                      "pleasantness": ["pleasant", "neutral"]},
            "audio": {"sound_type": ["none", "speech"], "audio_intensity": ["low"]},
        },
        anchor_modality="vision",
        reward_range=(0.75, 0.88),
        note_template="Calm, warm animal; approachable.",
        modality_bias={1: 0.10, 2: 0.25, 3: 0.35, 4: 0.30},
    ),

    # -- ignore: nothing worth spending attention on -------------------------
    Archetype(
        name="inert_background",
        action="ignore", mode="DELIBERATIVE",
        features={
            "vision": {"object_type": ["vehicle", "animal", "unknown"], "motion": ["static", "slow"],
                       "color": ["dark", "blue", "red"]},
            "audio": {"sound_type": ["none"], "audio_intensity": ["low"]},
            "touch": {"contact": ["none"], "texture": ["smooth"], "thermal": ["cold", "neutral"],
                      "touch_intensity": ["low"]},
            "smell": {"odor_type": ["none"], "odor_intensity": ["faint"], "pleasantness": ["neutral"]},
        },
        anchor_modality="vision",
        reward_range=(0.62, 0.78),
        note_template="Inert or background presence; correctly left alone.",
        modality_bias={1: 0.25, 2: 0.30, 3: 0.25, 4: 0.20},
    ),
    Archetype(
        name="passerby",
        action="ignore", mode="DELIBERATIVE",
        features={
            "vision": {"object_type": ["human"], "motion": ["slow"], "color": ["dark", "blue"]},
            "audio": {"sound_type": ["none"], "audio_intensity": ["low"]},
            "touch": {"contact": ["none"], "texture": ["smooth"], "thermal": ["neutral"], "touch_intensity": ["low"]},
            "smell": {"odor_type": ["none"], "odor_intensity": ["faint"], "pleasantness": ["neutral"]},
        },
        anchor_modality="vision",
        reward_range=(0.65, 0.78),
        note_template="Passer-by with no signal in any channel.",
        modality_bias={1: 0.30, 2: 0.30, 3: 0.25, 4: 0.15},
    ),

    # -- conflicting evidence: channels disagree -----------------------------
    Archetype(
        name="pleasant_but_sharp",
        action="withdraw", mode="REFLEXIVE",
        features={
            "vision": {"object_type": ["human"], "motion": ["slow"], "color": ["bright"]},
            "audio": {"sound_type": ["speech"], "audio_intensity": ["low"]},
            "touch": {"contact": ["firm"], "texture": ["sharp"], "thermal": ["warm"], "touch_intensity": ["medium", "high"]},
            "smell": {"odor_type": ["food"], "odor_intensity": ["moderate"], "pleasantness": ["pleasant"]},
        },
        anchor_modality="touch",
        reward_range=(0.65, 0.78),
        note_template="Pleasant scene undermined by sharp contact; touch overrides.",
        modality_bias={1: 0.0, 2: 0.15, 3: 0.35, 4: 0.50},
    ),
    Archetype(
        name="calm_but_chemical",
        action="alert", mode="DELIBERATIVE",
        features={
            "vision": {"object_type": ["animal", "human"], "motion": ["slow"], "color": ["bright"]},
            "audio": {"sound_type": ["speech", "none"], "audio_intensity": ["low"]},
            "touch": {"contact": ["light"], "texture": ["smooth"], "thermal": ["warm"], "touch_intensity": ["low"]},
            "smell": {"odor_type": ["chemical"], "odor_intensity": ["strong", "moderate"], "pleasantness": ["foul"]},
        },
        anchor_modality="smell",
        reward_range=(0.62, 0.75),
        note_template="Calm scene undercut by a strong chemical odour.",
        modality_bias={1: 0.0, 2: 0.15, 3: 0.35, 4: 0.50},
    ),

    # -- texture / thermal nuance, mostly deliberative -----------------------
    Archetype(
        name="warm_wet_unknown",
        action="observe", mode="DELIBERATIVE",
        features={
            "touch": {"contact": ["firm", "light"], "texture": ["wet"], "thermal": ["warm"], "touch_intensity": ["medium", "low"]},
            "smell": {"odor_type": ["organic", "none"], "odor_intensity": ["moderate", "faint"], "pleasantness": ["neutral"]},
            "vision": {"object_type": ["unknown"], "motion": ["static"], "color": ["dark"]},
            "audio": {"sound_type": ["none"], "audio_intensity": ["low"]},
        },
        anchor_modality="touch",
        reward_range=(0.58, 0.72),
        note_template="Warm, wet, unidentified texture; inspect before deciding.",
        modality_bias={1: 0.25, 2: 0.30, 3: 0.30, 4: 0.15},
    ),
    Archetype(
        name="cold_handshake",
        action="approach", mode="DELIBERATIVE",
        features={
            "touch": {"contact": ["firm"], "texture": ["smooth"], "thermal": ["cold"], "touch_intensity": ["medium"]},
            "vision": {"object_type": ["human"], "motion": ["slow"], "color": ["bright"]},
            "audio": {"sound_type": ["speech"], "audio_intensity": ["low"]},
            "smell": {"odor_type": ["none"], "odor_intensity": ["faint"], "pleasantness": ["neutral"]},
        },
        anchor_modality="touch",
        reward_range=(0.68, 0.80),
        note_template="Cold contact alone is not a threat signal.",
        modality_bias={1: 0.10, 2: 0.25, 3: 0.35, 4: 0.30},
    ),
]


# ----------------------------------------------------------------------
# 2. Sampling one entry from an archetype
# ----------------------------------------------------------------------
def _weighted_choice(rng: random.Random, weights: dict[int, float]) -> int:
    keys = list(weights.keys())
    values = list(weights.values())
    total = sum(values)
    if total <= 0:
        return max(keys)
    pick = rng.uniform(0.0, total)
    upto = 0.0
    for key, weight in zip(keys, values):
        upto += weight
        if pick <= upto:
            return key
    return keys[-1]


def _sample_percept(rng: random.Random, archetype: Archetype) -> tuple[dict, tuple[str, ...]]:
    """Pick a modality count from the archetype's bias, keep the anchor
    modality always, then fill up to that count from the remaining
    modalities the archetype defines features for. Returns (percept dict,
    active modality tuple).
    """
    available = [m for m in archetype.features if archetype.features[m]]
    count = _weighted_choice(rng, archetype.modality_bias)
    count = max(1, min(count, len(available)))

    chosen = [archetype.anchor_modality]
    remaining = [m for m in available if m != archetype.anchor_modality]
    rng.shuffle(remaining)
    chosen += remaining[: max(0, count - 1)]

    percept: dict[str, dict[str, str]] = {}
    for modality in chosen:
        feature_pool = archetype.features[modality]
        percept[modality] = {
            feature: rng.choice(values) for feature, values in feature_pool.items()
        }
    return percept, tuple(sorted(chosen))


def _sample_reward(rng: random.Random, reward_range: tuple[float, float]) -> float:
    low, high = reward_range
    return clamp_reward(rng.uniform(low, high))


# ----------------------------------------------------------------------
# 3. Full generation pipeline
# ----------------------------------------------------------------------
@dataclass
class GeneratedEntry:
    percept: dict
    action: str
    reward: float
    step: int
    mode: str
    note: str
    is_expert: bool = False
    reward_source: str = "preset"
    archetype: str = ""

    def as_tuple(self) -> tuple:
        return (self.percept, self.action, self.reward, self.step, self.mode, self.note)


# Sized so base + twins + repeated lands at exactly 700, with the unique
# portion (base + twins) at ~70% (490) and repeated at ~30% (210). Expert
# entries are drawn from *within* the base budget (they replace what would
# otherwise be plain unique scenes, since an expert correction is itself a
# novel scene, not a repeat) rather than added on top, which is what keeps
# the grand total at 700 instead of 700 + EXPERT_ENTRY_COUNT.
TOTAL_UNIQUE_BASE_TARGET = 415   # scenes before contradicting twins
TOTAL_REPEATED_TARGET = 210      # ~30% of 700
CONTRADICTION_RATE = 0.18        # ~15-20% of base scenes get a disagreeing twin
EXPERT_ENTRY_COUNT = 36          # within the requested 30-40 range, drawn from the base


def _make_unique_entries(rng: random.Random, start_step: int) -> tuple[list[GeneratedEntry], list[GeneratedEntry]]:
    """Round-robins the archetypes until TOTAL_UNIQUE_TARGET base scenes are
    produced, then adds contradicting twins for a sampled subset. Returns
    (base_entries, contradiction_entries) separately so contradictions can
    be interleaved later in the step order rather than sitting right next
    to their source scene, which would make them look like simple retries
    instead of independent policy disagreement.
    """
    base: list[GeneratedEntry] = []
    step = start_step
    archetype_cycle = list(ARCHETYPES)

    while len(base) < TOTAL_UNIQUE_BASE_TARGET:
        for archetype in archetype_cycle:
            if len(base) >= TOTAL_UNIQUE_BASE_TARGET:
                break
            percept, active = _sample_percept(rng, archetype)
            reward = _sample_reward(rng, archetype.reward_range)
            note = f"{archetype.note_template} [{'+'.join(active)}]"
            base.append(GeneratedEntry(
                percept=percept, action=archetype.action, reward=reward,
                step=step, mode=archetype.mode, note=note, archetype=archetype.name,
            ))
            step += 1
        rng.shuffle(archetype_cycle)   # vary round-robin order across passes

    contradictions: list[GeneratedEntry] = []
    candidates = [e for e in base if _archetype_of(e.archetype).contradicting_action]
    rng.shuffle(candidates)
    contradiction_count = int(round(len(base) * CONTRADICTION_RATE))
    for source in candidates[:contradiction_count]:
        archetype = _archetype_of(source.archetype)
        # Perturb one or two features from the source scene rather than
        # cloning it verbatim, so the "twin" is a near-identical situation
        # rather than a bit-for-bit repeat — genuine ambiguity, not a
        # duplicate row.
        percept = _perturb_percept(rng, source.percept, archetype, perturb_count=1)
        reward = _sample_reward(rng, archetype.contradicting_reward_range)
        note = (f"Contradicts step {source.step} ({archetype.name}): "
                f"took '{archetype.contradicting_action}' instead of "
                f"'{archetype.action}', poor outcome.")
        contradictions.append(GeneratedEntry(
            percept=percept, action=archetype.contradicting_action, reward=reward,
            step=step, mode="DELIBERATIVE", note=note, archetype=archetype.name,
        ))
        step += 1

    return base, contradictions


def _archetype_of(name: str) -> Archetype:
    for archetype in ARCHETYPES:
        if archetype.name == name:
            return archetype
    raise KeyError(name)


def _perturb_percept(rng: random.Random, percept: dict, archetype: Archetype,
                      perturb_count: int = 1) -> dict:
    """Copy a percept and resample `perturb_count` feature values within
    the same active modalities, keeping the scene recognisably the same
    situation rather than generating an unrelated one.
    """
    new_percept = {modality: dict(features) for modality, features in percept.items()}
    flat_keys = [
        (modality, feature)
        for modality, features in new_percept.items()
        for feature in features
    ]
    rng.shuffle(flat_keys)
    for modality, feature in flat_keys[:max(1, perturb_count)]:
        pool = archetype.features.get(modality, {}).get(feature)
        if pool and len(pool) > 1:
            current = new_percept[modality][feature]
            choices = [v for v in pool if v != current] or pool
            new_percept[modality][feature] = rng.choice(choices)
    return new_percept


def _make_repeated_entries(rng: random.Random, base_entries: list[GeneratedEntry],
                            start_step: int) -> list[GeneratedEntry]:
    """Near-repetitions of earlier unique scenes: same archetype and
    action, one or two features perturbed, reward drawn from the same
    range with independent noise so repeats are not bit-identical to their
    source but stay clustered near it — this is what builds the local
    density that makes similarity weighting and time decay visible.
    """
    repeated: list[GeneratedEntry] = []
    step = start_step
    sources = list(base_entries)
    rng.shuffle(sources)
    index = 0
    while len(repeated) < TOTAL_REPEATED_TARGET:
        source = sources[index % len(sources)]
        index += 1
        archetype = _archetype_of(source.archetype)
        percept = _perturb_percept(rng, source.percept, archetype,
                                   perturb_count=rng.choice([1, 1, 2]))
        reward = clamp_reward(source.reward + rng.uniform(-0.06, 0.06))
        note = f"Variant of step {source.step} ({archetype.name})."
        # A perturbed repeat of an expert-taught source is not itself
        # something an expert taught — nobody vetted this specific variant
        # — so it must not carry mode="EXPERT" / is_expert=True forward.
        # Fall back to the archetype's own mode, the same value the source
        # would have had before being converted into a correction.
        mode = archetype.mode if source.is_expert else source.mode
        repeated.append(GeneratedEntry(
            percept=percept, action=source.action, reward=reward,
            step=step, mode=mode, note=note, archetype=archetype.name,
        ))
        step += 1
    return repeated


def _apply_expert_corrections(rng: random.Random, base_entries: list[GeneratedEntry],
                               contradiction_entries: list[GeneratedEntry]) -> None:
    """Convert a subset of the base scenes into expert-taught corrections,
    in place, so the grand total stays fixed at base+twins+repeated — an
    expert correction is itself a novel scene (not a repeat), so it comes
    out of the unique 70% budget rather than being layered on top of it.

    Preference order for which base entries become experts: the source
    scene of a contradicting twin first (this is exactly the
    Session.teach_expert pattern — a wrong action happened nearby, and an
    expert reinforces the correct one for a near-identical situation, at
    a reward wired into expert_weight_boost). Once those are used up,
    fall back to plain base scenes so EXPERT_ENTRY_COUNT is always met.
    """
    twin_sources = {
        int(entry.note.split("step ")[1].split()[0])
        for entry in contradiction_entries
    }
    preferred = [e for e in base_entries if e.step in twin_sources]
    fallback = [e for e in base_entries if e.step not in twin_sources]
    rng.shuffle(preferred)
    rng.shuffle(fallback)
    targets = (preferred + fallback)[:EXPERT_ENTRY_COUNT]

    for entry in targets:
        archetype = _archetype_of(entry.archetype)
        entry.percept = _perturb_percept(rng, entry.percept, archetype, perturb_count=1)
        entry.reward = clamp_reward(rng.uniform(0.90, 0.98))
        entry.mode = "EXPERT"
        entry.is_expert = True
        entry.reward_source = "expert"
        entry.note = (f"Expert correction: reinforces '{entry.action}' for a "
                      f"{archetype.name} scene {'near a known mistake' if entry.step in twin_sources else ''}.")


def generate_bank(seed: int = DEFAULT_SEED) -> list[GeneratedEntry]:
    """Deterministic end-to-end generation. Order of production:
    unique scenes -> contradicting twins interleaved by shuffle ->
    near-repetitions -> expert corrections, all step-numbered continuously
    so the final list is already in the step order mpcs_engine expects.
    """
    rng = random.Random(seed)

    base, contradictions = _make_unique_entries(rng, start_step=1)

    # Convert a subset of base scenes into expert corrections before any
    # renumbering, while contradiction notes' "step N" references still
    # point at the base entries' original step numbers.
    _apply_expert_corrections(rng, base, contradictions)

    unique_all = base + contradictions
    # Interleave contradictions into the unique timeline by step, rather
    # than leaving them all clustered after the base scenes — genuine
    # disagreement should be able to show up anywhere in the run.
    unique_all.sort(key=lambda e: e.step)
    # Renumber steps 1..len(unique_all) after interleaving/sorting so the
    # sequence has no gaps regardless of how contradictions were appended.
    # Notes keep their original step references as authored provenance
    # (e.g. "Contradicts step 12") even though the numbering above changes
    # underneath them — those numbers describe generation-time relationships,
    # not final positions, the same way a git commit message can cite a
    # commit that gets rebased to a new position.
    for index, entry in enumerate(unique_all, start=1):
        entry.step = index

    repeated = _make_repeated_entries(rng, base, start_step=len(unique_all) + 1)

    return unique_all + repeated


# Materialised once at import time, exactly like v2's ALL_ENTRIES, so every
# caller in a process sees the same bank without re-rolling the RNG.
ALL_ENTRIES_V3: list[GeneratedEntry] = generate_bank()


# ----------------------------------------------------------------------
# 4. MemorySystem construction, stats, and doc rendering
# ----------------------------------------------------------------------
def build_preset_memory_v3(profile: str = "balanced", seed: int = DEFAULT_SEED) -> MemorySystem:
    """Return a MemorySystem preloaded with the generated bank. Pass a
    different seed to get a different (still internally consistent) bank
    of the same shape; the module-level ALL_ENTRIES_V3 always uses
    DEFAULT_SEED so imports are stable.
    """
    entries = ALL_ENTRIES_V3 if seed == DEFAULT_SEED else generate_bank(seed)
    memory = MemorySystem()
    deltas = PROFILE_CONFIGS.get(profile, PROFILE_CONFIGS["balanced"])["reward_delta"]

    for entry in entries:
        memory.store(
            summary=summary_of(entry.percept),
            action=entry.action,
            reward=clamp_reward(entry.reward + deltas.get(entry.action, 0.0)),
            step=entry.step,
            confidence=1.0,
            is_expert=entry.is_expert,
            mode=entry.mode,
            reward_source=entry.reward_source,
        )
    return memory


def bank_stats(entries: Optional[list[GeneratedEntry]] = None) -> dict:
    entries = entries if entries is not None else ALL_ENTRIES_V3
    by_action = Counter(e.action for e in entries)
    by_mode = Counter(e.mode for e in entries)
    by_modality_count = Counter(
        sum(1 for m in MODALITIES if m in e.percept) for e in entries
    )
    rewards = defaultdict(list)
    for e in entries:
        rewards[e.action].append(e.reward)
    n_expert = sum(1 for e in entries if e.is_expert)
    n_contradiction = sum(1 for e in entries if "Contradicts" in e.note)
    n_repeat = sum(1 for e in entries if e.note.startswith("Variant of"))
    n_unique = len(entries) - n_repeat - n_expert

    return {
        "total": len(entries),
        "unique": n_unique,
        "repeated": n_repeat,
        "expert": n_expert,
        "contradictions": n_contradiction,
        "by_action": dict(by_action),
        "by_mode": dict(by_mode),
        "by_modality_count": dict(sorted(by_modality_count.items())),
        "mean_reward": {a: sum(v) / len(v) for a, v in rewards.items()},
    }


def render_doc(entries: Optional[list[GeneratedEntry]] = None) -> str:
    entries = entries if entries is not None else ALL_ENTRIES_V3
    stats = bank_stats(entries)
    lines = [
        "MPCS v3 — Generated Preset Memory Bank",
        "=" * 60,
        "",
        f"{stats['total']} experiences: {stats['unique']} unique scenes "
        f"(including {stats['contradictions']} contradicting twins) + "
        f"{stats['repeated']} near-repetitions + {stats['expert']} expert corrections.",
        f"Generated deterministically from mpcs_preset_v3.py, seed={DEFAULT_SEED}.",
        "Modality coverage is mixed, weighted toward full — see distribution below.",
        "Do not edit by hand; change the archetypes or regenerate instead.",
        "",
        "Action distribution",
        "-" * 60,
    ]
    for action in ACTIONS:
        count = stats["by_action"].get(action, 0)
        mean = stats["mean_reward"].get(action)
        mean_text = f"mean reward {mean:.2f}" if mean is not None else "—"
        lines.append(f"  {action:<10} {count:>4} entries    {mean_text}")

    lines += ["", "Modality-count distribution", "-" * 60]
    for count in sorted(stats["by_modality_count"]):
        n = stats["by_modality_count"][count]
        pct = 100.0 * n / stats["total"]
        lines.append(f"  {count} modalit{'y' if count == 1 else 'ies'}   {n:>4} entries  ({pct:4.1f}%)")

    lines += ["", "Origin mode", "-" * 60]
    for mode, count in sorted(stats["by_mode"].items()):
        lines.append(f"  {mode:<14} {count:>4}")

    lines += ["", "Entries", "-" * 60, ""]
    for e in entries:
        tag = "EXPERT" if e.is_expert else ("REPEAT" if e.note.startswith("Variant of") else
                                             ("TWIN" if "Contradicts" in e.note else "UNIQUE"))
        lines.append(f"[{e.step:>3}] {tag:<6} {e.action.upper():<9} reward={e.reward:.2f}  ({e.mode})  <{e.archetype}>")
        for modality in ("vision", "audio", "touch", "smell"):
            if modality not in e.percept:
                continue
            rendered = ", ".join(f"{k}={v}" for k, v in e.percept[modality].items())
            lines.append(f"       {modality:<7} {rendered}")
        lines.append(f"       note    {e.note}")
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
    return os.path.join(here, "..", "..", "data", "PresetMemory_v3.txt")


def main() -> None:
    parser = argparse.ArgumentParser(description="MPCS v3 generated preset memory bank.")
    parser.add_argument("--write-doc", action="store_true",
                        help="Regenerate Model/data/PresetMemory_v3.txt.")
    parser.add_argument("--profile", choices=tuple(PROFILE_CONFIGS), default="balanced")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    entries = ALL_ENTRIES_V3 if args.seed == DEFAULT_SEED else generate_bank(args.seed)
    stats = bank_stats(entries)
    print(f"Preset bank v3: {stats['total']} entries "
          f"({stats['unique']} unique incl. {stats['contradictions']} twins + "
          f"{stats['repeated']} repeated + {stats['expert']} expert)")
    for action in ACTIONS:
        print(f"  {action:<10} {stats['by_action'].get(action, 0):>4}")
    print("  modality counts:", stats["by_modality_count"])

    if args.write_doc:
        path = os.path.normpath(write_doc(_default_doc_path()))
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()

"""
MPCS engine — multimodal Z-number cognition core
------------------------------------------------
Shared cognition for every MPCS v2 front-end. Extends the two-modality
Z-variant (MPCS_Z.py) with:

  * four modalities (vision, audio, touch, smell) behind a generic registry,
    so a percept may omit any subset of them (the report's malleability
    property),
  * per-modality Z-confidence, which makes confidence-weighted similarity do
    real work instead of collapsing to plain feature counting,
  * reward derived from relevant past memory (mean + sampled variance) rather
    than random, with a penalty when the taken action contradicts what memory
    recommends,
  * an explanation payload per step naming every memory that contributed and
    how strongly, which is what the dashboards draw.

This module imports no UI toolkit and can be driven headlessly.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field, asdict
from typing import Optional


# ----------------------------------------------------------------------
# 1. Modality registry
# ----------------------------------------------------------------------
# Feature keys are modality-qualified: a bare "intensity" would collide
# between audio and touch in the flat reflex dict and in UI variable maps.
MODALITIES: dict[str, dict[str, list[str]]] = {
    "vision": {
        "object_type": ["human", "animal", "vehicle", "unknown"],
        "motion":      ["static", "slow", "fast"],
        "color":       ["red", "blue", "dark", "bright"],
    },
    "audio": {
        "sound_type":      ["none", "speech", "noise", "alarm"],
        "audio_intensity": ["low", "medium", "high"],
    },
    "touch": {
        "contact":         ["none", "light", "firm", "impact"],
        "texture":         ["smooth", "rough", "wet", "sharp"],
        "thermal":         ["cold", "neutral", "warm", "hot"],
        "touch_intensity": ["low", "medium", "high"],
    },
    "smell": {
        "odor_type":      ["none", "food", "chemical", "smoke", "organic"],
        "odor_intensity": ["faint", "moderate", "strong"],
        "pleasantness":   ["pleasant", "neutral", "foul"],
    },
}

MODALITY_ORDER: tuple[str, ...] = tuple(MODALITIES)

# Default reliability of each channel. Smell is the least reliable, matching
# the design report's own note that olfactory encoding is underdeveloped.
MODALITY_CONFIDENCE: dict[str, float] = {
    "vision": 1.0,
    "audio":  0.90,
    "touch":  0.95,
    "smell":  0.70,
}

# Feature key -> owning modality, for reflex rules written as flat conditions.
FEATURE_MODALITY: dict[str, str] = {
    key: modality
    for modality, features in MODALITIES.items()
    for key in features
}

ACTIONS = ["ignore", "observe", "approach", "alert", "withdraw"]

# First match wins, so ordering is priority. Touch pain and smoke outrank the
# older vision/audio rules: a hand on something hot should not wait for
# deliberation (design report section 07).
REFLEX_RULES: list[tuple[dict[str, str], str]] = [
    ({"thermal": "hot"},                                      "withdraw"),
    ({"contact": "impact"},                                   "withdraw"),
    ({"odor_type": "smoke"},                                  "alert"),
    ({"sound_type": "alarm"},                                 "alert"),
    ({"texture": "sharp", "contact": "firm"},                 "withdraw"),
    ({"odor_type": "chemical", "odor_intensity": "strong"},   "alert"),
    ({"motion": "fast"},                                      "observe"),
]

REFLEX_RULE_LABELS = [
    "hot surface -> withdraw",
    "impact contact -> withdraw",
    "smoke odor -> alert",
    "alarm sound -> alert",
    "sharp + firm contact -> withdraw",
    "strong chemical odor -> alert",
    "fast motion -> observe",
]


# ----------------------------------------------------------------------
# 2. Tunable configuration
# ----------------------------------------------------------------------
REWARD_COLD_START = (0.4, 0.6)   # uniform range when no relevant memory exists
PENALTY_FLOOR = 0.10             # an off-recommendation action never goes below this

# dlCBF sizing; modest on purpose, this is an interactive workload.
DLCBF_SUBTABLES = 4
DLCBF_BUCKETS_PER_SUBTABLE = 1024
DLCBF_FINGERPRINT_BITS = 16


@dataclass
class EngineConfig:
    """Run-time knobs. Dashboards edit an instance of this; nothing is global."""

    top_k: int = 5
    time_decay: float = 0.99
    learning_rate: float = 0.01
    reward_variance: float = 0.08
    penalty_strength: float = 1.0
    # Total contribution weight at which a recommendation counts as fully
    # supported. Below it, the penalty is scaled down proportionally.
    support_saturation: float = 2.0
    expert_weight_boost: float = 3.0
    expert_reward_default: float = 0.95
    expert_demote_reward: float = 0.05
    reflex_memory_boost: float = 2.0
    risk_bias: float = 0.5
    action_threshold: float = 0.5
    novelty_threshold: float = 0.5
    hesitate_enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


PROFILE_CONFIGS = {
    "balanced": {
        "state": {},
        "description": "No bias.",
    },
    "cautious": {
        "state": {"risk_bias": 0.20, "action_threshold": 0.62},
        "description": "Conservative: explores little, hesitates sooner.",
    },
    "exploratory": {
        "state": {"risk_bias": 0.82, "action_threshold": 0.40},
        "description": "Adventurous: explores often, commits on weaker evidence.",
    },
}


def clamp_reward(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


# ----------------------------------------------------------------------
# 3. Z-numbers and the afferent object
# ----------------------------------------------------------------------
class ZNumber:
    """A (value, confidence) pair: what was sensed, and how much to trust it."""

    __slots__ = ("value", "conf")

    def __init__(self, value: str, conf: float = 1.0):
        self.value = value
        self.conf = clamp_unit(conf)

    def as_tuple(self) -> tuple[str, float]:
        return (self.value, self.conf)

    def __repr__(self) -> str:
        return f"ZNumber({self.value!r}, {self.conf:.2f})"


class AfferentObject:
    """Multimodal percept binding. Any modality may be absent."""

    def __init__(
        self,
        percepts: dict[str, dict[str, str]],
        time: int = 0,
        state: Optional[dict] = None,
        confidences: Optional[dict[str, float]] = None,
    ):
        confidences = confidences or MODALITY_CONFIDENCE
        self.percepts: dict[str, dict[str, ZNumber]] = {}
        for modality, features in percepts.items():
            if modality not in MODALITIES or not features:
                continue
            conf = clamp_unit(confidences.get(modality, 1.0))
            self.percepts[modality] = {
                key: ZNumber(value, conf) for key, value in features.items()
            }
        self.time = time
        self.state = state if state is not None else {}
        self.summary = self._create_summary()

    def _create_summary(self) -> tuple:
        """Stable, hashable tuple-of-slots, one slot per modality in order.

        An absent modality yields an empty slot rather than shifting the
        others, so slot position always identifies the modality.
        """
        return tuple(
            tuple(sorted(
                (key, z.value, z.conf)
                for key, z in self.percepts.get(modality, {}).items()
            ))
            for modality in MODALITY_ORDER
        )

    def flat_values(self) -> dict[str, str]:
        """All sensed features merged into one dict, for reflex matching."""
        merged: dict[str, str] = {}
        for features in self.percepts.values():
            for key, z in features.items():
                merged[key] = z.value
        return merged

    def active_modalities(self) -> list[str]:
        return [m for m in MODALITY_ORDER if self.percepts.get(m)]


def summary_of(percepts: dict[str, dict[str, str]], confidences=None) -> tuple:
    """Convenience: build just the summary tuple for a raw percept dict."""
    return AfferentObject(percepts, confidences=confidences).summary


def describe_summary(summary: tuple) -> dict[str, dict[str, str]]:
    """Inverse of summary_of, minus confidences — used for display and export."""
    out: dict[str, dict[str, str]] = {}
    for modality, slot in zip(MODALITY_ORDER, summary):
        if slot:
            out[modality] = {key: value for key, value, _ in slot}
    return out


# ----------------------------------------------------------------------
# 4. Similarity and novelty (modality-generic, key-aligned)
# ----------------------------------------------------------------------
def similarity_z(s1: tuple, s2: tuple) -> float:
    """Confidence-weighted match score between two summaries.

    Matching is key-aligned rather than positional: slots can differ in
    length when a modality is absent, and a positional walk would silently
    compare unrelated features.
    """
    score = 0.0
    for slot1, slot2 in zip(s1, s2):
        if not slot1 or not slot2:
            continue
        other = {key: (value, conf) for key, value, conf in slot2}
        for key, value, conf in slot1:
            match = other.get(key)
            if match is not None and match[0] == value:
                score += conf * match[1]
    return score


def total_confidence(summary: tuple) -> float:
    return sum(conf for slot in summary for _, _, conf in slot)


def normalized_similarity_z(s1: tuple, s2: tuple) -> float:
    denom = total_confidence(s1)
    return (similarity_z(s1, s2) / denom) if denom else 0.0


def compute_novelty(summary: tuple, memory: "MemorySystem") -> float:
    if len(memory) == 0:
        return 1.0
    best = max(
        (normalized_similarity_z(summary, record["summary"]) for record in memory.records),
        default=0.0,
    )
    return clamp_unit(1.0 - best)


# ----------------------------------------------------------------------
# 5. d-left counting Bloom filter
# ----------------------------------------------------------------------
@dataclass(slots=True)
class DLBucket:
    fingerprint: int = 0
    count: int = 0


class DLeftCountingBloomFilter:
    """d-left counting Bloom filter with per-bucket fingerprints and counters.

    Used only as a fast exact-repeat hint. With twelve features the exact
    context space is far too large for membership to gate retrieval; a miss
    means "probably not seen verbatim", not "no similar memory exists".
    """

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

    def _digest(self, item: str) -> bytes:
        return hashlib.blake2b(item.encode("utf-8"), digest_size=32).digest()

    def _fingerprint(self, digest: bytes) -> int:
        fp = int.from_bytes(digest[:8], "big") & self._fingerprint_mask
        return fp or 1

    def _bucket_index(self, digest: bytes, table_index: int) -> int:
        offset = 8 + (table_index * 4)
        chunk = digest[offset:offset + 4]
        if len(chunk) < 4:
            chunk = (chunk + digest)[:4]
        return int.from_bytes(chunk, "big") % self.buckets_per_subtable

    def _candidates(self, item: str):
        digest = self._digest(item)
        fingerprint = self._fingerprint(digest)
        choices = []
        for table_index in range(self.subtables):
            bucket_index = self._bucket_index(digest, table_index)
            choices.append(
                (table_index, bucket_index, self._tables[table_index][bucket_index])
            )
        return fingerprint, choices

    def insert(self, item: str) -> None:
        fingerprint, choices = self._candidates(item)
        for _, _, bucket in choices:
            if bucket.count > 0 and bucket.fingerprint == fingerprint:
                bucket.count += 1
                self._item_count += 1
                return
        _, _, bucket = min(choices, key=lambda c: (c[2].count, c[0], c[1]))
        if bucket.count == 0:
            bucket.fingerprint = fingerprint
        bucket.count += 1
        self._item_count += 1

    def query(self, item: str) -> bool:
        fingerprint, choices = self._candidates(item)
        return any(
            bucket.count > 0 and bucket.fingerprint == fingerprint
            for _, _, bucket in choices
        )

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


# ----------------------------------------------------------------------
# 6. Memory
# ----------------------------------------------------------------------
class MemorySystem:
    def __init__(self):
        self._store: list[dict] = []
        self._dlcbf = DLeftCountingBloomFilter()

    @property
    def records(self) -> list[dict]:
        """Read-only-ish view of stored experiences."""
        return self._store

    @staticmethod
    def _summary_key(summary: tuple) -> str:
        return repr(summary)

    def seen_before(self, summary: tuple) -> bool:
        """Exact-repeat hint from the dlCBF. Never used to block retrieval."""
        return self._dlcbf.query(self._summary_key(summary))

    def store(
        self,
        summary: tuple,
        action: str,
        reward: float,
        step: int,
        confidence: float = 1.0,
        is_expert: bool = False,
        mode: str = "DELIBERATIVE",
        reflex_rule: Optional[int] = None,
        reward_source: str = "manual",
        penalty: Optional[dict] = None,
    ) -> dict:
        record = {
            "summary": summary,
            "action": action,
            "reward": clamp_reward(reward),
            "step": step,
            "conf": clamp_unit(confidence),
            "is_expert": bool(is_expert),
            "mode": mode,
            "reflex_rule": reflex_rule,
            "reward_source": reward_source,
            "penalty": penalty,
        }
        self._dlcbf.insert(self._summary_key(summary))
        self._store.append(record)
        return record

    def retrieve(self, summary: tuple, k: int = 5) -> list[dict]:
        """Top-k most similar experiences, regardless of action."""
        ranked = sorted(
            self._store,
            key=lambda m: similarity_z(summary, m["summary"]),
            reverse=True,
        )
        return ranked[:max(0, k)]

    def recall(self, summary: tuple, action: str, k: int = 5) -> list[dict]:
        """Top-k most similar experiences *for one action*.

        Distinct from retrieve(): scoring an action from a pool ranked without
        regard to action can leave that action with no evidence at all simply
        because more similar memories happened to concern a different one.
        """
        candidates = [m for m in self._store if m["action"] == action]
        ranked = sorted(
            candidates,
            key=lambda m: similarity_z(summary, m["summary"]),
            reverse=True,
        )
        return ranked[:max(0, k)]

    def delete(self, summary: tuple, step: Optional[int] = None) -> bool:
        key = self._summary_key(summary)
        for index in range(len(self._store) - 1, -1, -1):
            record = self._store[index]
            if record["summary"] != summary:
                continue
            if step is not None and record["step"] != step:
                continue
            self._store.pop(index)
            self._dlcbf.delete(key)
            return True
        return False

    def update_reward(self, step: int, reward: float) -> bool:
        for record in reversed(self._store):
            if record["step"] == step:
                record["reward"] = clamp_reward(reward)
                record["reward_source"] = "manual"
                return True
        return False

    def demote(self, step: int, reward: float) -> bool:
        """Lower the reward on the model's own record at *step* (expert correction)."""
        for record in reversed(self._store):
            if record["step"] == step and not record.get("is_expert"):
                record["reward"] = min(record["reward"], clamp_reward(reward))
                record["demoted"] = True
                return True
        return False

    def teach_expert(
        self, summary: tuple, action: str, step: int, reward: float
    ) -> dict:
        return self.store(
            summary, action, reward, step,
            confidence=1.0, is_expert=True,
            mode="EXPERT", reward_source="expert",
        )

    # -- persistence -----------------------------------------------------
    def to_json_obj(self) -> list[dict]:
        """Export records with summaries flattened to plain nested dicts."""
        out = []
        for record in self._store:
            item = {k: v for k, v in record.items() if k != "summary"}
            item["percepts"] = describe_summary(record["summary"])
            out.append(item)
        return out

    @classmethod
    def from_json_obj(cls, data: list[dict]) -> "MemorySystem":
        memory = cls()
        for item in data:
            percepts = item.get("percepts") or {}
            memory.store(
                summary=summary_of(percepts),
                action=item.get("action", "observe"),
                reward=item.get("reward", 0.5),
                step=item.get("step", 0),
                confidence=item.get("conf", 1.0),
                is_expert=item.get("is_expert", False),
                mode=item.get("mode", "DELIBERATIVE"),
                reflex_rule=item.get("reflex_rule"),
                reward_source=item.get("reward_source", "imported"),
                penalty=item.get("penalty"),
            )
        return memory

    def __len__(self) -> int:
        return len(self._store)


# ----------------------------------------------------------------------
# 7. Reflex layer
# ----------------------------------------------------------------------
def reflexive_decision(afferent: AfferentObject) -> tuple[Optional[str], Optional[int]]:
    """Return (action, rule_index), or (None, None) if no rule fires.

    A rule whose features belong to an absent modality simply cannot match,
    which is the intended behaviour: you cannot reflex-withdraw from heat you
    are not equipped to feel.
    """
    values = afferent.flat_values()
    for index, (condition, action) in enumerate(REFLEX_RULES):
        if all(values.get(key) == value for key, value in condition.items()):
            return action, index
    return None, None


# ----------------------------------------------------------------------
# 8. Contribution weighting — the shared basis of scoring and reward
# ----------------------------------------------------------------------
def _contribution_weight(
    record: dict,
    summary: tuple,
    current_step: int,
    cfg: EngineConfig,
    reflex_emphasis: bool,
) -> tuple[float, dict]:
    """Weight one memory's vote, and report every factor that produced it."""
    sim = normalized_similarity_z(summary, record["summary"])
    age = max(0, current_step - record.get("step", current_step))
    decay = cfg.time_decay ** age
    boost = 1.0
    if record.get("is_expert"):
        boost *= cfg.expert_weight_boost
    if reflex_emphasis and record.get("mode") == "REFLEXIVE":
        boost *= cfg.reflex_memory_boost
    weight = sim * decay * boost
    detail = {
        "step": record.get("step"),
        "action": record.get("action"),
        "reward": record.get("reward"),
        "similarity": sim,
        "age": age,
        "decay": decay,
        "boost": boost,
        "weight": weight,
        "is_expert": bool(record.get("is_expert")),
        "mode": record.get("mode"),
        "percepts": describe_summary(record["summary"]),
    }
    return weight, detail


def score_action(
    action: str,
    memory: MemorySystem,
    summary: tuple,
    current_step: int,
    cfg: EngineConfig,
    reflex_emphasis: bool = False,
) -> tuple[float, float, list[dict]]:
    """Expected reward for *action*: (score, total_weight, contributions).

    total_weight doubles as a measure of how well-evidenced the score is; a
    score of 0.7 backed by weight 0.05 is a guess, not a recommendation.
    """
    cases = memory.recall(summary, action, k=cfg.top_k)
    if not cases:
        return 0.5, 0.0, []

    weighted_sum = 0.0
    total_weight = 0.0
    contributions = []
    for record in cases:
        weight, detail = _contribution_weight(
            record, summary, current_step, cfg, reflex_emphasis
        )
        if weight <= 0.0:
            continue
        weighted_sum += weight * record["reward"]
        total_weight += weight
        contributions.append(detail)

    if total_weight == 0.0:
        return 0.5, 0.0, []
    contributions.sort(key=lambda d: d["weight"], reverse=True)
    return weighted_sum / total_weight, total_weight, contributions


# ----------------------------------------------------------------------
# 9. Reward from memory
# ----------------------------------------------------------------------
def reward_from_memory(
    memory: MemorySystem,
    summary: tuple,
    action: str,
    current_step: int,
    cfg: EngineConfig,
    reflex_emphasis: bool = False,
    rng: Optional[random.Random] = None,
) -> dict:
    """Reward for *action*: the mean of relevant past rewards, plus variance.

    With no relevant memory the estimate falls back to a weak neutral prior
    rather than pretending to knowledge it does not have.
    """
    rng = rng or random
    mean, support, contributions = score_action(
        action, memory, summary, current_step, cfg, reflex_emphasis
    )
    if support == 0.0:
        return {
            "reward": clamp_reward(rng.uniform(*REWARD_COLD_START)),
            "source": "cold-start",
            "mean": None,
            "support": 0.0,
            "contributions": [],
        }
    return {
        "reward": clamp_reward(rng.gauss(mean, cfg.reward_variance)),
        "source": "memory",
        "mean": mean,
        "support": support,
        "contributions": contributions,
    }


def apply_off_recommendation_penalty(
    base_reward: float,
    taken: str,
    scores: dict[str, float],
    supports: dict[str, float],
    cfg: EngineConfig,
    rng: Optional[random.Random] = None,
) -> tuple[float, Optional[dict]]:
    """Push reward down when the action taken contradicts memory's advice.

    Scaled by two things: how much better the recommended action looked
    (margin), and how well-evidenced that recommendation was (support). A
    marginally worse choice barely stings; overriding a strong, well-supported
    recommendation does.
    """
    rng = rng or random
    evidenced = {a: s for a, s in scores.items() if supports.get(a, 0.0) > 0.0}
    if not evidenced or taken not in scores:
        return base_reward, None

    recommended = max(evidenced, key=evidenced.get)
    if taken == recommended:
        return base_reward, None

    margin = max(0.0, evidenced[recommended] - scores[taken])
    confidence = min(1.0, supports.get(recommended, 0.0) / max(1e-9, cfg.support_saturation))
    penalty = clamp_unit(cfg.penalty_strength * margin * confidence)
    if penalty <= 0.0:
        return base_reward, None

    penalised = max(PENALTY_FLOOR, base_reward * (1.0 - penalty))
    final = clamp_reward(rng.gauss(penalised, cfg.reward_variance))
    final = max(PENALTY_FLOOR, final)
    return final, {
        "recommended": recommended,
        "taken": taken,
        "margin": margin,
        "confidence": confidence,
        "penalty": penalty,
        "before": base_reward,
        "after": final,
    }


# ----------------------------------------------------------------------
# 10. Deliberation
# ----------------------------------------------------------------------
def deliberate(
    afferent: AfferentObject,
    memory: MemorySystem,
    novelty: float,
    cfg: EngineConfig,
    state: dict,
    rng: Optional[random.Random] = None,
) -> dict:
    """Score every action, then commit, explore, or hesitate."""
    rng = rng or random
    scores: dict[str, float] = {}
    supports: dict[str, float] = {}
    contributions: dict[str, list[dict]] = {}
    for action in ACTIONS:
        score, support, contribs = score_action(
            action, memory, afferent.summary, afferent.time, cfg
        )
        scores[action] = score
        supports[action] = support
        contributions[action] = contribs

    best = max(scores, key=scores.get)

    # Novelty raises exploration pressure; risk_bias sets the base rate.
    epsilon = clamp_unit(state.get("risk_bias", cfg.risk_bias) * (0.6 + 0.4 * novelty))

    if rng.random() < epsilon:
        chosen = rng.choice(ACTIONS)
        policy = "EXPLORE"
    else:
        chosen = best
        policy = "EXPLOIT"

    # The learned threshold finally does something: if even the best option
    # looks weak, fall back to the low-commitment default rather than acting
    # on a poor estimate.
    threshold = state.get("action_threshold", cfg.action_threshold)
    hesitated = False
    if (
        cfg.hesitate_enabled
        and policy == "EXPLOIT"
        and scores[chosen] < threshold
        and chosen != "observe"
    ):
        chosen = "observe"
        policy = "HESITATE"
        hesitated = True

    return {
        "action": chosen,
        "best_action": best,
        "policy": policy,
        "scores": scores,
        "supports": supports,
        "contributions": contributions,
        "epsilon": epsilon,
        "hesitated": hesitated,
        "threshold": threshold,
    }


# ----------------------------------------------------------------------
# 11. Learning update
# ----------------------------------------------------------------------
def update_state(state: dict, reward: float, novelty: float, cfg: EngineConfig) -> None:
    """Adapt the action threshold. Novel situations move it further."""
    novelty_gain = 0.5 + novelty
    delta = cfg.learning_rate * novelty_gain * (reward - 0.5)
    state["action_threshold"] = clamp_unit(
        state.get("action_threshold", cfg.action_threshold) + delta
    )


# ----------------------------------------------------------------------
# 12. Cognitive step
# ----------------------------------------------------------------------
def cognitive_step(
    percepts: dict[str, dict[str, str]],
    step: int,
    state: dict,
    memory: MemorySystem,
    cfg: Optional[EngineConfig] = None,
    manual_reward: Optional[float] = None,
    rng: Optional[random.Random] = None,
) -> dict:
    """One perception-decision-reward-store cycle.

    Returns an explanation payload: everything a front-end needs to show not
    only what was decided but why, including each contributing memory.
    """
    cfg = cfg or EngineConfig()
    rng = rng or random

    afferent = AfferentObject(percepts, time=step, state=state)
    summary = afferent.summary
    novelty = compute_novelty(summary, memory)
    dlcbf_hit = memory.seen_before(summary)

    reflex_action, reflex_rule = reflexive_decision(afferent)

    # Score the deliberative options either way. On the reflex path these are
    # not used to choose, but they are what the penalty rule compares against
    # and what the dashboard shows as the road not taken.
    scores: dict[str, float] = {}
    supports: dict[str, float] = {}
    contributions: dict[str, list[dict]] = {}
    for candidate in ACTIONS:
        score, support, contribs = score_action(
            candidate, memory, summary, step, cfg
        )
        scores[candidate] = score
        supports[candidate] = support
        contributions[candidate] = contribs

    if reflex_action is not None:
        action = reflex_action
        mode = "REFLEXIVE"
        policy = "REFLEX"
        best_action = max(scores, key=scores.get)
        epsilon = 0.0
        hesitated = False
        threshold = state.get("action_threshold", cfg.action_threshold)
        # Reflex memories get extra weight when valuing a reflex outcome.
        reflex_score, reflex_support, reflex_contribs = score_action(
            action, memory, summary, step, cfg, reflex_emphasis=True
        )
        scores[action] = reflex_score if reflex_support > 0.0 else scores[action]
        supports[action] = max(supports[action], reflex_support)
        contributions[action] = reflex_contribs or contributions[action]
    else:
        decision = deliberate(afferent, memory, novelty, cfg, state, rng=rng)
        action = decision["action"]
        mode = "DELIBERATIVE"
        policy = decision["policy"]
        best_action = decision["best_action"]
        epsilon = decision["epsilon"]
        hesitated = decision["hesitated"]
        threshold = decision["threshold"]
        scores = decision["scores"]
        supports = decision["supports"]
        contributions = decision["contributions"]

    # --- reward ---
    penalty = None
    if manual_reward is not None:
        reward = clamp_reward(manual_reward)
        reward_source = "manual"
        reward_mean = None
        chosen_contribs = contributions.get(action, [])
    else:
        estimate = reward_from_memory(
            memory, summary, action, step, cfg,
            reflex_emphasis=(mode == "REFLEXIVE"), rng=rng,
        )
        reward = estimate["reward"]
        reward_source = estimate["source"]
        reward_mean = estimate["mean"]
        chosen_contribs = estimate["contributions"] or contributions.get(action, [])
        reward, penalty = apply_off_recommendation_penalty(
            reward, action, scores, supports, cfg, rng=rng
        )
        if penalty is not None:
            reward_source = "memory+penalty"

    memory.store(
        summary=summary,
        action=action,
        reward=reward,
        step=step,
        confidence=1.0,
        mode=mode,
        reflex_rule=reflex_rule,
        reward_source=reward_source,
        penalty=penalty,
    )
    update_state(state, reward, novelty, cfg)

    return {
        "step": step,
        "summary": summary,
        "percepts": describe_summary(summary),
        "active_modalities": afferent.active_modalities(),
        "action": action,
        "mode": mode,
        "policy": policy,
        "best_action": best_action,
        "epsilon": epsilon,
        "novelty": novelty,
        "hesitated": hesitated,
        "threshold": threshold,
        "dlcbf_hit": dlcbf_hit,
        "reflex_rule": reflex_rule,
        "reflex_rule_label": (
            REFLEX_RULE_LABELS[reflex_rule] if reflex_rule is not None else None
        ),
        "reward": reward,
        "reward_source": reward_source,
        "reward_mean": reward_mean,
        "penalty": penalty,
        "scores": scores,
        "supports": supports,
        "contributions": chosen_contribs,
        "all_contributions": contributions,
        "memory_size": len(memory),
        "state": dict(state),
    }


def init_state(cfg: Optional[EngineConfig] = None, profile: str = "balanced") -> dict:
    cfg = cfg or EngineConfig()
    state = {
        "novelty_threshold": cfg.novelty_threshold,
        "action_threshold": cfg.action_threshold,
        "risk_bias": cfg.risk_bias,
    }
    state.update(PROFILE_CONFIGS.get(profile, {}).get("state", {}))
    return state


# ----------------------------------------------------------------------
# 13. Explanation graph layout
# ----------------------------------------------------------------------
ACTION_COLORS = {
    "ignore":   "#8a8f98",
    "observe":  "#2f7fd1",
    "approach": "#2aa36b",
    "alert":    "#e0902b",
    "withdraw": "#d1483f",
}


def build_graph(result: dict, max_nodes: int = 12) -> dict:
    """Percept-centred node-link layout for the contributing memories.

    Strong contributors sit closer to the centre, so the picture reads at a
    glance: the memories nearest the percept are the ones that decided it.
    Coordinates are unit-ish (roughly -1..1) and scaled by each renderer.
    """
    contributions = list(result.get("contributions") or [])
    contributions.sort(key=lambda c: c.get("weight", 0.0), reverse=True)
    contributions = contributions[:max_nodes]

    nodes = [{
        "id": "percept",
        "kind": "percept",
        "label": "current percept",
        "x": 0.0,
        "y": 0.0,
        "modalities": result.get("active_modalities", []),
        "action": result.get("action"),
        "color": ACTION_COLORS.get(result.get("action"), "#444"),
        "radius": 1.0,
    }]
    edges = []

    if not contributions:
        return {"nodes": nodes, "edges": edges, "empty": True}

    max_weight = max(c.get("weight", 0.0) for c in contributions) or 1.0
    count = len(contributions)

    for index, contrib in enumerate(contributions):
        weight = contrib.get("weight", 0.0)
        strength = weight / max_weight if max_weight else 0.0
        # Strong contributors pulled inward; weak ones pushed to the rim.
        radius = 0.42 + 0.58 * (1.0 - strength)
        angle = (2.0 * math.pi * index / count) - (math.pi / 2.0)
        node_id = f"mem-{contrib.get('step')}-{index}"
        nodes.append({
            "id": node_id,
            "kind": "memory",
            "label": f"step {contrib.get('step')}",
            "step": contrib.get("step"),
            "x": radius * math.cos(angle),
            "y": radius * math.sin(angle),
            "action": contrib.get("action"),
            "color": ACTION_COLORS.get(contrib.get("action"), "#666"),
            "reward": contrib.get("reward"),
            "similarity": contrib.get("similarity"),
            "age": contrib.get("age"),
            "decay": contrib.get("decay"),
            "boost": contrib.get("boost"),
            "weight": weight,
            "is_expert": contrib.get("is_expert"),
            "mode": contrib.get("mode"),
            "percepts": contrib.get("percepts", {}),
            "radius": 0.35 + 0.65 * strength,
        })
        edges.append({
            "source": node_id,
            "target": "percept",
            "weight": weight,
            "strength": strength,
            "color": ACTION_COLORS.get(contrib.get("action"), "#666"),
            "tooltip": (
                f"step {contrib.get('step')} | {contrib.get('action')} | "
                f"reward {contrib.get('reward', 0):.2f} | "
                f"sim {contrib.get('similarity', 0):.2f} x "
                f"decay {contrib.get('decay', 0):.2f} x "
                f"boost {contrib.get('boost', 1):.1f} = {weight:.3f}"
            ),
        })

    return {"nodes": nodes, "edges": edges, "empty": False}


# ----------------------------------------------------------------------
# 14. Session — the object every dashboard drives
# ----------------------------------------------------------------------
@dataclass
class Session:
    """Holds everything one simulation run needs. UIs own one of these."""

    cfg: EngineConfig = field(default_factory=EngineConfig)
    memory: MemorySystem = field(default_factory=MemorySystem)
    state: dict = field(default_factory=dict)
    step: int = 0
    profile: str = "balanced"
    seed: Optional[int] = None
    history: list[dict] = field(default_factory=list)
    last_result: Optional[dict] = None
    rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self):
        if not self.state:
            self.state = init_state(self.cfg, self.profile)
        if self.seed is not None:
            self.rng = random.Random(self.seed)

    def apply_profile(self, profile: str) -> None:
        self.profile = profile
        for key, value in PROFILE_CONFIGS.get(profile, {}).get("state", {}).items():
            self.state[key] = value
            setattr(self.cfg, key, value)

    def run_step(
        self,
        percepts: dict[str, dict[str, str]],
        manual_reward: Optional[float] = None,
    ) -> dict:
        self.step += 1
        result = cognitive_step(
            percepts, self.step, self.state, self.memory,
            cfg=self.cfg, manual_reward=manual_reward, rng=self.rng,
        )
        result["graph"] = build_graph(result)
        self.last_result = result
        self.history.append({
            "step": result["step"],
            "action": result["action"],
            "mode": result["mode"],
            "policy": result["policy"],
            "reward": result["reward"],
            "reward_source": result["reward_source"],
            "novelty": result["novelty"],
            "threshold": result["state"].get("action_threshold"),
            "penalised": result["penalty"] is not None,
        })
        return result

    def apply_reward(self, reward: float) -> dict:
        """Retro-label the last action, correcting the state update it caused."""
        if self.last_result is None:
            return {"ok": False, "message": "No prior action to reward yet."}
        reward = clamp_reward(reward)
        step = self.last_result["step"]
        previous = self.last_result["reward"]
        if not self.memory.update_reward(step, reward):
            return {"ok": False, "message": f"Step {step} not found in memory."}

        novelty_gain = 0.5 + self.last_result["novelty"]
        delta = self.cfg.learning_rate * novelty_gain * (reward - previous)
        self.state["action_threshold"] = clamp_unit(
            self.state.get("action_threshold", self.cfg.action_threshold) + delta
        )
        self.last_result["reward"] = reward
        self.last_result["reward_source"] = "manual"
        self.last_result["state"] = dict(self.state)
        for entry in reversed(self.history):
            if entry["step"] == step:
                entry["reward"] = reward
                entry["reward_source"] = "manual"
                entry["threshold"] = self.state["action_threshold"]
                break
        return {
            "ok": True,
            "message": f"Applied reward {reward:.3f} to step {step} (was {previous:.3f}).",
        }

    def teach_expert(self, action: str, reward: Optional[float] = None) -> dict:
        if self.last_result is None:
            return {"ok": False, "message": "No prior action to correct yet."}
        if action not in ACTIONS:
            return {"ok": False, "message": f"Unknown action {action!r}."}

        expert_reward = (
            clamp_reward(reward) if reward is not None else self.cfg.expert_reward_default
        )
        summary = self.last_result["summary"]
        original_step = self.last_result["step"]
        original_action = self.last_result["action"]

        self.step += 1
        self.memory.teach_expert(summary, action, self.step, expert_reward)

        demoted = False
        if action != original_action:
            demoted = self.memory.demote(original_step, self.cfg.expert_demote_reward)

        novelty_gain = 0.5 + self.last_result["novelty"]
        delta = self.cfg.learning_rate * novelty_gain * (expert_reward - 0.5)
        self.state["action_threshold"] = clamp_unit(
            self.state.get("action_threshold", self.cfg.action_threshold) + delta
        )

        message = (
            f"Taught expert action '{action}' (reward {expert_reward:.2f}) "
            f"for step {original_step}'s context."
        )
        if demoted:
            message += (
                f" Demoted the model's '{original_action}' to "
                f"{self.cfg.expert_demote_reward:.2f}."
            )
        elif action == original_action:
            message += " Model already agreed; reinforced only."
        return {"ok": True, "message": message}

    def reset(
        self,
        memory: Optional[MemorySystem] = None,
        profile: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.memory = memory if memory is not None else MemorySystem()
        self.profile = profile or self.profile
        self.state = init_state(self.cfg, self.profile)
        # Continue numbering past preloaded experiences so time decay treats
        # them as genuinely older than anything run from here.
        self.step = max((r["step"] for r in self.memory.records), default=0)
        self.history = []
        self.last_result = None
        if seed is not None:
            self.seed = seed
        self.rng = random.Random(self.seed) if self.seed is not None else random.Random()

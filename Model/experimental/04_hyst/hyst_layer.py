"""
HyST layer — hard filters, soft residual, over the MPCS engine
----------------------------------------------------------------
Implements Step 1 of the perceptual-memory-indexing gameplan
(docs/MPCS_Memory_Indexing_Report.html, section 04 / 11, L2): split every
percept's features into a hard, safety-critical set and a soft, negotiable
set, then judge novelty and retrieval in two stages instead of one flat scan.

Today mpcs_engine.similarity_z treats every feature identically: a mismatch
on `thermal` costs exactly what a mismatch on `color` costs, and nothing is
graded (`warm` vs `hot` scores the same as `cold` vs `hot` — zero). This
module fixes both, without touching the engine:

  1. Hard predicate first. A memory that disagrees with the percept on any
     hard slot is excluded from the candidate set entirely — it cannot be
     "similar enough" to argue past a safety mismatch no matter how many
     decorative features line up.
  2. Graded soft kernel second, over survivors only. Soft features use an
     ordinal closeness table (e.g. warm~hot partial credit) instead of exact
     match, so genuinely similar percepts read as similar.

Two run-time controls the engine does not have, both requested nuances:

  * `divergent` (soft-constraint switch, exploration). When True, the hard
    filter is relaxed into a heavily-discounted soft one instead of an
    exclusion — near-misses on hard slots survive but are penalised, which
    is what lets creative / divergent retrieval surface distant analogies
    instead of returning nothing.
  * `urgent` (importance/urgency flag, sole convergent thinking). When True,
    the hard filter is absolute regardless of `divergent` (urgency always
    wins), and retrieval collapses to the single nearest surviving memory
    rather than a ranked top-k — there is no time to weigh alternatives.

This module is additive: it imports mpcs_engine and calls its functions, it
does not modify them. A dashboard can run stock MPCS and HyST side by side
against the same MemorySystem.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "02_core"))

import mpcs_engine as E


# ----------------------------------------------------------------------
# 1. Hard/soft slot classification, seeded from REFLEX_RULES
# ----------------------------------------------------------------------
def hard_slots_from_reflex_rules() -> set[str]:
    """Every feature key appearing in a reflex condition is hard by
    construction (report section 07/11): these are exactly the features the
    system already treats as too important to negotiate on.
    """
    hard: set[str] = set()
    for condition, _action in E.REFLEX_RULES:
        hard.update(condition.keys())
    return hard


DEFAULT_HARD_SLOTS: set[str] = hard_slots_from_reflex_rules()


# ----------------------------------------------------------------------
# 2. Graded soft kernel — ordinal closeness instead of exact match
# ----------------------------------------------------------------------
# Only ordinal-feeling scales get a closeness table; nominal ones (color,
# object_type, sound_type, odor_type...) keep exact match, because "close to
# red" has no principled meaning the way "close to hot" does.
ORDINAL_SCALES: dict[str, list[str]] = {
    "thermal":         ["cold", "neutral", "warm", "hot"],
    "motion":          ["static", "slow", "fast"],
    "audio_intensity": ["low", "medium", "high"],
    "touch_intensity": ["low", "medium", "high"],
    "odor_intensity":  ["faint", "moderate", "strong"],
    "contact":         ["none", "light", "firm", "impact"],
    "pleasantness":    ["foul", "neutral", "pleasant"],
}


def ordinal_closeness(feature: str, value_a: str, value_b: str) -> float:
    """1.0 for identical values, graded credit for nearby ordinal values,
    0.0 for values on a scale this module does not recognise as ordinal or
    too far apart to be considered anything but a mismatch.
    """
    if value_a == value_b:
        return 1.0
    scale = ORDINAL_SCALES.get(feature)
    if not scale or value_a not in scale or value_b not in scale:
        return 0.0
    span = len(scale) - 1
    distance = abs(scale.index(value_a) - scale.index(value_b))
    # Linear falloff; adjacent steps still count for something, opposite
    # ends of the scale do not.
    return max(0.0, 1.0 - distance / span)


# ----------------------------------------------------------------------
# 3. Slot policy — the object dashboards create and tune
# ----------------------------------------------------------------------
@dataclass
class SlotPolicy:
    """Which features are hard vs soft, and the two run-time nuances."""

    hard_slots: set[str] = field(default_factory=lambda: set(DEFAULT_HARD_SLOTS))
    divergent: bool = False   # soft-constraint switch: exploration
    urgent: bool = False      # urgency/importance flag: sole convergent thinking

    # Per-mismatch cost when `divergent` relaxes the filter instead of
    # excluding. Swept on the v3 bank: 0.15 re-admitted nearly everything
    # (accuracy fell to stock's 33%, unsafe calls 34%); 0.6 keeps 56% accuracy
    # at 10% unsafe. At >= 0.5 two mismatches already zero a memory's weight.
    divergent_mismatch_discount: float = 0.6

    def is_hard(self, feature: str) -> bool:
        return feature in self.hard_slots

    def set_hard(self, feature: str, hard: bool) -> None:
        if hard:
            self.hard_slots.add(feature)
        else:
            self.hard_slots.discard(feature)


# ----------------------------------------------------------------------
# 4. Hard-predicate check and split similarity
# ----------------------------------------------------------------------
def _slot_values(summary: tuple) -> dict[str, tuple[str, float]]:
    """Flatten a summary tuple into {feature: (value, confidence)}."""
    flat: dict[str, tuple[str, float]] = {}
    for slot in summary:
        for key, value, conf in slot:
            flat[key] = (value, conf)
    return flat


def hard_predicate_ok(
    query: dict[str, tuple[str, float]],
    candidate: dict[str, tuple[str, float]],
    policy: SlotPolicy,
) -> bool:
    """True if *candidate* agrees with *query* on every hard slot the query
    actually has a value for. A hard slot absent from the query imposes no
    constraint — you cannot fail a check on a feature you did not sense.
    """
    for feature in policy.hard_slots:
        if feature not in query:
            continue
        q_value, _ = query[feature]
        c_value = candidate.get(feature)
        if c_value is None or c_value[0] != q_value:
            return False
    return True


def hard_mismatch_count(
    query: dict[str, tuple[str, float]],
    candidate: dict[str, tuple[str, float]],
    policy: SlotPolicy,
) -> int:
    mismatches = 0
    for feature in policy.hard_slots:
        if feature not in query:
            continue
        q_value, _ = query[feature]
        c_value = candidate.get(feature)
        if c_value is None or c_value[0] != q_value:
            mismatches += 1
    return mismatches


def split_similarity(
    summary_a: tuple,
    summary_b: tuple,
    policy: SlotPolicy,
) -> Optional[float]:
    """Confidence-weighted similarity, hard slots gated, soft slots graded.

    Returns None if the candidate is excluded outright (hard mismatch under
    a non-divergent policy). Otherwise returns a normalised score in [0, 1],
    reduced by `divergent_mismatch_discount` per hard-slot mismatch when
    `policy.divergent` is True.
    """
    query = _slot_values(summary_a)
    candidate = _slot_values(summary_b)

    hard_ok = hard_predicate_ok(query, candidate, policy)
    if not hard_ok and not policy.divergent:
        return None
    if not hard_ok and policy.urgent:
        # Urgency always wins: no relaxation, regardless of divergent mode.
        return None

    score = 0.0
    denom = 0.0
    for feature, (q_value, q_conf) in query.items():
        denom += q_conf
        c = candidate.get(feature)
        if c is None:
            continue
        c_value, c_conf = c
        if policy.is_hard(feature):
            closeness = 1.0 if c_value == q_value else 0.0
        else:
            closeness = ordinal_closeness(feature, q_value, c_value)
        score += closeness * min(q_conf, c_conf)

    normalised = (score / denom) if denom else 0.0

    if not hard_ok and policy.divergent:
        mismatches = hard_mismatch_count(query, candidate, policy)
        normalised *= max(0.0, 1.0 - policy.divergent_mismatch_discount * mismatches)

    return E.clamp_unit(normalised)


# ----------------------------------------------------------------------
# 5. Novelty and retrieval, HyST-style
# ----------------------------------------------------------------------
def compute_novelty_hyst(
    summary: tuple,
    memory: E.MemorySystem,
    policy: SlotPolicy,
) -> tuple[float, int]:
    """Novelty over the admissible set only. Returns (novelty, admissible_count).

    An empty admissible set (every stored memory fails the hard predicate)
    reads as full novelty — the report's point exactly: four matching
    decorative features must never argue the system out of "this is new and
    potentially dangerous".
    """
    if len(memory) == 0:
        return 1.0, 0

    best = 0.0
    admissible = 0
    for record in memory.records:
        sim = split_similarity(summary, record["summary"], policy)
        if sim is None:
            continue
        admissible += 1
        if sim > best:
            best = sim
    if admissible == 0:
        return 1.0, 0
    return E.clamp_unit(1.0 - best), admissible


def retrieve_hyst(
    summary: tuple,
    memory: E.MemorySystem,
    policy: SlotPolicy,
    k: int = 5,
) -> list[dict]:
    """Top-k admissible memories, ranked by split similarity.

    Under `policy.urgent`, k is forced to 1: sole convergent thinking takes
    the single best admissible match and stops, rather than weighing a
    ranked set of alternatives.
    """
    if policy.urgent:
        k = 1

    scored = []
    for record in memory.records:
        sim = split_similarity(summary, record["summary"], policy)
        if sim is None:
            continue
        scored.append((sim, record))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {**record, "hyst_similarity": sim}
        for sim, record in scored[:max(0, k)]
    ]


def recall_hyst(
    summary: tuple,
    memory: E.MemorySystem,
    action: str,
    policy: SlotPolicy,
    k: int = 5,
) -> list[dict]:
    """Top-k admissible memories for one action — the HyST analogue of
    MemorySystem.recall, used by score_action_hyst below.
    """
    if policy.urgent:
        k = 1
    scored = []
    for record in memory.records:
        if record["action"] != action:
            continue
        sim = split_similarity(summary, record["summary"], policy)
        if sim is None:
            continue
        scored.append((sim, record))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {**record, "hyst_similarity": sim}
        for sim, record in scored[:max(0, k)]
    ]


# ----------------------------------------------------------------------
# 6. Action scoring over the HyST-filtered candidate set
# ----------------------------------------------------------------------
def score_action_hyst(
    action: str,
    memory: E.MemorySystem,
    summary: tuple,
    current_step: int,
    cfg: E.EngineConfig,
    policy: SlotPolicy,
) -> tuple[float, float, list[dict]]:
    """Same contract as mpcs_engine.score_action, but candidates are drawn
    from the hard-filtered admissible set rather than every stored memory
    sharing the action.
    """
    top_k = 1 if policy.urgent else cfg.top_k
    cases = recall_hyst(summary, memory, action, policy, k=top_k)
    if not cases:
        return 0.5, 0.0, []

    weighted_sum = 0.0
    total_weight = 0.0
    contributions = []
    for record in cases:
        age = max(0, current_step - record.get("step", current_step))
        decay = cfg.time_decay ** age
        boost = 1.0
        if record.get("is_expert"):
            boost *= cfg.expert_weight_boost
        weight = record["hyst_similarity"] * decay * boost
        if weight <= 0.0:
            continue
        weighted_sum += weight * record["reward"]
        total_weight += weight
        contributions.append({
            "step": record.get("step"),
            "action": record.get("action"),
            "reward": record.get("reward"),
            "similarity": record["hyst_similarity"],
            "age": age,
            "decay": decay,
            "boost": boost,
            "weight": weight,
            "is_expert": bool(record.get("is_expert")),
            "mode": record.get("mode"),
            "percepts": E.describe_summary(record["summary"]),
        })

    if total_weight == 0.0:
        return 0.5, 0.0, []
    contributions.sort(key=lambda d: d["weight"], reverse=True)
    return weighted_sum / total_weight, total_weight, contributions


# ----------------------------------------------------------------------
# 7. One HyST cognitive step, mirroring mpcs_engine.cognitive_step
# ----------------------------------------------------------------------
def hyst_step(
    percepts: dict[str, dict[str, str]],
    step: int,
    state: dict,
    memory: E.MemorySystem,
    policy: SlotPolicy,
    cfg: Optional[E.EngineConfig] = None,
    manual_reward: Optional[float] = None,
    rng=None,
) -> dict:
    """A cognitive step that answers novelty and scoring through the HyST
    hard/soft split instead of the engine's flat similarity_z. Reflexes,
    deliberation policy (explore/exploit/hesitate) and reward derivation are
    otherwise unchanged from mpcs_engine — HyST only changes *which*
    memories count as evidence and *how similar* they are judged to be.
    """
    cfg = cfg or E.EngineConfig()
    rng = rng or __import__("random")

    afferent = E.AfferentObject(percepts, time=step, state=state)
    summary = afferent.summary
    novelty, admissible = compute_novelty_hyst(summary, memory, policy)
    dlcbf_hit = memory.seen_before(summary)

    reflex_action, reflex_rule = E.reflexive_decision(afferent)

    scores: dict[str, float] = {}
    supports: dict[str, float] = {}
    contributions: dict[str, list[dict]] = {}
    for candidate in E.ACTIONS:
        score, support, contribs = score_action_hyst(
            candidate, memory, summary, step, cfg, policy
        )
        scores[candidate] = score
        supports[candidate] = support
        contributions[candidate] = contribs

    if reflex_action is not None:
        action = reflex_action
        mode = "REFLEXIVE"
        decision_policy = "REFLEX"
        best_action = E.best_evidenced_action(scores, supports)
        epsilon = 0.0
        hesitated = False
        threshold = state.get("action_threshold", cfg.action_threshold)
    else:
        mode = "DELIBERATIVE"
        best_action = E.best_evidenced_action(scores, supports)
        if policy.urgent:
            # Sole convergent thinking: no exploration, no hesitation —
            # urgency means committing to the best admissible answer now.
            action = best_action
            decision_policy = "CONVERGE"
            epsilon = 0.0
            hesitated = False
            threshold = state.get("action_threshold", cfg.action_threshold)
        else:
            epsilon = E.clamp_unit(
                state.get("risk_bias", cfg.risk_bias) * (0.6 + 0.4 * novelty)
            )
            if rng.random() < epsilon:
                action = rng.choice(E.ACTIONS)
                decision_policy = "EXPLORE"
            else:
                action = best_action
                decision_policy = "EXPLOIT"

            threshold = state.get("action_threshold", cfg.action_threshold)
            hesitated = False
            if (
                cfg.hesitate_enabled
                and decision_policy == "EXPLOIT"
                and scores[action] < threshold
                and action != "observe"
            ):
                action = "observe"
                decision_policy = "HESITATE"
                hesitated = True

    penalty = None
    if manual_reward is not None:
        reward = E.clamp_reward(manual_reward)
        reward_source = "manual"
        reward_mean = None
        chosen_contribs = contributions.get(action, [])
    else:
        mean, support, contribs = score_action_hyst(
            action, memory, summary, step, cfg, policy
        )
        if support == 0.0:
            reward = E.clamp_reward(rng.uniform(*E.REWARD_COLD_START))
            reward_source = "cold-start"
            reward_mean = None
            chosen_contribs = []
        else:
            reward = E.clamp_reward(rng.gauss(mean, cfg.reward_variance))
            reward_source = "memory"
            reward_mean = mean
            chosen_contribs = contribs
        reward, penalty = E.apply_off_recommendation_penalty(
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
    E.update_state(state, reward, novelty, cfg)

    return {
        "step": step,
        "summary": summary,
        "percepts": E.describe_summary(summary),
        "active_modalities": afferent.active_modalities(),
        "action": action,
        "mode": mode,
        "policy": decision_policy,
        "best_action": best_action,
        "epsilon": epsilon,
        "novelty": novelty,
        "admissible_count": admissible,
        "memory_size": len(memory),
        "hesitated": hesitated,
        "threshold": threshold,
        "dlcbf_hit": dlcbf_hit,
        "reflex_rule": reflex_rule,
        "reflex_rule_label": (
            E.REFLEX_RULE_LABELS[reflex_rule] if reflex_rule is not None else None
        ),
        "reward": reward,
        "reward_source": reward_source,
        "reward_mean": reward_mean,
        "penalty": penalty,
        "scores": scores,
        "supports": supports,
        "contributions": chosen_contribs,
        "all_contributions": contributions,
        "state": dict(state),
        "hard_slots": sorted(policy.hard_slots),
        "divergent": policy.divergent,
        "urgent": policy.urgent,
    }


# ----------------------------------------------------------------------
# 8. Session wrapper — same shape as E.Session, drives a HyST run
# ----------------------------------------------------------------------
@dataclass
class HystSession:
    """Holds one HyST simulation run. Mirrors mpcs_engine.Session's shape
    so a dashboard can switch between stock and HyST scoring with minimal
    branching.
    """

    cfg: E.EngineConfig = field(default_factory=E.EngineConfig)
    memory: E.MemorySystem = field(default_factory=E.MemorySystem)
    policy: SlotPolicy = field(default_factory=SlotPolicy)
    state: dict = field(default_factory=dict)
    step: int = 0
    profile: str = "balanced"
    seed: Optional[int] = None
    history: list = field(default_factory=list)
    last_result: Optional[dict] = None
    rng: object = None

    def __post_init__(self):
        import random
        if not self.state:
            self.state = E.init_state(self.cfg, self.profile)
        self.rng = random.Random(self.seed) if self.seed is not None else random.Random()

    def apply_profile(self, profile: str) -> None:
        self.profile = profile
        for key, value in E.PROFILE_CONFIGS.get(profile, {}).get("state", {}).items():
            self.state[key] = value
            setattr(self.cfg, key, value)

    def run_step(
        self,
        percepts: dict[str, dict[str, str]],
        manual_reward: Optional[float] = None,
    ) -> dict:
        self.step += 1
        result = hyst_step(
            percepts, self.step, self.state, self.memory, self.policy,
            cfg=self.cfg, manual_reward=manual_reward, rng=self.rng,
        )
        result["graph"] = E.build_graph(result)
        self.last_result = result
        self.history.append({
            "step": result["step"],
            "action": result["action"],
            "mode": result["mode"],
            "policy": result["policy"],
            "reward": result["reward"],
            "reward_source": result["reward_source"],
            "novelty": result["novelty"],
            "admissible_count": result["admissible_count"],
            "threshold": result["state"].get("action_threshold"),
            "penalised": result["penalty"] is not None,
        })
        return result

    def reset(
        self,
        memory: Optional[E.MemorySystem] = None,
        profile: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> None:
        import random
        self.memory = memory if memory is not None else E.MemorySystem()
        self.profile = profile or self.profile
        self.state = E.init_state(self.cfg, self.profile)
        self.step = max((r["step"] for r in self.memory.records), default=0)
        self.history = []
        self.last_result = None
        if seed is not None:
            self.seed = seed
        self.rng = random.Random(self.seed) if self.seed is not None else random.Random()

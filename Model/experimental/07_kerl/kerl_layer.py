"""
KERL layer — constrained selection over SHMF's retrieved subgraph
-------------------------------------------------------------------
Adapts KERL (Mohbat & Zaki, ACL 2025) as specified in
docs/Perceptual_Memory_Indexing_Report.html §05/§10 and
docs/MPCS_Memory_Indexing_Report.html §05/§07 (layer L3). KERL's recipes and
LLM are irrelevant here; its structure is not:

  retrieve connected structure once  ->  guard it  ->  read it several ways

1. Retrieval is SHMF (HMGI partition -> HyST hard/soft filter, with
   auto-relax). KERL adds nothing to *how* memories are found.

2. Near-miss guard. A candidate may only contribute if its recorded
   modalities cover the channels of the features the decision turns on (the
   query's hard slots). Strict HyST survivors always pass — they matched those
   features exactly — so the guard bites on SHMF's relaxed re-pass, which can
   admit, say, an audio-only memory into a thermal decision. Rejected
   candidates are kept as (satisfying, near-miss) calibration pairs, KERL's
   positive/negative sampling.

3. Fused relevance per candidate (report §10), minus the context term, which
   has no data in MPCS yet:
       R(m) = w_s * sim_semantic + w_e * sim_emotional + w_g * graph_term
       omega(m) = R(m) * decay^age * boost
   graph_term is HMGI's (1/h) sum over h=2 hops of episode edges: how strongly
   the memory's neighbours (previous step, same action, same object) were
   themselves retrieved. Weights shift with novelty: high novelty leans on
   the graph, low novelty on semantic similarity.

4. Three heads over the one guarded candidate set:
     HEAD-A  action value + support per action (the engine's scoring, on omega)
     HEAD-E  valence/arousal of the situation, derived from retrieved memories'
             sensory cues, reflex-rule hits and the spread of action outcomes
             — never stored, the way KERL-Nutri derives nutrients
     HEAD-X  a plain-language explanation naming the evidence

5. Empty-candidate path is designed, not defaulted: with no admissible
   evidence the step is labelled UNGROUNDED and falls back to `observe`.
   (The engine's best_evidenced_action now does the same for G4-G7; KERL
   additionally names it and explains it.)

HEAD-E ships behind `affect_enabled` (default off), as the report requires:
its outputs are always computed and shown, but only influence retrieval
(w_e) and exploration (threat suppresses epsilon) when switched on. The
affect derivation is our proposal and the least-evidenced part of the design.
"""

from __future__ import annotations

import math
import os
import random
import sys
from dataclasses import dataclass, field
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
for _d in ("02_core", "04_hyst", "05_hmgi", "06_shmf"):
    sys.path.insert(0, os.path.join(_HERE, "..", _d))

import mpcs_engine as E
from hmgi_layer import build_episodes
from hyst_layer import SlotPolicy
from shmf_layer import ShmfPipeline


# ----------------------------------------------------------------------
# 1. Configuration and fusion weights
# ----------------------------------------------------------------------
@dataclass
class KerlConfig:
    w_s: float = 0.7          # semantic (SHMF similarity)
    w_e: float = 0.15         # emotional — used only when affect_enabled
    w_g: float = 0.3          # graph term over episode edges
    affect_enabled: bool = False
    guard_enabled: bool = True
    calibrate_every: int = 25   # steps between automatic calibrations; 0 = manual only
    calibration_lr: float = 0.05
    calibration_margin: float = 0.05
    max_pairs: int = 500

    def weights(self) -> dict:
        return {"w_s": self.w_s, "w_e": self.w_e if self.affect_enabled else 0.0, "w_g": self.w_g}


# ----------------------------------------------------------------------
# 2. Affect cues (HEAD-E inputs) — our proposal, derived from features
# ----------------------------------------------------------------------
_LEVEL = {"none": 0.0, "low": 0.0, "faint": 0.0, "static": 0.0,
          "light": 0.3, "slow": 0.3, "medium": 0.5, "moderate": 0.5, "firm": 0.6,
          "high": 1.0, "strong": 1.0, "fast": 0.8, "impact": 1.0}
_AROUSAL_KEYS = ("audio_intensity", "touch_intensity", "odor_intensity", "motion", "contact")


def flat_features(summary: tuple) -> dict[str, str]:
    return {key: value for slot in summary for key, value, _ in slot}


def reflex_hits(flat: dict[str, str]) -> list[str]:
    return [action for condition, action in E.REFLEX_RULES
            if all(flat.get(k) == v for k, v in condition.items())]


def affect_of(flat: dict[str, str]) -> tuple[float, float]:
    """(valence in [-1, 1], arousal in [0, 1]) for one percept's features.

    Threat is a reflex rule firing — the engine's own definition of danger.
    Valence adds hedonic cues (smell pleasantness, food, speech, temperature,
    sharpness); arousal averages whatever intensity-like channels were sensed.
    """
    hits = reflex_hits(flat)
    threat = 1.0 if any(a in ("withdraw", "alert") for a in hits) else (0.4 if hits else 0.0)
    if flat.get("sound_type") == "alarm":
        threat = max(threat, 1.0)

    v = {"pleasant": 0.5, "foul": -0.5}.get(flat.get("pleasantness"), 0.0)
    v += 0.2 if flat.get("odor_type") == "food" else 0.0
    v += 0.2 if flat.get("sound_type") == "speech" else 0.0
    v += {"warm": 0.1, "hot": -0.3, "cold": -0.1}.get(flat.get("thermal"), 0.0)
    v -= 0.2 if flat.get("texture") == "sharp" else 0.0
    v -= 0.7 * threat

    cues = [_LEVEL[flat[k]] for k in _AROUSAL_KEYS if flat.get(k) in _LEVEL]
    if flat.get("sound_type") in ("alarm", "noise"):
        cues.append(1.0 if flat["sound_type"] == "alarm" else 0.5)
    a = 0.5 * threat + 0.5 * (sum(cues) / len(cues) if cues else 0.0)
    return max(-1.0, min(1.0, v)), max(0.0, min(1.0, a))


def emotional_similarity(va: tuple[float, float], vb: tuple[float, float]) -> float:
    # valence spans 2, arousal spans 1 -> max distance sqrt(5)
    return 1.0 - math.hypot(va[0] - vb[0], va[1] - vb[1]) / math.sqrt(5.0)


# ----------------------------------------------------------------------
# 3. Episode adjacency for the graph term (O(N), cached by store size)
# ----------------------------------------------------------------------
class EpisodeGraph:
    """Undirected neighbours per step: previous episode, most recent
    same-action episode, most recent same-object episode — the same three
    G-facet edges hmgi_layer.Episode defines, built in one forward pass.
    """

    def __init__(self):
        self._size = -1
        self.neighbours: dict[int, set[int]] = {}

    def refresh(self, memory: E.MemorySystem) -> None:
        if self._size == len(memory):
            return
        nb: dict[int, set[int]] = {}
        prev = None
        last_action: dict[str, int] = {}
        last_object: dict[str, int] = {}
        for record in memory.records:
            step = record["step"]
            nb.setdefault(step, set())
            obj = flat_features(record["summary"]).get("object_type")
            for other in (prev, last_action.get(record["action"]), last_object.get(obj) if obj else None):
                if other is not None and other != step:
                    nb[step].add(other)
                    nb.setdefault(other, set()).add(step)
            prev = step
            last_action[record["action"]] = step
            if obj:
                last_object[obj] = step
        self.neighbours = nb
        self._size = len(memory)

    def graph_term(self, step: int, sims: dict[int, float]) -> float:
        """(1/h) sum over h = 2 hops of mean similarity of retrieved neighbours."""
        hop1 = self.neighbours.get(step, set())
        hop2 = set().union(*(self.neighbours.get(n, set()) for n in hop1)) - hop1 - {step} if hop1 else set()
        scores = []
        for hop in (hop1, hop2):
            hit = [sims[n] for n in hop if n in sims]
            scores.append(sum(hit) / len(hit) if hit else 0.0)
        return sum(scores) / 2.0


# ----------------------------------------------------------------------
# 4. The KERL reader
# ----------------------------------------------------------------------
@dataclass
class Candidate:
    record: dict
    sim_s: float
    sim_e: float = 0.0
    graph: float = 0.0
    relevance: float = 0.0
    omega: float = 0.0
    affect: tuple[float, float] = (0.0, 0.0)

    def features(self) -> tuple[float, float, float]:
        return (self.sim_s, self.sim_e, self.graph)


class KerlReader:
    """Owns an ShmfPipeline and reads its candidates through the guard,
    fusion and three heads. Calibration pairs accumulate across steps.
    """

    def __init__(self, memory: E.MemorySystem, policy: Optional[SlotPolicy] = None,
                 kcfg: Optional[KerlConfig] = None, auto_relax: bool = True):
        self.pipeline = ShmfPipeline(memory, policy or SlotPolicy(), auto_relax=auto_relax)
        self.kcfg = kcfg or KerlConfig()
        self.graph = EpisodeGraph()
        self.pairs: list[tuple[tuple, tuple]] = []   # (satisfying features, near-miss features)
        self.last_calibration: Optional[dict] = None

    @property
    def memory(self) -> E.MemorySystem:
        return self.pipeline.memory

    @property
    def policy(self) -> SlotPolicy:
        return self.pipeline.policy

    # -- guard ---------------------------------------------------------
    def decisive_modalities(self, query_flat: dict[str, str]) -> set[str]:
        return {E.FEATURE_MODALITY[f] for f in self.policy.hard_slots if f in query_flat}

    @staticmethod
    def covers(record_summary: tuple, needed: set[str]) -> bool:
        present = {m for m, slot in zip(E.MODALITY_ORDER, record_summary) if slot}
        return needed <= present

    # -- one full read of the memory for a query -------------------------
    def read(self, summary: tuple, step: int, cfg: E.EngineConfig,
             reflex_emphasis: bool = False) -> dict:
        memory = self.memory
        self.graph.refresh(memory)
        novelty, stats = self.pipeline.novelty(summary)
        scored, _ = self.pipeline.scored_candidates(summary)

        query_flat = flat_features(summary)
        query_affect = affect_of(query_flat)
        needed = self.decisive_modalities(query_flat)

        kept, rejected = [], []
        for sim, record in scored:
            cand = Candidate(record=record, sim_s=sim)
            if self.kcfg.guard_enabled and needed and not self.covers(record["summary"], needed):
                rejected.append(cand)
            else:
                kept.append(cand)

        sims = {c.record["step"]: c.sim_s for c in kept}
        w = self.kcfg.weights()
        w_s = w["w_s"] * (1.25 - 0.5 * novelty)   # low novelty: trust resemblance
        w_g = w["w_g"] * (0.75 + 0.5 * novelty)   # high novelty: trust adjacency
        w_e = w["w_e"]
        for cand in kept + rejected:
            cand.affect = affect_of(flat_features(cand.record["summary"]))
            cand.sim_e = emotional_similarity(query_affect, cand.affect)
            cand.graph = self.graph.graph_term(cand.record["step"], sims)
            cand.relevance = w_s * cand.sim_s + w_e * cand.sim_e + w_g * cand.graph

        for cand in kept:
            age = max(0, step - cand.record.get("step", step))
            boost = cfg.expert_weight_boost if cand.record.get("is_expert") else 1.0
            if reflex_emphasis and cand.record.get("mode") == "REFLEXIVE":
                boost *= cfg.reflex_memory_boost
            cand.omega = cand.relevance * (cfg.time_decay ** age) * boost

        if rejected and kept:
            best = max(kept, key=lambda c: c.omega)
            for miss in rejected:
                self.pairs.append((best.features(), miss.features()))
            del self.pairs[:-self.kcfg.max_pairs]

        head_a = self._head_a(kept, cfg)
        head_e = self._head_e(kept, head_a, query_affect)
        head_x = self._head_x(query_flat, kept, rejected, head_a, head_e, needed)
        return {
            "novelty": novelty,
            "stats": stats,
            "kept": kept,
            "rejected": rejected,
            "head_a": head_a,
            "head_e": head_e,
            "head_x": head_x,
            "grounded": any(v["support"] > 0 for v in head_a.values()),
            "weights_used": {"w_s": w_s, "w_e": w_e, "w_g": w_g},
        }

    # -- heads ---------------------------------------------------------
    def _head_a(self, kept: list[Candidate], cfg: E.EngineConfig) -> dict:
        k = 1 if self.policy.urgent else cfg.top_k
        out = {}
        for action in E.ACTIONS:
            cases = sorted((c for c in kept if c.record["action"] == action and c.omega > 0),
                           key=lambda c: c.omega, reverse=True)[:k]
            support = sum(c.omega for c in cases)
            value = (sum(c.omega * c.record["reward"] for c in cases) / support) if support else 0.5
            out[action] = {"value": value, "support": support, "cases": cases}
        return out

    @staticmethod
    def _head_e(kept: list[Candidate], head_a: dict, query_affect: tuple[float, float]) -> dict:
        total = sum(c.omega for c in kept)
        if total <= 0:
            return {"valence": query_affect[0], "arousal": query_affect[1],
                    "source": "percept-only", "stakes": 0.0,
                    "query_valence": query_affect[0], "query_arousal": query_affect[1]}
        valence = sum(c.omega * c.affect[0] for c in kept) / total
        cue_arousal = sum(c.omega * c.affect[1] for c in kept) / total
        evidenced = [v["value"] for v in head_a.values() if v["support"] > 0]
        # Stakes: how far apart the best and worst evidenced outcomes are.
        # A situation where the right action scores 0.9 and the wrong 0.1 is
        # high-arousal whatever it looks like.
        stakes = (max(evidenced) - min(evidenced)) if len(evidenced) > 1 else 0.0
        return {"valence": valence, "arousal": min(1.0, 0.6 * cue_arousal + 0.4 * stakes),
                "source": "retrieved", "stakes": stakes,
                "query_valence": query_affect[0], "query_arousal": query_affect[1]}

    @staticmethod
    def _head_x(query_flat, kept, rejected, head_a, head_e, needed) -> str:
        cues = [f"{k}={query_flat[k]}" for k in sorted(query_flat)
                if any(k in cond for cond, _ in E.REFLEX_RULES)]
        lines = [f"Decisive cues: {', '.join(cues) or 'none (no hard slots sensed)'}."]
        if not kept:
            lines.append("No admissible memory — nothing may justify an action; falling back to observe.")
        else:
            by_action: dict[str, int] = {}
            for c in kept:
                by_action[c.record["action"]] = by_action.get(c.record["action"], 0) + 1
            mix = ", ".join(f"{n} {a}" for a, n in sorted(by_action.items(), key=lambda p: -p[1]))
            lines.append(f"{len(kept)} admissible episodes: {mix}.")
            ranked = sorted(((a, v) for a, v in head_a.items() if v["support"] > 0),
                            key=lambda p: -p[1]["value"])
            if ranked:
                a, v = ranked[0]
                top = v["cases"][0].record
                lines.append(f"Best-supported: {a} (value {v['value']:.2f}, support {v['support']:.2f}); "
                             f"strongest voice step {top['step']} "
                             f"({'expert, ' if top.get('is_expert') else ''}reward {top['reward']:.2f}).")
        if rejected:
            chans = "+".join(sorted(needed))
            lines.append(f"{len(rejected)} near-miss(es) rejected for lacking the {chans} channel.")
        tone = ("threatening" if head_e["valence"] < -0.3 else
                "pleasant" if head_e["valence"] > 0.3 else "neutral")
        lines.append(f"Affect ({head_e['source']}): {tone}, valence {head_e['valence']:+.2f}, "
                     f"arousal {head_e['arousal']:.2f}.")
        return " ".join(lines)

    # -- calibration (KERL negative sampling) -----------------------------
    def _score(self, f: tuple, w: tuple) -> float:
        return sum(a * b for a, b in zip(f, w))

    def calibrate(self) -> dict:
        """Pairwise perceptron over (satisfying, near-miss) pairs: nudge
        (w_s, w_e, w_g) until satisfying memories out-rank their near-misses
        by the margin. w_e is frozen while affect is disabled.
        """
        k = self.kcfg
        if not self.pairs:
            self.last_calibration = {"pairs": 0, "violated_before": 0, "violated_after": 0,
                                     "weights": k.weights()}
            return self.last_calibration
        w = [k.w_s, k.w_e if k.affect_enabled else 0.0, k.w_g]

        def violations(weights):
            return sum(self._score(p, weights) <= self._score(n, weights) + k.calibration_margin
                       for p, n in self.pairs)

        before = violations(w)
        for _ in range(20):
            changed = False
            for p, n in self.pairs:
                if self._score(p, w) <= self._score(n, w) + k.calibration_margin:
                    for i in range(3):
                        if i == 1 and not k.affect_enabled:
                            continue
                        w[i] = max(0.05, w[i] + k.calibration_lr * (p[i] - n[i]))
                    changed = True
            if not changed:
                break
        live = [0, 1, 2] if k.affect_enabled else [0, 2]
        norm = sum(w[i] for i in live)
        for i in live:
            w[i] /= norm
        after = violations(w)
        accepted = after < before   # no measurable gain -> keep the current weights
        if accepted:
            k.w_s, k.w_g = w[0], w[2]
            if k.affect_enabled:
                k.w_e = w[1]
        self.last_calibration = {"pairs": len(self.pairs), "violated_before": before,
                                 "violated_after": after if accepted else before,
                                 "accepted": accepted, "weights": k.weights()}
        return self.last_calibration


# ----------------------------------------------------------------------
# 5. One KERL cognitive step
# ----------------------------------------------------------------------
def kerl_step(
    percepts: dict[str, dict[str, str]],
    step: int,
    state: dict,
    reader: KerlReader,
    cfg: Optional[E.EngineConfig] = None,
    manual_reward: Optional[float] = None,
    rng=None,
) -> dict:
    cfg = cfg or E.EngineConfig()
    rng = rng or random
    memory = reader.memory
    policy = reader.policy

    afferent = E.AfferentObject(percepts, time=step, state=state)
    summary = afferent.summary
    dlcbf_hit = memory.seen_before(summary)
    reflex_action, reflex_rule = E.reflexive_decision(afferent)

    reading = reader.read(summary, step, cfg, reflex_emphasis=reflex_action is not None)
    novelty = reading["novelty"]
    head_a, head_e = reading["head_a"], reading["head_e"]
    scores = {a: v["value"] for a, v in head_a.items()}
    supports = {a: v["support"] for a, v in head_a.items()}
    evidenced = {a: s for a, s in scores.items() if supports[a] > 0}
    best_action = max(evidenced, key=evidenced.get) if evidenced else "observe"
    threshold = state.get("action_threshold", cfg.action_threshold)
    epsilon, hesitated = 0.0, False

    if reflex_action is not None:
        action, mode, policy_name = reflex_action, "REFLEXIVE", "REFLEX"
    else:
        mode = "DELIBERATIVE"
        epsilon = E.clamp_unit(state.get("risk_bias", cfg.risk_bias) * (0.6 + 0.4 * novelty))
        if reader.kcfg.affect_enabled:
            # Emotion as a routing signal: threat (negative valence x arousal)
            # suppresses exploration. Pleasant or calm scenes are unaffected.
            epsilon *= 1.0 - head_e["arousal"] * max(0.0, -head_e["valence"])
        if policy.urgent:
            action, policy_name, epsilon = best_action, "CONVERGE", 0.0
        elif rng.random() < epsilon:
            action, policy_name = rng.choice(E.ACTIONS), "EXPLORE"
        elif not evidenced:
            action, policy_name = "observe", "UNGROUNDED"
        else:
            action, policy_name = best_action, "EXPLOIT"
            if cfg.hesitate_enabled and scores[action] < threshold and action != "observe":
                action, policy_name, hesitated = "observe", "HESITATE", True

    penalty = None
    predicted = scores[action] if supports.get(action, 0) > 0 else None
    if manual_reward is not None:
        reward, reward_source, reward_mean = E.clamp_reward(manual_reward), "manual", None
    elif predicted is None:
        reward, reward_source, reward_mean = E.clamp_reward(rng.uniform(*E.REWARD_COLD_START)), "cold-start", None
    else:
        reward = E.clamp_reward(rng.gauss(predicted, cfg.reward_variance))
        reward_source, reward_mean = "memory", predicted
        reward, penalty = E.apply_off_recommendation_penalty(reward, action, scores, supports, cfg, rng=rng)
        if penalty is not None:
            reward_source = "memory+penalty"

    contributions = [{
        "step": c.record["step"], "action": c.record["action"], "reward": c.record["reward"],
        "similarity": c.sim_s, "age": max(0, step - c.record["step"]),
        "decay": cfg.time_decay ** max(0, step - c.record["step"]),
        "boost": cfg.expert_weight_boost if c.record.get("is_expert") else 1.0,
        "weight": c.omega, "is_expert": bool(c.record.get("is_expert")), "mode": c.record.get("mode"),
        "percepts": E.describe_summary(c.record["summary"]),
        "sim_e": c.sim_e, "graph": c.graph, "relevance": c.relevance,
    } for c in head_a[action]["cases"]]

    memory.store(summary=summary, action=action, reward=reward, step=step, confidence=1.0,
                 mode=mode, reflex_rule=reflex_rule, reward_source=reward_source, penalty=penalty)
    E.update_state(state, reward, novelty, cfg)

    stats = reading["stats"]
    return {
        "step": step, "summary": summary, "percepts": E.describe_summary(summary),
        "active_modalities": afferent.active_modalities(),
        "action": action, "mode": mode, "policy": policy_name, "best_action": best_action,
        "epsilon": epsilon, "novelty": novelty, "hesitated": hesitated, "threshold": threshold,
        "dlcbf_hit": dlcbf_hit, "reflex_rule": reflex_rule,
        "reflex_rule_label": E.REFLEX_RULE_LABELS[reflex_rule] if reflex_rule is not None else None,
        "reward": reward, "reward_source": reward_source, "reward_mean": reward_mean, "penalty": penalty,
        "scores": scores, "supports": supports, "contributions": contributions,
        "memory_size": len(memory), "state": dict(state),
        "hard_slots": sorted(policy.hard_slots), "divergent": policy.divergent, "urgent": policy.urgent,
        "pipeline": {
            "store_size": stats.store_size, "after_partition": stats.after_partition,
            "after_hard_soft": stats.after_hard_soft,
            "partition_reduction_pct": stats.partition_reduction_pct,
            "filter_reduction_pct": stats.filter_reduction_pct,
            "total_reduction_pct": stats.total_reduction_pct,
            "partition_elapsed_ms": stats.partition_elapsed_ms,
            "filter_elapsed_ms": stats.filter_elapsed_ms, "relaxed": stats.relaxed,
        },
        "kerl": {
            "grounded": reading["grounded"],
            "admissible": len(reading["kept"]),
            "near_misses": [c.record["step"] for c in reading["rejected"]],
            "affect": head_e,
            "affect_enabled": reader.kcfg.affect_enabled,
            "explanation": reading["head_x"],
            "weights": reader.kcfg.weights(),
            "weights_used": reading["weights_used"],
            "predicted": predicted,
            "prediction_error": (reward - predicted) if predicted is not None else None,
            "calibration_pairs": len(reader.pairs),
        },
    }


# ----------------------------------------------------------------------
# 6. Session — same shape as ShmfSession, so SHMF's dashboard can drive it
# ----------------------------------------------------------------------
@dataclass
class KerlSession:
    cfg: E.EngineConfig = field(default_factory=E.EngineConfig)
    memory: E.MemorySystem = field(default_factory=E.MemorySystem)
    policy: SlotPolicy = field(default_factory=SlotPolicy)
    kcfg: KerlConfig = field(default_factory=KerlConfig)
    state: dict = field(default_factory=dict)
    step: int = 0
    profile: str = "balanced"
    seed: Optional[int] = None
    history: list = field(default_factory=list)
    last_result: Optional[dict] = None
    rng: object = None
    reader: Optional[KerlReader] = None

    def __post_init__(self):
        if not self.state:
            self.state = E.init_state(self.cfg, self.profile)
        self.rng = random.Random(self.seed) if self.seed is not None else random.Random()
        self.reader = KerlReader(self.memory, self.policy, self.kcfg)

    @property
    def pipeline(self) -> ShmfPipeline:
        return self.reader.pipeline

    def apply_profile(self, profile: str) -> None:
        self.profile = profile
        for key, value in E.PROFILE_CONFIGS.get(profile, {}).get("state", {}).items():
            self.state[key] = value
            setattr(self.cfg, key, value)

    def calibrate(self) -> dict:
        return self.reader.calibrate()

    def run_step(self, percepts: dict[str, dict[str, str]],
                 manual_reward: Optional[float] = None) -> dict:
        self.step += 1
        result = kerl_step(percepts, self.step, self.state, self.reader,
                           cfg=self.cfg, manual_reward=manual_reward, rng=self.rng)
        if self.kcfg.calibrate_every and self.step % self.kcfg.calibrate_every == 0:
            result["kerl"]["calibration"] = self.calibrate()
        result["graph"] = E.build_graph(result)
        result["episodes"] = [ep.to_dict() for ep in build_episodes(self.memory)[-12:]]
        self.last_result = result
        p = result["pipeline"]
        self.history.append({
            "step": result["step"], "action": result["action"], "mode": result["mode"],
            "policy": result["policy"], "reward": result["reward"],
            "reward_source": result["reward_source"], "novelty": result["novelty"],
            "threshold": result["state"].get("action_threshold"),
            "penalised": result["penalty"] is not None,
            "total_reduction_pct": p["total_reduction_pct"],
            "partition_reduction_pct": p["partition_reduction_pct"],
            "filter_reduction_pct": p["filter_reduction_pct"],
            "valence": result["kerl"]["affect"]["valence"],
            "arousal": result["kerl"]["affect"]["arousal"],
        })
        return result

    def reset(self, memory: Optional[E.MemorySystem] = None, profile: Optional[str] = None,
              seed: Optional[int] = None) -> None:
        self.memory = memory if memory is not None else E.MemorySystem()
        self.reader = KerlReader(self.memory, self.policy, self.kcfg)
        self.profile = profile or self.profile
        self.state = E.init_state(self.cfg, self.profile)
        self.step = max((r["step"] for r in self.memory.records), default=0)
        self.history = []
        self.last_result = None
        if seed is not None:
            self.seed = seed
        self.rng = random.Random(self.seed) if self.seed is not None else random.Random()

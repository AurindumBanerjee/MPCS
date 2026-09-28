"""
SHMF — Smart Hybrid-Modality Filtering
-----------------------------------------
The layered composition the design report actually describes (section 07,
L1 -> L2): HMGI's modality-partitioned scan runs first to cheaply cut the
candidate set down by active modality, then HyST's hard/soft slot filter
runs only over that reduced set, instead of over the whole store.

Neither hmgi_layer.py nor hyst_layer.py is modified to build this — SHMF
imports both as libraries and pipes one's output into the other:

    query
      -> PartitionedMemory.candidates(query)      [HMGI: cheap, structural]
      -> split_similarity(query, candidate, ...)  [HyST: hard/soft, graded]
      -> ranked / admissible / novel

Why this order and not the reverse
------------------------------------
Partitioning is a pure scan-scope cut with no notion of "hard" or "soft" —
it only asks "does this record touch a modality the query touches at all".
Running it first is free in the sense that it can never wrongly exclude a
record HyST would have kept: a record HMGI drops shares zero modalities
with the query, so every one of its features is absent from the query too,
which means HyST's own hard_predicate_ok would have skipped every hard
slot on it anyway and its soft-kernel contribution would have been zero.
Running the expensive, semantically rich hard/soft split only after the
cheap cut is therefore not an approximation — see verify_pipeline_equivalence
below, which checks this claim against a live memory bank rather than
asserting it.

What SHMF adds beyond gluing the two together
------------------------------------------------
  * PipelineStats — per-step visibility into *both* cuts happening in
    sequence: how many records the partition removed, then how many the
    hard/soft filter removed from what was left, so a dashboard can show
    the whole funnel instead of only the final admissible count.
  * A single SHMF step/session, mirroring the shape of E.Session,
    HystSession and HmgiSession, so a dashboard can offer all four
    (stock / HyST / HMGI / SHMF) side by side with minimal branching.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hmgi"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hyst"))

import mpcs_engine as E
from hmgi_layer import PartitionedMemory, ScanStats, build_episodes
from hyst_layer import SlotPolicy, split_similarity


# ----------------------------------------------------------------------
# 1. Pipeline-wide instrumentation — both cuts, one funnel
# ----------------------------------------------------------------------
@dataclass
class PipelineStats:
    """One query's cost through both stages, so a dashboard can show the
    whole funnel (store -> partition survivors -> hard/soft survivors)
    instead of only the combined result.
    """

    store_size: int
    after_partition: int
    after_hard_soft: int
    partition_elapsed_ms: float
    filter_elapsed_ms: float

    @property
    def partition_reduction_pct(self) -> float:
        if self.store_size == 0:
            return 0.0
        return 100.0 * (1.0 - self.after_partition / self.store_size)

    @property
    def filter_reduction_pct(self) -> float:
        if self.after_partition == 0:
            return 0.0
        return 100.0 * (1.0 - self.after_hard_soft / self.after_partition)

    @property
    def total_reduction_pct(self) -> float:
        if self.store_size == 0:
            return 0.0
        return 100.0 * (1.0 - self.after_hard_soft / self.store_size)


@dataclass
class PipelineInstrumentation:
    history: list[PipelineStats] = field(default_factory=list)
    max_history: int = 200

    def record(self, stats: PipelineStats) -> None:
        self.history.append(stats)
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def summary(self) -> dict:
        if not self.history:
            return {"count": 0}
        last = self.history[-1]
        return {
            "count": len(self.history),
            "avg_total_reduction_pct": sum(s.total_reduction_pct for s in self.history) / len(self.history),
            "last_total_reduction_pct": last.total_reduction_pct,
            "last_partition_reduction_pct": last.partition_reduction_pct,
            "last_filter_reduction_pct": last.filter_reduction_pct,
            "last_store_size": last.store_size,
            "last_after_partition": last.after_partition,
            "last_after_hard_soft": last.after_hard_soft,
        }


# ----------------------------------------------------------------------
# 2. The pipeline itself
# ----------------------------------------------------------------------
class ShmfPipeline:
    """Owns one PartitionedMemory (HMGI) and one SlotPolicy (HyST) over a
    shared MemorySystem, and runs queries through both stages in order.
    """

    def __init__(self, memory: E.MemorySystem, policy: Optional[SlotPolicy] = None):
        self.memory = memory
        self.partitioned = PartitionedMemory(memory)
        self.policy = policy or SlotPolicy()
        self.instrumentation = PipelineInstrumentation()

    def scored_candidates(self, query_summary: tuple) -> tuple[list[tuple[float, dict]], PipelineStats]:
        """Full pipeline for one query: partition, then hard/soft filter,
        returning (similarity, record) pairs for every survivor plus the
        stats for both stages.
        """
        t0 = time.perf_counter()
        partitioned_candidates = self.partitioned.candidates(query_summary)
        t1 = time.perf_counter()

        scored: list[tuple[float, dict]] = []
        for record in partitioned_candidates:
            sim = split_similarity(query_summary, record["summary"], self.policy)
            if sim is not None:
                scored.append((sim, record))
        t2 = time.perf_counter()

        stats = PipelineStats(
            store_size=len(self.memory),
            after_partition=len(partitioned_candidates),
            after_hard_soft=len(scored),
            partition_elapsed_ms=(t1 - t0) * 1000.0,
            filter_elapsed_ms=(t2 - t1) * 1000.0,
        )
        self.instrumentation.record(stats)
        return scored, stats

    def novelty(self, query_summary: tuple) -> tuple[float, PipelineStats]:
        if len(self.memory) == 0:
            empty_stats = PipelineStats(0, 0, 0, 0.0, 0.0)
            self.instrumentation.record(empty_stats)
            return 1.0, empty_stats
        scored, stats = self.scored_candidates(query_summary)
        if not scored:
            return 1.0, stats
        best = max(sim for sim, _ in scored)
        return E.clamp_unit(1.0 - best), stats

    def retrieve(self, query_summary: tuple, k: int = 5) -> list[dict]:
        if self.policy.urgent:
            k = 1
        scored, _stats = self.scored_candidates(query_summary)
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [{**record, "shmf_similarity": sim} for sim, record in scored[:max(0, k)]]

    def recall(self, query_summary: tuple, action: str, k: int = 5) -> list[dict]:
        if self.policy.urgent:
            k = 1
        scored, _stats = self.scored_candidates(query_summary)
        matching = [(sim, r) for sim, r in scored if r["action"] == action]
        matching.sort(key=lambda pair: pair[0], reverse=True)
        return [{**record, "shmf_similarity": sim} for sim, record in matching[:max(0, k)]]

    def score_action(
        self, action: str, query_summary: tuple, current_step: int, cfg: E.EngineConfig,
        reflex_emphasis: bool = False,
    ) -> tuple[float, float, list[dict]]:
        top_k = 1 if self.policy.urgent else cfg.top_k
        cases = self.recall(query_summary, action, k=top_k)
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
            if reflex_emphasis and record.get("mode") == "REFLEXIVE":
                boost *= cfg.reflex_memory_boost
            weight = record["shmf_similarity"] * decay * boost
            if weight <= 0.0:
                continue
            weighted_sum += weight * record["reward"]
            total_weight += weight
            contributions.append({
                "step": record.get("step"),
                "action": record.get("action"),
                "reward": record.get("reward"),
                "similarity": record["shmf_similarity"],
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
# 3. One SHMF cognitive step, mirroring hmgi_step / hyst_step
# ----------------------------------------------------------------------
def shmf_step(
    percepts: dict[str, dict[str, str]],
    step: int,
    state: dict,
    pipeline: ShmfPipeline,
    cfg: Optional[E.EngineConfig] = None,
    manual_reward: Optional[float] = None,
    rng=None,
) -> dict:
    cfg = cfg or E.EngineConfig()
    rng = rng or __import__("random")
    memory = pipeline.memory

    afferent = E.AfferentObject(percepts, time=step, state=state)
    summary = afferent.summary
    novelty, pipeline_stats = pipeline.novelty(summary)
    dlcbf_hit = memory.seen_before(summary)

    reflex_action, reflex_rule = E.reflexive_decision(afferent)

    scores: dict[str, float] = {}
    supports: dict[str, float] = {}
    contributions: dict[str, list[dict]] = {}
    for candidate in E.ACTIONS:
        score, support, contribs = pipeline.score_action(candidate, summary, step, cfg)
        scores[candidate] = score
        supports[candidate] = support
        contributions[candidate] = contribs

    if reflex_action is not None:
        action = reflex_action
        mode = "REFLEXIVE"
        policy_name = "REFLEX"
        best_action = max(scores, key=scores.get)
        epsilon = 0.0
        hesitated = False
        threshold = state.get("action_threshold", cfg.action_threshold)
        reflex_score, reflex_support, reflex_contribs = pipeline.score_action(
            action, summary, step, cfg, reflex_emphasis=True
        )
        scores[action] = reflex_score if reflex_support > 0.0 else scores[action]
        supports[action] = max(supports[action], reflex_support)
        contributions[action] = reflex_contribs or contributions[action]
    else:
        mode = "DELIBERATIVE"
        best_action = max(scores, key=scores.get)
        if pipeline.policy.urgent:
            # Sole convergent thinking: commit directly to the best
            # admissible answer, no explore/hesitate — same semantics as
            # HyST's own urgent handling, carried through the pipeline.
            action = best_action
            policy_name = "CONVERGE"
            epsilon = 0.0
            hesitated = False
            threshold = state.get("action_threshold", cfg.action_threshold)
        else:
            epsilon = E.clamp_unit(
                state.get("risk_bias", cfg.risk_bias) * (0.6 + 0.4 * novelty)
            )
            if rng.random() < epsilon:
                action = rng.choice(E.ACTIONS)
                policy_name = "EXPLORE"
            else:
                action = best_action
                policy_name = "EXPLOIT"

            threshold = state.get("action_threshold", cfg.action_threshold)
            hesitated = False
            if (
                cfg.hesitate_enabled
                and policy_name == "EXPLOIT"
                and scores[action] < threshold
                and action != "observe"
            ):
                action = "observe"
                policy_name = "HESITATE"
                hesitated = True

    penalty = None
    if manual_reward is not None:
        reward = E.clamp_reward(manual_reward)
        reward_source = "manual"
        reward_mean = None
        chosen_contribs = contributions.get(action, [])
    else:
        mean, support, contribs = pipeline.score_action(
            action, summary, step, cfg, reflex_emphasis=(mode == "REFLEXIVE")
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
        "policy": policy_name,
        "best_action": best_action,
        "epsilon": epsilon,
        "novelty": novelty,
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
        "memory_size": len(memory),
        "state": dict(state),
        "hard_slots": sorted(pipeline.policy.hard_slots),
        "divergent": pipeline.policy.divergent,
        "urgent": pipeline.policy.urgent,
        "pipeline": {
            "store_size": pipeline_stats.store_size,
            "after_partition": pipeline_stats.after_partition,
            "after_hard_soft": pipeline_stats.after_hard_soft,
            "partition_reduction_pct": pipeline_stats.partition_reduction_pct,
            "filter_reduction_pct": pipeline_stats.filter_reduction_pct,
            "total_reduction_pct": pipeline_stats.total_reduction_pct,
            "partition_elapsed_ms": pipeline_stats.partition_elapsed_ms,
            "filter_elapsed_ms": pipeline_stats.filter_elapsed_ms,
        },
    }


# ----------------------------------------------------------------------
# 4. Session wrapper — same shape as E.Session / HystSession / HmgiSession
# ----------------------------------------------------------------------
@dataclass
class ShmfSession:
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
    pipeline: Optional[ShmfPipeline] = None

    def __post_init__(self):
        import random
        if not self.state:
            self.state = E.init_state(self.cfg, self.profile)
        self.rng = random.Random(self.seed) if self.seed is not None else random.Random()
        self.pipeline = ShmfPipeline(self.memory, self.policy)

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
        result = shmf_step(
            percepts, self.step, self.state, self.pipeline,
            cfg=self.cfg, manual_reward=manual_reward, rng=self.rng,
        )
        result["graph"] = E.build_graph(result)
        result["episodes"] = [ep.to_dict() for ep in build_episodes(self.memory)[-12:]]
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
            "total_reduction_pct": result["pipeline"]["total_reduction_pct"],
            "partition_reduction_pct": result["pipeline"]["partition_reduction_pct"],
            "filter_reduction_pct": result["pipeline"]["filter_reduction_pct"],
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
        self.pipeline = ShmfPipeline(self.memory, self.policy)
        self.profile = profile or self.profile
        self.state = E.init_state(self.cfg, self.profile)
        self.step = max((r["step"] for r in self.memory.records), default=0)
        self.history = []
        self.last_result = None
        if seed is not None:
            self.seed = seed
        self.rng = random.Random(self.seed) if self.seed is not None else random.Random()


# ----------------------------------------------------------------------
# 5. Correctness/equivalence check, run by the smoke test
# ----------------------------------------------------------------------
def verify_pipeline_equivalence(memory: E.MemorySystem, policy: SlotPolicy,
                                 queries: list[tuple]) -> list[str]:
    """For every query, checks that running HMGI's partition then HyST's
    filter produces the same admissible set (as a set of steps) that
    running HyST's filter alone over the whole store would. This is the
    claim the module docstring makes about the ordering being safe, not
    an approximation — checked here against real data rather than merely
    asserted in prose.

    Returns a list of human-readable mismatch descriptions; empty means
    every query checked out.
    """
    from hyst_layer import split_similarity as _split

    problems: list[str] = []
    pipeline = ShmfPipeline(memory, policy)
    for query in queries:
        piped_scored, _ = pipeline.scored_candidates(query)
        piped_steps = {r["step"] for _, r in piped_scored}

        direct_steps = set()
        for record in memory.records:
            sim = _split(query, record["summary"], policy)
            if sim is not None:
                direct_steps.add(record["step"])

        if piped_steps != direct_steps:
            problems.append(
                f"mismatch: pipeline={sorted(piped_steps)} direct={sorted(direct_steps)}"
            )
    return problems

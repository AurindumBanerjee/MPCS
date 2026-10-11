"""
HMGI layer — multi-facet episodes and modality-partitioned screening
----------------------------------------------------------------------
Implements Step 2 of the perceptual-memory-indexing gameplan
(docs/MPCS_Memory_Indexing_Report.html, section 03 / 07 / 11, L0 + L1):
give each stored experience a relational facet alongside its existing
symbolic summary, and cut the linear scan down to the partitions that
actually share a modality with the query, instead of touching every record
on every step.

What this module deliberately does NOT build, and why
-------------------------------------------------------
The report's own ablation numbers, and its own build order (section 11),
gate the expensive parts of HMGI behind measured need:

  * No learned dense embeddings (the "E" facet). MPCS features are
    categorical; a real embedding table needs a training signal this
    system does not yet have, and nothing downstream reads it yet.
  * No HNSW-style approximate nearest-neighbour graph. The report warns
    partition overhead can exceed the saving below roughly 10^4-10^5
    records, and the current preset bank is ~70 records. Building a real
    ANN index now would add complexity with no measurable benefit and no
    way to tell if it even helps.
  * No MVCC delta store. That exists to avoid rebuilding an index on every
    write; there is no index yet to avoid rebuilding.

What this module DOES build, matching the report's "build cheap structure
first, index only when instrumentation says so" order:

  1. Episode — the four-facet record shape, with Phi (the engine's existing
     summary, untouched) and G (typed relational edges: previous episode,
     same-object/same-action neighbours) computed from context already
     available at write time. E and A stay as documented placeholders,
     ready for KERL, which is deferred.
  2. PartitionedMemory — wraps a MemorySystem and buckets record indices by
     active-modality set. A query only scans the union of buckets sharing
     at least one modality with it, which is a subset of the full store
     for any percept that omits a channel, and the whole store otherwise
     (a change of *scan scope*, not of stored representation).
  3. ScanInstrumentation — per-query counters (records scanned vs. store
     size, wall-clock) so a dashboard can show whether the partition is
     actually buying anything at the current scale, which is the report's
     explicit gate (section 11) before building anything more elaborate.

This module is additive: it reads MemorySystem.records and mpcs_engine's
similarity functions, it does not modify mpcs_engine.py.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "02_core"))

import mpcs_engine as E


# ----------------------------------------------------------------------
# 1. Episode — the four-facet record (L0)
# ----------------------------------------------------------------------
@dataclass
class Episode:
    """A memory record read as four facets instead of one flat tuple.

    Phi (structured) is exactly today's summary tuple — nothing about the
    engine's existing similarity/novelty math needs to change, since Phi
    *is* what those functions already consume.

    G (relational) is new: typed edges to the episode's neighbours in the
    same run. It costs nothing to sense (it is derived from step order and
    action/summary equality, not from a new channel) and gives the system
    something a flat tuple structurally cannot hold: "this followed that",
    "this involved the same kind of object as that".

    E (dense per-modality embeddings) and A (derived affect) are named
    here as documented gaps, matching CurrentStatus.md, but left unset.
    Populating them is KERL's job (deferred) and HMGI's own encoder design
    problem — doing it with hand-picked categorical embeddings now would be
    guesswork with nothing downstream to validate it against.
    """

    step: int
    summary: tuple                      # Phi — unchanged from mpcs_engine
    action: str
    reward: float
    active_modalities: tuple[str, ...]  # which Phi slots are non-empty
    prev_step: Optional[int] = None     # G — previous episode in the run
    same_action_prev: Optional[int] = None   # G — most recent same-action episode
    same_object_prev: Optional[int] = None   # G — most recent episode sharing
                                              # a vision.object_type value
    dense: Optional[dict] = None        # E — placeholder, unset (deferred)
    affect: Optional[dict] = None       # A — placeholder, unset (deferred, KERL)

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "percepts": E.describe_summary(self.summary),
            "action": self.action,
            "reward": self.reward,
            "active_modalities": list(self.active_modalities),
            "edges": {
                "prev": self.prev_step,
                "same_action_prev": self.same_action_prev,
                "same_object_prev": self.same_object_prev,
            },
        }


def _object_type_of(summary: tuple) -> Optional[str]:
    """Pull vision.object_type out of a summary tuple, if present."""
    described = E.describe_summary(summary)
    return described.get("vision", {}).get("object_type")


def build_episode(record: dict, prior_episodes: list["Episode"]) -> Episode:
    """Derive G-facet edges for one stored record against everything
    already turned into an Episode in this run, in step order.
    """
    summary = record["summary"]
    active = tuple(
        modality for modality, slot in zip(E.MODALITY_ORDER, summary) if slot
    )
    object_type = _object_type_of(summary)

    prev_step = prior_episodes[-1].step if prior_episodes else None
    same_action_prev = next(
        (ep.step for ep in reversed(prior_episodes) if ep.action == record["action"]),
        None,
    )
    same_object_prev = None
    if object_type is not None:
        same_object_prev = next(
            (ep.step for ep in reversed(prior_episodes)
             if _object_type_of(ep.summary) == object_type),
            None,
        )

    return Episode(
        step=record["step"],
        summary=summary,
        action=record["action"],
        reward=record["reward"],
        active_modalities=active,
        prev_step=prev_step,
        same_action_prev=same_action_prev,
        same_object_prev=same_object_prev,
    )


def build_episodes(memory: E.MemorySystem) -> list[Episode]:
    """Build the full G-facet graph for a memory store, in stored order.

    Stored order is step order for every path in mpcs_engine (store() is
    always append-only), so a single forward pass is enough — no need to
    sort.
    """
    episodes: list[Episode] = []
    for record in memory.records:
        episodes.append(build_episode(record, episodes))
    return episodes


# ----------------------------------------------------------------------
# 2. Scan instrumentation — the report's explicit gate before indexing
# ----------------------------------------------------------------------
@dataclass
class ScanStats:
    """One query's scan cost: what a dashboard needs to answer 'is the
    partition actually helping yet' rather than assuming it.
    """

    store_size: int
    scanned: int
    partitions_touched: int
    partitions_total: int
    elapsed_ms: float

    @property
    def reduction_pct(self) -> float:
        if self.store_size == 0:
            return 0.0
        return 100.0 * (1.0 - self.scanned / self.store_size)


@dataclass
class ScanInstrumentation:
    """Rolling log of ScanStats across a session, for the dashboard chart."""

    history: list[ScanStats] = field(default_factory=list)
    max_history: int = 200

    def record(self, stats: ScanStats) -> None:
        self.history.append(stats)
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def summary(self) -> dict:
        if not self.history:
            return {"count": 0}
        reductions = [s.reduction_pct for s in self.history]
        times = [s.elapsed_ms for s in self.history]
        return {
            "count": len(self.history),
            "avg_reduction_pct": sum(reductions) / len(reductions),
            "last_reduction_pct": reductions[-1],
            "avg_elapsed_ms": sum(times) / len(times),
            "last_elapsed_ms": times[-1],
            "last_store_size": self.history[-1].store_size,
            "last_scanned": self.history[-1].scanned,
        }


# ----------------------------------------------------------------------
# 3. PartitionedMemory — modality-partitioned scan scope (L1, structural)
# ----------------------------------------------------------------------
class PartitionedMemory:
    """Wraps a MemorySystem and buckets record indices by active-modality
    set, so a query only scans records sharing at least one modality with
    it.

    This is a scan-scope optimisation, not a new storage format: records
    still live in MemorySystem._store exactly as before. Rebuilding the
    partition index is O(N) and happens whenever the underlying store
    length changes, which at the interactive scale MPCS runs at today
    (single-digit ms for a few hundred records) is not worth guarding with
    an MVCC delta store — that machinery is deferred until instrumentation
    shows otherwise (report section 11).
    """

    def __init__(self, memory: E.MemorySystem):
        self.memory = memory
        self.instrumentation = ScanInstrumentation()
        self._partitions: dict[str, list[int]] = {m: [] for m in E.MODALITY_ORDER}
        self._built_for_size = -1
        self._rebuild()

    def _rebuild(self) -> None:
        self._partitions = {m: [] for m in E.MODALITY_ORDER}
        for index, record in enumerate(self.memory.records):
            for modality, slot in zip(E.MODALITY_ORDER, record["summary"]):
                if slot:
                    self._partitions[modality].append(index)
        self._built_for_size = len(self.memory)

    def _ensure_current(self) -> None:
        if self._built_for_size != len(self.memory):
            self._rebuild()

    def candidate_indices(self, query_summary: tuple) -> list[int]:
        """Indices of every record sharing at least one active modality
        with the query. Union across the query's active partitions, so a
        record active in touch+smell is found by either.
        """
        self._ensure_current()
        active = [
            modality for modality, slot in zip(E.MODALITY_ORDER, query_summary)
            if slot
        ]
        if not active:
            return list(range(len(self.memory)))

        seen: set[int] = set()
        for modality in active:
            seen.update(self._partitions.get(modality, []))
        # Sorted rather than left in union-discovery order: retrieve/recall
        # break similarity ties with a stable sort, and a tie's resolution
        # must not depend on which partition happened to contribute a
        # record first. Sorting here restores the same insertion order
        # memory.records iterates in, so a tie-broken top-k matches the
        # exhaustive scan's tie-broken top-k exactly, not just its score.
        return sorted(seen)

    def candidates(self, query_summary: tuple) -> list[dict]:
        """The actual records for candidate_indices(), instrumented."""
        start = time.perf_counter()
        indices = self.candidate_indices(query_summary)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        active_count = sum(
            1 for modality, slot in zip(E.MODALITY_ORDER, query_summary) if slot
        )
        self.instrumentation.record(ScanStats(
            store_size=len(self.memory),
            scanned=len(indices),
            partitions_touched=active_count or len(E.MODALITY_ORDER),
            partitions_total=len(E.MODALITY_ORDER),
            elapsed_ms=elapsed_ms,
        ))
        records = self.memory.records
        return [records[i] for i in indices]

    def partition_sizes(self) -> dict[str, int]:
        self._ensure_current()
        return {m: len(idxs) for m, idxs in self._partitions.items()}


# ----------------------------------------------------------------------
# 4. Partitioned novelty / retrieval / scoring — same contracts as
#    mpcs_engine, scoped to the candidate set from PartitionedMemory
# ----------------------------------------------------------------------
def compute_novelty_partitioned(
    summary: tuple,
    partitioned: PartitionedMemory,
) -> float:
    """Same semantics as mpcs_engine.compute_novelty, scanning only the
    modality-matched candidate set instead of the whole store. Because the
    candidate set is exactly the records that *can* score above zero
    (similarity_z requires overlapping, non-empty slots to contribute
    anything), this is not an approximation — it is the same answer,
    reached by skipping records that were mathematically guaranteed to
    contribute nothing.
    """
    if len(partitioned.memory) == 0:
        return 1.0
    candidates = partitioned.candidates(summary)
    if not candidates:
        return 1.0
    best = max(
        (E.normalized_similarity_z(summary, record["summary"]) for record in candidates),
        default=0.0,
    )
    return E.clamp_unit(1.0 - best)


def retrieve_partitioned(
    summary: tuple,
    partitioned: PartitionedMemory,
    k: int = 5,
) -> list[dict]:
    candidates = partitioned.candidates(summary)
    ranked = sorted(
        candidates,
        key=lambda m: E.similarity_z(summary, m["summary"]),
        reverse=True,
    )
    return ranked[:max(0, k)]


def recall_partitioned(
    summary: tuple,
    partitioned: PartitionedMemory,
    action: str,
    k: int = 5,
) -> list[dict]:
    candidates = [c for c in partitioned.candidates(summary) if c["action"] == action]
    ranked = sorted(
        candidates,
        key=lambda m: E.similarity_z(summary, m["summary"]),
        reverse=True,
    )
    return ranked[:max(0, k)]


def score_action_partitioned(
    action: str,
    partitioned: PartitionedMemory,
    summary: tuple,
    current_step: int,
    cfg: E.EngineConfig,
    reflex_emphasis: bool = False,
) -> tuple[float, float, list[dict]]:
    """Same contract and same arithmetic as mpcs_engine.score_action, but
    drawing candidates from the modality-partitioned scan instead of the
    full store.
    """
    cases = recall_partitioned(summary, partitioned, action, k=cfg.top_k)
    if not cases:
        return 0.5, 0.0, []

    weighted_sum = 0.0
    total_weight = 0.0
    contributions = []
    for record in cases:
        weight, detail = E._contribution_weight(
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
# 5. One HMGI cognitive step, mirroring mpcs_engine.cognitive_step
# ----------------------------------------------------------------------
def hmgi_step(
    percepts: dict[str, dict[str, str]],
    step: int,
    state: dict,
    partitioned: PartitionedMemory,
    cfg: Optional[E.EngineConfig] = None,
    manual_reward: Optional[float] = None,
    rng=None,
) -> dict:
    """A cognitive step identical in decision logic to mpcs_engine's, but
    every memory access — novelty, scoring, reward — goes through the
    partitioned scan instead of a full linear pass. Reflexes, exploration
    policy, and reward derivation are unchanged: HMGI only changes *how
    much of memory gets touched* to answer the same questions.
    """
    cfg = cfg or E.EngineConfig()
    rng = rng or __import__("random")
    memory = partitioned.memory

    afferent = E.AfferentObject(percepts, time=step, state=state)
    summary = afferent.summary
    novelty = compute_novelty_partitioned(summary, partitioned)
    dlcbf_hit = memory.seen_before(summary)

    reflex_action, reflex_rule = E.reflexive_decision(afferent)

    scores: dict[str, float] = {}
    supports: dict[str, float] = {}
    contributions: dict[str, list[dict]] = {}
    for candidate in E.ACTIONS:
        score, support, contribs = score_action_partitioned(
            candidate, partitioned, summary, step, cfg
        )
        scores[candidate] = score
        supports[candidate] = support
        contributions[candidate] = contribs

    if reflex_action is not None:
        action = reflex_action
        mode = "REFLEXIVE"
        policy = "REFLEX"
        best_action = E.best_evidenced_action(scores, supports)
        epsilon = 0.0
        hesitated = False
        threshold = state.get("action_threshold", cfg.action_threshold)
        reflex_score, reflex_support, reflex_contribs = score_action_partitioned(
            action, partitioned, summary, step, cfg, reflex_emphasis=True
        )
        scores[action] = reflex_score if reflex_support > 0.0 else scores[action]
        supports[action] = max(supports[action], reflex_support)
        contributions[action] = reflex_contribs or contributions[action]
    else:
        best = E.best_evidenced_action(scores, supports)
        epsilon = E.clamp_unit(
            state.get("risk_bias", cfg.risk_bias) * (0.6 + 0.4 * novelty)
        )
        if rng.random() < epsilon:
            action = rng.choice(E.ACTIONS)
            policy = "EXPLORE"
        else:
            action = best
            policy = "EXPLOIT"

        threshold = state.get("action_threshold", cfg.action_threshold)
        hesitated = False
        if (
            cfg.hesitate_enabled
            and policy == "EXPLOIT"
            and scores[action] < threshold
            and action != "observe"
        ):
            action = "observe"
            policy = "HESITATE"
            hesitated = True
        mode = "DELIBERATIVE"
        best_action = best

    penalty = None
    if manual_reward is not None:
        reward = E.clamp_reward(manual_reward)
        reward_source = "manual"
        reward_mean = None
        chosen_contribs = contributions.get(action, [])
    else:
        mean, support, contribs = score_action_partitioned(
            action, partitioned, summary, step, cfg,
            reflex_emphasis=(mode == "REFLEXIVE"),
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

    last_scan = partitioned.instrumentation.history[-1] if partitioned.instrumentation.history else None

    return {
        "step": step,
        "summary": summary,
        "percepts": E.describe_summary(summary),
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
        "scan": {
            "store_size": last_scan.store_size if last_scan else len(memory),
            "scanned": last_scan.scanned if last_scan else len(memory),
            "reduction_pct": last_scan.reduction_pct if last_scan else 0.0,
            "elapsed_ms": last_scan.elapsed_ms if last_scan else 0.0,
            "partitions_touched": last_scan.partitions_touched if last_scan else 0,
            "partitions_total": last_scan.partitions_total if last_scan else len(E.MODALITY_ORDER),
        },
    }


# ----------------------------------------------------------------------
# 6. Session wrapper — same shape as E.Session / HystSession
# ----------------------------------------------------------------------
@dataclass
class HmgiSession:
    """Holds one HMGI simulation run. Mirrors mpcs_engine.Session's shape
    so a dashboard can switch between stock, HyST, and HMGI scoring with
    minimal branching.
    """

    cfg: E.EngineConfig = field(default_factory=E.EngineConfig)
    memory: E.MemorySystem = field(default_factory=E.MemorySystem)
    state: dict = field(default_factory=dict)
    step: int = 0
    profile: str = "balanced"
    seed: Optional[int] = None
    history: list = field(default_factory=list)
    last_result: Optional[dict] = None
    rng: object = None
    partitioned: Optional[PartitionedMemory] = None

    def __post_init__(self):
        import random
        if not self.state:
            self.state = E.init_state(self.cfg, self.profile)
        self.rng = random.Random(self.seed) if self.seed is not None else random.Random()
        self.partitioned = PartitionedMemory(self.memory)

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
        result = hmgi_step(
            percepts, self.step, self.state, self.partitioned,
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
            "scan_reduction_pct": result["scan"]["reduction_pct"],
            "scan_elapsed_ms": result["scan"]["elapsed_ms"],
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
        self.partitioned = PartitionedMemory(self.memory)
        self.profile = profile or self.profile
        self.state = E.init_state(self.cfg, self.profile)
        self.step = max((r["step"] for r in self.memory.records), default=0)
        self.history = []
        self.last_result = None
        if seed is not None:
            self.seed = seed
        self.rng = random.Random(self.seed) if self.seed is not None else random.Random()

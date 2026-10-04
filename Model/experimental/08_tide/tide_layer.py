"""
TIDE layer — Time-bounded Inference over Dynamic Episodes
---------------------------------------------------------------
Builds the open items of the task audit (docs/MPCS_Progress_Report.html §12)
and the first steps of the spatio-temporal proposal
(docs/MPCS_Data_Structures_Report.html §11) on top of KERL. Retrieval is
still SHMF; the guard, fusion, heads and calibration are still KERL's. TIDE
changes how the retrieved structure is *read*:

1. Spreading activation with pruning (HMGI activation/pruning task).
   KERL's graph term was a fixed two-hop average. TIDE seeds every admitted
   candidate with activation = similarity x salience and spreads it over typed
   episode edges (prev, same action, same object, same place) for up to
   `spread_hops` hops, with per-hop decay, fan-out normalisation and a
   recency factor per node (ACT-R-style power decay). Contributions below
   `prune_threshold` x the strongest seed are cut, and at most `max_active`
   nodes survive. A candidate's graph term is the activation it *received*
   from others, normalised to [0, 1]. (Collins & Loftus 1975; HippoRAG's
   Personalized-PageRank reading is the same idea.)

2. Intensity and affect as salience (HMGI affect task). Seed activation is
   scaled by (1 + salience_gain x arousal) of the remembered episode; KERL's
   arousal already combines threat and intensity channels. Alarming, intense
   memories therefore spread further.

3. Place (spatio-temporal step 1). A percept may carry
   {"where": {"place": "kitchen/stove"}}. The engine ignores that modality;
   TIDE stores the place on the record, links episodes with same-place
   edges and adds w_p x (shared path prefix) to relevance.

4. Sufficiency-routed output (KERL tasks). If the best evidenced action leads
   the runner-up by `direct_margin` with at least `direct_min_support`, the
   read is DIRECT: action plus a one-line reason. Otherwise it is SUBGRAPH:
   the whole activated structure (nodes with action, reward, activation,
   whether it could vote, and the typed edges between them) is returned for
   inspection. No evidence at all stays UNGROUNDED, with the subgraph of
   whatever was activated.

5. Anytime deadline with passive verification (latency tasks). Under the
   urgent flag the read gets `urgent_deadline_ms` (or, deterministically,
   `urgent_budget` candidates). Candidates are read strongest first; when the
   budget runs out the decision is made on what was read and the rest are
   marked PASSIVE. A passive pass then reads everything and checks the
   decision — in a background thread, or synchronously when
   `verify_async=False`. Disagreements are logged and written onto the stored
   memory as `passive_check`. The SHMF index stage itself is not
   interruptible; the budget governs the deliberative read.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
for _d in ("02_core", "04_hyst", "05_hmgi", "06_shmf", "07_kerl"):
    sys.path.insert(0, os.path.join(_HERE, "..", _d))

import mpcs_engine as E
from hyst_layer import SlotPolicy
from hmgi_layer import build_episodes
from kerl_layer import (Candidate, KerlConfig, KerlReader, KerlSession, affect_of,
                        emotional_similarity, flat_features, kerl_step)

EDGE_TYPES = ("prev", "action", "object", "place")


# ----------------------------------------------------------------------
# 1. Configuration
# ----------------------------------------------------------------------
@dataclass
class TideConfig(KerlConfig):
    # spreading activation
    spread_hops: int = 3
    hop_decay: float = 0.5
    edge_weights: dict = field(default_factory=lambda: {
        "prev": 0.5, "action": 0.7, "object": 1.0, "place": 1.0})
    recency_power: float = 0.2          # node factor (1 + age) ** -power
    salience_gain: float = 0.8          # seed x (1 + gain * arousal)
    prune_threshold: float = 0.05       # relative to the strongest seed
    max_active: int = 80
    # place
    w_p: float = 0.15
    # sufficiency routing
    direct_margin: float = 0.25
    direct_min_support: float = 0.8
    # anytime deadline (urgent only)
    urgent_deadline_ms: Optional[float] = 2.0
    urgent_budget: Optional[int] = None  # candidates; overrides the clock when set
    min_read: int = 3
    verify_async: bool = True


def place_of(percepts: dict) -> Optional[str]:
    where = percepts.get("where") or {}
    return where.get("place")


def place_similarity(a: Optional[str], b: Optional[str]) -> float:
    """Shared path prefix: kitchen/stove vs kitchen/sink -> 0.5."""
    if not a or not b:
        return 0.0
    pa, pb = a.split("/"), b.split("/")
    shared = 0
    for x, y in zip(pa, pb):
        if x != y:
            break
        shared += 1
    return shared / max(len(pa), len(pb))


# ----------------------------------------------------------------------
# 2. Typed episode graph + spreading activation
# ----------------------------------------------------------------------
class ActivationGraph:
    """Typed, undirected episode edges built in one forward pass: previous
    episode, most recent same-action, same-object and same-place episode.
    `refresh` replaces the adjacency dict instead of mutating it, so a
    passive thread holding the old dict reads a consistent snapshot.
    """

    def __init__(self):
        self._size = -1
        self.neighbours: dict[int, list[tuple[int, str]]] = {}

    def refresh(self, memory: E.MemorySystem) -> None:
        if self._size == len(memory):
            return
        nb: dict[int, list[tuple[int, str]]] = {}
        prev = None
        last: dict[str, dict] = {t: {} for t in ("action", "object", "place")}
        for record in memory.records:
            step = record["step"]
            nb.setdefault(step, [])
            keys = {"action": record["action"],
                    "object": flat_features(record["summary"]).get("object_type"),
                    "place": record.get("place")}
            links = [(prev, "prev")] + [(last[t].get(k), t) for t, k in keys.items() if k]
            for other, typ in links:
                if other is not None and other != step:
                    nb[step].append((other, typ))
                    nb.setdefault(other, []).append((step, typ))
            prev = step
            for t, k in keys.items():
                if k:
                    last[t][k] = step
        self.neighbours = nb
        self._size = len(memory)


def spread(seeds: dict[int, float], neighbours: dict, now: int, acfg: TideConfig) -> dict:
    """Spreading activation from `seeds`. Returns activation per node,
    the amount each node received from others, and pruning counts."""
    if not seeds:
        return {"activation": {}, "received": {}, "pruned_edges": 0, "pruned_nodes": 0, "hops": 0}
    floor = acfg.prune_threshold * max(seeds.values())
    act = dict(seeds)
    received: dict[int, float] = {}
    frontier = dict(seeds)
    pruned_edges, hops = 0, 0
    for _ in range(acfg.spread_hops):
        nxt: dict[int, float] = {}
        for node, a in frontier.items():
            edges = neighbours.get(node, ())
            if not edges:
                continue
            share = a * acfg.hop_decay / len(edges)
            for other, typ in edges:
                add = share * acfg.edge_weights.get(typ, 0.0) * (1 + max(0, now - other)) ** -acfg.recency_power
                if add < floor:
                    pruned_edges += 1
                    continue
                nxt[other] = nxt.get(other, 0.0) + add
        if not nxt:
            break
        hops += 1
        for node, add in nxt.items():
            act[node] = act.get(node, 0.0) + add
            received[node] = received.get(node, 0.0) + add
        frontier = nxt
    ranked = sorted(act.items(), key=lambda p: -p[1])
    kept = {n: a for n, a in ranked[:acfg.max_active] if a >= floor}
    return {"activation": kept, "received": {n: received.get(n, 0.0) for n in kept},
            "pruned_edges": pruned_edges, "pruned_nodes": len(act) - len(kept), "hops": hops}


# ----------------------------------------------------------------------
# 3. The TIDE reader
# ----------------------------------------------------------------------
class TideReader(KerlReader):
    """KERL reader with activation-based graph term, place relevance,
    sufficiency routing and an anytime budget. Returns everything
    kerl_step expects, plus an `tide` block."""

    def __init__(self, memory: E.MemorySystem, policy: Optional[SlotPolicy] = None,
                 acfg: Optional[TideConfig] = None, auto_relax: bool = True):
        super().__init__(memory, policy, acfg or TideConfig(), auto_relax=auto_relax)
        self.graph = ActivationGraph()
        self.query_place: Optional[str] = None
        self.verifications: list[dict] = []
        self._lock = threading.RLock()
        self.last_tide: Optional[dict] = None
        self._threads: list[threading.Thread] = []

    @property
    def acfg(self) -> TideConfig:
        return self.kcfg

    # -- budget -----------------------------------------------------------
    def _budget(self) -> tuple[Optional[int], Optional[float]]:
        if not self.policy.urgent:
            return None, None
        if self.acfg.urgent_budget is not None:
            return self.acfg.urgent_budget, None
        return None, self.acfg.urgent_deadline_ms

    # -- one read ------------------------------------------------------------
    def read(self, summary: tuple, step: int, cfg: E.EngineConfig,
             reflex_emphasis: bool = False) -> dict:
        t0 = time.perf_counter()
        self.graph.refresh(self.memory)
        novelty, stats = self.pipeline.novelty(summary)
        scored, _ = self.pipeline.scored_candidates(summary)
        scored = sorted(scored, key=lambda p: (-p[0], p[1]["step"]))   # strongest first
        budget_n, budget_ms = self._budget()
        reading = self._read_core(scored, summary, step, cfg, reflex_emphasis, novelty,
                                  self.graph.neighbours, self.query_place, t0,
                                  budget_n, budget_ms, collect_pairs=True)
        reading["stats"] = stats
        reading["tide"]["elapsed_ms"] = (time.perf_counter() - t0) * 1000.0
        self.last_tide = reading["tide"]
        if reading["tide"]["passive"]:
            self._schedule_verification(scored, summary, step, cfg, reflex_emphasis, novelty,
                                        self.graph.neighbours, self.query_place, reading)
        return reading

    def _read_core(self, scored, summary, step, cfg, reflex_emphasis, novelty, neighbours,
                   query_place, t0, budget_n, budget_ms, collect_pairs) -> dict:
        acfg = self.acfg
        query_flat = flat_features(summary)
        query_affect = affect_of(query_flat)
        needed = self.decisive_modalities(query_flat)

        # Anytime read: strongest candidates first, stop at the budget.
        read_list, passive = [], []
        for i, (sim, record) in enumerate(scored):
            if i >= acfg.min_read and (
                    (budget_n is not None and i >= budget_n) or
                    (budget_ms is not None and (time.perf_counter() - t0) * 1000.0 > budget_ms)):
                passive = [r for _, r in scored[i:]]
                break
            cand = Candidate(record=record, sim_s=sim)
            cand.affect = affect_of(flat_features(record["summary"]))
            read_list.append(cand)

        kept, rejected = [], []
        for cand in read_list:
            if acfg.guard_enabled and needed and not self.covers(cand.record["summary"], needed):
                rejected.append(cand)
            else:
                kept.append(cand)

        # Spreading activation seeded by admitted candidates, scaled by salience.
        seeds = {c.record["step"]: c.sim_s * (1.0 + acfg.salience_gain * c.affect[1]) for c in kept}
        sp = spread(seeds, neighbours, step, acfg)
        top_received = max(sp["received"].values(), default=0.0)

        w = acfg.weights()
        w_s = w["w_s"] * (1.25 - 0.5 * novelty)
        w_g = w["w_g"] * (0.75 + 0.5 * novelty)
        w_e = w["w_e"]
        for cand in kept + rejected:
            s = cand.record["step"]
            cand.sim_e = emotional_similarity(query_affect, cand.affect)
            cand.graph = (sp["received"].get(s, 0.0) / top_received) if top_received > 0 else 0.0
            cand.relevance = (w_s * cand.sim_s + w_e * cand.sim_e + w_g * cand.graph
                              + acfg.w_p * place_similarity(query_place, cand.record.get("place")))
        for cand in kept:
            age = max(0, step - cand.record.get("step", step))
            boost = cfg.expert_weight_boost if cand.record.get("is_expert") else 1.0
            if reflex_emphasis and cand.record.get("mode") == "REFLEXIVE":
                boost *= cfg.reflex_memory_boost
            cand.omega = cand.relevance * (cfg.time_decay ** age) * boost

        if collect_pairs and rejected and kept:
            best = max(kept, key=lambda c: c.omega)
            for miss in rejected:
                self.pairs.append((best.features(), miss.features()))
            del self.pairs[:-acfg.max_pairs]

        head_a = self._head_a(kept, cfg)
        head_e = self._head_e(kept, head_a, query_affect)
        route, margin, best = self._route(head_a)
        if route == "DIRECT":
            v = head_a[best]
            head_x = (f"Direct: {best} leads by {margin:.2f} with support {v['support']:.2f} "
                      f"from {len(v['cases'])} episode(s); strongest step {v['cases'][0].record['step']}.")
        else:
            head_x = self._head_x(query_flat, kept, rejected, head_a, head_e, needed)
        return {
            "novelty": novelty, "kept": kept, "rejected": rejected,
            "head_a": head_a, "head_e": head_e, "head_x": head_x,
            "grounded": best is not None,
            "weights_used": {"w_s": w_s, "w_e": w_e, "w_g": w_g, "w_p": acfg.w_p},
            "tide": {
                "route": route, "margin": margin, "best": best or "observe",
                "subgraph": None if route == "DIRECT" else self._subgraph(sp, kept, neighbours),
                "activation": {"seeds": len(seeds), "active": len(sp["activation"]),
                               "hops": sp["hops"], "pruned_edges": sp["pruned_edges"],
                               "pruned_nodes": sp["pruned_nodes"]},
                "read": len(read_list), "total": len(scored), "passive": len(passive),
                "budget": budget_n if budget_n is not None else budget_ms,
                "budget_kind": "candidates" if budget_n is not None else ("ms" if budget_ms else None),
                "query_place": query_place,
            },
        }

    def _route(self, head_a: dict) -> tuple[str, float, Optional[str]]:
        ev = sorted(((v["value"], a) for a, v in head_a.items() if v["support"] > 0), reverse=True)
        if not ev:
            return "UNGROUNDED", 0.0, None
        best = ev[0][1]
        margin = ev[0][0] - (ev[1][0] if len(ev) > 1 else 0.5)
        if margin >= self.acfg.direct_margin and head_a[best]["support"] >= self.acfg.direct_min_support:
            return "DIRECT", margin, best
        return "SUBGRAPH", margin, best

    def _subgraph(self, sp: dict, kept: list[Candidate], neighbours: dict) -> dict:
        active = sp["activation"]
        voters = {c.record["step"] for c in kept}
        by_step = {r["step"]: r for r in self.memory.records if r["step"] in active}
        nodes = [{"step": s, "action": by_step[s]["action"], "reward": by_step[s]["reward"],
                  "activation": a, "voter": s in voters, "place": by_step[s].get("place"),
                  "is_expert": bool(by_step[s].get("is_expert"))}
                 for s, a in sorted(active.items(), key=lambda p: -p[1]) if s in by_step]
        edges = sorted({(min(s, o), max(s, o), t) for s in active
                        for o, t in neighbours.get(s, ()) if o in active})
        return {"nodes": nodes, "edges": [{"a": a, "b": b, "type": t} for a, b, t in edges]}

    # -- passive verification ---------------------------------------------------
    def _schedule_verification(self, scored, summary, step, cfg, reflex_emphasis, novelty,
                               neighbours, query_place, partial) -> None:
        def run():
            full = self._read_core(scored, summary, step, cfg, reflex_emphasis, novelty, neighbours,
                                   query_place, time.perf_counter(), None, None, collect_pairs=False)
            entry = {"step": step, "partial_best": partial["tide"]["best"],
                     "full_best": full["tide"]["best"], "read": partial["tide"]["read"],
                     "total": partial["tide"]["total"]}
            entry["agreed"] = entry["partial_best"] == entry["full_best"]
            with self._lock:
                self.verifications.append(entry)
                self._annotate(entry)

        if self.acfg.verify_async:
            t = threading.Thread(target=run, daemon=True)
            self._threads.append(t)
            t.start()
        else:
            run()

    def _annotate(self, entry: dict) -> None:
        # The step's own record is stored after the read; tide_step calls
        # this again once it exists, so whichever comes second writes it.
        for rec in reversed(self.memory.records[-50:]):
            if rec["step"] == entry["step"]:
                rec["passive_check"] = entry
                return

    def wait_passive(self, timeout: float = 5.0) -> None:
        for t in self._threads:
            t.join(timeout)
        self._threads = [t for t in self._threads if t.is_alive()]

    def verification_summary(self) -> dict:
        with self._lock:
            n = len(self.verifications)
            agreed = sum(v["agreed"] for v in self.verifications)
        return {"checked": n, "agreed": agreed, "disagreed": n - agreed}


# ----------------------------------------------------------------------
# 4. Step and session
# ----------------------------------------------------------------------
def tide_step(percepts: dict, step: int, state: dict, reader: TideReader,
               cfg: Optional[E.EngineConfig] = None, manual_reward: Optional[float] = None,
               rng=None) -> dict:
    """kerl_step with the TIDE reader, plus place bookkeeping. The lock
    keeps a passive thread from annotating while the step stores."""
    place = place_of(percepts)
    with reader._lock:
        reader.query_place = place
        result = kerl_step(percepts, step, state, reader, cfg=cfg,
                           manual_reward=manual_reward, rng=rng)
        reader.memory.records[-1]["place"] = place
        for entry in reader.verifications:
            if entry["step"] == step:
                reader._annotate(entry)
    result["tide"] = reader.last_tide
    result["place"] = place
    return result


@dataclass
class TideSession(KerlSession):
    kcfg: TideConfig = field(default_factory=TideConfig)

    def __post_init__(self):
        super().__post_init__()
        self.reader = TideReader(self.memory, self.policy, self.kcfg)

    def run_step(self, percepts: dict, manual_reward: Optional[float] = None) -> dict:
        self.step += 1
        result = tide_step(percepts, self.step, self.state, self.reader,
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
            "route": result["tide"]["route"],
        })
        return result

    def reset(self, memory: Optional[E.MemorySystem] = None, profile: Optional[str] = None,
              seed: Optional[int] = None) -> None:
        super().reset(memory=memory, profile=profile, seed=seed)
        self.reader = TideReader(self.memory, self.policy, self.kcfg)

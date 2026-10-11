"""
Baseline v2 — the original MPCS baseline on the four-sense schema
--------------------------------------------------------------------
The legacy baseline (Model/reference/mpcs.py, G1) only knows vision + audio
and four actions, so on the newer banks it cannot perceive heat or smell and
cannot say `withdraw`. Baseline v2 keeps its *algorithm* unchanged and gives
it the same data the newer models see:

  similarity   number of matching feature values / number of query features
               (no confidences, no hard/soft split, no ordinal closeness)
  retrieval    global top-k (k = 5) over the whole memory, no index
  scoring      per action: similarity x 0.99^age weighted mean reward over
               the retrieved cases that took that action
  decision     best evidenced action; observe when nothing is evidenced
               (the engine's rule since the empty-evidence fix, so the
               comparison isolates retrieval rather than tie-breaking)
  gate         optional: consult memory only if the d-left counting Bloom
               filter says the exact scene was seen (the G2/G3 idea)

It reads the engine's MemorySystem directly, so it runs on bank v2/v3
exactly as HyST, HMGI and SHMF do. It is a reference point, not a
contender: everything HyST/HMGI/SHMF add is absent by design.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "02_core"))

import mpcs_engine as E

TOP_K = 5
TIME_DECAY = 0.99


def flat(summary: tuple) -> dict[str, str]:
    return {key: value for slot in summary for key, value, _ in slot}


def similarity(query: tuple, memory: tuple) -> float:
    """Share of the query's features whose value the memory matches exactly."""
    q, m = flat(query), flat(memory)
    return sum(m.get(k) == v for k, v in q.items()) / len(q) if q else 0.0


@dataclass
class BaselineV2:
    memory: E.MemorySystem
    gate: bool = False
    k: int = TOP_K

    def retrieve(self, summary: tuple) -> list[tuple[float, dict]]:
        if self.gate and not self.memory.seen_before(summary):
            return []
        ranked = sorted(((similarity(summary, r["summary"]), r) for r in self.memory.records),
                        key=lambda p: (-p[0], p[1]["step"]))
        return [p for p in ranked[:self.k] if p[0] > 0]

    def recommend(self, summary: tuple, step: int) -> dict:
        cases = self.retrieve(summary)
        scores, supports = {}, {}
        for action in E.ACTIONS:
            num = den = 0.0
            for sim, r in cases:
                if r["action"] == action:
                    w = sim * TIME_DECAY ** max(0, step - r["step"])
                    num += w * r["reward"]
                    den += w
            scores[action] = num / den if den else 0.5
            supports[action] = den
        novelty = 1.0 - max((similarity(summary, r["summary"]) for r in self.memory.records), default=0.0)
        return {"best": E.best_evidenced_action(scores, supports), "scores": scores,
                "supports": supports, "cases": cases, "novelty": novelty,
                "gate": (self.memory.seen_before(summary) if self.gate else None)}

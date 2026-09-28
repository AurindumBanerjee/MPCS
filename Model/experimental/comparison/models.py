"""
Uniform adapters over every MPCS generation, calling each model's own code.

All adapters take a *canonical percept* ({modality: {feature: value}} in the
v2 feature schema) and return the model's greedy recommendation with
exploration switched off. Each adapter uses its model's own decision rule, so
quirks such as a 0.5 tie resolving to `ignore` count against that model.

Generation  Model        Source                                  Memory gate
----------  -----------  --------------------------------------  -----------------
G1          Basic        Model/reference/mpcs.py                 none
G2          Bloom        Model/reference/BloomMPCS.py            Bloom filter
G3          Z+dlCBF      experimental/01_baseline_z/MPCS_Z.py    d-left counting BF
G4          Core v2      experimental/02_core/mpcs_engine.py     none (dlCBF is a hint)
G5          HyST         experimental/04_hyst                    hard/soft filter
G6          HMGI         experimental/05_hmgi                    modality partitions
G7          SHMF         experimental/06_shmf                    partition -> filter
G8          KERL         experimental/07_kerl                    SHMF + near-miss guard

G1-G3 only know vision + audio and four actions (no `withdraw`). They receive
a projection of each percept with touch and smell dropped and
`audio_intensity` renamed to `intensity` — the schema limit is part of what
is being measured, not something the harness hides.
"""

from __future__ import annotations

import os
import random
import sys
import time

_EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REF = os.path.join(os.path.dirname(_EXP), "reference")
for _p in (_REF, os.path.join(_EXP, "01_baseline_z"), os.path.join(_EXP, "02_core"),
           os.path.join(_EXP, "04_hyst"), os.path.join(_EXP, "05_hmgi"),
           os.path.join(_EXP, "06_shmf"), os.path.join(_EXP, "07_kerl")):
    sys.path.insert(0, _p)

import mpcs as G1
import BloomMPCS as G2
import MPCS_Z as G3
import mpcs_engine as E
from hyst_layer import SlotPolicy, compute_novelty_hyst, score_action_hyst
from hmgi_layer import PartitionedMemory, compute_novelty_partitioned, score_action_partitioned
from shmf_layer import ShmfPipeline
from kerl_layer import KerlReader

LEGACY_ACTIONS = list(G1.ACTIONS)


def legacy_view(percept: dict) -> tuple[dict, dict]:
    """Project a canonical percept onto the G1-G3 (vision, audio) schema."""
    vision = dict(percept.get("vision", {}))
    audio_src = percept.get("audio", {})
    audio = {}
    if "sound_type" in audio_src:
        audio["sound_type"] = audio_src["sound_type"]
    if "audio_intensity" in audio_src:
        audio["intensity"] = audio_src["audio_intensity"]
    return vision, audio


class Adapter:
    name = "?"
    generation = "?"
    schema = "v2"           # "legacy" = vision+audio, 4 actions
    actions = E.ACTIONS

    def load(self, records: list[dict]) -> float:
        """Build this model's memory from canonical records; returns ms."""
        t0 = time.perf_counter()
        self._load(records)
        return (time.perf_counter() - t0) * 1000.0

    def recommend(self, percept: dict, step: int) -> dict:
        """Returns best, scores, evidence (bool), scanned (int), gate (bool|None), novelty."""
        raise NotImplementedError


# ----------------------------------------------------------------------
# G1-G3: legacy two-modality models
# ----------------------------------------------------------------------
class _Legacy(Adapter):
    schema = "legacy"
    actions = LEGACY_ACTIONS
    mod = None

    def _summary(self, vision, audio):
        return self.mod.AfferentObject(vision=vision, audio=audio, time=0, state={}).summary

    def _store(self, summary, rec):
        self.mem.store(summary, rec["action"], rec["reward"], rec["step"])

    def _load(self, records):
        self.mem = self.mod.MemorySystem()
        for rec in records:
            self._store(self._summary(*legacy_view(rec["percept"])), rec)

    def _gate(self, summary):
        return None

    def _novelty(self, summary):
        return self.mod.compute_novelty(summary, self.mem)

    def _simulate(self, action, cases, summary, step):
        return self.mod.simulate_action(action, cases, summary, step)

    def _nsim(self, a, b):
        return self.mod.normalized_similarity(a, b)

    def recommend(self, percept, step):
        vision, audio = legacy_view(percept)
        summary = self._summary(vision, audio)
        random.seed(step)  # legacy scorers roll a random prior when nothing is retrieved
        cases = self.mem.retrieve(summary)
        scores = {a: self._simulate(a, cases, summary, step) for a in self.actions}
        evidence = any(c["action"] in self.actions and self._nsim(summary, c["summary"]) > 0
                       for c in cases)
        gate = self._gate(summary)
        return {"best": max(scores, key=scores.get), "scores": scores, "evidence": evidence,
                "scanned": 0 if gate is False else len(self.mem),
                "gate": gate, "novelty": self._novelty(summary)}


class Basic(_Legacy):
    name, generation, mod = "Basic", "G1", G1


class Bloom(_Legacy):
    name, generation, mod = "Bloom", "G2", G2

    def _gate(self, summary):
        return self.mem.maybe_seen(summary)


class ZdlCBF(_Legacy):
    name, generation, mod = "Z+dlCBF", "G3", G3

    def _summary(self, vision, audio):
        return G3.AfferentZObject(vision=vision, audio=audio, time=0, state={}).summary

    def _store(self, summary, rec):
        self.mem.store(summary, rec["action"], rec["reward"], rec["step"],
                       confidence=1.0, is_expert=rec.get("is_expert", False))

    def _load(self, records):
        self.mem = G3.MemorySystemZ()
        for rec in records:
            self._store(self._summary(*legacy_view(rec["percept"])), rec)

    def _gate(self, summary):
        return self.mem._dlcbf.query(self.mem._summary_key(summary))

    def _novelty(self, summary):
        return G3.compute_novelty_z(summary, self.mem)

    def _simulate(self, action, cases, summary, step):
        return G3.simulate_action_z(action, cases, summary, step)

    def _nsim(self, a, b):
        return G3.normalized_similarity_z(a, b)


# ----------------------------------------------------------------------
# G4-G8: four-modality models sharing the v2 engine's MemorySystem
# ----------------------------------------------------------------------
class _Modern(Adapter):
    cfg = E.EngineConfig()

    def _load(self, records):
        self.mem = E.MemorySystem()
        for rec in records:
            self.mem.store(E.summary_of(rec["percept"]), rec["action"], rec["reward"], rec["step"],
                           is_expert=rec.get("is_expert", False), mode=rec.get("mode", "DELIBERATIVE"))
        self._after_load()

    def _after_load(self):
        pass

    def _score(self, summary, action, step):
        raise NotImplementedError

    def _novelty(self, summary):
        raise NotImplementedError

    def _scanned(self, summary):
        return len(self.mem)

    def recommend(self, percept, step):
        summary = E.summary_of(percept)
        scores, supports = {}, {}
        for a in E.ACTIONS:
            scores[a], supports[a], _ = self._score(summary, a, step)
        # The engine's own deliberate(): best evidenced action, observe when none.
        return {"best": E.best_evidenced_action(scores, supports), "scores": scores,
                "evidence": any(s > 0 for s in supports.values()),
                "scanned": self._scanned(summary), "gate": None,
                "novelty": self._novelty(summary)}


class CoreV2(_Modern):
    name, generation = "Core v2", "G4"

    def _score(self, s, a, step):
        return E.score_action(a, self.mem, s, step, self.cfg)

    def _novelty(self, s):
        return E.compute_novelty(s, self.mem)


class HyST(_Modern):
    name, generation = "HyST", "G5"

    def _after_load(self):
        self.policy = SlotPolicy()

    def _score(self, s, a, step):
        return score_action_hyst(a, self.mem, s, step, self.cfg, self.policy)

    def _novelty(self, s):
        return compute_novelty_hyst(s, self.mem, self.policy)[0]


class HMGI(_Modern):
    name, generation = "HMGI", "G6"

    def _after_load(self):
        self.part = PartitionedMemory(self.mem)

    def _score(self, s, a, step):
        return score_action_partitioned(a, self.part, s, step, self.cfg)

    def _novelty(self, s):
        return compute_novelty_partitioned(s, self.part)

    def _scanned(self, s):
        return len(self.part.candidate_indices(s))


class SHMF(_Modern):
    name, generation = "SHMF", "G7"

    def _after_load(self):
        self.pipe = ShmfPipeline(self.mem, SlotPolicy())

    def _score(self, s, a, step):
        return self.pipe.score_action(a, s, step, self.cfg)

    def _novelty(self, s):
        return self.pipe.novelty(s)[0]

    def _scanned(self, s):
        return self.pipe.scored_candidates(s)[1].after_partition


class KERL(_Modern):
    name, generation = "KERL", "G8"

    def _after_load(self):
        self.reader = KerlReader(self.mem, SlotPolicy())

    def recommend(self, percept, step):
        reading = self.reader.read(E.summary_of(percept), step, self.cfg)
        head_a = reading["head_a"]
        evidenced = {a: v["value"] for a, v in head_a.items() if v["support"] > 0}
        return {"best": max(evidenced, key=evidenced.get) if evidenced else "observe",
                "scores": {a: v["value"] for a, v in head_a.items()},
                "evidence": bool(evidenced), "scanned": reading["stats"].after_partition,
                "gate": None, "novelty": reading["novelty"]}


ALL_MODELS = [Basic, Bloom, ZdlCBF, CoreV2, HyST, HMGI, SHMF, KERL]

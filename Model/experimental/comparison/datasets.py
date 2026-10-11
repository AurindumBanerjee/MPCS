"""
The three preset memory banks in one canonical form, plus their query sets.

Canonical record: {"percept": {modality: {feature: value}}, "action", "reward",
"step", "is_expert", "mode"} in the v2 feature schema. The v1 bank's audio
`intensity` becomes `audio_intensity`; nothing else changes.

Bank  Source                                         Size  Modalities       Actions
v1    Model/reference/mpcs_preset_memory.py            30  vision+audio     4
v2    experimental/02_core/mpcs_preset_v2.py           70  all four         5
v3    experimental/02_core/mpcs_preset_v3.py          700  partial (1-4)    5

Query sets (label = the correct action; queries are never stored):
  seen   Exact percepts from the bank whose best-rewarded action scored >= 0.6.
         A membership filter's best case: every query was stored verbatim.
  near   Each labelled seen percept with ONE non-safety feature changed to
         another value, excluding any variant that exists verbatim in the bank.
         Safety features (anything in a v2 reflex rule) are never changed, so
         the original verdict still holds. The generalisation case.
  clean  v3 only: fresh samples from the 16 scenario archetypes (label = the
         archetype's action). Same generator as the bank, different seed.
  noisy  v3 only: as `clean`, with one feature re-drawn from its full range —
         sensor noise that may leave the archetype's value pool.
"""

from __future__ import annotations

import os
import random
import sys

_EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(_EXP), "reference"))
sys.path.insert(0, os.path.join(_EXP, "02_core"))

import mpcs_engine as E
import mpcs_preset_v2 as P2
import mpcs_preset_v3 as P3

SAFETY_FEATURES = {k for cond, _ in E.REFLEX_RULES for k in cond}
DANGER = {"alert", "withdraw"}


def _record(percept, action, reward, step, is_expert=False, mode="DELIBERATIVE") -> dict:
    return {"percept": percept, "action": action, "reward": reward, "step": step,
            "is_expert": is_expert, "mode": mode}


def bank_v1() -> list[dict]:
    from mpcs_preset_memory import build_preset_memory  # reference launcher
    out = []
    for m in build_preset_memory("balanced")._store:
        vision, audio = dict(m["summary"][0]), dict(m["summary"][1])
        audio["audio_intensity"] = audio.pop("intensity")
        out.append(_record({"vision": vision, "audio": audio}, m["action"], m["reward"], m["step"]))
    return out


def bank_v2() -> list[dict]:
    return [_record(p, a, r, s, mode=mode) for p, a, r, s, mode, _ in P2.ALL_ENTRIES]


def bank_v3() -> list[dict]:
    return [_record(e.percept, e.action, e.reward, e.step, e.is_expert, e.mode)
            for e in P3.ALL_ENTRIES_V3]


BANKS = {"v1": bank_v1, "v2": bank_v2, "v3": bank_v3}


def _key(percept: dict) -> tuple:
    return tuple(sorted((m, tuple(sorted(f.items()))) for m, f in percept.items()))


def seen_queries(records: list[dict]) -> list[tuple[dict, str]]:
    best: dict[tuple, dict] = {}
    for r in records:
        k = _key(r["percept"])
        if k not in best or r["reward"] > best[k]["reward"]:
            best[k] = r
    return [(r["percept"], r["action"]) for r in best.values() if r["reward"] >= 0.6]


def near_queries(records: list[dict]) -> list[tuple[dict, str]]:
    stored = {_key(r["percept"]) for r in records}
    out, emitted = [], set()
    for percept, label in seen_queries(records):
        for modality, features in percept.items():
            for feature, value in features.items():
                if feature in SAFETY_FEATURES:
                    continue
                for other in E.MODALITIES[modality][feature]:
                    if other == value:
                        continue
                    variant = {m: dict(f) for m, f in percept.items()}
                    variant[modality][feature] = other
                    k = _key(variant)
                    if k in stored or k in emitted:
                        continue
                    emitted.add(k)
                    out.append((variant, label))
    return out


def archetype_queries(seed: int, n: int, noisy: bool) -> list[tuple[dict, str]]:
    rng = random.Random(seed)
    out = []
    for i in range(n):
        arch = P3.ARCHETYPES[i % len(P3.ARCHETYPES)]
        percept, _ = P3._sample_percept(rng, arch)
        if noisy:
            m = rng.choice(list(percept))
            f = rng.choice(list(percept[m]))
            percept[m][f] = rng.choice(E.MODALITIES[m][f])
        out.append((percept, arch.action))
    return out


NEAR_CAP = 600   # v3 yields thousands of near variants; a fixed-seed sample keeps runs quick


def query_sets(bank: str, records: list[dict]) -> dict[str, list[tuple[dict, str]]]:
    near = near_queries(records)
    if len(near) > NEAR_CAP:
        near = random.Random(7).sample(near, NEAR_CAP)
    sets = {"seen": seen_queries(records), "near": near}
    if bank == "v3":
        sets["clean"] = archetype_queries(99, 480, noisy=False)
        sets["noisy"] = archetype_queries(123, 480, noisy=True)
    return sets

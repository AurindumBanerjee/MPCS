"""Smoke checks for the TIDE layer — run directly, no test framework."""

from __future__ import annotations

import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _d in ("02_core", "04_hyst", "06_shmf", "07_kerl"):
    sys.path.insert(0, os.path.join(_HERE, "..", _d))
sys.path.insert(0, _HERE)

import mpcs_engine as E
from mpcs_preset_v3 import build_preset_memory_v3
from hyst_layer import SlotPolicy
from tide_layer import (ActivationGraph, TideConfig, TideReader, TideSession,
                        place_similarity, spread)


def summ(**features) -> tuple:
    percepts: dict = {}
    for key, value in features.items():
        percepts.setdefault(E.FEATURE_MODALITY[key], {})[key] = value
    return E.summary_of(percepts)


def main() -> None:
    cfg = E.EngineConfig()

    # 1. Spreading activation reaches neighbours, decays per hop, and prunes.
    chain = {1: [(2, "prev")], 2: [(1, "prev"), (3, "prev")], 3: [(2, "prev"), (4, "prev")],
             4: [(3, "prev")]}
    loose = spread({1: 1.0}, chain, now=4, acfg=TideConfig(prune_threshold=0.0))
    a = loose["activation"]
    assert a[1] > a[2] > a[3] > 0, a
    tight = spread({1: 1.0}, chain, now=4, acfg=TideConfig(prune_threshold=0.2))
    assert 3 not in tight["activation"] and tight["pruned_edges"] > 0, tight
    capped = spread({1: 1.0}, chain, now=4, acfg=TideConfig(prune_threshold=0.0, max_active=2))
    assert len(capped["activation"]) == 2
    print("ok  spreading activation decays per hop, prunes weak edges, caps active nodes")

    # 2. Salience: an arousing memory spreads further than a calm one of equal similarity.
    def neighbour_activation(seed_features):
        mem = E.MemorySystem()
        mem.store(summ(**seed_features), action="alert", reward=0.8, step=1)
        mem.store(summ(object_type="box", color="grey"), action="observe", reward=0.5, step=2)
        reader = TideReader(mem, SlotPolicy(hard_slots=set()), TideConfig(prune_threshold=0.0))
        reader.graph.refresh(mem)
        from kerl_layer import affect_of, flat_features
        rec = mem.records[0]
        arousal = affect_of(flat_features(rec["summary"]))[1]
        seed = {1: 1.0 * (1 + reader.acfg.salience_gain * arousal)}
        return spread(seed, reader.graph.neighbours, 2, reader.acfg)["activation"].get(2, 0.0)

    calm = neighbour_activation({"object_type": "box", "sound_type": "silence"})
    loud = neighbour_activation({"object_type": "box", "sound_type": "alarm", "audio_intensity": "high"})
    assert loud > calm, (loud, calm)
    print(f"ok  salience: alarm-memory passes {loud:.3f} vs calm {calm:.3f} to its neighbour")

    # 3. Place: hierarchical similarity and same-place edges.
    assert place_similarity("kitchen/stove", "kitchen/stove") == 1.0
    assert place_similarity("kitchen/stove", "kitchen/sink") == 0.5
    assert place_similarity("kitchen/stove", None) == 0.0
    session = TideSession(seed=1, policy=SlotPolicy())
    session.kcfg.verify_async = False
    for i in range(4):
        where = "kitchen/stove" if i % 2 == 0 else "garage"
        session.run_step({"vision": {"object_type": "pan", "color": "grey"},
                          "where": {"place": where}}, manual_reward=0.5)
    places = [r.get("place") for r in session.memory.records]
    assert places == ["kitchen/stove", "garage", "kitchen/stove", "garage"], places
    g = ActivationGraph()
    g.refresh(session.memory)
    assert (3, "place") in g.neighbours[1], g.neighbours[1]
    print("ok  place: stored per record, same-place edges link steps 1-3 and 2-4")

    # 4. Routing: clear evidence -> DIRECT; conflicting -> SUBGRAPH; none -> UNGROUNDED.
    mem = E.MemorySystem()
    for s in range(1, 6):
        mem.store(summ(object_type="ball", color="red"), action="approach", reward=0.95, step=s)
    mem.store(summ(object_type="ball", color="red"), action="ignore", reward=0.1, step=6)
    reader = TideReader(mem, SlotPolicy(hard_slots=set()))
    direct = reader.read(summ(object_type="ball", color="red"), 7, cfg)
    assert direct["tide"]["route"] == "DIRECT" and direct["tide"]["subgraph"] is None, direct["tide"]
    assert direct["tide"]["best"] == "approach"

    mem2 = E.MemorySystem()
    mem2.store(summ(object_type="dog", color="dark"), action="approach", reward=0.6, step=1)
    mem2.store(summ(object_type="dog", color="dark"), action="observe", reward=0.55, step=2)
    reader2 = TideReader(mem2, SlotPolicy(hard_slots=set()))
    mixed = reader2.read(summ(object_type="dog", color="dark"), 3, cfg)
    sg = mixed["tide"]["subgraph"]
    assert mixed["tide"]["route"] == "SUBGRAPH" and sg and sg["nodes"] and sg["edges"], mixed["tide"]

    empty = TideReader(E.MemorySystem(), SlotPolicy()).read(summ(object_type="dog"), 1, cfg)
    assert empty["tide"]["route"] == "UNGROUNDED" and empty["tide"]["best"] == "observe"
    print("ok  routing: clear lead -> DIRECT, close call -> SUBGRAPH "
          f"({len(sg['nodes'])} nodes, {len(sg['edges'])} edges), no evidence -> UNGROUNDED")

    # 5. Anytime budget: only under urgent; decision on a partial read; passive
    # remainder verified and written onto the stored memory.
    bank = build_preset_memory_v3("balanced")
    # The bank's most frequent scene, so the strict urgent filter has plenty to read.
    counts: dict = {}
    for rec in bank.records:
        counts[rec["summary"]] = counts.get(rec["summary"], 0) + 1
    query = E.describe_summary(max(counts, key=counts.get))
    calm_session = TideSession(seed=3, kcfg=TideConfig(urgent_budget=5, verify_async=False))
    calm_session.reset(memory=build_preset_memory_v3("balanced"), seed=3)
    r = calm_session.run_step(query, manual_reward=0.5)
    assert r["tide"]["passive"] == 0, "budget must not apply without the urgent flag"

    urgent = TideSession(seed=3, policy=SlotPolicy(urgent=True),
                         kcfg=TideConfig(urgent_budget=5, verify_async=False))
    urgent.reset(memory=bank, seed=3)
    r = urgent.run_step(query, manual_reward=0.5)
    t = r["tide"]
    assert t["read"] == 5 and t["passive"] == t["total"] - 5 > 0, t
    check = urgent.memory.records[-1].get("passive_check")
    assert check and check["step"] == r["step"] and "agreed" in check, check
    print(f"ok  anytime: urgent read {t['read']}/{t['total']}, {t['passive']} passive; "
          f"verification {'agreed' if check['agreed'] else 'DISAGREED'} and was stored on the record")

    # 6. Async verification completes in the background.
    bg = TideSession(seed=4, policy=SlotPolicy(urgent=True),
                     kcfg=TideConfig(urgent_budget=3, verify_async=True))
    bg.reset(memory=build_preset_memory_v3("balanced"), seed=4)
    rng = random.Random(4)
    for _ in range(5):
        bg.run_step(query, manual_reward=rng.uniform(0, 1))
    bg.reader.wait_passive()
    summary = bg.reader.verification_summary()
    assert summary["checked"] == 5, summary
    assert all("passive_check" in rec for rec in bg.memory.records[-5:])
    print(f"ok  async passive threads: {summary}")

    # 7. A normal session on the full bank runs and routes.
    s = TideSession(seed=5)
    s.reset(memory=build_preset_memory_v3("balanced"), seed=5)
    routes = {}
    for _ in range(30):
        r = s.run_step(query)
        routes[r["tide"]["route"]] = routes.get(r["tide"]["route"], 0) + 1
    print(f"ok  30-step session, routes {routes}")
    print("\nall TIDE smoke checks passed")


if __name__ == "__main__":
    main()

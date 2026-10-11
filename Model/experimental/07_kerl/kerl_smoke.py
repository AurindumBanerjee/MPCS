"""Smoke checks for the KERL layer — run directly, no test framework."""

from __future__ import annotations

import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _d in ("02_core", "04_hyst", "06_shmf"):
    sys.path.insert(0, os.path.join(_HERE, "..", _d))
sys.path.insert(0, _HERE)

import mpcs_engine as E
from mpcs_preset_v3 import build_preset_memory_v3
from hyst_layer import SlotPolicy
from shmf_layer import ShmfPipeline
from kerl_layer import KerlConfig, KerlReader, KerlSession, affect_of, kerl_step


def summ(**features) -> tuple:
    percepts: dict = {}
    for key, value in features.items():
        percepts.setdefault(E.FEATURE_MODALITY[key], {})[key] = value
    return E.summary_of(percepts)


def main() -> None:
    cfg = E.EngineConfig()

    # 1. Guard: query = fast motion + alarm. Nothing matches strictly, so SHMF
    # relaxes. Each candidate misses one hard feature and survives the relaxed
    # pass at a discount — but step 1 misses it because it has no audio
    # channel at all, so it cannot speak to the alarm and the guard rejects
    # it. Step 2 heard a different sound and is kept.
    mem = E.MemorySystem()
    mem.store(summ(object_type="animal", motion="fast", color="dark"),
              action="approach", reward=0.9, step=1)
    mem.store(summ(object_type="animal", motion="fast", color="dark",
                   sound_type="noise", audio_intensity="high"),
              action="observe", reward=0.7, step=2)
    reader = KerlReader(mem)
    q = summ(object_type="animal", motion="fast", color="dark",
             sound_type="alarm", audio_intensity="high")
    reading = reader.read(q, 10, cfg)
    assert reading["stats"].relaxed
    rejected = [c.record["step"] for c in reading["rejected"]]
    kept = [c.record["step"] for c in reading["kept"]]
    assert 1 in rejected and 2 in kept, (kept, rejected)
    assert len(reader.pairs) == len(rejected)
    print(f"[ok] guard keeps audio-covering near-miss {kept}, rejects audio-less {rejected}, "
          f"logs {len(reader.pairs)} calibration pair(s)")

    # 2. Strict survivors always pass the guard.
    bank = build_preset_memory_v3("balanced")
    strict_reader = KerlReader(bank, auto_relax=False)
    random.seed(4)
    for _ in range(100):
        percepts = {m: {k: random.choice(v) for k, v in E.MODALITIES[m].items()}
                    for m in random.sample(E.MODALITY_ORDER, k=random.randint(1, 4))}
        assert not strict_reader.read(E.summary_of(percepts), 800, cfg)["rejected"]
    print("[ok] guard never rejects a strict HyST survivor (100 random queries)")

    # 3. Affect cues point the right way.
    danger = affect_of({"thermal": "hot", "odor_type": "smoke", "sound_type": "alarm",
                        "touch_intensity": "high"})
    pleasant = affect_of({"object_type": "human", "sound_type": "speech", "odor_type": "food",
                          "pleasantness": "pleasant", "thermal": "warm"})
    assert danger[0] < -0.5 and danger[1] > 0.7, danger
    assert pleasant[0] > 0.3 and pleasant[1] < 0.5, pleasant
    print(f"[ok] affect: hot+smoke+alarm {danger[0]:+.2f}/{danger[1]:.2f}, "
          f"pleasant scene {pleasant[0]:+.2f}/{pleasant[1]:.2f}")

    # 4. With graph and affect terms off and every candidate used (top_k
    # large), HEAD-A reproduces SHMF exactly — fusion only rescales omega
    # uniformly, so the weighted means match. (At the default top_k=5 they
    # differ by design: KERL ranks by full omega, SHMF by similarity alone.)
    cfg = E.EngineConfig(top_k=10_000)
    plain = KerlReader(bank, auto_relax=False, kcfg=KerlConfig(w_g=0.0, affect_enabled=False))
    shmf = ShmfPipeline(bank, SlotPolicy(), auto_relax=False)
    random.seed(5)
    checked = 0
    for _ in range(60):
        percepts = {m: {k: random.choice(v) for k, v in E.MODALITIES[m].items()}
                    for m in random.sample(E.MODALITY_ORDER, k=random.randint(1, 4))}
        s = E.summary_of(percepts)
        head_a = plain.read(s, 800, cfg)["head_a"]
        for action in E.ACTIONS:
            ref, ref_support, _ = shmf.score_action(action, s, 800, cfg)
            if ref_support > 0:
                assert abs(head_a[action]["value"] - ref) < 1e-9, (action, head_a[action]["value"], ref)
                checked += 1
    print(f"[ok] HEAD-A == SHMF action value on {checked} evidenced (query, action) pairs "
          f"when graph/affect terms are off")

    # 5. Empty memory: UNGROUNDED -> observe, never a 0.5-tie 'ignore'.
    state = E.init_state()
    state["risk_bias"] = 0.0
    result = kerl_step({"vision": {"object_type": "unknown", "motion": "static", "color": "dark"}},
                       step=1, state=state, reader=KerlReader(E.MemorySystem()),
                       rng=random.Random(0))
    assert result["policy"] == "UNGROUNDED" and result["action"] == "observe"
    assert "No admissible memory" in result["kerl"]["explanation"]
    print("[ok] empty candidate set -> UNGROUNDED observe, explained")

    # 6. HEAD-X names the strongest voice; affect flag off leaves w_e unused.
    session = KerlSession(seed=1)
    session.reset(memory=build_preset_memory_v3("balanced"), seed=1)
    session.state["risk_bias"] = 0.0
    r = session.run_step({"vision": {"object_type": "human", "motion": "slow", "color": "bright"},
                          "audio": {"sound_type": "speech", "audio_intensity": "low"}})
    top = r["contributions"][0]["step"] if r["contributions"] else None
    assert top is None or f"step {top}" in r["kerl"]["explanation"], r["kerl"]["explanation"]
    assert r["kerl"]["weights_used"]["w_e"] == 0.0
    print(f"[ok] HEAD-X: {r['kerl']['explanation']}")

    # 7. Calibration never increases violated pairs.
    for _ in range(40):
        percepts = {m: {k: random.choice(v) for k, v in E.MODALITIES[m].items()}
                    for m in random.sample(E.MODALITY_ORDER, k=random.randint(1, 3))}
        session.run_step(percepts)
    report = session.calibrate()
    assert report["violated_after"] <= report["violated_before"]
    print(f"[ok] calibration on {report['pairs']} pairs: violations "
          f"{report['violated_before']} -> {report['violated_after']}, weights {report['weights']}")

    print("\nAll KERL smoke checks passed.")


if __name__ == "__main__":
    main()

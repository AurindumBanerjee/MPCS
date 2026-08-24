"""
Headless verification for the MPCS v2 engine.

Exercises the behaviours the dashboards depend on, with no UI involved:
reflexes across all four modalities, memory-derived reward, the
off-recommendation penalty, reflex-memory emphasis, absent-modality
handling, the preset bank, and threshold wiring.

Run:
    python engine_smoke.py
"""

from __future__ import annotations

import random
import statistics

import mcps_engine as E
from mcps_preset_v2 import build_preset_memory, bank_stats


PASS, FAIL = "PASS", "FAIL"
_results: list[tuple[str, str, str]] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    _results.append((PASS if condition else FAIL, name, detail))
    marker = "  ok  " if condition else " FAIL "
    print(f"[{marker}] {name}" + (f"\n           {detail}" if detail else ""))
    return condition


def neutral(**overrides) -> dict:
    """A percept with nothing alarming in any channel."""
    percepts = {
        "vision": {"object_type": "unknown", "motion": "static", "color": "blue"},
        "audio": {"sound_type": "none", "audio_intensity": "low"},
        "touch": {"contact": "none", "texture": "smooth",
                  "thermal": "neutral", "touch_intensity": "low"},
        "smell": {"odor_type": "none", "odor_intensity": "faint",
                  "pleasantness": "neutral"},
    }
    for modality, features in overrides.items():
        percepts[modality] = {**percepts[modality], **features}
    return percepts


# ----------------------------------------------------------------------
def test_import_and_headless_run():
    print("\n--- 1. Import and headless stepping ---")
    session = E.Session(seed=7)
    rng = random.Random(11)
    for _ in range(20):
        percepts = {
            modality: {
                key: rng.choice(options) for key, options in features.items()
            }
            for modality, features in E.MODALITIES.items()
        }
        session.run_step(percepts)
    check("20 headless steps complete", session.step == 20, f"step={session.step}")
    check("memory grew to 20", len(session.memory) == 20, f"size={len(session.memory)}")
    check("history recorded", len(session.history) == 20)
    result = session.last_result
    for key in ("action", "mode", "policy", "reward", "reward_source",
                "contributions", "scores", "graph"):
        check(f"payload has '{key}'", key in result)


def test_reflexes():
    print("\n--- 2. Touch and smell reflexes ---")
    session = E.Session(seed=3)

    r = session.run_step(neutral(touch={"thermal": "hot"}))
    check("thermal=hot -> WITHDRAW", r["action"] == "withdraw", f"got {r['action']}")
    check("hot fires rule 0", r["reflex_rule"] == 0, f"rule={r['reflex_rule']}")
    check("mode is REFLEXIVE", r["mode"] == "REFLEXIVE")

    r = session.run_step(neutral(smell={"odor_type": "smoke"}))
    check("odor=smoke -> ALERT", r["action"] == "alert", f"got {r['action']}")
    check("smoke fires rule 2", r["reflex_rule"] == 2, f"rule={r['reflex_rule']}")

    r = session.run_step(neutral(touch={"contact": "impact"}))
    check("contact=impact -> WITHDRAW", r["action"] == "withdraw", f"got {r['action']}")

    r = session.run_step(neutral(touch={"contact": "firm", "texture": "sharp"}))
    check("sharp+firm -> WITHDRAW", r["action"] == "withdraw", f"got {r['action']}")

    r = session.run_step(neutral(smell={"odor_type": "chemical",
                                        "odor_intensity": "strong"}))
    check("strong chemical -> ALERT", r["action"] == "alert", f"got {r['action']}")

    r = session.run_step(neutral(vision={"motion": "fast"}))
    check("motion=fast -> OBSERVE (v1 reflex intact)",
          r["action"] == "observe", f"got {r['action']}")

    r = session.run_step(neutral(audio={"sound_type": "alarm"}))
    check("alarm -> ALERT (v1 reflex intact)", r["action"] == "alert", f"got {r['action']}")

    # Priority: hot outranks alarm.
    r = session.run_step(neutral(touch={"thermal": "hot"},
                                 audio={"sound_type": "alarm"}))
    check("hot outranks alarm", r["action"] == "withdraw" and r["reflex_rule"] == 0,
          f"got {r['action']} rule={r['reflex_rule']}")

    r = session.run_step(neutral())
    check("neutral percept is not reflexive", r["mode"] == "DELIBERATIVE",
          f"got {r['mode']}")


def test_reward_from_memory():
    print("\n--- 3. Reward is memory-derived, not random ---")
    session = E.Session(seed=5)
    session.cfg.hesitate_enabled = False
    context = neutral(vision={"object_type": "human", "motion": "slow"})

    r1 = session.run_step(context, manual_reward=0.9)
    check("first run of fresh context is cold-start or manual",
          r1["reward_source"] == "manual")

    # Seed two high-reward memories for the action that will be chosen again.
    session.run_step(context, manual_reward=0.9)

    # Measure only the exploit steps: exploration deliberately picks an
    # off-recommendation action, which the penalty rule then marks down, so
    # including those would measure the penalty rather than the estimate.
    exploited, explored = [], []
    for _ in range(20):
        r = session.run_step(context)
        (exploited if r["policy"] == "EXPLOIT" else explored).append(r["reward"])
    mean = statistics.mean(exploited)
    check("repeated context draws reward near 0.9, not uniform",
          0.72 <= mean <= 1.0,
          f"mean over {len(exploited)} exploit steps = {mean:.3f}")
    if explored:
        check("exploration off-recommendation scores below exploitation",
              statistics.mean(explored) < mean,
              f"explore {statistics.mean(explored):.3f} < exploit {mean:.3f}")

    # A genuinely fresh context with no matching action memory: cold start.
    fresh = E.Session(seed=9)
    fresh.cfg.hesitate_enabled = False
    r = fresh.run_step(neutral(vision={"object_type": "vehicle", "color": "dark"}))
    check("fresh context reports cold-start",
          r["reward_source"] == "cold-start", f"source={r['reward_source']}")
    check("cold-start reward in [0.4, 0.6]",
          0.4 <= r["reward"] <= 0.6, f"reward={r['reward']:.3f}")


def test_off_recommendation_penalty():
    print("\n--- 4. Off-recommendation penalty scales with margin ---")
    cfg = E.EngineConfig()
    rng = random.Random(2)

    # Wide margin, well-supported recommendation.
    scores = {"alert": 0.95, "approach": 0.20, "ignore": 0.5,
              "observe": 0.5, "withdraw": 0.5}
    supports = {"alert": 4.0, "approach": 2.5, "ignore": 0.0,
                "observe": 0.0, "withdraw": 0.0}
    heavy, info = E.apply_off_recommendation_penalty(
        0.80, "approach", scores, supports, cfg, rng=rng
    )
    check("wide margin penalised", info is not None and heavy < 0.5,
          f"0.80 -> {heavy:.3f}, penalty={info['penalty']:.3f}" if info else "no penalty")
    check("penalty names the recommendation",
          info is not None and info["recommended"] == "alert")

    # Narrow margin, same support.
    scores_near = dict(scores, approach=0.90)
    light, info_near = E.apply_off_recommendation_penalty(
        0.80, "approach", scores_near, supports, cfg, rng=rng
    )
    check("narrow margin penalised only lightly", light > heavy,
          f"narrow -> {light:.3f} vs wide -> {heavy:.3f}")

    # Taking the recommended action is never penalised.
    same, info_same = E.apply_off_recommendation_penalty(
        0.80, "alert", scores, supports, cfg, rng=rng
    )
    check("recommended action escapes penalty",
          info_same is None and same == 0.80)

    # Unsupported recommendation should not drive a penalty.
    no_support = {a: 0.0 for a in supports}
    unpen, info_unsup = E.apply_off_recommendation_penalty(
        0.80, "approach", scores, no_support, cfg, rng=rng
    )
    check("no evidence means no penalty", info_unsup is None and unpen == 0.80)

    check("penalty floor respected", heavy >= E.PENALTY_FLOOR,
          f"{heavy:.3f} >= {E.PENALTY_FLOOR}")

    # End to end against the preset bank: approach a fire.
    session = E.Session(seed=4)
    session.reset(memory=build_preset_memory())
    session.cfg.hesitate_enabled = False
    fire = {
        "vision": {"object_type": "unknown", "motion": "static", "color": "bright"},
        "audio": {"sound_type": "none", "audio_intensity": "low"},
        "touch": {"contact": "firm", "texture": "smooth",
                  "thermal": "warm", "touch_intensity": "high"},
        "smell": {"odor_type": "chemical", "odor_intensity": "moderate",
                  "pleasantness": "foul"},
    }
    forced = E.cognitive_step(
        fire, session.step + 1, session.state, session.memory,
        cfg=session.cfg, rng=session.rng,
    )
    check("live step produces scores for every action",
          all(a in forced["scores"] for a in E.ACTIONS))


def test_reflex_emphasis():
    print("\n--- 5. Reflex memories weigh more on the reflex path ---")
    cfg = E.EngineConfig()
    memory = E.MemorySystem()
    context = neutral(touch={"thermal": "hot"})
    summary = E.summary_of(context)

    # Same action, same context: reflex-origin memory is bad, deliberative good.
    memory.store(summary, "withdraw", 0.20, 1, mode="REFLEXIVE")
    memory.store(summary, "withdraw", 0.90, 2, mode="DELIBERATIVE")

    plain, _, _ = E.score_action("withdraw", memory, summary, 3, cfg,
                                 reflex_emphasis=False)
    boosted, _, _ = E.score_action("withdraw", memory, summary, 3, cfg,
                                   reflex_emphasis=True)
    check("reflex emphasis pulls the estimate toward reflex memories",
          boosted < plain, f"plain={plain:.3f}, reflex-weighted={boosted:.3f}")

    contribs = E.score_action("withdraw", memory, summary, 3, cfg,
                              reflex_emphasis=True)[2]
    reflex_detail = next(c for c in contribs if c["mode"] == "REFLEXIVE")
    delib_detail = next(c for c in contribs if c["mode"] == "DELIBERATIVE")
    check("reflex memory carries the boost factor",
          reflex_detail["boost"] == cfg.reflex_memory_boost
          and delib_detail["boost"] == 1.0,
          f"reflex boost={reflex_detail['boost']}, delib boost={delib_detail['boost']}")


def test_malleability():
    print("\n--- 6. Absent modalities ---")
    full = E.summary_of(neutral())
    partial_percepts = {k: v for k, v in neutral().items() if k != "smell"}
    partial = E.summary_of(partial_percepts)

    smell_index = E.MODALITY_ORDER.index("smell")
    check("absent smell yields an empty slot", partial[smell_index] == ())
    check("other slots keep their position",
          partial[E.MODALITY_ORDER.index("vision")] == full[E.MODALITY_ORDER.index("vision")])
    check("total confidence drops without smell",
          E.total_confidence(partial) < E.total_confidence(full),
          f"{E.total_confidence(partial):.2f} < {E.total_confidence(full):.2f}")
    check("similarity still computes across differing slot lengths",
          E.normalized_similarity_z(partial, full) > 0.0,
          f"sim={E.normalized_similarity_z(partial, full):.3f}")

    session = E.Session(seed=13)
    for _ in range(5):
        session.run_step(partial_percepts)
    check("five steps run with smell disabled", session.step == 5)
    check("active modalities exclude smell",
          "smell" not in session.last_result["active_modalities"],
          str(session.last_result["active_modalities"]))

    # A reflex on an absent channel cannot fire.
    no_touch = {k: v for k, v in neutral(touch={"thermal": "hot"}).items()
                if k != "touch"}
    r = E.Session(seed=1).run_step(no_touch)
    check("touch reflex cannot fire without a touch channel",
          r["mode"] == "DELIBERATIVE", f"mode={r['mode']}")


def test_preset_bank():
    print("\n--- 7. Preset memory bank ---")
    memory = build_preset_memory()
    stats = bank_stats()
    check("bank holds 70 entries", len(memory) == 70, f"size={len(memory)}")
    check("50 novel + 20 repeated",
          stats["novel"] == 50 and stats["repeated"] == 20,
          f"{stats['novel']} + {stats['repeated']}")
    check("every action represented",
          all(stats["by_action"].get(a, 0) > 0 for a in E.ACTIONS),
          str(stats["by_action"]))
    check("withdraw well represented",
          stats["by_action"].get("withdraw", 0) >= 8,
          f"withdraw={stats['by_action'].get('withdraw')}")

    all_four = all(
        len([slot for slot in record["summary"] if slot]) == 4
        for record in memory.records
    )
    check("every record carries all four modalities", all_four)
    steps = sorted(r["step"] for r in memory.records)
    check("steps span 1..70 without duplicates",
          steps == list(range(1, 71)), f"min={steps[0]}, max={steps[-1]}")

    low = [r for r in memory.records if r["reward"] < 0.35]
    check("bank includes low-reward off-recommendation precedent",
          len(low) >= 4, f"{len(low)} entries below 0.35")

    cautious = build_preset_memory("cautious")
    base_approach = statistics.mean(
        r["reward"] for r in memory.records if r["action"] == "approach")
    caut_approach = statistics.mean(
        r["reward"] for r in cautious.records if r["action"] == "approach")
    check("cautious profile discounts approach", caut_approach < base_approach,
          f"{caut_approach:.3f} < {base_approach:.3f}")


def test_threshold_wiring():
    print("\n--- 8. action_threshold drives behaviour ---")
    session = E.Session(seed=21)
    start = session.state["action_threshold"]
    context = neutral(vision={"object_type": "human"})
    for _ in range(40):
        session.run_step(context, manual_reward=0.95)
    raised = session.state["action_threshold"]
    check("high rewards raise the threshold", raised > start,
          f"{start:.4f} -> {raised:.4f}")

    session2 = E.Session(seed=22)
    for _ in range(40):
        session2.run_step(neutral(vision={"object_type": "animal"}),
                          manual_reward=0.05)
    check("low rewards lower the threshold",
          session2.state["action_threshold"] < start,
          f"{start:.4f} -> {session2.state['action_threshold']:.4f}")

    # With a high threshold and weak evidence, deliberation should hesitate.
    hes = E.Session(seed=23)
    hes.state["action_threshold"] = 0.95
    hes.state["risk_bias"] = 0.0          # suppress exploration
    hes.reset(memory=build_preset_memory())
    hes.state["action_threshold"] = 0.95
    hes.state["risk_bias"] = 0.0
    saw_hesitate = False
    for i in range(15):
        r = hes.run_step(neutral(vision={"object_type": "unknown",
                                         "color": ["red", "blue", "dark", "bright"][i % 4]}))
        if r["policy"] == "HESITATE":
            saw_hesitate = True
            break
    check("weak evidence under a high threshold yields HESITATE", saw_hesitate)

    # And the fallback is the low-commitment action.
    check("hesitation falls back to observe",
          (not saw_hesitate) or hes.last_result["action"] == "observe",
          f"action={hes.last_result['action']}")


def test_graph_payload():
    print("\n--- 9. Explanation graph ---")
    session = E.Session(seed=31)
    session.reset(memory=build_preset_memory())
    session.cfg.hesitate_enabled = False
    context = {
        "vision": {"object_type": "human", "motion": "slow", "color": "bright"},
        "audio": {"sound_type": "speech", "audio_intensity": "low"},
        "touch": {"contact": "light", "texture": "smooth",
                  "thermal": "warm", "touch_intensity": "low"},
        "smell": {"odor_type": "food", "odor_intensity": "moderate",
                  "pleasantness": "pleasant"},
    }
    result = session.run_step(context)
    graph = result["graph"]
    check("graph has a percept centre",
          graph["nodes"][0]["kind"] == "percept" and graph["nodes"][0]["x"] == 0.0)
    check("graph has memory nodes", len(graph["nodes"]) > 1,
          f"{len(graph['nodes']) - 1} memory nodes")
    check("edges match memory nodes",
          len(graph["edges"]) == len(graph["nodes"]) - 1)

    if len(graph["nodes"]) > 2:
        memory_nodes = graph["nodes"][1:]
        strongest = max(memory_nodes, key=lambda n: n["weight"])
        weakest = min(memory_nodes, key=lambda n: n["weight"])
        d_strong = (strongest["x"] ** 2 + strongest["y"] ** 2) ** 0.5
        d_weak = (weakest["x"] ** 2 + weakest["y"] ** 2) ** 0.5
        check("stronger contributors sit closer to the centre",
              d_strong <= d_weak + 1e-9,
              f"strong r={d_strong:.3f}, weak r={d_weak:.3f}")
    check("every edge carries a weight breakdown",
          all("tooltip" in e and e["weight"] >= 0 for e in graph["edges"]))

    # The dashboards read these fields off every memory node. Missing one
    # breaks a renderer at draw time rather than here, so pin the contract.
    required = {"id", "kind", "step", "action", "mode", "reward", "similarity",
                "decay", "boost", "weight", "age", "radius", "is_expert",
                "color", "x", "y", "percepts"}
    memory_nodes = [n for n in graph["nodes"] if n["kind"] == "memory"]
    missing = {
        field for node in memory_nodes for field in required if field not in node
    }
    check("memory nodes expose the full renderer contract", not missing,
          f"missing: {sorted(missing)}" if missing else f"{len(required)} fields present")
    check("percept node exposes its contract",
          {"kind", "x", "y", "color", "action", "modalities"} <= set(graph["nodes"][0]))


def test_persistence():
    print("\n--- 10. Memory export and import ---")
    memory = build_preset_memory()
    exported = memory.to_json_obj()
    restored = E.MemorySystem.from_json_obj(exported)
    check("round trip preserves size", len(restored) == len(memory),
          f"{len(restored)} vs {len(memory)}")

    original_summaries = {E.MemorySystem._summary_key(r["summary"])
                          for r in memory.records}
    restored_summaries = {E.MemorySystem._summary_key(r["summary"])
                          for r in restored.records}
    check("round trip preserves summaries",
          original_summaries == restored_summaries)
    check("round trip preserves rewards",
          all(abs(a["reward"] - b["reward"]) < 1e-9
              for a, b in zip(memory.records, restored.records)))

    probe = E.summary_of(neutral(touch={"thermal": "hot"},
                                 audio={"sound_type": "alarm"}))
    cfg = E.EngineConfig()
    before = E.score_action("withdraw", memory, probe, 71, cfg)[0]
    after = E.score_action("withdraw", restored, probe, 71, cfg)[0]
    check("scoring survives the round trip", abs(before - after) < 1e-9,
          f"{before:.6f} vs {after:.6f}")


def main() -> None:
    test_import_and_headless_run()
    test_reflexes()
    test_reward_from_memory()
    test_off_recommendation_penalty()
    test_reflex_emphasis()
    test_malleability()
    test_preset_bank()
    test_threshold_wiring()
    test_graph_payload()
    test_persistence()

    failures = [r for r in _results if r[0] == FAIL]
    print("\n" + "=" * 60)
    print(f"{len(_results) - len(failures)}/{len(_results)} checks passed")
    if failures:
        print("\nFailures:")
        for _, name, detail in failures:
            print(f"  - {name}" + (f" ({detail})" if detail else ""))
        raise SystemExit(1)
    print("All engine checks passed.")


if __name__ == "__main__":
    main()

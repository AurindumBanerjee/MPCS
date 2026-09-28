"""Quick smoke test for the HyST layer — run directly, no test framework."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "02_core"))

import mpcs_engine as E
from hyst_layer import SlotPolicy, compute_novelty_hyst, hyst_step, split_similarity


def make_summary(**kwargs) -> tuple:
    # thermal/contact/texture -> touch; odor_type -> smell
    percepts = {
        "touch": {},
        "smell": {},
    }
    for key, value in kwargs.items():
        modality = E.FEATURE_MODALITY[key]
        percepts.setdefault(modality, {})[key] = value
    return E.summary_of(percepts)


def main() -> None:
    memory = E.MemorySystem()
    # A memory that matches on decorative features but mismatches on the
    # hard safety feature `thermal`.
    cold_but_similar = make_summary(thermal="cold", contact="firm", texture="rough")
    memory.store(cold_but_similar, action="approach", reward=0.9, step=1)

    hot_query = make_summary(thermal="hot", contact="firm", texture="rough")

    policy = SlotPolicy()
    assert "thermal" in policy.hard_slots, "thermal must be seeded as hard from REFLEX_RULES"

    # Strict mode: the cold memory must be excluded outright despite matching
    # contact + texture, because thermal disagrees on a hard slot.
    sim = split_similarity(hot_query, cold_but_similar, policy)
    assert sim is None, f"expected hard exclusion, got {sim}"
    novelty, admissible = compute_novelty_hyst(hot_query, memory, policy)
    assert admissible == 0
    assert novelty == 1.0
    print("[ok] strict hard filter excludes thermal mismatch")

    # Divergent mode: same query, but exploration is allowed — the mismatch
    # survives, discounted, instead of being erased.
    divergent_policy = SlotPolicy(divergent=True)
    sim_div = split_similarity(hot_query, cold_but_similar, divergent_policy)
    assert sim_div is not None and 0.0 < sim_div < 1.0, f"expected discounted match, got {sim_div}"
    print(f"[ok] divergent mode admits the mismatch at discounted similarity {sim_div:.3f}")

    # Urgent mode always wins over divergent: no relaxation regardless.
    urgent_policy = SlotPolicy(divergent=True, urgent=True)
    sim_urgent = split_similarity(hot_query, cold_but_similar, urgent_policy)
    assert sim_urgent is None, "urgency must override divergent relaxation"
    print("[ok] urgent flag overrides divergent relaxation")

    # Graded soft kernel: warm vs hot should score higher than cold vs hot
    # on the ordinal thermal scale, when thermal is treated as soft.
    soft_policy = SlotPolicy(hard_slots=set())
    warm_summary = make_summary(thermal="warm")
    cold_summary = make_summary(thermal="cold")
    hot_summary = make_summary(thermal="hot")
    warm_sim = split_similarity(hot_summary, warm_summary, soft_policy)
    cold_sim = split_similarity(hot_summary, cold_summary, soft_policy)
    assert warm_sim > cold_sim, f"expected graded credit, got warm={warm_sim} cold={cold_sim}"
    print(f"[ok] graded soft kernel: warm~hot={warm_sim:.3f} > cold~hot={cold_sim:.3f}")

    # End-to-end step: urgent flag should force convergent (no explore/hesitate).
    state = E.init_state()
    memory2 = E.MemorySystem()
    memory2.store(make_summary(thermal="warm", contact="light"), action="observe", reward=0.8, step=1)
    result = hyst_step(
        {"touch": {"thermal": "warm", "contact": "light", "texture": "smooth", "touch_intensity": "low"}},
        step=2, state=state, memory=memory2,
        policy=SlotPolicy(urgent=True),
    )
    assert result["policy"] in ("REFLEX", "CONVERGE"), result["policy"]
    print(f"[ok] urgent step converges directly: policy={result['policy']} action={result['action']}")

    print("\nAll HyST smoke checks passed.")


if __name__ == "__main__":
    main()

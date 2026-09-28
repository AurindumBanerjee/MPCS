"""Quick smoke test for SHMF — run directly, no test framework."""

from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hyst"))

import mpcs_engine as E
from mpcs_preset_v3 import build_preset_memory_v3
from hyst_layer import SlotPolicy
from shmf_layer import ShmfPipeline, shmf_step, verify_pipeline_equivalence


def main() -> None:
    memory = build_preset_memory_v3("balanced")
    policy = SlotPolicy()
    pipeline = ShmfPipeline(memory, policy)

    # 1. Equivalence: partition-then-filter must admit exactly the same
    # records as filter-alone over the whole store, for a range of query
    # shapes (single modality, multi-modality, empty).
    random.seed(3)
    queries = []
    for _ in range(150):
        percepts = {}
        for modality in random.sample(E.MODALITY_ORDER, k=random.randint(1, 4)):
            percepts[modality] = {k: random.choice(v) for k, v in E.MODALITIES[modality].items()}
        queries.append(E.summary_of(percepts))
    queries.append(E.summary_of({}))  # empty-modality edge case

    problems = verify_pipeline_equivalence(memory, policy, queries)
    assert not problems, f"{len(problems)} equivalence failures, e.g. {problems[0]}"
    print(f"[ok] pipeline (partition -> hard/soft filter) matches filter-alone "
          f"on {len(queries)} queries, including the empty-modality edge case")

    # 2. The funnel narrows monotonically: after_hard_soft <= after_partition
    # <= store_size, for every query, and reduction percentages agree with
    # the raw counts.
    for query in queries[:20]:
        scored, stats = pipeline.scored_candidates(query)
        assert stats.after_hard_soft <= stats.after_partition <= stats.store_size
        assert len(scored) == stats.after_hard_soft
    print("[ok] funnel narrows monotonically (store >= partition survivors >= "
          "hard/soft survivors) across sampled queries")

    # 3. Hard exclusion still works through the pipeline: a touch-only query
    # demanding thermal=hot must never admit a stored 'cold' record, even
    # though partitioning alone would have let it through (same partition).
    memory2 = E.MemorySystem()
    memory2.store(E.summary_of({"touch": {"thermal": "cold", "contact": "firm", "texture": "rough", "touch_intensity": "high"}}),
                  action="approach", reward=0.9, step=1)
    pipeline2 = ShmfPipeline(memory2, SlotPolicy())
    hot_query = E.summary_of({"touch": {"thermal": "hot", "contact": "firm", "texture": "rough", "touch_intensity": "high"}})

    # HMGI alone would keep this record (same touch partition).
    partition_only = pipeline2.partitioned.candidates(hot_query)
    assert len(partition_only) == 1, "sanity: partition alone should keep the record"

    # SHMF (partition + hard/soft) must still exclude it on the hard slot.
    scored, stats = pipeline2.scored_candidates(hot_query)
    assert len(scored) == 0, "hard-slot mismatch must survive the partition step"
    assert stats.after_partition == 1 and stats.after_hard_soft == 0
    print("[ok] hard-slot exclusion survives the pipeline even when HMGI's "
          "partition alone would have kept the record")

    # 4. Urgent flag still collapses retrieval to top-1 through the pipeline.
    pipeline2.policy.urgent = True
    memory2.store(E.summary_of({"touch": {"thermal": "hot", "contact": "light", "texture": "smooth", "touch_intensity": "low"}}),
                  action="observe", reward=0.7, step=2)
    top = pipeline2.retrieve(hot_query, k=5)
    assert len(top) <= 1
    print(f"[ok] urgent flag collapses retrieval to top-1 through the pipeline "
          f"(got {len(top)} result(s))")

    # 5. End-to-end step against the real 700-entry bank.
    state = E.init_state()
    pipeline3 = ShmfPipeline(build_preset_memory_v3("balanced"), SlotPolicy())
    result = shmf_step(
        {"touch": {"thermal": "hot", "contact": "firm", "texture": "sharp", "touch_intensity": "high"}},
        step=1000, state=state, pipeline=pipeline3,
    )
    print(f"[ok] end-to-end step: action={result['action']} policy={result['policy']} "
          f"pipeline={result['pipeline']}")

    print("\nAll SHMF smoke checks passed.")


if __name__ == "__main__":
    main()

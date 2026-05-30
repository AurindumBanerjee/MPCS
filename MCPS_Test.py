"""
MCPS_Test - benchmark Bloom-backed MPCS against baseline MPCS.

This script compares negative-heavy and positive-heavy membership/retrieval
workloads using the regular MemorySystem from mpcs.py and the Bloom-backed
MemorySystem from BloomMCPS.py.

Output:
    Prints a JSON metrics report and returns the same metrics from run_benchmark().

Run:
    python MCPS_Test.py
"""

from __future__ import annotations

import json
import random
import statistics
import time
from dataclasses import dataclass
from itertools import product
from typing import Iterable

from mpcs import AfferentObject as BaseAfferentObject
from mpcs import MemorySystem as BaseMemorySystem
from mpcs import VISION_FEATURES as BASE_VISION_FEATURES
from mpcs import AUDIO_FEATURES as BASE_AUDIO_FEATURES

from BloomMCPS import AfferentObject as BloomAfferentObject
from BloomMCPS import MemorySystem as BloomMemorySystem
from BloomMCPS import VISION_FEATURES as BLOOM_VISION_FEATURES
from BloomMCPS import AUDIO_FEATURES as BLOOM_AUDIO_FEATURES


@dataclass(frozen=True)
class BenchmarkResult:
    label: str
    kind: str
    query_count: int
    total_ms: float
    avg_ms: float
    median_ms: float
    p95_ms: float
    queries_per_sec: float


def _feature_space() -> tuple[dict, dict]:
    """Use the shared MPCS feature schema for both implementations."""
    if BASE_VISION_FEATURES != BLOOM_VISION_FEATURES or BASE_AUDIO_FEATURES != BLOOM_AUDIO_FEATURES:
        raise RuntimeError("Baseline and Bloom feature schemas differ; benchmark cannot compare fairly.")
    return BASE_VISION_FEATURES, BASE_AUDIO_FEATURES


def _make_summary(vision: dict, audio: dict, use_bloom: bool = False) -> tuple:
    afferent_cls = BloomAfferentObject if use_bloom else BaseAfferentObject
    return afferent_cls(vision=vision, audio=audio, time=0, state={}).summary


def _build_memory(memory_cls, use_bloom: bool, entries: list[tuple[dict, dict, str, float, int]]):
    memory = memory_cls()
    for vision, audio, action, reward, step in entries:
        memory.store(_make_summary(vision, audio, use_bloom=use_bloom), action, reward, step)
    return memory


def _all_contexts() -> list[tuple[dict, dict]]:
    """Enumerate the full finite feature space so positive and negative sets do not overlap."""
    vision_features, audio_features = _feature_space()
    contexts: list[tuple[dict, dict]] = []
    for object_type, motion, color, sound_type, intensity in product(
        vision_features["object_type"],
        vision_features["motion"],
        vision_features["color"],
        audio_features["sound_type"],
        audio_features["intensity"],
    ):
        contexts.append(
            (
                {
                    "object_type": object_type,
                    "motion": motion,
                    "color": color,
                },
                {
                    "sound_type": sound_type,
                    "intensity": intensity,
                },
            )
        )
    return contexts


def _generate_entries(rng: random.Random, count: int) -> list[tuple[dict, dict, str, float, int]]:
    contexts = _all_contexts()
    actions = ["ignore", "observe", "approach", "alert"]
    selected = rng.sample(contexts, k=min(count, len(contexts)))

    entries = []
    for step, (vision, audio) in enumerate(selected, start=1):
        action = rng.choice(actions)
        reward = round(rng.uniform(0.35, 0.95), 3)
        entries.append((vision, audio, action, reward, step))
    return entries


def _make_negative_queries(entries: list[tuple[dict, dict, str, float, int]], count: int, rng: random.Random) -> list[tuple]:
    """Use contexts outside the stored memory set so the negative workload is truly negative."""
    stored_contexts = {(repr(vision), repr(audio)) for vision, audio, *_ in entries}
    remaining = [context for context in _all_contexts() if (repr(context[0]), repr(context[1])) not in stored_contexts]
    if not remaining:
        raise RuntimeError("No unseen contexts remain for negative-heavy benchmark.")

    queries = []
    for i in range(count):
        vision, audio = remaining[i % len(remaining)]
        queries.append((vision, audio))
    rng.shuffle(queries)
    return queries


def _make_positive_queries(entries: list[tuple[dict, dict, str, float, int]], count: int) -> list[tuple]:
    """Re-use stored contexts to create positive-heavy queries."""
    vision_audio_pairs = [(vision, audio) for vision, audio, *_ in entries]
    queries = []
    for i in range(count):
        vision, audio = vision_audio_pairs[i % len(vision_audio_pairs)]
        queries.append((vision, audio))
    return queries


def _time_queries(
    memory,
    queries: Iterable[tuple[dict, dict]],
    use_bloom: bool,
) -> BenchmarkResult:
    timings_ms: list[float] = []
    query_count = 0

    for vision, audio in queries:
        query_count += 1
        summary = _make_summary(vision, audio, use_bloom=use_bloom)

        start = time.perf_counter()
        memory.maybe_seen(summary)
        memory.retrieve(summary)
        timings_ms.append((time.perf_counter() - start) * 1000.0)

    total_ms = sum(timings_ms)
    avg_ms = statistics.fmean(timings_ms) if timings_ms else 0.0
    median_ms = statistics.median(timings_ms) if timings_ms else 0.0
    p95_ms = statistics.quantiles(timings_ms, n=20)[18] if len(timings_ms) >= 20 else (max(timings_ms) if timings_ms else 0.0)
    qps = (query_count / (total_ms / 1000.0)) if total_ms > 0 else 0.0

    return BenchmarkResult(
        label="",
        kind="",
        query_count=query_count,
        total_ms=total_ms,
        avg_ms=avg_ms,
        median_ms=median_ms,
        p95_ms=p95_ms,
        queries_per_sec=qps,
    )


def _benchmark_case(
    label: str,
    entries: list[tuple[dict, dict, str, float, int]],
    queries: list[tuple[dict, dict]],
) -> dict:
    bloom_memory = _build_memory(BloomMemorySystem, use_bloom=True, entries=entries)
    base_memory = _build_memory(BaseMemorySystem, use_bloom=False, entries=entries)

    bloom_result = _time_queries(bloom_memory, queries, use_bloom=True)
    base_result = _time_queries(base_memory, queries, use_bloom=False)

    def as_dict(kind: str, result: BenchmarkResult) -> dict:
        return {
            "label": label,
            "kind": kind,
            "query_count": result.query_count,
            "total_ms": round(result.total_ms, 4),
            "avg_ms": round(result.avg_ms, 6),
            "median_ms": round(result.median_ms, 6),
            "p95_ms": round(result.p95_ms, 6),
            "queries_per_sec": round(result.queries_per_sec, 2),
        }

    bloom_dict = as_dict("bloom", bloom_result)
    base_dict = as_dict("baseline", base_result)

    speedup = (base_result.total_ms / bloom_result.total_ms) if bloom_result.total_ms > 0 else None
    bloom_dict["speedup_vs_baseline"] = round(speedup, 3) if speedup is not None else None

    return {
        "label": label,
        "baseline": base_dict,
        "bloom": bloom_dict,
        "delta_ms_total": round(base_result.total_ms - bloom_result.total_ms, 4),
        "delta_ms_avg": round(base_result.avg_ms - bloom_result.avg_ms, 6),
    }


def run_benchmark(
    seed: int = 42,
    memory_size: int = 180,
    negative_query_count: int = 4000,
    positive_query_count: int = 4000,
) -> dict:
    """Run negative-heavy and positive-heavy benchmarks and return metrics."""
    rng = random.Random(seed)
    max_unique = len(_all_contexts())
    memory_size = max(1, min(memory_size, max_unique // 2))
    entries = _generate_entries(rng, memory_size)
    positive_queries = _make_positive_queries(entries, positive_query_count)
    negative_queries = _make_negative_queries(entries, negative_query_count, rng)

    metrics = {
        "seed": seed,
        "memory_size": memory_size,
        "negative_heavy": _benchmark_case("negative_heavy", entries, negative_queries),
        "positive_heavy": _benchmark_case("positive_heavy", entries, positive_queries),
    }
    return metrics


def main() -> None:
    metrics = run_benchmark()
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

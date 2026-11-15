"""Dedicated Ablation Study & Extended Indexing Benchmarks on Bank v3.

Runs:
1. Component Ablation Study across MPCS G9 TIDE (disabling individual modules).
2. Extended Indexing Techniques: SimHash LSH (64-bit) & Slot Inverted Bitset Index.
"""

from __future__ import annotations

import json
import sys
import time
import hashlib
from pathlib import Path
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "LocalKG" / "experiments"))
sys.path.insert(0, str(REPO_ROOT / "Model" / "experimental" / "02_core"))

import benchmark_indexing_and_tide as B
from mpcs_preset_v3 import build_preset_memory_v3, ARCHETYPES
import random
from dataclasses import dataclass

DANGER_ACTIONS = {"alert", "withdraw"}
UNSAFE_IF_DANGER = {"approach", "ignore"}

@dataclass
class EvalQuery:
    percept: object
    expected_action: str


def bench_simhash_lsh(records, clean_queries, noisy_queries, bits=64, seed=42):
    """64-bit SimHash / LSH random projection binary sketch index."""
    t0 = time.perf_counter()
    # Build vocabulary of (slot, value) tokens
    vocab = {}
    for rec in records:
        for mod in rec["summary"]:
            for k, v, _ in mod:
                tok = (k, v)
                if tok not in vocab:
                    vocab[tok] = len(vocab)
    dim = len(vocab)
    rng = np.random.default_rng(seed)
    proj = rng.standard_normal((dim, bits))

    def encode(summary):
        vec = np.zeros(dim, dtype=np.float32)
        for mod in summary:
            for k, v, _ in mod:
                idx = vocab.get((k, v))
                if idx is not None:
                    vec[idx] = 1.0
        bits_arr = (vec @ proj) >= 0
        val = 0
        for b_i, bit in enumerate(bits_arr):
            if bit:
                val |= (1 << b_i)
        return val

    sigs = [encode(r["summary"]) for r in records]
    build_ms = (time.perf_counter() - t0) * 1000.0
    space_kb = (len(sigs) * 8 + dim * bits * 8) / 1024.0

    def eval_split(queries):
        correct = 0
        unsafe = 0
        lats = []
        for q in queries:
            ts = time.perf_counter()
            q_sig = encode(q.percept.summary)
            best_i = 0
            best_dist = bits + 1
            for i, s in enumerate(sigs):
                d = (q_sig ^ s).bit_count()
                if d < best_dist:
                    best_dist = d
                    best_i = i
            lats.append((time.perf_counter() - ts) * 1000.0)
            pred = records[best_i]["action"]
            if pred == q.expected_action:
                correct += 1
            if q.expected_action in DANGER_ACTIONS and pred in UNSAFE_IF_DANGER:
                unsafe += 1
        n = len(queries)
        return {
            "acc": 100.0 * correct / n,
            "unsafe": 100.0 * unsafe / n,
            "lat_ms": float(np.mean(lats)),
        }

    return {
        "name": "SimHash LSH (64-bit)",
        "space_kb": round(space_kb, 1),
        "build_ms": round(build_ms, 2),
        "clean": eval_split(clean_queries),
        "noisy": eval_split(noisy_queries),
    }


def bench_inverted_bitset(records, clean_queries, noisy_queries):
    """Exact (slot, value) -> Python int bitmask index."""
    t0 = time.perf_counter()
    bitsets = {}
    for i, rec in enumerate(records):
        bit = 1 << i
        for mod in rec["summary"]:
            for k, v, _ in mod:
                tok = (k, v)
                bitsets[tok] = bitsets.get(tok, 0) | bit
    build_ms = (time.perf_counter() - t0) * 1000.0
    space_kb = sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in bitsets.items()) / 1024.0

    def eval_split(queries):
        correct = 0
        unsafe = 0
        lats = []
        for q in queries:
            ts = time.perf_counter()
            # Score by number of matching (slot, val) bitsets
            scores = {}
            for mod in q.percept.summary:
                for k, v, _ in mod:
                    mask = bitsets.get((k, v), 0)
                while mask:
                    lsb = mask & -mask
                    idx = lsb.bit_length() - 1
                    scores[idx] = scores.get(idx, 0) + 1
                    mask ^= lsb
            best_i = max(scores, key=scores.get) if scores else 0
            lats.append((time.perf_counter() - ts) * 1000.0)
            pred = records[best_i]["action"]
            if pred == q.expected_action:
                correct += 1
            if q.expected_action in DANGER_ACTIONS and pred in UNSAFE_IF_DANGER:
                unsafe += 1
        n = len(queries)
        return {
            "acc": 100.0 * correct / n,
            "unsafe": 100.0 * unsafe / n,
            "lat_ms": float(np.mean(lats)),
        }

    return {
        "name": "Slot Inverted Bitset",
        "space_kb": round(space_kb, 1),
        "build_ms": round(build_ms, 2),
        "clean": eval_split(clean_queries),
        "noisy": eval_split(noisy_queries),
    }


def main():
    mem = build_preset_memory_v3()
    records = mem.records
    rng = random.Random(42)
    clean_q = []
    noisy_q = []
    class _P:
        def __init__(self, s): self.summary = s
    for _ in range(480):
        rec = rng.choice(records)
        clean_q.append(EvalQuery(percept=_P(rec["summary"]), expected_action=rec["action"]))
        noisy_mods = [list(m) for m in rec["summary"]]
        for m in noisy_mods:
            non_safety = [idx for idx, (k, v, _) in enumerate(m) if k not in ("thermal", "contact", "odor_type", "sound_type", "texture")]
            if non_safety:
                m.pop(rng.choice(non_safety))
                break
        noisy_q.append(EvalQuery(percept=_P(tuple(tuple(m) for m in noisy_mods)), expected_action=rec["action"]))
    print(f"Loaded Bank v3: {len(records)} records, {len(clean_q)} clean, {len(noisy_q)} noisy")

    lsh = bench_simhash_lsh(records, clean_q, noisy_q)
    bset = bench_inverted_bitset(records, clean_q, noisy_q)

    print("\n=== EXTENDED INDEXING TECHNIQUES ===")
    for res in (lsh, bset):
        print(
            f"{res['name']:22s} | Space: {res['space_kb']:6.1f} KB | Build: {res['build_ms']:5.2f} ms | "
            f"Clean Acc: {res['clean']['acc']:5.1f}% (Unsafe {res['clean']['unsafe']:4.1f}%) | "
            f"Noisy Acc: {res['noisy']['acc']:5.1f}% (Unsafe {res['noisy']['unsafe']:4.1f}%) | "
            f"Lat: {res['clean']['lat_ms']:.3f} ms"
        )

    out = REPO_ROOT / "docs" / "extended_indexing_results.json"
    out.write_text(json.dumps({"simhash_lsh": lsh, "inverted_bitset": bset}, indent=2), encoding="utf-8")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()

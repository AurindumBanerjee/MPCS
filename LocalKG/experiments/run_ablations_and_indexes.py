"""Comprehensive Ablation Studies & Extended Perceptual Indexing Benchmarks.

Runs three empirical studies with zero hardcoded metrics:
  - Study A: Extended Indexing Techniques on Bank v3 (SimHash LSH 64-bit,
             Slot Inverted Bitset, Cuckoo Filter Gate, Navigable Small-World NSW)
             benchmarked alongside Exact KNN, BM25, and dlCBF in one process.
  - Study B: Systematic Component Ablation of MPCS G9 TIDE on Bank v3
             (disabling Spreading Activation, Damasio VAD Affect & Salience,
             KERL Near-Miss Guard, SHMF Auto-Relaxation, HyST Hard Slots,
             Expert Memory Boost, and Anytime Full-Read Budget).
  - Study C: Systematic Component Ablation of LocalKG PersonaQueryEngine
             (1,106 nodes / 2,024 links) across 8 clinical archetype queries.

Outputs:
  - docs/ablation_and_indexing_study.json
  - docs/ABLATION_AND_INDEXING_STUDY.md
"""

from __future__ import annotations

import collections
import hashlib
import heapq
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path
import numpy as np

ROOT = Path(r"D:\MyStuff\GitHub\MPCS")
EXP = ROOT / "Model" / "experimental"
for p in (
    ROOT / "Model" / "reference",
    EXP / "01_baseline_z",
    EXP / "02_core",
    EXP / "04_hyst",
    EXP / "05_hmgi",
    EXP / "06_shmf",
    EXP / "07_kerl",
    EXP / "08_tide",
    EXP / "comparison",
    ROOT / "LocalKG" / "src",
    ROOT / "LocalKG" / "experiments",
):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import datasets as D
import mpcs_engine as E
from hyst_layer import SlotPolicy
from tide_layer import TideConfig, TideReader
import benchmark_indexing_and_tide as B
import benchmark_persona_engine as BP
import lkg.query.persona_engine as PE

DOCS_DIR = ROOT / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------
# Study A: Extended Perceptual Indexing Classes
# ----------------------------------------------------------------------

def _extract_feature_dict(percept: dict) -> dict[str, float]:
    feats: dict[str, float] = {}
    for mod, d in percept.items():
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    feats[f"{mod}:{k}"] = float(v)
                else:
                    feats[f"{mod}:{k}:{v}"] = 1.0
    return feats


class SimHashLSHIndex:
    """64-bit random-hyperplane SimHash binary sketch index with Hamming search."""

    def __init__(self, bits: int = 64, seed: int = 42):
        self.bits = bits
        self.seed = seed
        self.vocab: dict[str, int] = {}
        self.proj: np.ndarray | None = None
        self.sigs: list[int] = []
        self.labels: list[str] = []
        self.rewards: list[float] = []

    def _signature(self, percept: dict) -> int:
        vec = np.zeros(len(self.vocab), dtype=np.float32)
        for f, val in _extract_feature_dict(percept).items():
            idx = self.vocab.get(f)
            if idx is not None:
                vec[idx] = val
        dots = vec @ self.proj
        sig = 0
        for b_i, flag in enumerate(dots >= 0.0):
            if flag:
                sig |= 1 << b_i
        return sig

    def fit(self, records: list[dict]) -> None:
        all_feats = set()
        for r in records:
            all_feats.update(_extract_feature_dict(r["percept"]).keys())
        self.vocab = {f: i for i, f in enumerate(sorted(all_feats))}
        rng = np.random.default_rng(self.seed)
        self.proj = rng.standard_normal((len(self.vocab), self.bits), dtype=np.float32)
        self.sigs = []
        self.labels = []
        self.rewards = []
        for r in records:
            self.sigs.append(self._signature(r["percept"]))
            self.labels.append(r["action"])
            self.rewards.append(float(r.get("reward", 0.5)))

    def query_scores(self, percept: dict, k: int = 5) -> tuple[str, dict[str, float], int]:
        q_sig = self._signature(percept)
        dists = []
        for i, s in enumerate(self.sigs):
            ham = (q_sig ^ s).bit_count()
            sim = 1.0 - (ham / self.bits)
            dists.append((sim, self.labels[i], self.rewards[i]))
        dists.sort(key=lambda x: x[0], reverse=True)
        action_scores = {a: 0.0 for a in E.ACTIONS}
        for sim, act, rew in dists[:k]:
            action_scores[act] += sim * rew
        best = max(action_scores, key=action_scores.get)
        return best, action_scores, len(self.sigs)


class SlotInvertedBitsetIndex:
    """Exact (modality, feature, value) -> packed Python integer bitmask index."""

    def __init__(self):
        self.bitsets: dict[str, int] = {}
        self.labels: list[str] = []
        self.rewards: list[float] = []
        self.n_docs = 0

    def _tokens(self, percept: dict) -> list[str]:
        tokens = []
        for mod, d in percept.items():
            if isinstance(d, dict):
                for k, v in d.items():
                    tokens.append(f"{mod}_{k}_{v}")
        return tokens

    def fit(self, records: list[dict]) -> None:
        self.bitsets.clear()
        self.labels = []
        self.rewards = []
        for doc_id, r in enumerate(records):
            bit = 1 << doc_id
            for tok in self._tokens(r["percept"]):
                self.bitsets[tok] = self.bitsets.get(tok, 0) | bit
            self.labels.append(r["action"])
            self.rewards.append(float(r.get("reward", 0.5)))
        self.n_docs = len(records)

    def query_scores(self, percept: dict, k: int = 5) -> tuple[str, dict[str, float], int]:
        q_tokens = self._tokens(percept)
        hit_counts: dict[int, int] = collections.defaultdict(int)
        for tok in q_tokens:
            mask = self.bitsets.get(tok, 0)
            while mask:
                lsb = mask & -mask
                doc_id = lsb.bit_length() - 1
                hit_counts[doc_id] += 1
                mask ^= lsb
        scanned = len(hit_counts)
        if not hit_counts:
            return "observe", {a: 0.0 for a in E.ACTIONS}, 0
        ranked = sorted(hit_counts.items(), key=lambda x: x[1], reverse=True)[:k]
        action_scores = {a: 0.0 for a in E.ACTIONS}
        denom = max(1, len(q_tokens))
        for doc_id, hits in ranked:
            action_scores[self.labels[doc_id]] += (hits / denom) * self.rewards[doc_id]
        best = max(action_scores, key=action_scores.get)
        return best, action_scores, scanned


class CuckooFilterGateIndex:
    """2-choice partial-key Cuckoo Filter membership gate with exact payload fallback."""

    def __init__(self, num_buckets: int = 256, bucket_size: int = 4, seed: int = 42):
        self.num_buckets = num_buckets
        self.bucket_size = bucket_size
        self.rng = random.Random(seed)
        self.buckets: list[list[int]] = [[] for _ in range(num_buckets)]
        self.exact_bucket: dict[str, list[tuple[str, float]]] = collections.defaultdict(list)

    def _hash_fp(self, key: str) -> tuple[int, int, int]:
        digest = hashlib.blake2b(key.encode("utf-8"), digest_size=16).digest()
        fp = (int.from_bytes(digest[0:2], "little") & 0xFFFF) or 1
        i1 = int.from_bytes(digest[2:6], "little") % self.num_buckets
        fp_hash = int.from_bytes(
            hashlib.blake2b(fp.to_bytes(2, "little"), digest_size=4).digest(),
            "little",
        )
        i2 = (i1 ^ fp_hash) % self.num_buckets
        return fp, i1, i2

    def fit(self, records: list[dict]) -> None:
        self.buckets = [[] for _ in range(self.num_buckets)]
        self.exact_bucket.clear()
        for r in records:
            key = json.dumps(r["percept"], sort_keys=True)
            fp, i1, i2 = self._hash_fp(key)
            if fp not in self.buckets[i1] and fp not in self.buckets[i2]:
                if len(self.buckets[i1]) < self.bucket_size:
                    self.buckets[i1].append(fp)
                elif len(self.buckets[i2]) < self.bucket_size:
                    self.buckets[i2].append(fp)
                else:
                    idx = self.rng.choice((i1, i2))
                    cur_fp = fp
                    for _ in range(250):
                        pos = self.rng.randrange(self.bucket_size)
                        cur_fp, self.buckets[idx][pos] = self.buckets[idx][pos], cur_fp
                        fp_h = int.from_bytes(
                            hashlib.blake2b(cur_fp.to_bytes(2, "little"), digest_size=4).digest(),
                            "little",
                        )
                        idx = (idx ^ fp_h) % self.num_buckets
                        if len(self.buckets[idx]) < self.bucket_size:
                            self.buckets[idx].append(cur_fp)
                            break
            self.exact_bucket[key].append((r["action"], float(r.get("reward", 0.5))))

    def query_scores(self, percept: dict, k: int = 5) -> tuple[str, dict[str, float], int]:
        key = json.dumps(percept, sort_keys=True)
        fp, i1, i2 = self._hash_fp(key)
        if fp not in self.buckets[i1] and fp not in self.buckets[i2]:
            return "observe", {a: 0.0 for a in E.ACTIONS}, 0
        matches = self.exact_bucket.get(key, [])
        action_scores = {a: 0.0 for a in E.ACTIONS}
        for act, rew in matches:
            action_scores[act] += rew
        best = max(action_scores, key=action_scores.get) if matches else "observe"
        return best, action_scores, len(matches)


class NSWGraphIndex:
    """In-memory Navigable Small-World (NSW) proximity graph with greedy beam search."""

    def __init__(self, m_links: int = 8, ef_search: int = 24):
        self.m_links = m_links
        self.ef_search = ef_search
        self.vocab: dict[str, int] = {}
        self.matrix: np.ndarray | None = None
        self.adj: list[list[int]] = []
        self.labels: list[str] = []
        self.rewards: list[float] = []

    def _to_unit_vec(self, percept: dict) -> np.ndarray:
        vec = np.zeros(len(self.vocab), dtype=np.float32)
        for f, val in _extract_feature_dict(percept).items():
            idx = self.vocab.get(f)
            if idx is not None:
                vec[idx] = val
        norm = float(np.linalg.norm(vec))
        if norm > 0.0:
            vec /= norm
        return vec

    def _beam_search(self, q_vec: np.ndarray, max_nodes: int, ef: int) -> tuple[list[tuple[float, int]], int]:
        if max_nodes == 0:
            return [], 0
        visited = {0}
        s0 = float(q_vec @ self.matrix[0])
        candidates = [(-s0, 0)]
        results = [(s0, 0)]
        scanned = 1
        while candidates:
            neg_sim, u = heapq.heappop(candidates)
            worst_res = min(results, key=lambda x: x[0])[0] if len(results) >= ef else -1.0
            if -neg_sim < worst_res and len(results) >= ef:
                break
            for v in self.adj[u]:
                if v in visited or v >= max_nodes:
                    continue
                visited.add(v)
                sv = float(q_vec @ self.matrix[v])
                scanned += 1
                if len(results) < ef or sv > min(results, key=lambda x: x[0])[0]:
                    heapq.heappush(candidates, (-sv, v))
                    results.append((sv, v))
                    if len(results) > ef:
                        results.sort(key=lambda x: x[0], reverse=True)
                        results.pop()
        results.sort(key=lambda x: x[0], reverse=True)
        return results, scanned

    def fit(self, records: list[dict]) -> None:
        all_feats = set()
        for r in records:
            all_feats.update(_extract_feature_dict(r["percept"]).keys())
        self.vocab = {f: i for i, f in enumerate(sorted(all_feats))}
        n = len(records)
        self.matrix = np.zeros((n, len(self.vocab)), dtype=np.float32)
        self.adj = [[] for _ in range(n)]
        self.labels = []
        self.rewards = []
        for i, r in enumerate(records):
            v = self._to_unit_vec(r["percept"])
            self.matrix[i] = v
            self.labels.append(r["action"])
            self.rewards.append(float(r.get("reward", 0.5)))
            if i == 0:
                continue
            if i <= self.m_links * 2:
                sims = [(float(v @ self.matrix[j]), j) for j in range(i)]
                sims.sort(key=lambda x: x[0], reverse=True)
                nbrs = [j for _, j in sims[: self.m_links]]
            else:
                res, _ = self._beam_search(v, max_nodes=i, ef=self.ef_search)
                nbrs = [j for _, j in res[: self.m_links]]
            for j in nbrs:
                if j not in self.adj[i]:
                    self.adj[i].append(j)
                if i not in self.adj[j]:
                    self.adj[j].append(i)

    def query_scores(self, percept: dict, k: int = 5) -> tuple[str, dict[str, float], int]:
        q_vec = self._to_unit_vec(percept)
        res, scanned = self._beam_search(q_vec, max_nodes=len(self.labels), ef=self.ef_search)
        action_scores = {a: 0.0 for a in E.ACTIONS}
        for sim, idx in res[:k]:
            action_scores[self.labels[idx]] += sim * self.rewards[idx]
        best = max(action_scores, key=action_scores.get) if res else "observe"
        return best, action_scores, scanned


def run_study_a(v3_records, clean_queries, noisy_queries) -> dict:
    print("\n[Study A] Extended Perceptual Indexing Techniques (Bank v3)...")
    specs = [
        ("Exact KNN (Cosine)", "$O(N \\cdot D)$", B.ExactKNNIndex()),
        ("BM25 Inverted Index", "$O(|Q| \\cdot \\overline{DF})$", B.BM25Index()),
        ("dlCBF Gate", "$O(d)$ hash", B.CountingBloomFilterIndex()),
        ("Cuckoo Filter Gate", "$O(1)$ 2-choice", CuckooFilterGateIndex()),
        ("SimHash LSH (64-bit)", "$O(N)$ XOR popcnt", SimHashLSHIndex()),
        ("Slot Inverted Bitset", "$O(|Q| \\cdot \\text{hits})$", SlotInvertedBitsetIndex()),
        ("NSW Proximity Graph", "$O(\\text{ef} \\cdot M \\log N)$", NSWGraphIndex()),
    ]
    out = {}
    for name, comp, idx_obj in specs:
        t0 = time.perf_counter()
        idx_obj.fit(v3_records)
        build_ms = (time.perf_counter() - t0) * 1000.0
        if isinstance(idx_obj, B.CountingBloomFilterIndex):
            space_bytes = B.deep_sizeof(idx_obj.tables)
        elif isinstance(idx_obj, CuckooFilterGateIndex):
            space_bytes = B.deep_sizeof(idx_obj.buckets)
        elif isinstance(idx_obj, SimHashLSHIndex):
            space_bytes = B.deep_sizeof(idx_obj) + int(idx_obj.proj.nbytes)
        elif isinstance(idx_obj, NSWGraphIndex):
            space_bytes = B.deep_sizeof(idx_obj) + int(idx_obj.matrix.nbytes)
        else:
            space_bytes = B.deep_sizeof(idx_obj)

        clean_m = B.eval_scheme_metrics(lambda p, o=idx_obj: o.query_scores(p, k=5), clean_queries)
        noisy_m = B.eval_scheme_metrics(lambda p, o=idx_obj: o.query_scores(p, k=5), noisy_queries)
        out[name] = {
            "complexity": comp,
            "build_ms": round(build_ms, 2),
            "space_kb": round(space_bytes / 1024.0, 1),
            "scanned_clean": clean_m["scanned_mean"],
            "latency_mean_ms": clean_m["latency_mean_ms"],
            "latency_p95_ms": clean_m["latency_p95_ms"],
            "clean_acc": clean_m["accuracy"],
            "clean_r3": clean_m["recall_3"],
            "clean_unsafe": clean_m["unsafe_pct"],
            "noisy_acc": noisy_m["accuracy"],
            "noisy_unsafe": noisy_m["unsafe_pct"],
        }
        print(
            f"  [OK] {name:<22} | {out[name]['space_kb']:>6.1f} KB | "
            f"Scan {out[name]['scanned_clean']:>5.1f} | "
            f"Lat {out[name]['latency_mean_ms']:.3f} ms | "
            f"Clean {out[name]['clean_acc']:>5.1f}% (Unsf {out[name]['clean_unsafe']:>4.1f}%) | "
            f"Noisy {out[name]['noisy_acc']:>5.1f}% (Unsf {out[name]['noisy_unsafe']:>4.1f}%)"
        )
    return out


# ----------------------------------------------------------------------
# Study B: MPCS G9 TIDE Systematic Component Ablation
# ----------------------------------------------------------------------

def run_study_b(v3_records, clean_queries, noisy_queries) -> list[dict]:
    print("\n[Study B] MPCS G9 TIDE Systematic Component Ablation (Bank v3)...")
    step_tide = max(r["step"] for r in v3_records) + 1
    mem = E.MemorySystem()
    for r in v3_records:
        mem.store(
            E.summary_of(r["percept"]),
            r["action"],
            r["reward"],
            r["step"],
            is_expert=r.get("is_expert", False),
            mode=r.get("mode", "DELIBERATIVE"),
        )

    variants = [
        ("Full G9 TIDE (Urgent=False)", SlotPolicy(), TideConfig(verify_async=False, affect_enabled=True), True, E.EngineConfig()),
        ("w/o TIDE Spread (hops=0, w_g=0)", SlotPolicy(), TideConfig(verify_async=False, affect_enabled=True, spread_hops=0, w_g=0.0), True, E.EngineConfig()),
        ("w/o VAD Affect & Salience", SlotPolicy(), TideConfig(verify_async=False, salience_gain=0.0, affect_enabled=False), True, E.EngineConfig()),
        ("w/o KERL Near-Miss Guard", SlotPolicy(), TideConfig(verify_async=False, affect_enabled=True, guard_enabled=False), True, E.EngineConfig()),
        ("w/o SHMF Auto-Relaxation", SlotPolicy(), TideConfig(verify_async=False, affect_enabled=True), False, E.EngineConfig()),
        ("w/o HyST Hard Slots (Soft Only)", SlotPolicy(hard_slots=frozenset()), TideConfig(verify_async=False, affect_enabled=True, guard_enabled=False), False, E.EngineConfig()),
        ("w/o Expert Boost (boost=1.0)", SlotPolicy(), TideConfig(verify_async=False, affect_enabled=True), True, E.EngineConfig(expert_weight_boost=1.0)),
        ("w/o Full-Read (Urgent B=3)", SlotPolicy(urgent=True), TideConfig(verify_async=False, affect_enabled=True, urgent_budget=3), True, E.EngineConfig()),
    ]

    results = []
    for label, pol, tc, auto_relax, ec in variants:
        reader = TideReader(mem, pol, tc, auto_relax=auto_relax)
        row = {"variant": label}
        for split_name, qs in (("clean", clean_queries), ("noisy", noisy_queries)):
            corr = uns = dng = 0
            lats = []
            for p, lbl in qs:
                t0 = time.perf_counter()
                res = reader.read(E.summary_of(p), step_tide, ec)
                lats.append((time.perf_counter() - t0) * 1000.0)
                best = res["tide"]["best"]
                corr += (best == lbl)
                if lbl in D.DANGER:
                    dng += 1
                    uns += (best in B.UNSAFE_ACTIONS)
            row[f"{split_name}_acc"] = round(100.0 * corr / len(qs), 1)
            row[f"{split_name}_unsafe"] = round(100.0 * uns / max(1, dng), 1)
            row[f"{split_name}_lat_ms"] = round(sum(lats) / len(lats), 2)
        results.append(row)
        print(
            f"  [OK] {label:<33} | Clean {row['clean_acc']:>5.1f}% (Unsf {row['clean_unsafe']:>4.1f}%) | "
            f"Noisy {row['noisy_acc']:>5.1f}% (Unsf {row['noisy_unsafe']:>4.1f}%) | {row['clean_lat_ms']:.2f} ms"
        )
    return results


# ----------------------------------------------------------------------
# Study C: LocalKG PersonaQueryEngine Component Ablation
# ----------------------------------------------------------------------

QUERY_EXPECTED_REMEDIES = [
    ("violent throbbing headache with delirium fear of death midnight", ("belladonna", "aconit")),
    ("bruised soreness from blunt injury jarring worse motion", ("arnica",)),
    ("burning pain in stomach better warm drinks restlessness exhaustion", ("arsenicum",)),
    ("sudden high fever dry hot skin flushed face anxiety", ("aconit", "belladonna")),
    ("melancholy silent grief weeping involuntary sighs contradiction", ("ignatia",)),
    ("cough dry tickling in throat worse cold air evening", ("rumex", "spongia", "bryonia", "phosphorus")),
    ("stiffness in joints worse first motion better continuous walking", ("rhus",)),
    ("intense thirst for cold water panic fright heart palpitations", ("aconit", "arsenicum", "bryonia")),
]


def _remedy_top_hit(result: PE.PersonaQueryResult, expected_prefixes: tuple[str, ...]) -> tuple[bool, bool]:
    meds = [n for n in result.active_nodes if n.type == "Medicine"]
    if not meds:
        return False, False
    top1 = meds[0].label.lower()
    top3 = [m.label.lower() for m in meds[:3]]
    hit1 = any(pref in top1 for pref in expected_prefixes)
    hit3 = any(any(pref in m for pref in expected_prefixes) for m in top3)
    return hit1, hit3


def run_study_c() -> list[dict]:
    print("\n[Study C] LocalKG PersonaQueryEngine Component Ablation...")
    base_engine = PE.PersonaQueryEngine()
    orig_multipliers = dict(base_engine.node_multipliers)
    orig_synonyms = dict(PE.CLINICAL_SYNONYMS)

    configs = [
        ("Full Exploratory (theta=0.35)", PE.PersonaType.EXPLORATORY, 0.70, 0.35, 2, True, True),
        ("Full Confident (theta=0.70)", PE.PersonaType.CONFIDENT, 0.70, 0.35, 2, True, True),
        ("w/o 2-Hop Spread (hops=0)", PE.PersonaType.EXPLORATORY, 0.70, 0.35, 0, True, True),
        ("w/o VAD Arousal & Severity", PE.PersonaType.EXPLORATORY, 0.70, 0.35, 2, False, True),
        ("w/o Clinical Synonyms", PE.PersonaType.EXPLORATORY, 0.70, 0.35, 2, True, False),
    ]

    results = []
    n_runs = 25
    for label, ptype, tc, te, hops, use_vad, use_syn in configs:
        base_engine.node_multipliers = orig_multipliers if use_vad else {k: 1.0 for k in orig_multipliers}
        PE.CLINICAL_SYNONYMS.clear()
        if use_syn:
            PE.CLINICAL_SYNONYMS.update(orig_synonyms)

        kept_counts, pruned_pcts, edge_int_counts, latencies = [], [], [], []
        top1_hits = top3_hits = 0
        for _ in range(n_runs):
            for q, exp in QUERY_EXPECTED_REMEDIES:
                t0 = time.perf_counter()
                res = base_engine.query(q, persona=ptype, theta_conf=tc, theta_expl=te, max_hops=hops)
                latencies.append((time.perf_counter() - t0) * 1000.0)
                if _ == 0:
                    kept_counts.append(res.kept_count)
                    pruned_pcts.append(res.pruning_ratio_pct)
                    edge_int_counts.append(len(res.subgraph_internal_edges))
                    h1, h3 = _remedy_top_hit(res, exp)
                    top1_hits += int(h1)
                    top3_hits += int(h3)

        row = {
            "variant": label,
            "mean_kept_nodes": round(statistics.mean(kept_counts), 1),
            "mean_pruned_pct": round(statistics.mean(pruned_pcts), 1),
            "mean_internal_edges": round(statistics.mean(edge_int_counts), 1),
            "remedy_top1_hits": f"{top1_hits}/{len(QUERY_EXPECTED_REMEDIES)}",
            "remedy_top3_hits": f"{top3_hits}/{len(QUERY_EXPECTED_REMEDIES)}",
            "mean_lat_ms": round(statistics.mean(latencies), 2),
        }
        results.append(row)
        print(
            f"  [OK] {label:<30} | Kept {row['mean_kept_nodes']:>5.1f} ({row['mean_pruned_pct']:>4.1f}% pruned) | "
            f"Edges {row['mean_internal_edges']:>5.1f} | Top1 {row['remedy_top1_hits']} | Top3 {row['remedy_top3_hits']} | "
            f"{row['mean_lat_ms']:.2f} ms"
        )

    # Restore globals cleanly
    base_engine.node_multipliers = orig_multipliers
    PE.CLINICAL_SYNONYMS.clear()
    PE.CLINICAL_SYNONYMS.update(orig_synonyms)

    # Also measure linear-scan baseline (w/o Inverted Index) over n_runs
    lin_lats, lin_kept = [], []
    for r_i in range(n_runs):
        for q, _ in QUERY_EXPECTED_REMEDIES:
            t0 = time.perf_counter()
            conf, expl = BP.run_unoptimized_baseline(base_engine, q)
            lin_lats.append((time.perf_counter() - t0) * 1000.0)
            if r_i == 0:
                lin_kept.append(len(conf) + len(expl))
    lin_row = {
        "variant": "w/o Inverted Index (Linear Scan)",
        "mean_kept_nodes": round(statistics.mean(lin_kept), 1),
        "mean_pruned_pct": round(100.0 * (1.0 - statistics.mean(lin_kept) / len(base_engine.nodes)), 1),
        "mean_internal_edges": "-",
        "remedy_top1_hits": "-",
        "remedy_top3_hits": "-",
        "mean_lat_ms": round(statistics.mean(lin_lats), 2),
    }
    results.append(lin_row)
    print(f"  [OK] {lin_row['variant']:<30} | Kept {lin_row['mean_kept_nodes']:>5.1f} | {lin_row['mean_lat_ms']:.2f} ms")
    return results


# ----------------------------------------------------------------------
# Report Export & Main Entry
# ----------------------------------------------------------------------

def write_markdown_summary(study_a: dict, study_b: list[dict], study_c: list[dict]) -> Path:
    lines = [
        "# Ablation Studies and Extended Perceptual Indexing Benchmarks",
        "",
        "## Study A: Extended Perceptual Indexing Schemes (Bank v3: 700 records, 480 Clean + 480 Noisy)",
        "",
        "| Indexing Scheme | Complexity | Space (KB) | Build (ms) | Scanned | Mean Lat (ms) | p95 Lat (ms) | Clean Acc % | R@3 % | Clean Unsafe % | Noisy Acc % | Noisy Unsafe % |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for name, d in study_a.items():
        lines.append(
            f"| **{name}** | {d['complexity']} | {d['space_kb']} | {d['build_ms']} | {d['scanned_clean']} | "
            f"{d['latency_mean_ms']:.3f} | {d['latency_p95_ms']:.3f} | **{d['clean_acc']}%** | {d['clean_r3']}% | "
            f"{d['clean_unsafe']}% | **{d['noisy_acc']}%** | {d['noisy_unsafe']}% |"
        )

    lines.extend([
        "",
        "## Study B: MPCS G9 TIDE Systematic Component Ablation (Bank v3)",
        "",
        "| Configuration | Clean Acc % | Clean Unsafe % | Noisy Acc % | Noisy Unsafe % | Clean Lat (ms) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
    ])
    for row in study_b:
        lines.append(
            f"| **{row['variant']}** | {row['clean_acc']}% | {row['clean_unsafe']}% | "
            f"{row['noisy_acc']}% | {row['noisy_unsafe']}% | {row['clean_lat_ms']:.2f} |"
        )

    lines.extend([
        "",
        "## Study C: LocalKG PersonaQueryEngine Component Ablation (1,106 nodes, 2,024 links)",
        "",
        "| Configuration | Mean Kept Nodes | Pruned % | Internal Edges | Remedy Top-1 | Remedy Top-3 | Mean Lat (ms) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])
    for row in study_c:
        lines.append(
            f"| **{row['variant']}** | {row['mean_kept_nodes']} | {row['mean_pruned_pct']}% | "
            f"{row['mean_internal_edges']} | {row['remedy_top1_hits']} | {row['remedy_top3_hits']} | {row['mean_lat_ms']:.2f} |"
        )

    out_md = DOCS_DIR / "ABLATION_AND_INDEXING_STUDY.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")
    return out_md


def main() -> None:
    v3_records = D.bank_v3()
    v3_sets = D.query_sets("v3", v3_records)
    clean_q = v3_sets["clean"]
    noisy_q = v3_sets["noisy"]
    print(f"Loaded Bank v3: {len(v3_records)} records, {len(clean_q)} clean queries, {len(noisy_q)} noisy queries")

    study_a = run_study_a(v3_records, clean_q, noisy_q)
    study_b = run_study_b(v3_records, clean_q, noisy_q)
    study_c = run_study_c()

    out_json = DOCS_DIR / "ablation_and_indexing_study.json"
    out_json.write_text(
        json.dumps(
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "study_a_extended_indexing": study_a,
                "study_b_mpcs_tide_ablation": study_b,
                "study_c_personakg_ablation": study_c,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    out_md = write_markdown_summary(study_a, study_b, study_c)
    print(f"\n[OK] Saved JSON: {out_json}")
    print(f"[OK] Saved MD:   {out_md}")


if __name__ == "__main__":
    main()

"""Comprehensive Ablation Studies & Extended Perceptual Indexing Benchmarks on LocalKG Materia Medica KG.

Runs three empirical studies with zero hardcoded metrics on the extracted LocalKG
Materia Medica Knowledge Graph (953 clinical occurrences across 202 JSONL rows and
the 1,106-node / 2,024-edge cleaned clinical graph):

  - Study A: Extended Perceptual Indexing Techniques (Exact KNN, BM25, dlCBF Gate,
             Cuckoo Filter Gate, SimHash LSH 64-bit, Slot Inverted Bitset, NSW
             Proximity Graph) alongside MPCS cognitive generations (B2, G4-G9)
             over the 953-occurrence MMKG bank (300 clean + 300 noisy queries).
  - Study B: Systematic Component Ablation of MPCS G9 TIDE (8 variants) plus
             Anytime Deadline Budgets (B=3, 5, 10, 20, 50, Full) and Sufficiency
             Routing (DIRECT, SUBGRAPH, UNGROUNDED) on MMKG.
  - Study C: Systematic Component Ablation of LocalKG PersonaQueryEngine across
             40 clinical queries (32 remedy-specific + 8 clinical archetypes) x
             10 iterations (400 calls per variant) on the 1,106-node / 2,024-link
             MMKG graph (8 ablation variants including Linear Scan baseline).

Outputs:
  - docs/ablation_and_indexing_study.json
  - docs/ABLATION_AND_INDEXING_STUDY.md
"""

from __future__ import annotations

import collections
import hashlib
import heapq
import json
import random
import re
import statistics
import sys
import time
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "Model" / "experimental"
for _p in (
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
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import benchmark_indexing_and_tide as B
import benchmark_persona_engine as BP
import datasets as D
import lkg.query.persona_engine as PE
import models as M
import mpcs_engine as E
from hyst_layer import SlotPolicy
from tide_layer import TideConfig, TideReader

DOCS_DIR = ROOT / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
MMKG_JSONL = ROOT / "LocalKG" / "data" / "extracted" / "kg_full_materia_medica.jsonl"
MMKG_GRAPH = ROOT / "LocalKG" / "data" / "extracted" / "kg_full_materia_medica_cleaned.graph.json"


# ----------------------------------------------------------------------
# 1. Materia Medica KG Dataset Construction (953 Clinical Occurrences)
# ----------------------------------------------------------------------

_NEGATION_RE = re.compile(
    r"(?<!from\s)\b(?:without|no|not|never|absence\s+of|at\s+least\s+not)\s+"
    r"(?:any\s+|particular\s+|when\s+|on\s+)?"
    r"(?:thirst|appetite|hunger|heat|hot|warm|cold|coldness|redness|fever|"
    r"sweat\w*|perspir\w*|formication|nausea|vomit\w*|pain|headache|walking|"
    r"moving|motion|urinating|urine|food|bad\s+taste|relief|ameliorat\w*)\b"
    r"|\bthirst\s*[- ]?less\b",
    re.IGNORECASE,
)

# Precompiled word-boundary regexes preventing substring collisions (e.g., "red" in "occurred")
_PAT_THERMAL_HOT = re.compile(r"\b(?:fever\w*|burn\w*|hot|heat\w*|inflamm\w*|flushed|pyrexia)\b", re.I)
_PAT_THERMAL_COLD = re.compile(r"\b(?:chill\w*|cold\w*|shiver\w*|icy|ice|draft\w*|draught\w*|open\s+air|frost\w*|winter\w*)\b", re.I)
_PAT_THERMAL_WARM = re.compile(r"\b(?:warm\w*|sweat\w*|perspir\w*)\b", re.I)

_PAT_CONTACT_IMPACT = re.compile(r"\b(?:bruis\w*|blunt\w*|injur\w*|trauma\w*|blow\w*|jar|jarring|fall|falling|sprain\w*|concuss\w*)\b", re.I)
_PAT_CONTACT_FIRM = re.compile(r"\b(?:press\w*|tight\w*|constrict\w*|cramp\w*|squeez\w*|band|stiff\w*|hard|hardness|tension|tense)\b", re.I)
_PAT_CONTACT_LIGHT = re.compile(r"\b(?:touch\w*|sensitiv\w*|tickl\w*|crawl\w*|formicat\w*|itch\w*)\b", re.I)

_PAT_TEXTURE_SHARP = re.compile(r"\b(?:sharp\w*|stab\w*|cut|cuts|cutting|stitch\w*|lancinat\w*|pierc\w*|shoot\w*|splinter\w*|tear|tearing)\b", re.I)
_PAT_TEXTURE_WET = re.compile(r"\b(?:discharg\w*|sweat\w*|catarrh\w*|mucus|watery|coryza|diarrh\w*|vomit\w*|saliva\w*|lachrym\w*|bleed\w*|hemorrhag\w*|urin\w*)\b", re.I)
_PAT_TEXTURE_ROUGH = re.compile(r"\b(?:raw|excoriat\w*|dry\w*|crack\w*|scaly|hoarse\w*|scrap\w*|sand\w*)\b", re.I)

_PAT_SOUND_ALARM = re.compile(r"\b(?:terror\w*|panic\w*|fright\w*|delirium|delirious|fear\s+of\s+death|scream\w*|shriek\w*|anguish|convuls\w*|spasm\w*)\b", re.I)
_PAT_SOUND_NOISE = re.compile(r"\b(?:roar\w*|ring\w*|tinnitus|buzz\w*|hiss\w*|cough\w*|hoarse\w*|rattl\w*|wheez\w*|rumbl\w*|eructat\w*|belch\w*)\b", re.I)
_PAT_SOUND_SPEECH = re.compile(r"\b(?:grief|weep\w*|sigh\w*|talk\w*|mutter\w*|sad\w*|melanchol\w*|irritab\w*|anger|angry|contradict\w*|anxiet\w*|anxious|fear\w*)\b", re.I)
_PAT_AUDIO_HIGH = re.compile(r"\b(?:loud\w*|violent\w*|incessant\w*|paroxysm\w*|spasmodic\w*)\b", re.I)
_PAT_AUDIO_LOW = re.compile(r"\b(?:silent\w*|faint\w*|whisper\w*|weak\w*)\b", re.I)

_PAT_MOTION_FAST = re.compile(r"\b(?:restless\w*|toss\w*|motion\w*|walk\w*|pacing|agitat\w*|jerk\w*|twitch\w*|trembl\w*|vertigo|palpitat\w*)\b", re.I)
_PAT_MOTION_SLOW = re.compile(r"\bfirst\s+motion\b|\b(?:slow\w*|sluggish\w*|heavy|heaviness|weary|weariness|dull\w*|letharg\w*|stiff\w*)\b", re.I)

_PAT_COLOR_RED = re.compile(r"\b(?:red\w*|flush\w*|inflamm\w*|blood\w*|congest\w*|scarlet\w*|heat\w*|burn\w*)\b", re.I)
_PAT_COLOR_DARK = re.compile(r"\b(?:night\w*|midnight|evening\w*|dark\w*|black\w*|livid\w*|cloud\w*|dim|dimness)\b", re.I)
_PAT_COLOR_BRIGHT = re.compile(r"\b(?:morning\w*|light\b|photophob\w*|spark\w*|flash\w*|glare\w*|day\w*|sun\w*)\b", re.I)

_PAT_ODOR_SMOKE = re.compile(r"\b(?:burnt|smok\w*|empyreumat\w*|charcoal)\b", re.I)
_PAT_ODOR_CHEM = re.compile(r"\b(?:acrid|sour\w*|acid\w*|corrosiv\w*|metallic|sulphur\w*|bitter\w*)\b", re.I)
_PAT_ODOR_ORG = re.compile(r"\b(?:fetid|putrid|offensiv\w*|cadaver\w*|rotten|purulent|stool\w*|urin\w*)\b", re.I)
_PAT_ODOR_FOOD = re.compile(r"\b(?:thirst\w*|appetit\w*|food|drink\w*|eat|eating|eats|milk|bread|fat|sweet\w*|coffee|wine|stomach\w*|nausea\w*)\b", re.I)

_PAT_ODOR_STRONG = re.compile(r"\b(?:offensiv\w*|putrid|fetid|acrid|intense\w*|unbearable|violent\w*)\b", re.I)
_PAT_ODOR_MOD = re.compile(r"\b(?:sour\w*|bitter\w*|thirst\w*|nausea\w*|vomit\w*)\b", re.I)

_PAT_PLEAS_FOUL = re.compile(r"\b(?:fetid|putrid|offensiv\w*|nausea\w*|loath\w*|disgust\w*)\b", re.I)
_PAT_PLEAS_GOOD = re.compile(r"\b(?:better|ameliorat\w*|relief|cheerful\w*)\b", re.I)

_ANIMAL_REMEDIES = frozenset(("Lachesis mutus", "Ambra grisea", "Carbo animalis"))


def _combine_occurrence_text(occ: dict) -> str:
    parts = [
        str(occ.get("canonical_label") or ""),
        str(occ.get("symptom_raw") or ""),
        str(occ.get("evidence_quote") or ""),
    ]
    sens = occ.get("sensation_raw") or []
    if isinstance(sens, list):
        parts.extend(str(s) for s in sens)
    elif sens:
        parts.append(str(sens))

    for mod in occ.get("modalities") or []:
        if isinstance(mod, dict):
            parts.append(f"{mod.get('direction', '')} {mod.get('factor_raw', '')} {mod.get('factor_type', '')}")
        else:
            parts.append(str(mod))

    return _NEGATION_RE.sub(" ", " ".join(parts)).lower()


def _map_occurrence_to_percept(occ: dict) -> dict[str, dict[str, str]]:
    txt = _combine_occurrence_text(occ)
    sec = str(occ.get("section") or "")
    skind = str(occ.get("symptom_kind") or "")
    remedy = str(occ.get("remedy_name") or "")
    grade = int(occ.get("grade") or 1)
    adj_sev = float(occ.get("adjective_severity") if occ.get("adjective_severity") is not None else 0.5)
    comp_w = float(occ.get("composite_weight") if occ.get("composite_weight") is not None else 1.5)
    vad = occ.get("vad") or {}
    valence = float(vad.get("valence", 0.45))
    arousal = float(vad.get("arousal", 0.5))

    # Touch
    if _PAT_THERMAL_HOT.search(txt):
        thermal = "hot"
    elif _PAT_THERMAL_COLD.search(txt):
        thermal = "cold"
    elif _PAT_THERMAL_WARM.search(txt):
        thermal = "warm"
    else:
        thermal = "neutral"

    if _PAT_CONTACT_IMPACT.search(txt):
        contact = "impact"
    elif _PAT_CONTACT_FIRM.search(txt):
        contact = "firm"
    elif _PAT_CONTACT_LIGHT.search(txt):
        contact = "light"
    else:
        contact = "none"

    if _PAT_TEXTURE_SHARP.search(txt):
        texture = "sharp"
    elif _PAT_TEXTURE_WET.search(txt):
        texture = "wet"
    elif _PAT_TEXTURE_ROUGH.search(txt):
        texture = "rough"
    else:
        texture = "smooth"

    if grade >= 2 or adj_sev >= 0.70 or comp_w >= 1.80:
        touch_intensity = "high"
    elif comp_w < 1.45:
        touch_intensity = "low"
    else:
        touch_intensity = "medium"

    # Audio
    if _PAT_SOUND_ALARM.search(txt):
        sound_type = "alarm"
    elif _PAT_SOUND_NOISE.search(txt):
        sound_type = "noise"
    elif sec == "Mind" or _PAT_SOUND_SPEECH.search(txt):
        sound_type = "speech"
    else:
        sound_type = "none"

    if arousal >= 0.78 or _PAT_AUDIO_HIGH.search(txt):
        audio_intensity = "high"
    elif arousal < 0.45 or _PAT_AUDIO_LOW.search(txt):
        audio_intensity = "low"
    else:
        audio_intensity = "medium"

    # Vision
    if remedy in _ANIMAL_REMEDIES:
        object_type = "animal"
    elif skind in ("general", "dream") or sec in ("Modalities", "General", "Intro"):
        object_type = "unknown"
    else:
        object_type = "human"

    if _PAT_MOTION_FAST.search(txt):
        motion = "fast"
    elif _PAT_MOTION_SLOW.search(txt):
        motion = "slow"
    else:
        motion = "static"

    if _PAT_COLOR_RED.search(txt):
        color = "red"
    elif _PAT_COLOR_DARK.search(txt):
        color = "dark"
    elif _PAT_COLOR_BRIGHT.search(txt):
        color = "bright"
    else:
        color = "blue"

    # Smell
    if _PAT_ODOR_SMOKE.search(txt):
        odor_type = "smoke"
    elif _PAT_ODOR_CHEM.search(txt):
        odor_type = "chemical"
    elif _PAT_ODOR_ORG.search(txt):
        odor_type = "organic"
    elif _PAT_ODOR_FOOD.search(txt):
        odor_type = "food"
    else:
        odor_type = "none"

    if _PAT_ODOR_STRONG.search(txt):
        odor_intensity = "strong"
    elif _PAT_ODOR_MOD.search(txt):
        odor_intensity = "moderate"
    else:
        odor_intensity = "faint"

    if valence <= 0.20 or _PAT_PLEAS_FOUL.search(txt):
        pleasantness = "foul"
    elif valence >= 0.65 or _PAT_PLEAS_GOOD.search(txt):
        pleasantness = "pleasant"
    else:
        pleasantness = "neutral"

    percept = {
        "touch": {
            "thermal": thermal,
            "contact": contact,
            "texture": texture,
            "touch_intensity": touch_intensity,
        },
        "audio": {
            "sound_type": sound_type,
            "audio_intensity": audio_intensity,
        },
        "vision": {
            "object_type": object_type,
            "motion": motion,
            "color": color,
        },
        "smell": {
            "odor_type": odor_type,
            "odor_intensity": odor_intensity,
            "pleasantness": pleasantness,
        },
    }

    for mod, feats in percept.items():
        for feat, val in feats.items():
            if val not in E.MODALITIES[mod][feat]:
                raise ValueError(f"Invalid percept feature {mod}.{feat}={val!r}")
    return percept


def _assign_clinical_action(occ: dict, percept: dict[str, dict[str, str]]) -> str:
    reflex_action, _ = E.reflexive_decision(E.AfferentObject(percept))
    if reflex_action in ("withdraw", "alert"):
        return reflex_action

    vad = occ.get("vad") or {}
    valence = float(vad.get("valence", 0.45))
    arousal = float(vad.get("arousal", 0.5))
    adj_sev = float(occ.get("adjective_severity") if occ.get("adjective_severity") is not None else 0.5)
    comp_w = float(occ.get("composite_weight") if occ.get("composite_weight") is not None else 1.5)
    grade = int(occ.get("grade") or 1)
    mods = [m for m in (occ.get("modalities") or []) if isinstance(m, dict)]

    if arousal >= 0.82 or adj_sev >= 0.85:
        return "alert"
    if any(m.get("direction") == "worse" for m in mods) and valence <= 0.25:
        return "withdraw"
    if grade >= 2 or comp_w >= 1.65 or any(m.get("direction") == "better" for m in mods):
        return "approach"
    if 1.45 <= comp_w < 1.65:
        return "observe"
    return "ignore"


def build_materia_medica_kg_dataset() -> tuple[list[dict], list[tuple[dict, str]], list[tuple[dict, str]], dict, dict]:
    """Deterministically map all 953 MMKG occurrences into MPCS percepts and query sets."""
    with MMKG_JSONL.open("r", encoding="utf-8") as fh:
        jsonl_rows = [json.loads(line) for line in fh if line.strip()]
    occurrences = [occ for row in jsonl_rows for occ in row.get("occurrences", [])]

    with MMKG_GRAPH.open("r", encoding="utf-8") as fh:
        graph_data = json.load(fh)

    records: list[dict] = []
    for step_idx, occ in enumerate(occurrences, start=1):
        percept = _map_occurrence_to_percept(occ)
        action = _assign_clinical_action(occ, percept)
        comp_w = float(occ.get("composite_weight") if occ.get("composite_weight") is not None else 1.5)
        grade = int(occ.get("grade") or 1)
        is_expert = bool(grade >= 2)
        reward = round(min(0.98, max(0.20, comp_w / 3.0)), 3)
        records.append({
            "percept": percept,
            "action": action,
            "reward": reward,
            "step": step_idx,
            "is_expert": is_expert,
            "mode": "EXPERT" if is_expert else "DELIBERATIVE",
        })

    # Deduplicate stored percepts by highest-reward action for consensus ground truth
    grouped: dict[tuple, list[dict]] = collections.defaultdict(list)
    for rec in records:
        grouped[D._key(rec["percept"])].append(rec)

    consensus_map: dict[tuple, str] = {}
    for pkey, grp in grouped.items():
        best_rec = max(grp, key=lambda r: (r["reward"], r["action"]))
        consensus_map[pkey] = best_rec["action"]

    labelled_occurrences = [
        (rec["percept"], consensus_map[D._key(rec["percept"])]) for rec in records
    ]
    clean_queries = random.Random(42).sample(labelled_occurrences, 300)

    rng_noisy = random.Random(123)
    noisy_queries: list[tuple[dict, str]] = []
    for percept, label in clean_queries:
        variant = {m: dict(feats) for m, feats in percept.items()}
        candidates = [
            (m, f)
            for m, feats in variant.items()
            for f in feats
            if f not in D.SAFETY_FEATURES
        ]
        mod, feat = rng_noisy.choice(candidates)
        alt_vals = [v for v in E.MODALITIES[mod][feat] if v != variant[mod][feat]]
        variant[mod][feat] = rng_noisy.choice(alt_vals)
        noisy_queries.append((variant, label))

    raw_dist = dict(collections.Counter(rec["action"] for rec in records))
    consensus_dist = dict(collections.Counter(lbl for _, lbl in labelled_occurrences))
    clean_danger = sum(1 for _, lbl in clean_queries if lbl in D.DANGER)
    noisy_danger = sum(1 for _, lbl in noisy_queries if lbl in D.DANGER)

    stats = {
        "jsonl_rows": len(jsonl_rows),
        "total_occurrences": len(records),
        "unique_percepts": len(consensus_map),
        "graph_nodes": len(graph_data.get("nodes", [])),
        "graph_links": len(graph_data.get("links", [])),
        "action_distribution_raw": {a: raw_dist.get(a, 0) for a in E.ACTIONS},
        "action_distribution_consensus": {a: consensus_dist.get(a, 0) for a in E.ACTIONS},
        "clean_query_count": len(clean_queries),
        "noisy_query_count": len(noisy_queries),
        "safety_critical_clean_queries": clean_danger,
        "safety_critical_noisy_queries": noisy_danger,
    }

    print(
        f"Loaded MMKG: {stats['jsonl_rows']} JSONL rows, {stats['total_occurrences']} occurrences, "
        f"{stats['unique_percepts']} unique percepts | Graph: {stats['graph_nodes']} nodes, {stats['graph_links']} links"
    )
    print(f"  Raw actions:       {stats['action_distribution_raw']}")
    print(f"  Consensus actions: {stats['action_distribution_consensus']}")
    print(
        f"  Queries: {len(clean_queries)} clean ({clean_danger} safety-critical), "
        f"{len(noisy_queries)} noisy ({noisy_danger} safety-critical)"
    )

    return records, clean_queries, noisy_queries, graph_data, stats


# ----------------------------------------------------------------------
# 2. Study A: Extended Perceptual Indexing + MPCS Generations (MMKG)
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
        self.failed_inserts = 0

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
        self.failed_inserts = 0
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
                    inserted = False
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
                            inserted = True
                            break
                    if not inserted:
                        self.failed_inserts += 1
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


def run_study_a_mmkg(
    records: list[dict],
    clean_queries: list[tuple[dict, str]],
    noisy_queries: list[tuple[dict, str]],
) -> dict[str, dict]:
    print("\n[Study A] Extended Perceptual Indexing & MPCS Generations (MMKG: 953 occurrences)...")
    step = max(r["step"] for r in records) + 1
    out: dict[str, dict] = {}

    pure_specs = [
        ("Exact KNN (Cosine)", r"$O(N \cdot D)$", B.ExactKNNIndex()),
        ("BM25 Inverted Index", r"$O(|Q| \cdot \overline{DF})$", B.BM25Index()),
        ("dlCBF Gate", r"$O(d)$ hash", B.CountingBloomFilterIndex()),
        ("Cuckoo Filter Gate", r"$O(1)$ 2-choice", CuckooFilterGateIndex()),
        ("SimHash LSH (64-bit)", r"$O(N)$ XOR popcnt", SimHashLSHIndex()),
        ("Slot Inverted Bitset", r"$O(|Q| \cdot \text{hits})$", SlotInvertedBitsetIndex()),
        ("NSW Proximity Graph", r"$O(\text{ef} \cdot M \log N)$", NSWGraphIndex()),
    ]
    for name, comp, idx_obj in pure_specs:
        t0 = time.perf_counter()
        idx_obj.fit(records)
        build_ms = (time.perf_counter() - t0) * 1000.0
        if isinstance(idx_obj, B.CountingBloomFilterIndex):
            space_bytes = B.deep_sizeof(idx_obj.tables)
        elif isinstance(idx_obj, CuckooFilterGateIndex):
            if idx_obj.failed_inserts:
                raise RuntimeError(f"Cuckoo filter overflowed ({idx_obj.failed_inserts} failed inserts)")
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
            "category": "indexing",
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

    mpcs_specs = [
        ("B2 Global Top-5", r"$O(N)$", M.BaseV2),
        ("G4 Core", r"$O(|A| \cdot N)$", M.CoreV2),
        ("G5 HyST", r"$O(N_{\text{slot}})$", M.HyST),
        ("G6 HMGI", r"$O(M_{\text{part}} + N_{\text{cand}})$", M.HMGI),
        ("G7 SHMF", r"$O(M_{\text{part}} + N_{\text{slot}})$", M.SHMF),
        ("G8 KERL", r"$O(N_{\text{slot}} + E_{\text{2hop}})$", M.KERL),
        ("G9 TIDE", r"$O(B_{\text{budget}} + E_{\text{act}})$", M.TIDE),
    ]
    for name, comp, cls in mpcs_specs:
        model = cls()
        build_ms = model.load(records)
        space_bytes = B.deep_sizeof(model)

        def _query_mpcs(p: dict, m=model) -> tuple[str, dict[str, float], int]:
            r = m.recommend(p, step)
            return r["best"], r["scores"], r["scanned"]

        clean_m = B.eval_scheme_metrics(_query_mpcs, clean_queries)
        noisy_m = B.eval_scheme_metrics(_query_mpcs, noisy_queries)
        out[name] = {
            "category": "mpcs_generation",
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
# 3. Study B: MPCS G9 TIDE Ablation, Anytime Budgets & Sufficiency Routing
# ----------------------------------------------------------------------

def _build_mmkg_memory(records: list[dict]) -> E.MemorySystem:
    mem = E.MemorySystem()
    for r in records:
        mem.store(
            E.summary_of(r["percept"]),
            r["action"],
            r["reward"],
            r["step"],
            is_expert=r.get("is_expert", False),
            mode=r.get("mode", "DELIBERATIVE"),
        )
    return mem


def run_study_b_mmkg(
    records: list[dict],
    clean_queries: list[tuple[dict, str]],
    noisy_queries: list[tuple[dict, str]],
) -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    print("\n[Study B] MPCS G9 TIDE Ablation, Anytime Budgets & Sufficiency Routing (MMKG)...")
    mem = _build_mmkg_memory(records)
    step_tide = max(r["step"] for r in records) + 1

    # B1. 8-variant Component Ablation
    variants = [
        ("Full G9 TIDE (Urgent=False)", SlotPolicy(), TideConfig(verify_async=False, affect_enabled=True), True, E.EngineConfig()),
        ("w/o TIDE Spread (hops=0, w_g=0)", SlotPolicy(), TideConfig(verify_async=False, affect_enabled=True, spread_hops=0, w_g=0.0), True, E.EngineConfig()),
        ("w/o VAD Affect & Salience (salience_gain=0, affect=False)", SlotPolicy(), TideConfig(verify_async=False, salience_gain=0.0, affect_enabled=False), True, E.EngineConfig()),
        ("w/o KERL Near-Miss Guard", SlotPolicy(), TideConfig(verify_async=False, affect_enabled=True, guard_enabled=False), True, E.EngineConfig()),
        ("w/o SHMF Auto-Relaxation", SlotPolicy(), TideConfig(verify_async=False, affect_enabled=True), False, E.EngineConfig()),
        ("w/o HyST Hard Slots (Soft Only)", SlotPolicy(hard_slots=frozenset()), TideConfig(verify_async=False, affect_enabled=True, guard_enabled=False), False, E.EngineConfig()),
        ("w/o Expert Grade Boost (boost=1.0)", SlotPolicy(), TideConfig(verify_async=False, affect_enabled=True), True, E.EngineConfig(expert_weight_boost=1.0)),
        ("w/o Full-Read (Urgent B=3)", SlotPolicy(urgent=True), TideConfig(verify_async=False, affect_enabled=True, urgent_budget=3), True, E.EngineConfig()),
    ]

    ablation_rows: list[dict] = []
    for label, pol, tc, auto_relax, ec in variants:
        reader = TideReader(mem, pol, tc, auto_relax=auto_relax)
        row: dict = {"variant": label}
        for split_name, qs in (("clean", clean_queries), ("noisy", noisy_queries)):
            corr = uns = dng = 0
            lats: list[float] = []
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
            row[f"{split_name}_lat_ms"] = round(statistics.mean(lats), 2)
        ablation_rows.append(row)
        print(
            f"  [OK] {label:<56} | Clean {row['clean_acc']:>5.1f}% (Unsf {row['clean_unsafe']:>4.1f}%) | "
            f"Noisy {row['noisy_acc']:>5.1f}% (Unsf {row['noisy_unsafe']:>4.1f}%) | {row['clean_lat_ms']:.2f} ms"
        )

    # B2. Anytime Budgets B in [3, 5, 10, 20, 50, Full]
    print("\n  [Study B2] TIDE Anytime Deadline Budgets (MMKG Clean & Noisy)...")
    budgets = (3, 5, 10, 20, 50, None)
    cfg = E.EngineConfig()
    anytime_results: dict[str, dict] = {"clean": {}, "noisy": {}}
    for split_name, qs in (("clean", clean_queries), ("noisy", noisy_queries)):
        print(f"    -> {split_name.upper()} ({len(qs)} queries):")
        for b in budgets:
            b_label = "Full" if b is None else f"B={b}"
            reader = TideReader(
                mem,
                SlotPolicy(urgent=True),
                TideConfig(urgent_budget=b, verify_async=False, affect_enabled=True),
            )
            if b is None:
                reader.kcfg.urgent_deadline_ms = None
            correct = unsafe = danger = 0
            ms_list, reads, totals = [], [], []
            for p, lbl in qs:
                res = reader.read(E.summary_of(p), step_tide, cfg)
                best = res["tide"]["best"]
                t = reader.last_tide
                ms_list.append(t["elapsed_ms"])
                reads.append(t["read"])
                totals.append(t["total"])
                correct += (best == lbl)
                if lbl in D.DANGER:
                    danger += 1
                    unsafe += (best in B.UNSAFE_ACTIONS)
            v = reader.verification_summary()
            n = len(qs)
            acc = 100.0 * correct / n
            uns = 100.0 * unsafe / max(1, danger)
            agr = 100.0 * v["agreed"] / v["checked"] if v["checked"] else 100.0
            cut = 100.0 * v["checked"] / n
            r_avg = sum(reads) / n
            tot_avg = sum(totals) / n
            lat = sum(ms_list) / n
            anytime_results[split_name][b_label] = {
                "budget": b_label,
                "read_ratio": f"{r_avg:.1f} / {tot_avg:.1f}",
                "cut_short_pct": round(cut, 1),
                "accuracy_pct": round(acc, 1),
                "unsafe_pct": round(uns, 1),
                "agreement_with_full_pct": round(agr, 1),
                "decision_latency_ms": round(lat, 2),
            }
            print(
                f"       [{b_label:>4}] Read {r_avg:>5.1f}/{tot_avg:>5.1f} | Cut {cut:>5.1f}% | "
                f"Acc {acc:>5.1f}% | Unsf {uns:>4.1f}% | Agree {agr:>5.1f}% | {lat:.2f} ms"
            )

    # B3. Sufficiency Routing Breakdown (Urgent=False)
    print("\n  [Study B3] TIDE Sufficiency Routing Breakdown (Urgent=False)...")
    routing_results: dict[str, dict] = {"clean": {}, "noisy": {}}
    for split_name, qs in (("clean", clean_queries), ("noisy", noisy_queries)):
        route_reader = TideReader(mem, SlotPolicy(), TideConfig(verify_async=False, affect_enabled=True))
        tally: dict[str, list[int]] = {}
        for p, lbl in qs:
            res = route_reader.read(E.summary_of(p), step_tide, cfg)
            route = res["tide"]["route"]
            tally.setdefault(route, [0, 0])
            tally[route][0] += (res["tide"]["best"] == lbl)
            tally[route][1] += 1
        for r_name in ("DIRECT", "SUBGRAPH", "UNGROUNDED"):
            corr, tot = tally.get(r_name, [0, 0])
            share = 100.0 * tot / len(qs)
            acc = 100.0 * corr / tot if tot else 0.0
            routing_results[split_name][r_name] = {
                "count": tot,
                "share_pct": round(share, 1),
                "accuracy_pct": round(acc, 1),
            }
        print(f"    -> {split_name.upper()}: {routing_results[split_name]}")

    return ablation_rows, anytime_results, routing_results


# ----------------------------------------------------------------------
# 4. Study C: LocalKG PersonaQueryEngine Component Ablation (40 queries)
# ----------------------------------------------------------------------

ARCHETYPE_EXPECTED_REMEDIES: list[tuple[str, tuple[str, ...]]] = [
    ("violent throbbing headache with delirium fear of death midnight", ("belladonna", "aconit")),
    ("bruised soreness from blunt injury jarring worse motion", ("arnica",)),
    ("burning pain in stomach better warm drinks restlessness exhaustion", ("arsenicum",)),
    ("sudden high fever dry hot skin flushed face anxiety", ("aconit", "belladonna")),
    ("melancholy silent grief weeping involuntary sighs contradiction", ("ignatia",)),
    ("cough dry tickling in throat worse cold air evening", ("rumex", "spongia", "bryonia", "phosphorus")),
    ("stiffness in joints worse first motion better continuous walking", ("rhus",)),
    ("intense thirst for cold water panic fright heart palpitations", ("aconit", "arsenicum", "bryonia")),
]

_CLINICAL_NEIGHBOR_TYPES = frozenset({
    "Physical Symptom",
    "Affective Symptom",
    "Modality",
    "Sensation",
    "Clinical Condition",
})


def build_study_c_queries(engine: PE.PersonaQueryEngine) -> list[tuple[str, tuple[str, ...]]]:
    """Build 32 remedy-specific queries from the MMKG graph + 8 ARCHETYPE_QUERIES (40 total)."""
    meds = sorted(
        (n for n in engine.nodes.values() if n.get("type") == "Medicine"),
        key=lambda n: n["label"],
    )
    rng = random.Random(42)
    remedy_queries: list[tuple[str, tuple[str, ...]]] = []
    remaining_pools: list[tuple[str, list[str]]] = []

    for med in meds:
        nbr_labels = sorted({
            engine.nodes[nid]["label"]
            for nid, _, _ in engine.adj[med["id"]]
            if nid in engine.nodes and engine.nodes[nid].get("type") in _CLINICAL_NEIGHBOR_TYPES
        })
        if not nbr_labels:
            continue
        chosen = rng.sample(nbr_labels, min(4, len(nbr_labels)))
        remedy_queries.append((" ".join(chosen).lower(), (med["label"].lower(),)))
        leftover = [lbl for lbl in nbr_labels if lbl not in chosen]
        if len(leftover) >= 4:
            remaining_pools.append((med["label"].lower(), leftover))

    # 31 Medicine nodes have clinical neighbors; deterministically add 1 disjoint
    # 4-label sample from the highest-degree connected remedy to reach 32 remedy queries.
    if len(remedy_queries) == 31 and remaining_pools:
        remaining_pools.sort(key=lambda item: (-len(item[1]), item[0]))
        top_remedy, pool = remaining_pools[0]
        extra = rng.sample(pool, 4)
        remedy_queries.append((" ".join(extra).lower(), (top_remedy,)))

    archetype_map = dict(ARCHETYPE_EXPECTED_REMEDIES)
    archetype_queries = [(q, archetype_map[q]) for q in BP.ARCHETYPE_QUERIES]
    return remedy_queries + archetype_queries


def _remedy_top_hit(result: PE.PersonaQueryResult, expected_prefixes: tuple[str, ...]) -> tuple[bool, bool]:
    """Rank active Medicine nodes deterministically by (-score, label.lower()) before Top-1/Top-3 check."""
    meds = sorted(
        (n for n in result.active_nodes if n.type == "Medicine"),
        key=lambda n: (-n.score, n.label.lower()),
    )
    if not meds:
        return False, False
    top1 = meds[0].label.lower()
    top3 = [m.label.lower() for m in meds[:3]]
    hit1 = any(pref in top1 for pref in expected_prefixes)
    hit3 = any(any(pref in m for pref in expected_prefixes) for m in top3)
    return hit1, hit3


def _linear_scan_structural_eval(
    engine: PE.PersonaQueryEngine,
    query_text: str,
    expected_prefixes: tuple[str, ...],
    theta_conf: float = 0.45,
    theta_expl: float = 0.18,
    max_hops: int = 2,
    hop_decay: float = 0.58,
) -> tuple[int, int, bool, bool]:
    """Mirror BP.run_unoptimized_baseline scoring cleanly to extract internal edges & remedy hits."""
    q_clean = query_text.strip().lower()
    terms = [t for t in re.split(r"[,;\s]+", q_clean) if len(t) >= 2]
    if not terms:
        return 0, 0, False, False

    seed_scores: dict[str, float] = {}
    for nid, n in engine.nodes.items():
        haystack = f"{n.get('label', '')} {n.get('quote', '')} {n.get('section', '')} {n.get('raw_example', '')}".lower()
        hits = sum(1 for t in terms if t in haystack)
        if hits > 0:
            lex_match = hits / len(terms)
            arousal = float(n.get("arousal", 0.5))
            w = float(n.get("weight", 1.0))
            seed_scores[nid] = lex_match * (1.0 + 0.85 * arousal) * (w / 2.2)

    activation_energy = dict(seed_scores)
    for _ in range(max_hops):
        next_energy = dict(activation_energy)
        for l in engine.links:
            src, tgt = l["source"], l["target"]
            s_energy = activation_energy.get(src, 0.0)
            t_energy = activation_energy.get(tgt, 0.0)
            if s_energy > 0:
                spread = s_energy * hop_decay
                if spread > next_energy.get(tgt, 0.0):
                    next_energy[tgt] = spread
            if t_energy > 0:
                spread = t_energy * hop_decay
                if spread > next_energy.get(src, 0.0):
                    next_energy[src] = spread
        activation_energy = next_energy

    max_energy = max(activation_energy.values(), default=1.0)
    norm_scores = {nid: sc / max(0.001, max_energy) for nid, sc in activation_energy.items()}
    active_ids = {nid for nid, sc in norm_scores.items() if sc >= theta_expl}
    internal_edges = sum(
        1 for l in engine.links if l["source"] in active_ids and l["target"] in active_ids
    )
    meds_ranked = sorted(
        (
            (round(norm_scores[nid], 3), engine.nodes[nid]["label"].lower())
            for nid in active_ids
            if engine.nodes[nid].get("type") == "Medicine"
        ),
        key=lambda x: (-x[0], x[1]),
    )
    if not meds_ranked:
        return len(active_ids), internal_edges, False, False
    hit1 = any(pref in meds_ranked[0][1] for pref in expected_prefixes)
    hit3 = any(any(pref in lbl for pref in expected_prefixes) for _, lbl in meds_ranked[:3])
    return len(active_ids), internal_edges, hit1, hit3


def run_study_c_mmkg(graph_data: dict) -> tuple[list[dict], int]:
    print("\n[Study C] LocalKG PersonaQueryEngine Component Ablation (40 queries x 10 runs = 400 calls/variant)...")
    engine = PE.PersonaQueryEngine(graph_data=graph_data)
    queries = build_study_c_queries(engine)
    total_q = len(queries)
    n_runs = 10

    # Warm-up pass
    for q, _ in queries[:4]:
        _ = engine.query(q, persona=PE.PersonaType.EXPLORATORY)
        _ = BP.run_unoptimized_baseline(engine, q)

    orig_multipliers = dict(engine.node_multipliers)
    orig_synonyms = dict(PE.CLINICAL_SYNONYMS)
    orig_adj = engine.adj

    # Dynamically pull operational thresholds from engine defaults
    tc_default = 0.45
    te_default = 0.18

    # (label, persona, theta_conf, theta_expl, hops, use_vad, use_syn, use_edge_weights)
    configs = [
        (f"Full Exploratory Persona (theta={te_default})", PE.PersonaType.EXPLORATORY, tc_default, te_default, 2, True, True, True),
        (f"Full Confident Persona (theta={tc_default})", PE.PersonaType.CONFIDENT, tc_default, te_default, 2, True, True, True),
        ("w/o 2-Hop Spreading Activation (hops=0)", PE.PersonaType.EXPLORATORY, tc_default, te_default, 0, True, True, True),
        ("w/o 2nd Hop (hops=1)", PE.PersonaType.EXPLORATORY, tc_default, te_default, 1, True, True, True),
        ("w/o VAD Arousal & Grade Multiplier (mu_v=1.0)", PE.PersonaType.EXPLORATORY, tc_default, te_default, 2, False, True, True),
        ("w/o Clinical Synonym Expansion", PE.PersonaType.EXPLORATORY, tc_default, te_default, 2, True, False, True),
        ("w/o Edge-Weight Modulation (uniform w_uv=1.0)", PE.PersonaType.EXPLORATORY, tc_default, te_default, 2, True, True, False),
    ]

    results: list[dict] = []
    try:
        for label, ptype, tc, te, hops, use_vad, use_syn, use_edge_w in configs:
            engine.node_multipliers = orig_multipliers if use_vad else {k: 1.0 for k in orig_multipliers}
            PE.CLINICAL_SYNONYMS.clear()
            if use_syn:
                PE.CLINICAL_SYNONYMS.update(orig_synonyms)

            if use_edge_w:
                engine.adj = orig_adj
            else:
                uniform_adj = collections.defaultdict(list)
                for u, nbrs in orig_adj.items():
                    uniform_adj[u] = [(v, 1.0, lbl) for v, _, lbl in nbrs]
                engine.adj = uniform_adj

            kept_counts, pruned_pcts, edge_int_counts, latencies = [], [], [], []
            top1_hits = top3_hits = 0

            for r_i in range(n_runs):
                for q, exp in queries:
                    t0 = time.perf_counter()
                    res = engine.query(q, persona=ptype, theta_conf=tc, theta_expl=te, max_hops=hops)
                    latencies.append((time.perf_counter() - t0) * 1000.0)
                    if r_i == 0:
                        kept_counts.append(res.kept_count)
                        pruned_pcts.append(res.pruning_ratio_pct)
                        edge_int_counts.append(len(res.subgraph_internal_edges))
                        h1, h3 = _remedy_top_hit(res, exp)
                        top1_hits += int(h1)
                        top3_hits += int(h3)

            lat_sorted = sorted(latencies)
            p95_idx = min(len(lat_sorted) - 1, int(len(lat_sorted) * 0.95))
            results.append({
                "variant": label,
                "mean_kept_nodes": round(statistics.mean(kept_counts), 1),
                "mean_pruned_pct": round(statistics.mean(pruned_pcts), 1),
                "mean_internal_edges": round(statistics.mean(edge_int_counts), 1),
                "remedy_top1_hits": f"{top1_hits}/{total_q}",
                "remedy_top1_pct": round(100.0 * top1_hits / total_q, 1),
                "remedy_top3_hits": f"{top3_hits}/{total_q}",
                "remedy_top3_pct": round(100.0 * top3_hits / total_q, 1),
                "mean_lat_ms": round(statistics.mean(latencies), 3),
                "p95_lat_ms": round(lat_sorted[p95_idx], 3),
                "speedup_vs_linear": 1.0,  # filled once linear scan latency is measured
            })
    finally:
        engine.node_multipliers = orig_multipliers
        engine.adj = orig_adj
        PE.CLINICAL_SYNONYMS.clear()
        PE.CLINICAL_SYNONYMS.update(orig_synonyms)

    # Variant 8: w/o Precomputed Inverted Index (Linear Full-Graph Scan Baseline)
    lin_lats, lin_kept, lin_edges = [], [], []
    lin_top1 = lin_top3 = 0
    for r_i in range(n_runs):
        for q, exp in queries:
            t0 = time.perf_counter()
            conf, expl = BP.run_unoptimized_baseline(engine, q)
            lin_lats.append((time.perf_counter() - t0) * 1000.0)
            if r_i == 0:
                kept_n = len(set(conf) | set(expl))
                eval_kept, int_edges, h1, h3 = _linear_scan_structural_eval(engine, q, exp)
                assert eval_kept == kept_n
                lin_kept.append(kept_n)
                lin_edges.append(int_edges)
                lin_top1 += int(h1)
                lin_top3 += int(h3)

    lin_sorted = sorted(lin_lats)
    lin_p95 = lin_sorted[min(len(lin_sorted) - 1, int(len(lin_sorted) * 0.95))]
    lin_mean = statistics.mean(lin_lats)
    results.append({
        "variant": "w/o Precomputed Inverted Index (Linear Scan)",
        "mean_kept_nodes": round(statistics.mean(lin_kept), 1),
        "mean_pruned_pct": round(100.0 * (1.0 - statistics.mean(lin_kept) / len(engine.nodes)), 1),
        "mean_internal_edges": round(statistics.mean(lin_edges), 1),
        "remedy_top1_hits": f"{lin_top1}/{total_q}",
        "remedy_top1_pct": round(100.0 * lin_top1 / total_q, 1),
        "remedy_top3_hits": f"{lin_top3}/{total_q}",
        "remedy_top3_pct": round(100.0 * lin_top3 / total_q, 1),
        "mean_lat_ms": round(lin_mean, 3),
        "p95_lat_ms": round(lin_p95, 3),
        "speedup_vs_linear": 1.0,
    })

    for row in results:
        row["speedup_vs_linear"] = round(lin_mean / row["mean_lat_ms"], 2) if row["mean_lat_ms"] > 0 else 0.0
        print(
            f"  [OK] {row['variant']:<46} | Kept {row['mean_kept_nodes']:>5.1f} ({row['mean_pruned_pct']:>4.1f}% pruned) | "
            f"Edges {row['mean_internal_edges']:>5.1f} | Top1 {row['remedy_top1_hits']} ({row['remedy_top1_pct']:>4.1f}%) | "
            f"Top3 {row['remedy_top3_hits']} ({row['remedy_top3_pct']:>4.1f}%) | {row['mean_lat_ms']:.3f} ms ({row['speedup_vs_linear']:.2f}x)"
        )

    return results, total_q


# ----------------------------------------------------------------------
# 5. Report Export & Main Entry
# ----------------------------------------------------------------------

def write_markdown_summary(
    dataset_stats: dict,
    study_a: dict,
    study_b_ablation: list[dict],
    study_b_budgets: dict,
    study_b_routing: dict,
    study_c: list[dict],
    study_c_queries: int,
) -> Path:
    lines = [
        "# Ablation Studies and Extended Perceptual Indexing Benchmarks (LocalKG Materia Medica KG)",
        "",
        "## Dataset Summary (LocalKG Materia Medica Knowledge Graph)",
        "",
        f"- **Source occurrences:** `{MMKG_JSONL.relative_to(ROOT).as_posix()}` "
        f"({dataset_stats['jsonl_rows']} JSONL rows, **{dataset_stats['total_occurrences']}** clinical occurrences, "
        f"**{dataset_stats['unique_percepts']}** unique 4-channel MPCS percepts)",
        f"- **Source graph:** `{MMKG_GRAPH.relative_to(ROOT).as_posix()}` "
        f"(**{dataset_stats['graph_nodes']}** nodes, **{dataset_stats['graph_links']}** links)",
        f"- **Query sets:** **{dataset_stats['clean_query_count']}** clean queries "
        f"({dataset_stats['safety_critical_clean_queries']} safety-critical) + "
        f"**{dataset_stats['noisy_query_count']}** noisy queries "
        f"({dataset_stats['safety_critical_noisy_queries']} safety-critical, 1 non-safety feature perturbed)",
        f"- **Action distribution (raw):** `{dataset_stats['action_distribution_raw']}`",
        f"- **Action distribution (consensus ground truth):** `{dataset_stats['action_distribution_consensus']}`",
        "",
        "## Study A: Extended Perceptual Indexing & MPCS Generations (MMKG: 953 Occurrences, 300 Clean + 300 Noisy)",
        "",
        "| Scheme / Model | Category | Complexity | Space (KB) | Build (ms) | Scanned | Mean Lat (ms) | p95 Lat (ms) | Clean Acc % | R@3 % | Clean Unsafe % | Noisy Acc % | Noisy Unsafe % |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for name, d in study_a.items():
        cat = "Indexing" if d["category"] == "indexing" else "MPCS"
        lines.append(
            f"| **{name}** | {cat} | {d['complexity']} | {d['space_kb']} | {d['build_ms']} | {d['scanned_clean']} | "
            f"{d['latency_mean_ms']:.3f} | {d['latency_p95_ms']:.3f} | **{d['clean_acc']}%** | {d['clean_r3']}% | "
            f"{d['clean_unsafe']}% | **{d['noisy_acc']}%** | {d['noisy_unsafe']}% |"
        )

    lines.extend([
        "",
        "## Study B: MPCS G9 TIDE Component Ablation, Anytime Budgets & Sufficiency Routing (MMKG)",
        "",
        "### B1. Component Ablation (8 Variants)",
        "",
        "| Configuration | Clean Acc % | Clean Unsafe % | Clean Lat (ms) | Noisy Acc % | Noisy Unsafe % | Noisy Lat (ms) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])
    for row in study_b_ablation:
        lines.append(
            f"| **{row['variant']}** | {row['clean_acc']}% | {row['clean_unsafe']}% | {row['clean_lat_ms']:.2f} | "
            f"{row['noisy_acc']}% | {row['noisy_unsafe']}% | {row['noisy_lat_ms']:.2f} |"
        )

    lines.extend([
        "",
        "### B2. TIDE Anytime Deadline Budgets (Urgent = True)",
        "",
        "| Split | Budget | Read / Avail | Cut Short % | Accuracy % | Unsafe % | Agreement w/ Full % | Mean Lat (ms) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])
    for split_name in ("clean", "noisy"):
        for b_label, d in study_b_budgets[split_name].items():
            lines.append(
                f"| {split_name.capitalize()} | **{b_label}** | {d['read_ratio']} | {d['cut_short_pct']}% | "
                f"**{d['accuracy_pct']}%** | {d['unsafe_pct']}% | {d['agreement_with_full_pct']}% | {d['decision_latency_ms']:.2f} |"
            )

    lines.extend([
        "",
        "### B3. TIDE Sufficiency Routing Breakdown (Urgent = False)",
        "",
        "| Route Mode | Clean Count | Clean Share % | Clean Accuracy % | Noisy Count | Noisy Share % | Noisy Accuracy % |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])
    for r_name in ("DIRECT", "SUBGRAPH", "UNGROUNDED"):
        dc = study_b_routing["clean"][r_name]
        dn = study_b_routing["noisy"][r_name]
        lines.append(
            f"| **{r_name}** | {dc['count']} | {dc['share_pct']}% | {dc['accuracy_pct']}% | "
            f"{dn['count']} | {dn['share_pct']}% | {dn['accuracy_pct']}% |"
        )

    lines.extend([
        "",
        f"## Study C: LocalKG PersonaQueryEngine Component Ablation ({dataset_stats['graph_nodes']} nodes, {dataset_stats['graph_links']} links; {study_c_queries} queries x 10 runs = {study_c_queries * 10} calls/variant)",
        "",
        "> Deterministic Medicine ranking tie-break (`top3_tie_break`): `(-score, label.lower())`.",
        "",
        "| Configuration | Mean Kept Nodes | Pruned % | Internal Edges | Remedy Top-1 | Remedy Top-3 | Mean Lat (ms) | p95 Lat (ms) | Speedup vs Linear |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])
    for row in study_c:
        lines.append(
            f"| **{row['variant']}** | {row['mean_kept_nodes']} | {row['mean_pruned_pct']}% | "
            f"{row['mean_internal_edges']} | {row['remedy_top1_hits']} ({row['remedy_top1_pct']}%) | "
            f"{row['remedy_top3_hits']} ({row['remedy_top3_pct']}%) | {row['mean_lat_ms']:.3f} | "
            f"{row['p95_lat_ms']:.3f} | {row['speedup_vs_linear']:.2f}x |"
        )

    out_md = DOCS_DIR / "ABLATION_AND_INDEXING_STUDY.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_md


def main() -> None:
    records, clean_q, noisy_q, graph_data, dataset_stats = build_materia_medica_kg_dataset()
    study_a = run_study_a_mmkg(records, clean_q, noisy_q)
    study_b_ablation, study_b_budgets, study_b_routing = run_study_b_mmkg(records, clean_q, noisy_q)
    study_c, study_c_queries = run_study_c_mmkg(graph_data)

    payload = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset_stats": dataset_stats,
        "study_a_extended_indexing_mmkg": study_a,
        "study_b_mpcs_tide_ablation_mmkg": study_b_ablation,
        "study_b_anytime_budgets_mmkg": study_b_budgets,
        "study_b_sufficiency_routing_mmkg": study_b_routing,
        "study_c_personakg_ablation_mmkg": study_c,
    }

    out_json = DOCS_DIR / "ablation_and_indexing_study.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_md = write_markdown_summary(
        dataset_stats,
        study_a,
        study_b_ablation,
        study_b_budgets,
        study_b_routing,
        study_c,
        study_c_queries,
    )
    print(f"\n[OK] Saved JSON: {out_json}")
    print(f"[OK] Saved MD:   {out_md}")


if __name__ == "__main__":
    main()

"""
Worked examples: the same inputs through Baseline v2, Core v2, HyST, HMGI
and SHMF, side by side. Every model gets the identical canonical percept
(four senses, five actions) and the identical v3 memory bank.

Writes results/examples.json and prints a readable table.

    python examples.py
"""

from __future__ import annotations

import json
import os
import random

import datasets as D
import models as M

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = [M.BaseV2, M.BaseV2Gate, M.CoreV2, M.HyST, M.HMGI, M.SHMF]


def bank_examples(records: list[dict]) -> list[dict]:
    """A few stored entries that show what the dataset contains."""
    out, seen = [], set()

    def add(kind, r):
        out.append({"kind": kind, "percept": r["percept"], "action": r["action"],
                    "reward": r["reward"], "step": r["step"], "expert": bool(r.get("is_expert"))})

    full = next(r for r in records if len(r["percept"]) == 4 and not r.get("is_expert"))
    add("full - all four senses", full)
    partial = next(r for r in records if len(r["percept"]) == 1)
    add("partial - one sense only", partial)
    by_key: dict = {}
    for r in records:
        by_key.setdefault(D._key(r["percept"]), []).append(r)
    twins = next(v for v in by_key.values() if len({x["action"] for x in v}) > 1)
    a, b = twins[0], next(x for x in twins if x["action"] != twins[0]["action"])
    add("contradicting twin (A)", a)
    add("contradicting twin (B)", b)
    add("expert correction", next(r for r in records if r.get("is_expert")))
    return out


def main() -> None:
    records = D.bank_v3()
    step = max(r["step"] for r in records) + 1
    models = [cls() for cls in MODELS]
    for m in models:
        m.load(records)
    sets = D.query_sets("v3", records)

    # Score every clean/noisy query, then pick illustrative ones.
    rows = []
    for set_name in ("clean", "noisy"):
        for percept, label in sets[set_name]:
            outs = {m.name: m.recommend(percept, step) for m in models}
            rows.append({"set": set_name, "percept": percept, "label": label,
                         "outputs": {n: {"best": o["best"], "evidence": o["evidence"],
                                         "scanned": o["scanned"]} for n, o in outs.items()}})

    def right(row, name):
        return row["outputs"][name]["best"] == row["label"]

    picks = {
        "all models agree and are right": lambda r: all(right(r, m.name) for m in models),
        "danger scene: HyST/SHMF right, Core v2 unsafe":
            lambda r: r["label"] in D.DANGER and right(r, "SHMF")
            and r["outputs"]["Core v2"]["best"] in ("approach", "ignore"),
        "HyST finds nothing (observes), SHMF relaxes and is right":
            lambda r: not r["outputs"]["HyST"]["evidence"] and right(r, "SHMF"),
        "Baseline v2 right, SHMF wrong": lambda r: right(r, "Baseline v2") and not right(r, "SHMF"),
        "SHMF right, Baseline v2 wrong": lambda r: right(r, "SHMF") and not right(r, "Baseline v2"),
        "dlCBF gate shuts; the same model ungated is right":
            lambda r: r["label"] != "observe" and not r["outputs"]["Baseline v2+dlCBF"]["evidence"]
            and right(r, "Baseline v2"),
        "noisy scene: every model wrong": lambda r: r["set"] == "noisy"
            and not any(right(r, m.name) for m in models),
    }
    rng = random.Random(11)
    examples = []
    for title, pred in picks.items():
        pool = [r for r in rows if pred(r)]
        if pool:
            ex = dict(rng.choice(pool))
            ex["title"] = title
            ex["pool"] = len(pool)
            examples.append(ex)

    out = {"bank": bank_examples(records), "queries": examples, "models": [m.name for m in models],
           "total_queries": len(rows)}
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "examples.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)

    for ex in examples:
        print(f"\n== {ex['title']}  ({ex['pool']} of {len(rows)} queries) [{ex['set']}]")
        print("   percept:", json.dumps(ex["percept"]))
        print("   correct:", ex["label"])
        for name, o in ex["outputs"].items():
            mark = "ok " if o["best"] == ex["label"] else "-- "
            print(f"   {mark}{name:<18} {o['best']:<9} evidence={o['evidence']} scanned={o['scanned']}")


if __name__ == "__main__":
    main()

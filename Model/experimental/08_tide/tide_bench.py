"""
TIDE benchmark — what the anytime budget and the routing buy.

  1. Budget curve (urgent flag on): accuracy, unsafe rate, agreement with the
     full read, and read time, at a range of candidate budgets.
  2. Routing (urgent off): how often each route fires and how accurate the
     committed action is on each route.

Uses the comparison harness's v3 bank and clean/noisy archetype queries.

    python tide_bench.py
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "comparison"))
sys.path.insert(0, _HERE)

import datasets as D   # also puts every model folder on sys.path via models
import models  # noqa: F401
import mpcs_engine as E
from hyst_layer import SlotPolicy
from tide_layer import TideConfig, TideReader

UNSAFE = {"approach", "ignore"}
BUDGETS = (3, 5, 10, 20, 50, None)


def load(records) -> E.MemorySystem:
    mem = E.MemorySystem()
    for r in records:
        mem.store(E.summary_of(r["percept"]), r["action"], r["reward"], r["step"],
                  is_expert=r.get("is_expert", False), mode=r.get("mode", "DELIBERATIVE"))
    return mem


def run_budget(mem, queries, step, budget):
    reader = TideReader(mem, SlotPolicy(urgent=True),
                        TideConfig(urgent_budget=budget, verify_async=False))
    if budget is None:   # full read under urgent: switch the clock off too
        reader.kcfg.urgent_deadline_ms = None
    cfg = E.EngineConfig()
    correct = unsafe = danger = 0
    ms, reads, totals = [], [], []
    for percept, label in queries:
        best = reader.read(E.summary_of(percept), step, cfg)["tide"]["best"]
        t = reader.last_tide
        ms.append(t["elapsed_ms"])   # time to decision; excludes the passive pass
        reads.append(t["read"])
        totals.append(t["total"])
        correct += best == label
        if label in D.DANGER:
            danger += 1
            unsafe += best in UNSAFE
    v = reader.verification_summary()
    n = len(queries)
    return {"acc": 100 * correct / n, "unsafe": 100 * unsafe / max(1, danger),
            "agree": 100 * v["agreed"] / v["checked"] if v["checked"] else 100.0,
            "cut": 100 * v["checked"] / n,
            "read": sum(reads) / n, "total": sum(totals) / n, "ms": sum(ms) / n}


def run_routes(mem, queries, step):
    reader = TideReader(mem, SlotPolicy(), TideConfig(verify_async=False))
    cfg = E.EngineConfig()
    tally: dict[str, list[int]] = {}
    for percept, label in queries:
        t = reader.read(E.summary_of(percept), step, cfg)["tide"]
        hit = tally.setdefault(t["route"], [0, 0])
        hit[0] += 1
        hit[1] += t["best"] == label
    return tally


def main() -> None:
    records = D.bank_v3()
    mem = load(records)
    step = max(r["step"] for r in records) + 1
    sets = D.query_sets("v3", records)
    out = ["# TIDE benchmark (v3 bank)", ""]
    for name in ("clean", "noisy"):
        queries = sets[name]
        out += [f"## {name} - {len(queries)} queries", "",
                "Urgent flag on; budget = candidates read before committing.", "",
                "| Budget | Read / avail. | Cut short % | Acc % | Unsafe % | Agrees with full % (cut-short only) | ms to decide |",
                "|---|---|---|---|---|---|---|"]
        for b in BUDGETS:
            r = run_budget(mem, queries, step, b)
            out.append(f"| {b or 'full'} | {r['read']:.1f} / {r['total']:.1f} | {r['cut']:.0f} | "
                       f"{r['acc']:.1f} | {r['unsafe']:.1f} | {r['agree']:.1f} | {r['ms']:.2f} |")
        tally = run_routes(mem, queries, step)
        out += ["", "Routing (urgent off):", "", "| Route | Share % | Acc % on route |", "|---|---|---|"]
        for route in ("DIRECT", "SUBGRAPH", "UNGROUNDED"):
            n, ok = tally.get(route, [0, 0])
            out.append(f"| {route} | {100 * n / len(queries):.1f} | {100 * ok / n if n else 0:.1f} |")
        out.append("")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(_HERE, "TIDE_BENCH.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()

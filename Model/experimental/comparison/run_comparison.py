"""
Run every MPCS generation against every preset bank and write the results.

    python run_comparison.py              # all banks, writes results/RESULTS.md + results.json
    python run_comparison.py --bank v1    # one bank

Metrics per (bank, query set, model):
  acc        recommendation == label
  unsafe     approach/ignore recommended where the label is alert/withdraw
             (share of danger-labelled queries)
  noEvid     no retrieved memory supported any action — the score was a prior
  gate       share of queries a membership filter let through (Bloom / dlCBF)
  express    share of labels the model's action set can even say (G1-G3 lack withdraw)
  novelty    mean novelty the model reported
  scanned    mean records the model's retrieval touched
  ms/q       wall-clock per recommendation
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import statistics
import time

from datasets import BANKS, DANGER, query_sets
from models import ALL_MODELS

HERE = os.path.dirname(os.path.abspath(__file__))
UNSAFE = {"approach", "ignore"}


def evaluate(model, queries, step):
    n = len(queries)
    correct = unsafe = danger = noev = expressible = 0
    gates, novs, scanned, times, picks = [], [], [], [], []
    for percept, label in queries:
        t0 = time.perf_counter()
        r = model.recommend(percept, step)
        times.append((time.perf_counter() - t0) * 1000.0)
        picks.append(r["best"])
        correct += r["best"] == label
        expressible += label in model.actions
        noev += not r["evidence"]
        if label in DANGER:
            danger += 1
            unsafe += r["best"] in UNSAFE
        if r["gate"] is not None:
            gates.append(r["gate"])
        novs.append(r["novelty"])
        scanned.append(r["scanned"])
    return {
        "n": n,
        "acc": 100 * correct / n,
        "unsafe": 100 * unsafe / danger if danger else None,
        "noEvid": 100 * noev / n,
        "gate": 100 * sum(gates) / len(gates) if gates else None,
        "express": 100 * expressible / n,
        "novelty": statistics.mean(novs),
        "scanned": statistics.mean(scanned),
        "ms": statistics.mean(times),
        "picks": picks,
    }


def agreement(a: list, b: list) -> float:
    return 100 * sum(x == y for x, y in zip(a, b)) / len(a)


def fmt(v, spec=".1f", empty="—"):
    return empty if v is None else format(v, spec)


def run(banks: list[str]) -> dict:
    out = {"generated": datetime.datetime.now().isoformat(timespec="seconds"), "banks": {}}
    for bank in banks:
        records = BANKS[bank]()
        step = max(r["step"] for r in records) + 10
        sets = query_sets(bank, records)
        models = [cls() for cls in ALL_MODELS]
        load_ms = {m.name: m.load(records) for m in models}
        bank_out = {"records": len(records), "load_ms": load_ms, "sets": {}}
        print(f"\n##### bank {bank}: {len(records)} records, "
              + ", ".join(f"{k}={len(v)}" for k, v in sets.items()))
        for set_name, queries in sets.items():
            rows = {m.name: evaluate(m, queries, step) for m in models}
            pairs = {
                "Basic vs Z+dlCBF": agreement(rows["Basic"]["picks"], rows["Z+dlCBF"]["picks"]),
                "Basic vs Bloom": agreement(rows["Basic"]["picks"], rows["Bloom"]["picks"]),
                "Core v2 vs HMGI": agreement(rows["Core v2"]["picks"], rows["HMGI"]["picks"]),
                "HyST vs SHMF": agreement(rows["HyST"]["picks"], rows["SHMF"]["picks"]),
                "SHMF vs KERL": agreement(rows["SHMF"]["picks"], rows["KERL"]["picks"]),
            }
            for r in rows.values():
                del r["picks"]
            bank_out["sets"][set_name] = {"n": len(queries), "models": rows, "agreement": pairs}
            print(f"\n[{bank}/{set_name}] {len(queries)} queries")
            print(f"  {'model':<9}{'acc':>7}{'unsafe':>8}{'noEvid':>8}{'gate':>7}"
                  f"{'express':>9}{'novelty':>9}{'scanned':>9}{'ms/q':>7}")
            for m in models:
                r = rows[m.name]
                print(f"  {m.name:<9}{r['acc']:>7.1f}{fmt(r['unsafe'], empty='-'):>8}{r['noEvid']:>8.1f}"
                      f"{fmt(r['gate'], empty='-'):>7}{r['express']:>9.1f}{r['novelty']:>9.3f}"
                      f"{r['scanned']:>9.1f}{r['ms']:>7.2f}")
            print("  agreement: " + ", ".join(f"{k} {v:.0f}%" for k, v in pairs.items()))
        out["banks"][bank] = bank_out
    return out


GEN = {"Basic": "G1", "Bloom": "G2", "Z+dlCBF": "G3", "Core v2": "G4",
       "HyST": "G5", "HMGI": "G6", "SHMF": "G7", "KERL": "G8"}


def write_markdown(results: dict, path: str) -> None:
    lines = ["# MPCS model comparison — raw results", "",
             f"Generated {results['generated']} by `run_comparison.py`. "
             "Do not edit by hand; see `README.md` for method and analysis.", ""]
    for bank, b in results["banks"].items():
        lines += [f"## Bank {bank} ({b['records']} records)", "",
                  "Memory build time (ms): " + ", ".join(f"{k} {v:.1f}" for k, v in b["load_ms"].items()), ""]
        for set_name, s in b["sets"].items():
            lines += [f"### {bank} / {set_name} — {s['n']} queries", "",
                      "| Gen | Model | Acc % | Unsafe % | No evidence % | Gate pass % | Expressible % "
                      "| Novelty | Scanned | ms/query |",
                      "|---|---|---|---|---|---|---|---|---|---|"]
            for name, r in s["models"].items():
                lines.append(f"| {GEN[name]} | {name} | {r['acc']:.1f} | {fmt(r['unsafe'])} | "
                             f"{r['noEvid']:.1f} | {fmt(r['gate'])} | {r['express']:.1f} | "
                             f"{r['novelty']:.3f} | {r['scanned']:.1f} | {r['ms']:.2f} |")
            lines += ["", "Decision agreement: " + "; ".join(f"{k} {v:.0f}%"
                                                              for k, v in s["agreement"].items()), ""]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--bank", choices=tuple(BANKS), action="append")
    args = parser.parse_args()
    results = run(args.bank or list(BANKS))
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "results.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    write_markdown(results, os.path.join(HERE, "results", "RESULTS.md"))
    print(f"\nWrote results/RESULTS.md and results/results.json")


if __name__ == "__main__":
    main()

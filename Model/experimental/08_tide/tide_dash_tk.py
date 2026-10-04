"""
TIDE dashboard — Tkinter desktop app
---------------------------------------
Extends the KERL dashboard (07_kerl/kerl_dash_tk.py). Every SHMF and KERL
panel is inherited; TIDE adds a third tab, "TIDE · TIME & ACTIVATION":

  * route of the current read (DIRECT / SUBGRAPH / UNGROUNDED) and the
    margin that decided it,
  * spreading-activation stats (seeds, active nodes, hops, pruned edges),
  * the anytime budget: candidates read vs. available, how many went
    passive, and the passive verification tally,
  * the activated subgraph (top nodes, voter or context) when routed to
    SUBGRAPH,
  * controls: urgent deadline (ms), place for the next percept.

Run:
    python tide_dash_tk.py
    python tide_dash_tk.py --urgent --deadline 1.0
    python tide_dash_tk.py --scratch --seed 42
"""

from __future__ import annotations

import argparse
import os
import sys
import tkinter as tk
from tkinter import ttk

_HERE = os.path.dirname(os.path.abspath(__file__))
for _d in ("02_core", "04_hyst", "05_hmgi", "06_shmf", "07_kerl"):
    sys.path.insert(0, os.path.join(_HERE, "..", _d))
sys.path.insert(0, _HERE)

import mpcs_engine as E
from mpcs_preset_v2 import PROFILE_CONFIGS
from mpcs_preset_v3 import build_preset_memory_v3
from hyst_layer import SlotPolicy
import shmf_dash_tk as S
import kerl_dash_tk as K
from tide_layer import TideConfig, TideSession

ROUTE_FG = {"DIRECT": S.ACCENT, "SUBGRAPH": K.AFFECT_FG, "UNGROUNDED": S.WARN_FG}


class TideTkUI(K.KerlTkUI):
    TITLE = "MPCS — TIDE Dashboard (Tk)"
    BRAND = "MPCS · TIDE"
    TAGLINE = "Time-bounded Inference over Dynamic Episodes"

    def _build_graph(self, parent) -> None:
        super()._build_graph(parent)
        notebook = parent.winfo_children()[-1]
        tab = ttk.Frame(notebook, style="Panel.TFrame")
        notebook.add(tab, text="TIDE · TIME & ACTIVATION")
        self._build_tide_tab(tab)
        notebook.select(tab)

    def _build_tide_tab(self, tab) -> None:
        top = ttk.Frame(tab, style="Panel.TFrame")
        top.pack(fill="x", padx=8, pady=(8, 4))
        self.route_label = ttk.Label(top, text="—", style="Panel.TLabel", font=("Segoe UI", 14, "bold"))
        self.route_label.pack(side="left")
        self.route_note = ttk.Label(top, text="", style="Muted.TLabel", font=("Consolas", 8))
        self.route_note.pack(side="left", padx=10)

        ttk.Label(tab, text="ACTIVATION · ANYTIME BUDGET · PASSIVE CHECK",
                  style="Head.TLabel").pack(anchor="w", padx=8)
        self.tide_stats = ttk.Label(tab, text="", style="Panel.TLabel", font=("Consolas", 8), justify="left")
        self.tide_stats.pack(anchor="w", padx=8, pady=(2, 6))

        ttk.Label(tab, text="ACTIVATED SUBGRAPH (top nodes)", style="Head.TLabel").pack(anchor="w", padx=8)
        self.subgraph_text = tk.Text(tab, height=9, bg=S.FIELD, fg=S.TEXT, relief="flat",
                                     font=("Consolas", 8), wrap="none")
        self.subgraph_text.pack(fill="both", expand=True, padx=8, pady=(2, 6))

        controls = ttk.Frame(tab, style="Panel.TFrame")
        controls.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(controls, text="Urgent deadline ms", style="Panel.TLabel").pack(side="left")
        self.deadline_var = tk.StringVar(value=str(self.session.kcfg.urgent_deadline_ms))
        entry = ttk.Entry(controls, textvariable=self.deadline_var, width=6)
        entry.pack(side="left", padx=(4, 12))
        entry.bind("<Return>", lambda _e: self._on_deadline())
        ttk.Label(controls, text="Place", style="Panel.TLabel").pack(side="left")
        self.place_var = tk.StringVar(value="")
        ttk.Entry(controls, textvariable=self.place_var, width=18).pack(side="left", padx=4)
        ttk.Label(controls, text="e.g. kitchen/stove", style="Muted.TLabel").pack(side="left")

    def _on_deadline(self) -> None:
        try:
            value = float(self.deadline_var.get())
        except ValueError:
            return
        self.session.kcfg.urgent_deadline_ms = value
        self._refresh(f"Urgent deadline set to {value:g} ms.")

    # Place travels with the percept; the engine ignores the extra modality.
    def _collect_percepts(self):
        percepts = super()._collect_percepts()
        place = self.place_var.get().strip() if hasattr(self, "place_var") else ""
        if place:
            percepts["where"] = {"place": place}
        return percepts

    def _refresh(self, message: str) -> None:
        super()._refresh(message)
        if hasattr(self, "route_label"):
            self._render_tide(self.session.last_result)

    def _render_tide(self, result) -> None:
        v = self.session.reader.verification_summary()
        if result is None or "tide" not in result:
            self.route_label.config(text="—")
            self.tide_stats.config(text=f"passive checks  {v['checked']} ({v['agreed']} agreed)")
            self.subgraph_text.delete("1.0", "end")
            return
        t = result["tide"]
        self.route_label.config(text=t["route"], foreground=ROUTE_FG.get(t["route"], S.TEXT))
        self.route_note.config(text=f"best {t['best']}  margin {t['margin']:.2f}"
                                    f"{'  place ' + t['query_place'] if t['query_place'] else ''}")
        a = t["activation"]
        budget = (f"{t['budget']} {t['budget_kind']}" if t["budget_kind"] else "none (not urgent)")
        check = self.session.memory.records[-1].get("passive_check")
        self.tide_stats.config(text="\n".join([
            f"activation  seeds {a['seeds']}  active {a['active']}  hops {a['hops']}  "
            f"pruned edges {a['pruned_edges']}  pruned nodes {a['pruned_nodes']}",
            f"budget      {budget}   read {t['read']}/{t['total']}   passive {t['passive']}   "
            f"decided in {t['elapsed_ms']:.2f} ms",
            f"this step   " + ("no passive work" if not t["passive"] else
                               "verifying…" if check is None else
                               f"full read -> {check['full_best']} "
                               f"({'agrees' if check['agreed'] else 'DISAGREES'})"),
            f"all steps   {v['checked']} checked, {v['agreed']} agreed, {v['disagreed']} disagreed",
        ]))
        self.subgraph_text.delete("1.0", "end")
        sg = t["subgraph"]
        if not sg:
            self.subgraph_text.insert("end", "Direct route: no subgraph returned.")
            return
        lines = [f"{'step':>5}  {'action':<9} {'reward':>6}  {'act.':>5}  role     place"]
        for n in sg["nodes"][:25]:
            lines.append(f"{n['step']:>5}  {n['action']:<9} {n['reward']:>6.2f}  {n['activation']:>5.2f}  "
                         f"{'voter' if n['voter'] else 'context':<8} {n['place'] or ''}")
        lines.append(f"\n{len(sg['nodes'])} nodes, {len(sg['edges'])} edges")
        self.subgraph_text.insert("end", "\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="MPCS TIDE dashboard (Tkinter).")
    parser.add_argument("--scratch", action="store_true")
    parser.add_argument("--profile", choices=tuple(PROFILE_CONFIGS), default="balanced")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--affect", action="store_true")
    parser.add_argument("--divergent", action="store_true")
    parser.add_argument("--urgent", action="store_true")
    parser.add_argument("--deadline", type=float, default=2.0, help="Urgent deadline in ms.")
    args = parser.parse_args()

    session = TideSession(profile=args.profile, seed=args.seed,
                          policy=SlotPolicy(divergent=args.divergent, urgent=args.urgent),
                          kcfg=TideConfig(affect_enabled=args.affect, urgent_deadline_ms=args.deadline))
    memory = E.MemorySystem() if args.scratch else build_preset_memory_v3(args.profile)
    session.reset(memory=memory, profile=args.profile, seed=args.seed)
    session.apply_profile(args.profile)

    root = tk.Tk()
    TideTkUI(root, session)
    root.mainloop()


if __name__ == "__main__":
    main()

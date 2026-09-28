"""
KERL dashboard — Tkinter desktop app
---------------------------------------
Extends the SHMF dashboard (06_shmf/shmf_dash_tk.py) rather than copying
it: every SHMF panel — funnel, hard/soft slots, divergent/urgent switches,
episode graph — is inherited unchanged. KERL adds one tab next to the
episode graph, "KERL READING":

  * affect plane — valence (x) against arousal (y) for the retrieved
    situation (HEAD-E, filled dot), the raw percept (ring), and a trail of
    recent steps,
  * HEAD-X explanation for the current step,
  * grounding, near-miss guard rejections, prediction error, fusion weights,
  * switches for the affect flag and the near-miss guard, and a Calibrate
    button that re-tunes the fusion weights on the collected near-miss pairs.

Run:
    python kerl_dash_tk.py
    python kerl_dash_tk.py --affect          start with HEAD-E influencing decisions
    python kerl_dash_tk.py --scratch --seed 42
"""

from __future__ import annotations

import argparse
import os
import sys
import tkinter as tk
from tkinter import ttk

_HERE = os.path.dirname(os.path.abspath(__file__))
for _d in ("02_core", "04_hyst", "05_hmgi", "06_shmf"):
    sys.path.insert(0, os.path.join(_HERE, "..", _d))
sys.path.insert(0, _HERE)

import mpcs_engine as E
from mpcs_preset_v2 import PROFILE_CONFIGS
from mpcs_preset_v3 import build_preset_memory_v3
from hyst_layer import SlotPolicy
import shmf_dash_tk as S
from kerl_layer import KerlConfig, KerlSession

AFFECT_FG = "#c792ea"


class KerlTkUI(S.ShmfTkUI):
    TITLE = "MPCS — KERL Dashboard (Tk)"
    BRAND = "MPCS · KERL"
    TAGLINE = "Affect-aware constrained selection over SHMF"

    def _style(self) -> None:
        super()._style()
        style = ttk.Style()
        style.configure("TNotebook", background=S.PANEL, borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure("TNotebook.Tab", background=S.FIELD, foreground=S.MUTED,
                        padding=(10, 4), font=("Segoe UI", 8, "bold"), borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", S.PANEL), ("active", S.FIELD_HOVER)],
                  foreground=[("selected", S.ACCENT), ("active", S.TEXT)])
        style.configure("Affect.TCheckbutton", background=S.PANEL, foreground=AFFECT_FG,
                        indicatorcolor=S.FIELD, focuscolor=S.PANEL,
                        font=("Segoe UI", 9, "bold"), padding=2)
        style.map("Affect.TCheckbutton", background=[("active", S.PANEL)],
                  indicatorcolor=[("selected", AFFECT_FG), ("!selected", S.FIELD)])

    # -- layout: episode graph and KERL reading share one tabbed panel -----
    def _build_graph(self, parent) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(side="left", fill="both", expand=True)

        graph_tab = ttk.Frame(notebook, style="Panel.TFrame")
        notebook.add(graph_tab, text="EPISODE GRAPH")
        self._fill_episode_graph(graph_tab)

        kerl_tab = ttk.Frame(notebook, style="Panel.TFrame")
        notebook.add(kerl_tab, text="KERL READING")
        self._build_kerl_tab(kerl_tab)
        notebook.select(kerl_tab)

    def _build_kerl_tab(self, tab) -> None:
        left = ttk.Frame(tab, style="Panel.TFrame")
        left.pack(side="left", fill="y", padx=8, pady=8)
        ttk.Label(left, text="HEAD-E · AFFECT PLANE", style="Head.TLabel").pack(anchor="w")
        self.affect_canvas = tk.Canvas(left, bg=S.PANEL, highlightthickness=0, width=250, height=230)
        self.affect_canvas.pack(pady=(4, 0))
        ttk.Label(left, text="● retrieved   ○ percept   · recent steps",
                  style="Muted.TLabel").pack(anchor="w")

        right = ttk.Frame(tab, style="Panel.TFrame")
        right.pack(side="left", fill="both", expand=True, padx=(4, 8), pady=8)

        ttk.Label(right, text="HEAD-X · EXPLANATION", style="Head.TLabel").pack(anchor="w")
        self.explain_label = ttk.Label(right, text="", style="Panel.TLabel", wraplength=420,
                                       justify="left", font=("Segoe UI", 9))
        self.explain_label.pack(anchor="w", pady=(2, 10))

        ttk.Label(right, text="GROUNDING · GUARD · FUSION", style="Head.TLabel").pack(anchor="w")
        self.kerl_stats = ttk.Label(right, text="", style="Panel.TLabel",
                                    font=("Consolas", 8), justify="left")
        self.kerl_stats.pack(anchor="w", pady=(2, 8))

        controls = ttk.Frame(right, style="Panel.TFrame")
        controls.pack(anchor="w", fill="x")
        self.affect_var = tk.BooleanVar(value=self.session.kcfg.affect_enabled)
        ttk.Checkbutton(controls, text="Affect influences decisions (HEAD-E)",
                        variable=self.affect_var, style="Affect.TCheckbutton",
                        command=self._on_affect).pack(anchor="w")
        self.guard_var = tk.BooleanVar(value=self.session.kcfg.guard_enabled)
        ttk.Checkbutton(controls, text="Near-miss guard",
                        variable=self.guard_var, command=self._on_guard).pack(anchor="w")
        row = ttk.Frame(controls, style="Panel.TFrame")
        row.pack(anchor="w", pady=(6, 0))
        ttk.Button(row, text="Calibrate weights", command=self._on_calibrate).pack(side="left")
        self.calib_label = ttk.Label(row, text="", style="Muted.TLabel", font=("Consolas", 8))
        self.calib_label.pack(side="left", padx=8)

    # -- controls -----------------------------------------------------------
    def _on_affect(self) -> None:
        self.session.kcfg.affect_enabled = self.affect_var.get()
        self._refresh("Affect (HEAD-E) now " + ("influences retrieval and exploration."
                                                if self.session.kcfg.affect_enabled
                                                else "logged only, no influence."))

    def _on_guard(self) -> None:
        self.session.kcfg.guard_enabled = self.guard_var.get()
        self._refresh(f"Near-miss guard {'on' if self.session.kcfg.guard_enabled else 'off'}.")

    def _on_calibrate(self) -> None:
        report = self.session.calibrate()
        verdict = "accepted" if report.get("accepted") else "kept previous weights"
        self._refresh(f"Calibrated on {report['pairs']} near-miss pairs: violations "
                      f"{report['violated_before']} -> {report['violated_after']} ({verdict}).")

    # -- rendering ------------------------------------------------------------
    def _refresh(self, message: str) -> None:
        super()._refresh(message)
        result = self.session.last_result
        if result is not None and result["policy"] == "UNGROUNDED":
            self.note_label.config(text="Ungrounded — no admissible memory may justify an action; "
                                        "fell back to observe.", foreground=S.WARN_FG)
        self._render_kerl(result)

    def _render_kerl(self, result) -> None:
        kcfg = self.session.kcfg
        w = kcfg.weights()
        calib = self.session.reader.last_calibration
        self.calib_label.config(text=(f"last: {calib['violated_before']}→{calib['violated_after']} "
                                      f"on {calib['pairs']} pairs") if calib else "not run yet")
        if result is None:
            self.explain_label.config(text="No step run yet.")
            self.kerl_stats.config(text=f"weights  s={w['w_s']:.2f}  e={w['w_e']:.2f}  g={w['w_g']:.2f}")
            self._draw_affect(None)
            return
        k = result["kerl"]
        self.explain_label.config(text=k["explanation"])
        err = k["prediction_error"]
        self.kerl_stats.config(text="\n".join([
            f"grounded     {'yes' if k['grounded'] else 'NO'}   admissible {k['admissible']}"
            f"{'   (relaxed)' if result['pipeline']['relaxed'] else ''}",
            f"near-misses  {len(k['near_misses'])} rejected"
            + (f"  steps {k['near_misses'][:6]}" if k["near_misses"] else ""),
            f"prediction   {S.fmt(k['predicted'])}  error {'—' if err is None else f'{err:+.3f}'}",
            f"weights      s={w['w_s']:.2f}  e={w['w_e']:.2f}  g={w['w_g']:.2f}"
            f"   pairs {k['calibration_pairs']}",
        ]))
        self._draw_affect(result)

    def _draw_affect(self, result) -> None:
        c = self.affect_canvas
        c.delete("all")
        W, H, pad = 250, 230, 22

        def xy(v, a):
            return pad + (v + 1) / 2 * (W - 2 * pad), H - pad - a * (H - 2 * pad)

        c.create_rectangle(pad, pad, W - pad, H - pad, outline=S.LINE)
        mx, _ = xy(0, 0)
        _, my = xy(0, 0.5)
        c.create_line(mx, pad, mx, H - pad, fill=S.LINE, dash=(2, 3))
        c.create_line(pad, my, W - pad, my, fill=S.LINE, dash=(2, 3))
        for text, (v, a) in (("threat", (-0.55, 0.93)), ("excited", (0.55, 0.93)),
                             ("gloomy", (-0.55, 0.07)), ("calm", (0.55, 0.07))):
            x, y = xy(v, a)
            c.create_text(x, y, text=text, fill=S.MUTED, font=("Segoe UI", 7))
        c.create_text(W / 2, H - 8, text="valence  −1 … +1", fill=S.MUTED, font=("Segoe UI", 7))
        c.create_text(9, H / 2, text="arousal", fill=S.MUTED, font=("Segoe UI", 7), angle=90)

        for entry in self.session.history[-20:-1]:
            x, y = xy(entry["valence"], entry["arousal"])
            c.create_oval(x - 2, y - 2, x + 2, y + 2, fill=S.DISABLED, outline="")
        if result is None:
            return
        aff = result["kerl"]["affect"]
        qx, qy = xy(aff["query_valence"], aff["query_arousal"])
        c.create_oval(qx - 7, qy - 7, qx + 7, qy + 7, outline=S.TEXT, width=1.5)
        rx, ry = xy(aff["valence"], aff["arousal"])
        c.create_oval(rx - 6, ry - 6, rx + 6, ry + 6, fill=AFFECT_FG, outline="")


def main() -> None:
    parser = argparse.ArgumentParser(description="MPCS KERL dashboard (Tkinter).")
    parser.add_argument("--scratch", action="store_true",
                        help="Start with empty memory instead of the preset bank.")
    parser.add_argument("--profile", choices=tuple(PROFILE_CONFIGS), default="balanced")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--affect", action="store_true",
                        help="Let HEAD-E influence retrieval and exploration from the start.")
    parser.add_argument("--divergent", action="store_true")
    parser.add_argument("--urgent", action="store_true")
    args = parser.parse_args()

    session = KerlSession(profile=args.profile, seed=args.seed,
                          policy=SlotPolicy(divergent=args.divergent, urgent=args.urgent),
                          kcfg=KerlConfig(affect_enabled=args.affect))
    memory = E.MemorySystem() if args.scratch else build_preset_memory_v3(args.profile)
    session.reset(memory=memory, profile=args.profile, seed=args.seed)
    session.apply_profile(args.profile)

    root = tk.Tk()
    KerlTkUI(root, session)
    root.mainloop()


if __name__ == "__main__":
    main()

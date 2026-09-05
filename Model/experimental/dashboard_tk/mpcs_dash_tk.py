"""
MPCS v2 dashboard — Variant D: Tkinter desktop app
---------------------------------------------------
The same cognition as the other dashboards (the shared engine in ../core),
in a native desktop window. Needs nothing beyond the standard library, and
unlike the web variants it starts instantly with no server and no browser.

This supersedes the old baseline_z Tk UI: four modalities instead of two,
reward derived from memory instead of random, and — the part the old window
could not do at all — a contribution graph drawn on a Canvas showing which
memories produced each decision.

Run:
    python mcps_dash_tk.py
    python mcps_dash_tk.py --scratch     start with empty memory
    python mcps_dash_tk.py --profile cautious --seed 42
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tkinter as tk
from tkinter import filedialog, ttk

# The engine lives in ../core; add it to the path so this runs from anywhere.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))

import mcps_engine as E
from mcps_preset_v2 import PROFILE_CONFIGS, build_preset_memory


# Dark palette matching the web dashboards, so screenshots sit side by side.
BG, PANEL, LINE = "#10131a", "#171b24", "#3d465c"
TEXT, MUTED, ACCENT = "#e6e9ef", "#8b94a7", "#4c8dff"
# Raised surfaces: input fields sit lighter than their panel so the eye can
# find them without needing a border.
FIELD, FIELD_HOVER, SELECT = "#222839", "#2b3247", "#31527f"
DISABLED = "#7a8397"
# Primary-button fill: deeper than ACCENT so white text clears 4.5:1 on it.
GO = "#2f5fb0"
# Status text. Lighter than the equivalent node fills, because text needs more
# contrast than a filled shape does: the graph's #d1483f withdraw red only
# reaches 3.9:1 as text on the panel, which is under the 4.5:1 body-text bar.
OK_FG, WARN_FG = "#4ecf95", "#ff7b70"

PARAM_SPEC = [
    ("top_k",              "Top-k memories",      1,    20,   1),
    ("time_decay",         "Time decay base",     0.80, 1.00, 0.005),
    ("reward_variance",    "Reward variance",     0.00, 0.30, 0.01),
    ("penalty_strength",   "Penalty strength",    0.00, 2.00, 0.05),
    ("support_saturation", "Support saturation",  0.25, 6.00, 0.25),
    ("risk_bias",          "Risk bias (explore)", 0.00, 1.00, 0.01),
    ("action_threshold",   "Action threshold",    0.00, 1.00, 0.01),
    ("learning_rate",      "Learning rate",       0.00, 0.20, 0.005),
    ("expert_weight_boost", "Expert boost",       1.00, 6.00, 0.25),
    ("reflex_memory_boost", "Reflex memory boost", 1.00, 6.00, 0.25),
]


def fmt(value) -> str:
    return "—" if value is None else f"{value:.3f}"


def _relative_luminance(colour: str) -> float:
    colour = colour.lstrip("#")
    channels = [int(colour[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def ink_for(background: str) -> str:
    """Pick black or white text for a filled shape, whichever reads better.

    The action palette spans a wide lightness range — white on the alert
    orange is only 2.6:1, while white on the observe blue is fine. Choosing
    per colour keeps every node label legible instead of assuming white.
    """
    return "#0d1017" if _relative_luminance(background) > 0.35 else "#ffffff"


class CognitiveTkUI:
    def __init__(self, root: tk.Tk, session: E.Session):
        self.root = root
        self.session = session
        self.root.title("MPCS v2 — Cognitive Dashboard (Tk)")
        self.root.configure(bg=BG)
        self.root.minsize(1180, 760)

        self._feature_vars: dict[str, tk.StringVar] = {}
        self._modality_vars: dict[str, tk.BooleanVar] = {}
        self._param_vars: dict[str, tk.DoubleVar] = {}
        self._param_labels: dict[str, ttk.Label] = {}

        self._style()
        self._build()
        self._refresh(f"Loaded {len(self.session.memory)} experiences.")

    # -- styling ---------------------------------------------------------
    def _style(self) -> None:
        """Apply a dark theme.

        The subtlety here is that ttk's built-in themes carry *state maps*
        that override whatever you pass to configure(). clam, for instance,
        maps a readonly Combobox to a light grey field while leaving the
        foreground near-white — light text on a light field, invisible. Every
        widget that has such a map therefore needs an explicit map() call, not
        just configure(). The same applies to the Checkbutton indicator and to
        the Listbox that a Combobox pops up, which is a classic tk widget and
        ignores ttk styling entirely (handled via option_add below).
        """
        style = ttk.Style()
        try:
            style.theme_use("clam")   # the only built-in theme that honours
        except tk.TclError:           # background on most widgets
            pass

        style.configure(".", background=BG, foreground=TEXT,
                        fieldbackground=FIELD, bordercolor=LINE,
                        darkcolor=PANEL, lightcolor=PANEL,
                        troughcolor=BG, focuscolor=ACCENT, borderwidth=0)

        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)

        style.configure("TLabel", background=BG, foreground=TEXT,
                        font=("Segoe UI", 9))
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED,
                        font=("Segoe UI", 8))
        style.configure("Head.TLabel", background=PANEL, foreground=ACCENT,
                        font=("Segoe UI", 8, "bold"))
        style.configure("Action.TLabel", background=PANEL, foreground=TEXT,
                        font=("Segoe UI", 15, "bold"))

        style.configure("TLabelframe", background=PANEL, bordercolor=LINE,
                        borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background=PANEL, foreground=ACCENT,
                        font=("Segoe UI", 8, "bold"))

        # -- entries and comboboxes: the light-on-light offenders
        style.configure("TEntry", fieldbackground=FIELD, foreground=TEXT,
                        insertcolor=TEXT, bordercolor=LINE, borderwidth=1,
                        padding=4)
        style.map("TEntry",
                  fieldbackground=[("focus", FIELD_HOVER), ("!focus", FIELD)],
                  foreground=[("disabled", DISABLED), ("!disabled", TEXT)],
                  bordercolor=[("focus", ACCENT), ("!focus", LINE)])

        style.configure("TCombobox", fieldbackground=FIELD, background=FIELD,
                        foreground=TEXT, arrowcolor=TEXT, bordercolor=LINE,
                        borderwidth=1, padding=4)
        style.map(
            "TCombobox",
            # Without the explicit readonly entries here, clam paints #dcdad5.
            fieldbackground=[("readonly", "focus", FIELD_HOVER),
                             ("readonly", FIELD),
                             ("disabled", PANEL),
                             ("!disabled", FIELD)],
            background=[("readonly", FIELD), ("active", FIELD_HOVER),
                        ("!disabled", FIELD)],
            foreground=[("disabled", DISABLED),
                        ("readonly", "focus", "#ffffff"),
                        ("!disabled", TEXT)],
            arrowcolor=[("disabled", DISABLED), ("!disabled", ACCENT)],
            bordercolor=[("focus", ACCENT), ("!focus", LINE)],
            selectbackground=[("readonly", FIELD), ("!focus", FIELD)],
            selectforeground=[("readonly", TEXT), ("!focus", TEXT)],
        )

        # -- checkbuttons: the indicator square needs its own map or it stays
        # white-on-white and you cannot tell checked from unchecked
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT,
                        indicatorcolor=FIELD, focuscolor=PANEL,
                        font=("Segoe UI", 9, "bold"), padding=2)
        style.map("TCheckbutton",
                  background=[("active", PANEL)],
                  foreground=[("disabled", DISABLED), ("!disabled", TEXT)],
                  indicatorcolor=[("selected", ACCENT),
                                  ("pressed", FIELD_HOVER),
                                  ("!selected", FIELD)])

        # -- buttons
        style.configure("TButton", background=FIELD, foreground=TEXT,
                        bordercolor=LINE, borderwidth=1, focusthickness=0,
                        font=("Segoe UI", 9), padding=5, relief="flat")
        style.map("TButton",
                  background=[("pressed", SELECT), ("active", FIELD_HOVER),
                              ("!disabled", FIELD)],
                  foreground=[("disabled", DISABLED), ("!disabled", TEXT)],
                  bordercolor=[("active", ACCENT), ("!active", LINE)])

        # A deeper blue than ACCENT so white sits on it at ~5:1 rather than
        # the 3.2:1 the lighter accent gives.
        style.configure("Go.TButton", background=GO, foreground="#ffffff",
                        bordercolor=GO, font=("Segoe UI", 9, "bold"))
        style.map("Go.TButton",
                  background=[("pressed", "#24457c"), ("active", ACCENT),
                              ("!disabled", GO)],
                  foreground=[("!disabled", "#ffffff")],
                  bordercolor=[("!disabled", GO)])

        # -- sliders
        style.configure("TScale", background=PANEL, troughcolor=BG,
                        bordercolor=LINE, lightcolor=ACCENT, darkcolor=ACCENT)
        style.map("TScale", background=[("active", PANEL)])

        style.configure("Vertical.TScrollbar", background=FIELD,
                        troughcolor=BG, bordercolor=BG, arrowcolor=MUTED)
        style.map("Vertical.TScrollbar",
                  background=[("active", FIELD_HOVER), ("!active", FIELD)])

        # -- tables
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL,
                        foreground=TEXT, bordercolor=LINE, borderwidth=0,
                        rowheight=20, font=("Consolas", 8))
        style.map("Treeview",
                  background=[("selected", SELECT)],
                  foreground=[("selected", "#ffffff")])
        style.configure("Treeview.Heading", background=FIELD, foreground=ACCENT,
                        bordercolor=LINE, relief="flat",
                        font=("Segoe UI", 8, "bold"), padding=3)
        style.map("Treeview.Heading",
                  background=[("active", FIELD_HOVER), ("!active", FIELD)])

        # -- the Combobox dropdown is a classic tk Listbox, not a ttk widget,
        # so ttk styling never reaches it. These options do.
        self.root.option_add("*TCombobox*Listbox.background", FIELD)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.root.option_add("*TCombobox*Listbox.font", "{Segoe UI} 9")
        self.root.option_add("*TCombobox*Listbox.borderWidth", 0)

    # -- layout ----------------------------------------------------------
    def _build(self) -> None:
        outer = ttk.Frame(self.root)
        outer.pack(fill="both", expand=True)

        self._build_sidebar(outer)

        main = ttk.Frame(outer)
        main.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self._build_inputs(main)

        middle = ttk.Frame(main)
        middle.pack(fill="both", expand=True, pady=(10, 0))
        self._build_decision(middle)
        self._build_graph(middle)

        self._build_tables(main)

    def _build_sidebar(self, parent) -> None:
        bar = ttk.Frame(parent, style="Panel.TFrame", width=270)
        bar.pack(side="left", fill="y")
        bar.pack_propagate(False)

        ttk.Label(bar, text="MPCS v2", style="Panel.TLabel",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=12, pady=(12, 0))
        ttk.Label(bar, text="Multimodal cognitive simulator",
                  style="Muted.TLabel").pack(anchor="w", padx=12, pady=(0, 8))

        # -- memory source
        ttk.Label(bar, text="MEMORY SOURCE", style="Head.TLabel").pack(
            anchor="w", padx=12, pady=(8, 4))
        self.source_var = tk.StringVar(value="preset")
        ttk.Combobox(bar, textvariable=self.source_var, state="readonly", width=26,
                     values=("preset", "scratch")).pack(padx=12, fill="x")
        self.profile_var = tk.StringVar(value=self.session.profile)
        ttk.Label(bar, text="Profile", style="Muted.TLabel").pack(anchor="w", padx=12,
                                                                 pady=(6, 2))
        ttk.Combobox(bar, textvariable=self.profile_var, state="readonly", width=26,
                     values=tuple(PROFILE_CONFIGS)).pack(padx=12, fill="x")
        ttk.Label(bar, text="Seed (blank = random)", style="Muted.TLabel").pack(
            anchor="w", padx=12, pady=(6, 2))
        self.seed_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.seed_var).pack(padx=12, fill="x")

        row = ttk.Frame(bar, style="Panel.TFrame")
        row.pack(fill="x", padx=12, pady=8)
        ttk.Button(row, text="Load", command=self._load_memory).pack(side="left")
        ttk.Button(row, text="Export", command=self._export).pack(side="left", padx=4)
        ttk.Button(row, text="Import", command=self._import).pack(side="left")

        # -- parameters, scrollable because ten sliders do not fit
        ttk.Label(bar, text="PARAMETERS", style="Head.TLabel").pack(
            anchor="w", padx=12, pady=(8, 4))
        canvas = tk.Canvas(bar, bg=PANEL, highlightthickness=0, height=290)
        canvas.pack(fill="both", expand=True, padx=(12, 0))
        holder = ttk.Frame(canvas, style="Panel.TFrame")
        canvas.create_window((0, 0), window=holder, anchor="nw", width=232)
        holder.bind("<Configure>",
                    lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        for key, label, low, high, step in PARAM_SPEC:
            line = ttk.Frame(holder, style="Panel.TFrame")
            line.pack(fill="x", pady=(4, 0))
            ttk.Label(line, text=label, style="Muted.TLabel").pack(side="left")
            value_label = ttk.Label(line, text="", style="Panel.TLabel",
                                    font=("Consolas", 8))
            value_label.pack(side="right")
            self._param_labels[key] = value_label

            var = tk.DoubleVar(value=getattr(self.session.cfg, key))
            self._param_vars[key] = var
            ttk.Scale(holder, from_=low, to=high, variable=var, orient="horizontal",
                      command=lambda _v, k=key: self._on_param(k)).pack(fill="x")
            self._on_param(key)

        # -- reward and teaching
        ttk.Label(bar, text="REWARD & TEACHING", style="Head.TLabel").pack(
            anchor="w", padx=12, pady=(10, 4))
        ttk.Label(bar, text="Manual reward (blank = from memory)",
                  style="Muted.TLabel").pack(anchor="w", padx=12)
        self.reward_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.reward_var).pack(padx=12, fill="x", pady=2)

        row = ttk.Frame(bar, style="Panel.TFrame")
        row.pack(fill="x", padx=12, pady=4)
        ttk.Button(row, text="Apply to last",
                   command=self._apply_reward).pack(side="left")
        self.expert_var = tk.StringVar(value=E.ACTIONS[0])
        ttk.Combobox(row, textvariable=self.expert_var, state="readonly", width=10,
                     values=tuple(E.ACTIONS)).pack(side="left", padx=4)
        ttk.Button(bar, text="Teach expert",
                   command=self._teach).pack(padx=12, fill="x")

        self.message = ttk.Label(bar, text="", style="Panel.TLabel",
                                 foreground=ACCENT, wraplength=240,
                                 font=("Segoe UI", 8))
        self.message.pack(anchor="w", padx=12, pady=8)

    def _build_inputs(self, parent) -> None:
        box = ttk.LabelFrame(parent, text="SENSORY INPUT — untick a modality to "
                                          "remove that channel entirely")
        box.pack(fill="x")

        grid = ttk.Frame(box, style="Panel.TFrame")
        grid.pack(fill="x", padx=8, pady=8)

        for column, modality in enumerate(E.MODALITY_ORDER):
            cell = ttk.Frame(grid, style="Panel.TFrame")
            cell.grid(row=0, column=column, sticky="nsew", padx=5)
            grid.columnconfigure(column, weight=1)

            enabled = tk.BooleanVar(value=True)
            self._modality_vars[modality] = enabled
            head = ttk.Frame(cell, style="Panel.TFrame")
            head.pack(fill="x")
            ttk.Checkbutton(head, text=modality, variable=enabled).pack(side="left")
            ttk.Label(head, text=f"conf {E.MODALITY_CONFIDENCE[modality]:.2f}",
                      style="Muted.TLabel").pack(side="right")

            for key, options in E.MODALITIES[modality].items():
                ttk.Label(cell, text=key.replace("_", " "),
                          style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
                var = tk.StringVar(value=options[0])
                self._feature_vars[key] = var
                ttk.Combobox(cell, textvariable=var, values=options,
                             state="readonly", width=14).pack(fill="x")

        buttons = ttk.Frame(box, style="Panel.TFrame")
        buttons.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(buttons, text="Run step", style="Go.TButton",
                   command=self._run_step).pack(side="left")
        ttk.Button(buttons, text="Randomise",
                   command=self._randomise).pack(side="left", padx=6)
        ttk.Button(buttons, text="Reset", command=self._load_memory).pack(side="left")

    def _build_decision(self, parent) -> None:
        column = ttk.Frame(parent)
        column.pack(side="left", fill="y", padx=(0, 10))

        box = ttk.LabelFrame(column, text="DECISION")
        box.pack(fill="x")
        self.action_label = ttk.Label(box, text="—", style="Action.TLabel")
        self.action_label.pack(anchor="w", padx=10, pady=(8, 2))
        self.mode_label = ttk.Label(box, text="", style="Muted.TLabel")
        self.mode_label.pack(anchor="w", padx=10)
        self.stats_label = ttk.Label(box, text="", style="Panel.TLabel",
                                     font=("Consolas", 8), justify="left")
        self.stats_label.pack(anchor="w", padx=10, pady=6)
        self.note_label = ttk.Label(box, text="", style="Panel.TLabel",
                                    wraplength=300, font=("Segoe UI", 8))
        self.note_label.pack(anchor="w", padx=10, pady=(0, 8))

        box = ttk.LabelFrame(column, text="REWARD DERIVATION")
        box.pack(fill="x", pady=(10, 0))
        self.reward_label = ttk.Label(box, text="", style="Panel.TLabel",
                                      wraplength=300, justify="left",
                                      font=("Segoe UI", 8))
        self.reward_label.pack(anchor="w", padx=10, pady=8)

        box = ttk.LabelFrame(column, text="ACTION SCORES")
        box.pack(fill="both", expand=True, pady=(10, 0))
        self.scores_canvas = tk.Canvas(box, bg=PANEL, highlightthickness=0,
                                       width=310, height=130)
        self.scores_canvas.pack(padx=8, pady=8)

    def _build_graph(self, parent) -> None:
        box = ttk.LabelFrame(
            parent,
            text="MEMORY CONTRIBUTION GRAPH — which experiences produced this decision",
        )
        box.pack(side="left", fill="both", expand=True)
        self.graph_canvas = tk.Canvas(box, bg=PANEL, highlightthickness=0, height=340)
        self.graph_canvas.pack(fill="both", expand=True, padx=8, pady=8)
        self.graph_canvas.bind("<Configure>", lambda _e: self._draw_graph())

        legend = ttk.Frame(box, style="Panel.TFrame")
        legend.pack(fill="x", padx=8, pady=(0, 8))
        for action, colour in E.ACTION_COLORS.items():
            chip = tk.Canvas(legend, width=9, height=9, bg=PANEL,
                             highlightthickness=0)
            chip.create_oval(1, 1, 8, 8, fill=colour, outline="")
            chip.pack(side="left", padx=(6, 2))
            ttk.Label(legend, text=action, style="Muted.TLabel").pack(side="left")
        ttk.Label(legend, text="edge width = similarity x decay x boost",
                  style="Muted.TLabel").pack(side="right")

    def _build_tables(self, parent) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="both", expand=True, pady=(10, 0))

        box = ttk.LabelFrame(row, text="CONTRIBUTING MEMORIES")
        box.pack(side="left", fill="both", expand=True, padx=(0, 10))
        columns = ("step", "action", "reward", "sim", "decay", "boost", "weight")
        self.contrib_tree = ttk.Treeview(box, columns=columns, show="headings",
                                         height=7)
        for name in columns:
            self.contrib_tree.heading(name, text=name)
            self.contrib_tree.column(name, width=62, anchor="center")
        self.contrib_tree.pack(fill="both", expand=True, padx=6, pady=6)

        box = ttk.LabelFrame(row, text="STEP HISTORY")
        box.pack(side="left", fill="both", expand=True)
        columns = ("step", "action", "mode", "policy", "reward", "source")
        self.history_tree = ttk.Treeview(box, columns=columns, show="headings",
                                         height=7)
        for name in columns:
            self.history_tree.heading(name, text=name)
            self.history_tree.column(name, width=68, anchor="center")
        self.history_tree.pack(fill="both", expand=True, padx=6, pady=6)

    # -- actions ---------------------------------------------------------
    def _on_param(self, key: str) -> None:
        value = self._param_vars[key].get()
        if key == "top_k":
            value = int(round(value))
            self._param_labels[key].config(text=str(value))
        else:
            self._param_labels[key].config(text=f"{value:.3f}")
        setattr(self.session.cfg, key, value)
        if key in ("risk_bias", "action_threshold"):
            self.session.state[key] = float(value)

    def _collect_percepts(self) -> dict:
        percepts = {}
        for modality in E.MODALITY_ORDER:
            if not self._modality_vars[modality].get():
                continue
            percepts[modality] = {
                key: self._feature_vars[key].get()
                for key in E.MODALITIES[modality]
            }
        return percepts

    def _manual_reward(self):
        raw = self.reward_var.get().strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    def _run_step(self) -> None:
        percepts = self._collect_percepts()
        if not percepts:
            self._refresh("Enable at least one modality before running a step.")
            return
        self.session.run_step(percepts, manual_reward=self._manual_reward())
        self._refresh("")

    def _randomise(self) -> None:
        import random
        for modality in E.MODALITY_ORDER:
            for key, options in E.MODALITIES[modality].items():
                self._feature_vars[key].set(random.choice(options))

    def _load_memory(self) -> None:
        raw = self.seed_var.get().strip()
        try:
            seed = int(raw) if raw else None
        except ValueError:
            seed = None
        profile = self.profile_var.get()
        if self.source_var.get() == "preset":
            self.session.reset(memory=build_preset_memory(profile),
                               profile=profile, seed=seed)
            message = f"Loaded preset bank: {len(self.session.memory)} experiences."
        else:
            self.session.reset(memory=E.MemorySystem(), profile=profile, seed=seed)
            message = "Started from scratch with empty memory."
        self.session.apply_profile(profile)
        for key, var in self._param_vars.items():
            var.set(getattr(self.session.cfg, key))
            self._on_param(key)
        self._refresh(message)

    def _export(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")],
            initialfile="mcps_memory.json")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"memory": self.session.memory.to_json_obj(),
                       "profile": self.session.profile,
                       "config": self.session.cfg.to_dict()}, handle, indent=2)
        self._refresh(f"Exported {len(self.session.memory)} experiences.")

    def _import(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            records = data.get("memory", data)
            self.session.reset(memory=E.MemorySystem.from_json_obj(records),
                               profile=self.profile_var.get())
            self._refresh(f"Imported {len(self.session.memory)} experiences.")
        except Exception as exc:
            self._refresh(f"Import failed: {exc}")

    def _apply_reward(self) -> None:
        value = self._manual_reward()
        if value is None:
            self._refresh("Enter a reward between 0 and 1 first.")
            return
        self._refresh(self.session.apply_reward(value)["message"])

    def _teach(self) -> None:
        outcome = self.session.teach_expert(self.expert_var.get(),
                                            self._manual_reward())
        self._refresh(outcome["message"])

    # -- rendering -------------------------------------------------------
    def _refresh(self, message: str) -> None:
        self.message.config(text=message)
        result = self.session.last_result

        if result is None:
            self.action_label.config(text="—", foreground=TEXT)
            self.mode_label.config(text="No step run yet.")
            self.stats_label.config(text="")
            self.note_label.config(text="")
            self.reward_label.config(text="")
        else:
            self.action_label.config(text=result["action"].upper(),
                                     foreground=E.ACTION_COLORS[result["action"]])
            self.mode_label.config(
                text=f"{result['mode']} · {result['policy']} · step {result['step']}")
            self.stats_label.config(text="\n".join([
                f"novelty     {fmt(result['novelty'])}",
                f"epsilon     {fmt(result['epsilon'])}",
                f"threshold   {fmt(result['state']['action_threshold'])}",
                f"memory      {result['memory_size']}",
                f"seen before {'yes' if result['dlcbf_hit'] else 'no'}",
                f"channels    {', '.join(result['active_modalities']) or 'none'}",
            ]))

            note, colour = "", MUTED
            if result["reflex_rule_label"]:
                note = f"Reflex {result['reflex_rule']}: {result['reflex_rule_label']}"
                colour = OK_FG
            elif result["policy"] == "HESITATE":
                note = (f"Best score {fmt(result['scores'][result['best_action']])} "
                        f"below threshold {fmt(result['threshold'])} — "
                        f"fell back to observe.")
                colour = WARN_FG
            self.note_label.config(text=note, foreground=colour)
            self._render_reward(result)

        self._render_scores(result)
        self._draw_graph()
        self._render_tables(result)

    def _render_reward(self, result) -> None:
        lines = [f"source: {result['reward_source']}"]
        if result["reward_mean"] is not None:
            lines.append(f"memory mean {fmt(result['reward_mean'])} over "
                         f"{len(result['contributions'])} memories")
            lines.append(f"+ variance → {fmt(result['reward'])}")
        elif result["reward_source"] == "cold-start":
            lines.append(f"no relevant memory — prior {fmt(result['reward'])}")
        else:
            lines.append(f"reward {fmt(result['reward'])}")

        colour = TEXT
        if result["penalty"]:
            p = result["penalty"]
            colour = WARN_FG
            lines += [
                "",
                f"Off-recommendation: memory advised {p['recommended']}, "
                f"took {p['taken']}.",
                f"margin {fmt(p['margin'])} x conf {fmt(p['confidence'])} "
                f"→ penalty {fmt(p['penalty'])}",
                f"{fmt(p['before'])} → {fmt(p['after'])}",
            ]
        self.reward_label.config(text="\n".join(lines), foreground=colour)

    def _render_scores(self, result) -> None:
        canvas = self.scores_canvas
        canvas.delete("all")
        if result is None:
            canvas.create_text(155, 65, text="No step run yet.",
                               fill=MUTED, font=("Segoe UI", 9, "italic"))
            return

        for index, action in enumerate(E.ACTIONS):
            y = 12 + index * 24
            score = result["scores"][action]
            support = result["supports"].get(action, 0.0)
            chosen = action == result["action"]
            evidenced = support > 0

            canvas.create_text(14, y, anchor="w", text=action,
                               fill=TEXT if evidenced else MUTED,
                               font=("Segoe UI", 8, "bold" if chosen else "normal"))
            # Track: a visible well, not a near-black rectangle lost on the panel.
            canvas.create_rectangle(70, y - 6, 230, y + 6,
                                    fill=BG, outline=LINE, width=1)
            width = max(0, min(1.0, score)) * 158
            if width > 1:
                if evidenced:
                    canvas.create_rectangle(71, y - 5, 71 + width, y + 5,
                                            fill=E.ACTION_COLORS[action], outline="")
                else:
                    # No supporting memory: the 0.50 is a default, not a
                    # judgement. An outline says "nothing here" more clearly
                    # than a stippled fill, which just reads as a dim bar.
                    canvas.create_rectangle(71, y - 5, 71 + width, y + 5,
                                            fill="", outline=DISABLED, dash=(2, 2))
            canvas.create_text(236, y, anchor="w", text=f"{score:.2f}",
                               fill=TEXT if evidenced else MUTED,
                               font=("Consolas", 8, "bold" if chosen else "normal"))
            canvas.create_text(270, y, anchor="w", text=f"w={support:.2f}",
                               fill=MUTED if evidenced else DISABLED,
                               font=("Consolas", 7))
            if chosen:
                canvas.create_text(8, y, anchor="w", text="▸", fill=ACCENT,
                                   font=("Segoe UI", 10, "bold"))

    def _draw_graph(self) -> None:
        canvas = self.graph_canvas
        canvas.delete("all")
        result = self.session.last_result
        width = canvas.winfo_width() or 620
        height = canvas.winfo_height() or 340
        cx, cy = width / 2, height / 2

        if result is None:
            canvas.create_text(cx, cy, text="No step run yet.",
                               fill=MUTED, font=("Segoe UI", 9, "italic"))
            return

        graph = result["graph"]
        if graph["empty"]:
            canvas.create_text(
                cx, cy, width=width - 40, justify="center", fill=MUTED,
                font=("Segoe UI", 9, "italic"),
                text="No memories contributed to this decision —\n"
                     "the reward came from a cold-start prior.")
            return

        scale_x, scale_y = width * 0.36, height * 0.36
        positions = {n["id"]: (cx + n["x"] * scale_x, cy + n["y"] * scale_y)
                     for n in graph["nodes"]}
        max_weight = max((e["weight"] for e in graph["edges"]), default=1e-9) or 1e-9

        if result["penalty"]:
            canvas.create_text(
                10, 12, anchor="w", fill=WARN_FG, font=("Segoe UI", 8, "bold"),
                text=f"memory advised {result['penalty']['recommended']} — "
                     f"{result['action']} was taken instead")

        for edge in graph["edges"]:
            x0, y0 = positions[edge["source"]]
            ratio = edge["weight"] / max_weight
            canvas.create_line(x0, y0, cx, cy, fill=edge["color"],
                               width=1 + 6 * ratio)

        for node in graph["nodes"]:
            if node["kind"] == "percept":
                continue
            x, y = positions[node["id"]]
            radius = 11 + 12 * node["radius"]
            if node["is_expert"]:
                canvas.create_oval(x - radius - 4, y - radius - 4,
                                   x + radius + 4, y + radius + 4,
                                   outline="#ffd166", width=2)
            canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
                               fill=node["color"], outline=PANEL, width=2)
            if node["mode"] == "REFLEXIVE":
                # White pip marks a memory that itself came from a reflex.
                mark = radius * 0.7
                canvas.create_oval(x + mark - 4, y - mark - 4,
                                   x + mark + 4, y - mark + 4,
                                   fill="#ffffff", outline=node["color"])
            canvas.create_text(x, y, text=f"{node['reward']:.2f}",
                               fill=ink_for(node["color"]),
                               font=("Segoe UI", 8, "bold"))
            canvas.create_text(x, y + radius + 9, text=f"s{node['step']}",
                               fill=TEXT, font=("Segoe UI", 7))

        centre_fill = E.ACTION_COLORS[result["action"]]
        centre_ink = ink_for(centre_fill)
        canvas.create_oval(cx - 32, cy - 32, cx + 32, cy + 32,
                           fill=centre_fill, outline="#ffffff", width=2)
        canvas.create_text(cx, cy - 6, text="NOW", fill=centre_ink,
                           font=("Segoe UI", 8, "bold"))
        canvas.create_text(cx, cy + 7, text=result["action"].upper(),
                           fill=centre_ink, font=("Segoe UI", 7))

    def _render_tables(self, result) -> None:
        self.contrib_tree.delete(*self.contrib_tree.get_children())
        for contrib in (result or {}).get("contributions", []):
            marks = ("*" if contrib["is_expert"] else "") + \
                    ("r" if contrib["mode"] == "REFLEXIVE" else "")
            self.contrib_tree.insert("", "end", values=(
                contrib["step"], contrib["action"] + (f" {marks}" if marks else ""),
                f"{contrib['reward']:.2f}", f"{contrib['similarity']:.2f}",
                f"{contrib['decay']:.2f}", f"{contrib['boost']:.1f}",
                f"{contrib['weight']:.3f}"))

        self.history_tree.delete(*self.history_tree.get_children())
        for entry in reversed(self.session.history[-40:]):
            self.history_tree.insert("", "end", values=(
                entry["step"], entry["action"], entry["mode"], entry["policy"],
                f"{entry['reward']:.2f}" + (" !" if entry["penalised"] else ""),
                entry["reward_source"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="MPCS v2 dashboard (Tkinter).")
    parser.add_argument("--scratch", action="store_true",
                        help="Start with empty memory instead of the preset bank.")
    parser.add_argument("--profile", choices=tuple(PROFILE_CONFIGS),
                        default="balanced")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    session = E.Session(profile=args.profile, seed=args.seed)
    memory = E.MemorySystem() if args.scratch else build_preset_memory(args.profile)
    session.reset(memory=memory, profile=args.profile, seed=args.seed)
    session.apply_profile(args.profile)

    root = tk.Tk()
    CognitiveTkUI(root, session)
    root.mainloop()


if __name__ == "__main__":
    main()

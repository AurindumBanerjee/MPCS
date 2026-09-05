"""
MPCS v2 dashboard — Variant C: Dash / Plotly
---------------------------------------------
Same cognition as the other variants (mpcs_engine), different front-end.
Plotly earns its place here through real hover tooltips: every memory node
carries its own similarity, decay, boost and resulting weight, so the
arithmetic behind a decision is inspectable rather than merely depicted.

Requires:  pip install dash plotly
Run:       python mpcs_dash_plotly.py
"""

from __future__ import annotations

import base64
import json
import os
import sys

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ctx, dcc, html, no_update

# The engine lives in ../core; add it to the path so this runs from anywhere.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))

import mpcs_engine as E
from mpcs_preset_v2 import PROFILE_CONFIGS, build_preset_memory


# Dash callbacks are stateless, so the session lives here at module level.
# Single-user local tool; no cross-session isolation needed.
SESSION = E.Session()
SESSION.reset(memory=build_preset_memory("balanced"), profile="balanced")

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

BG, PANEL, LINE, TEXT, MUTED = "#10131a", "#171b24", "#2a3040", "#e6e9ef", "#8b94a7"

CARD = {"background": PANEL, "border": f"1px solid {LINE}", "borderRadius": "10px",
        "padding": "14px", "marginBottom": "14px"}
LABEL = {"fontSize": "12px", "color": MUTED, "margin": "8px 0 3px"}
HEAD = {"fontSize": "12px", "textTransform": "uppercase", "letterSpacing": ".7px",
        "color": MUTED, "fontWeight": "600", "margin": "0 0 10px"}


def fmt(value) -> str:
    return "—" if value is None else f"{value:.3f}"


# ----------------------------------------------------------------------
# Layout
# ----------------------------------------------------------------------
def sidebar() -> html.Div:
    return html.Div([
        html.H2("MPCS v2", style={"margin": "0", "fontSize": "18px"}),
        html.P("Multimodal cognitive simulator",
               style={"color": MUTED, "fontSize": "12px", "margin": "2px 0 16px"}),

        html.Div("Memory source", style=HEAD),
        dcc.Dropdown(
            id="source",
            options=[{"label": "Preset bank (70 experiences)", "value": "preset"},
                     {"label": "Start from scratch", "value": "scratch"}],
            value="preset", clearable=False,
            style={"background": PANEL, "color": "#111"},
        ),
        html.Div("Profile", style=LABEL),
        dcc.Dropdown(
            id="profile",
            options=[{"label": f"{k} — {v['description']}", "value": k}
                     for k, v in PROFILE_CONFIGS.items()],
            value="balanced", clearable=False, style={"color": "#111"},
        ),
        html.Div("Seed (blank = random)", style=LABEL),
        dcc.Input(id="seed", type="text", placeholder="e.g. 42",
                  style={"width": "100%", "background": "#1d2230", "color": TEXT,
                         "border": f"1px solid {LINE}", "borderRadius": "6px",
                         "padding": "6px 8px"}),
        html.Div([
            html.Button("Load memory", id="load-btn", n_clicks=0,
                        style={"background": "#4c8dff", "color": "#fff", "border": "0",
                               "borderRadius": "6px", "padding": "8px 12px",
                               "cursor": "pointer", "fontWeight": "600"}),
            html.Button("Export", id="export-btn", n_clicks=0,
                        style={"background": "#1d2230", "color": TEXT,
                               "border": f"1px solid {LINE}", "borderRadius": "6px",
                               "padding": "8px 12px", "cursor": "pointer",
                               "marginLeft": "8px"}),
        ], style={"marginTop": "10px"}),
        dcc.Download(id="download-memory"),

        dcc.Upload(
            id="upload-memory",
            children=html.Div("Drop or click to import memory JSON",
                              style={"fontSize": "11px", "color": MUTED}),
            style={"border": f"1px dashed {LINE}", "borderRadius": "6px",
                   "padding": "10px", "textAlign": "center", "marginTop": "10px",
                   "cursor": "pointer"},
        ),

        html.Div("Parameters", style={**HEAD, "marginTop": "20px"}),
        html.Div([
            html.Div([
                html.Div([
                    html.Span(label, style={"fontSize": "12px", "color": MUTED}),
                    html.B(id=f"val-{key}", style={"float": "right", "fontSize": "12px"}),
                ]),
                dcc.Slider(
                    id=f"p-{key}", min=lo, max=hi, step=stepv,
                    value=getattr(SESSION.cfg, key), marks=None,
                    tooltip={"placement": "bottom", "always_visible": False},
                ),
            ], style={"marginBottom": "10px"})
            for key, label, lo, hi, stepv in PARAM_SPEC
        ]),

        html.Div("Reward & teaching", style={**HEAD, "marginTop": "20px"}),
        html.Div("Manual reward (blank = derive from memory)", style=LABEL),
        dcc.Input(id="manual-reward", type="text", placeholder="blank = from memory",
                  style={"width": "100%", "background": "#1d2230", "color": TEXT,
                         "border": f"1px solid {LINE}", "borderRadius": "6px",
                         "padding": "6px 8px"}),
        html.Div([
            html.Button("Apply to last", id="reward-btn", n_clicks=0,
                        style={"background": "#1d2230", "color": TEXT,
                               "border": f"1px solid {LINE}", "borderRadius": "6px",
                               "padding": "8px 12px", "cursor": "pointer"}),
        ], style={"marginTop": "10px"}),
        html.Div("Expert action", style=LABEL),
        dcc.Dropdown(id="expert-action",
                     options=[{"label": a, "value": a} for a in E.ACTIONS],
                     value=E.ACTIONS[0], clearable=False, style={"color": "#111"}),
        html.Button("Teach expert", id="teach-btn", n_clicks=0,
                    style={"background": "#1d2230", "color": TEXT,
                           "border": f"1px solid {LINE}", "borderRadius": "6px",
                           "padding": "8px 12px", "cursor": "pointer",
                           "marginTop": "10px"}),
        html.P(id="message", style={"color": "#4c8dff", "fontSize": "12px",
                                    "marginTop": "12px", "minHeight": "18px"}),
    ], style={"width": "320px", "background": PANEL, "padding": "16px",
              "borderRight": f"1px solid {LINE}", "height": "100vh",
              "overflowY": "auto", "position": "sticky", "top": "0",
              "flexShrink": "0"})


def modality_block(modality: str) -> html.Div:
    return html.Div([
        html.Div([
            dcc.Checklist(
                id=f"on-{modality}", options=[{"label": f" {modality}", "value": "on"}],
                value=["on"], style={"fontWeight": "600", "display": "inline-block"},
            ),
            html.Small(f"confidence {E.MODALITY_CONFIDENCE[modality]:.2f}",
                       style={"color": MUTED, "float": "right", "fontSize": "11px"}),
        ]),
        *[html.Div([
            html.Div(key.replace("_", " "), style=LABEL),
            dcc.Dropdown(id=f"f-{key}",
                         options=[{"label": o, "value": o} for o in options],
                         value=options[0], clearable=False, style={"color": "#111"}),
        ]) for key, options in E.MODALITIES[modality].items()],
    ], style={"border": f"1px solid {LINE}", "borderRadius": "8px",
              "padding": "10px", "flex": "1", "minWidth": "190px"})


app = Dash(__name__, title="MPCS v2 — Cognitive Dashboard")
app.layout = html.Div([
    sidebar(),
    html.Div([
        html.Div([
            html.Div("Sensory input — uncheck a modality to remove that channel",
                     style=HEAD),
            html.Div([modality_block(m) for m in E.MODALITY_ORDER],
                     style={"display": "flex", "gap": "12px", "flexWrap": "wrap"}),
            html.Div([
                html.Button("Run step", id="run-btn", n_clicks=0,
                            style={"background": "#4c8dff", "color": "#fff",
                                   "border": "0", "borderRadius": "6px",
                                   "padding": "9px 16px", "cursor": "pointer",
                                   "fontWeight": "600"}),
            ], style={"marginTop": "12px"}),
        ], style=CARD),

        html.Div([
            html.Div([html.Div("Decision", style=HEAD), html.Div(id="decision")],
                     style={**CARD, "flex": "1", "minWidth": "240px"}),
            html.Div([html.Div("Reward derivation", style=HEAD), html.Div(id="reward")],
                     style={**CARD, "flex": "1", "minWidth": "240px"}),
            html.Div([html.Div("Action scores", style=HEAD),
                      dcc.Graph(id="scores-fig", config={"displayModeBar": False},
                                style={"height": "230px"})],
                     style={**CARD, "flex": "1.2", "minWidth": "260px"}),
        ], style={"display": "flex", "gap": "14px", "flexWrap": "wrap"}),

        html.Div([
            html.Div("Memory contribution graph — hover a node for its arithmetic",
                     style=HEAD),
            dcc.Graph(id="graph-fig", config={"displayModeBar": False},
                      style={"height": "440px"}),
        ], style=CARD),

        html.Div([
            html.Div([html.Div("Contributing memories", style=HEAD),
                      html.Div(id="contrib-table")],
                     style={**CARD, "flex": "1.4", "minWidth": "320px"}),
            html.Div([html.Div("Reward & threshold trace", style=HEAD),
                      dcc.Graph(id="trace-fig", config={"displayModeBar": False},
                                style={"height": "230px"})],
                     style={**CARD, "flex": "1", "minWidth": "260px"}),
        ], style={"display": "flex", "gap": "14px", "flexWrap": "wrap"}),

        html.Div([html.Div("Step history", style=HEAD), html.Div(id="history-table")],
                 style=CARD),
    ], style={"flex": "1", "padding": "18px 22px", "overflowX": "hidden"}),
], style={"display": "flex", "background": BG, "color": TEXT, "minHeight": "100vh",
          "fontFamily": "Segoe UI, system-ui, sans-serif", "margin": "0"})


# ----------------------------------------------------------------------
# Figures
# ----------------------------------------------------------------------
def dark(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        paper_bgcolor=PANEL, plot_bgcolor=PANEL, font_color=TEXT,
        margin=dict(l=8, r=8, t=8, b=8), height=height, showlegend=False,
    )
    return fig


def scores_figure(result) -> go.Figure:
    fig = go.Figure()
    if not result:
        return dark(fig, 230)
    actions = E.ACTIONS
    scores = [result["scores"][a] for a in actions]
    supports = [result["supports"].get(a, 0.0) for a in actions]
    fig.add_bar(
        x=scores, y=actions, orientation="h",
        marker=dict(
            color=[E.ACTION_COLORS[a] for a in actions],
            opacity=[1.0 if s > 0 else 0.35 for s in supports],
            line=dict(color=["#fff" if a == result["action"] else PANEL
                             for a in actions], width=2),
        ),
        text=[f"{s:.2f} (w={w:.2f})" for s, w in zip(scores, supports)],
        textposition="outside", textfont=dict(size=10, color=MUTED),
        hovertemplate="%{y}: %{x:.3f}<extra></extra>",
    )
    fig.update_xaxes(range=[0, 1.25], gridcolor=LINE, zeroline=False)
    fig.update_yaxes(gridcolor=PANEL)
    return dark(fig, 230)


def graph_figure(result) -> go.Figure:
    fig = go.Figure()
    if not result or result["graph"]["empty"]:
        fig.add_annotation(
            text="No memories contributed — the reward came from a cold-start prior.",
            showarrow=False, font=dict(color=MUTED, size=13),
        )
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        return dark(fig, 440)

    graph = result["graph"]
    positions = {n["id"]: (n["x"], n["y"]) for n in graph["nodes"]}
    max_weight = max((e["weight"] for e in graph["edges"]), default=1e-9) or 1e-9

    # Plotly has no node-link primitive: edges are one line trace each so
    # their widths can differ.
    for edge in graph["edges"]:
        x0, y0 = positions[edge["source"]]
        ratio = edge["weight"] / max_weight
        fig.add_scatter(
            x=[x0, 0.0], y=[y0, 0.0], mode="lines",
            line=dict(color=edge["color"], width=1 + 7 * ratio),
            opacity=0.25 + 0.6 * ratio, hoverinfo="skip",
        )

    memories = [n for n in graph["nodes"] if n["kind"] == "memory"]
    if memories:
        fig.add_scatter(
            x=[n["x"] for n in memories], y=[n["y"] for n in memories],
            mode="markers+text",
            marker=dict(
                size=[16 + 22 * n["radius"] for n in memories],
                color=[n["color"] for n in memories],
                line=dict(
                    color=["#ffd166" if n["is_expert"] else "#0d1017" for n in memories],
                    width=[3 if n["is_expert"] else 1.5 for n in memories],
                ),
            ),
            text=[f"{n['reward']:.2f}" for n in memories],
            textposition="middle center",
            textfont=dict(size=9, color="#fff"),
            customdata=[[n["step"], n["action"], n["mode"], n["reward"],
                         n["similarity"], n["decay"], n["boost"], n["weight"],
                         n["age"]] for n in memories],
            hovertemplate=(
                "<b>step %{customdata[0]} — %{customdata[1]}</b><br>"
                "origin: %{customdata[2]}<br>"
                "reward: %{customdata[3]:.3f}<br>"
                "similarity: %{customdata[4]:.3f}<br>"
                "decay: %{customdata[5]:.3f} (age %{customdata[8]})<br>"
                "boost: %{customdata[6]:.1f}<br>"
                "<b>weight: %{customdata[7]:.4f}</b><extra></extra>"
            ),
        )

    fig.add_scatter(
        x=[0], y=[0], mode="markers+text",
        marker=dict(size=64, color=E.ACTION_COLORS[result["action"]],
                    line=dict(color="#fff", width=2)),
        text=[f"NOW<br>{result['action'].upper()}"],
        textposition="middle center", textfont=dict(size=10, color="#fff"),
        hovertext=["current percept — " + ", ".join(result["active_modalities"])],
        hoverinfo="text",
    )

    if result["penalty"]:
        fig.add_annotation(
            x=0, y=1.12, xref="x", yref="y", showarrow=False,
            text=(f"memory advised {result['penalty']['recommended']} — "
                  f"{result['action']} was taken instead"),
            font=dict(color="#d1483f", size=12),
        )

    fig.update_xaxes(visible=False, range=[-1.3, 1.3])
    fig.update_yaxes(visible=False, range=[-1.25, 1.25],
                     scaleanchor="x", scaleratio=1)
    return dark(fig, 440)


def trace_figure(history) -> go.Figure:
    fig = go.Figure()
    if not history:
        return dark(fig, 230)
    steps = [h["step"] for h in history]
    fig.add_scatter(x=steps, y=[h["reward"] for h in history], mode="lines+markers",
                    line=dict(color="#4c8dff", width=2), name="reward",
                    hovertemplate="step %{x}: reward %{y:.3f}<extra></extra>")
    fig.add_scatter(x=steps, y=[h["threshold"] for h in history], mode="lines",
                    line=dict(color="#2aa36b", width=2), name="threshold",
                    hovertemplate="step %{x}: threshold %{y:.3f}<extra></extra>")
    penalised = [h for h in history if h["penalised"]]
    if penalised:
        fig.add_scatter(
            x=[h["step"] for h in penalised], y=[h["reward"] for h in penalised],
            mode="markers", marker=dict(color="#d1483f", size=9, symbol="x"),
            name="penalised", hovertemplate="step %{x}: penalised<extra></extra>",
        )
    fig.add_hline(y=0.5, line=dict(color=LINE, dash="dot"))
    fig.update_xaxes(gridcolor=LINE)
    fig.update_yaxes(gridcolor=LINE, range=[0, 1])
    fig.update_layout(showlegend=True,
                      legend=dict(orientation="h", y=1.14, font=dict(size=10)))
    return dark(fig, 230)


def table(rows, columns) -> html.Table:
    if not rows:
        return html.Div("Nothing yet.", style={"color": MUTED, "fontSize": "12px",
                                               "fontStyle": "italic"})
    cell = {"padding": "5px 8px", "borderBottom": f"1px solid {LINE}",
            "fontSize": "12px", "textAlign": "left"}
    head = {**cell, "color": MUTED, "fontSize": "11px", "textTransform": "uppercase"}
    return html.Table(
        [html.Tr([html.Th(c, style=head) for c, _ in columns])] +
        [html.Tr([html.Td(render(row), style=cell) for _, render in columns])
         for row in rows],
        style={"width": "100%", "borderCollapse": "collapse"},
    )


# ----------------------------------------------------------------------
# Panels
# ----------------------------------------------------------------------
def decision_panel(result):
    if not result:
        return html.Div("No step run yet.",
                        style={"color": MUTED, "fontStyle": "italic"})
    rows = [("novelty", fmt(result["novelty"])),
            ("epsilon", fmt(result["epsilon"])),
            ("action threshold", fmt(result["state"]["action_threshold"])),
            ("memory size", str(result["memory_size"])),
            ("seen verbatim", "yes" if result["dlcbf_hit"] else "no"),
            ("active channels", ", ".join(result["active_modalities"]) or "none")]
    extras = []
    if result["reflex_rule_label"]:
        extras.append(html.Div(
            f"Reflex rule {result['reflex_rule']}: {result['reflex_rule_label']}",
            style={"color": "#2aa36b", "fontSize": "12px", "marginTop": "8px"}))
    if result["policy"] == "HESITATE":
        extras.append(html.Div(
            f"Best score {fmt(result['scores'][result['best_action']])} fell below "
            f"threshold {fmt(result['threshold'])} — fell back to observe.",
            style={"color": "#d1483f", "fontSize": "12px", "marginTop": "8px"}))
    return html.Div([
        html.Span(result["action"].upper(), style={
            "background": E.ACTION_COLORS[result["action"]], "color": "#fff",
            "padding": "5px 14px", "borderRadius": "999px", "fontWeight": "700",
            "fontSize": "15px"}),
        html.Div(f"{result['mode']} · {result['policy']} · step {result['step']}",
                 style={"color": MUTED, "fontSize": "12px", "margin": "10px 0"}),
        *[html.Div([html.Span(k, style={"color": MUTED, "fontSize": "12px"}),
                    html.B(v, style={"float": "right", "fontSize": "12px"})])
          for k, v in rows],
        *extras,
    ])


def reward_panel(result):
    if not result:
        return html.Div("No step run yet.",
                        style={"color": MUTED, "fontStyle": "italic"})
    parts = [html.Div(f"source: {result['reward_source']}",
                      style={"color": MUTED, "fontSize": "12px"})]
    if result["reward_mean"] is not None:
        parts.append(html.Div(
            f"memory mean {fmt(result['reward_mean'])} over "
            f"{len(result['contributions'])} memories"))
        parts.append(html.Div(f"+ sampled variance → {fmt(result['reward'])}"))
    elif result["reward_source"] == "cold-start":
        parts.append(html.Div(
            f"no relevant memory — neutral prior {fmt(result['reward'])}"))
    else:
        parts.append(html.Div(f"reward {fmt(result['reward'])}"))
    if result["penalty"]:
        p = result["penalty"]
        parts.append(html.Div([
            html.Div(f"Off-recommendation: memory advised {p['recommended']}, "
                     f"took {p['taken']}.", style={"fontWeight": "600"}),
            html.Div(f"margin {fmt(p['margin'])} × support conf "
                     f"{fmt(p['confidence'])} → penalty {fmt(p['penalty'])}"),
            html.Div(f"{fmt(p['before'])} → {fmt(p['after'])}"),
        ], style={"color": "#d1483f", "marginTop": "8px", "fontSize": "12px"}))
    return html.Div(parts, style={"fontSize": "13px", "lineHeight": "1.9"})


def contrib_table(result):
    rows = (result or {}).get("contributions") or []
    return table(rows, [
        ("step", lambda c: str(c["step"])),
        ("action", lambda c: html.Span(
            c["action"] + (" ·expert" if c["is_expert"] else "")
            + (" ·reflex" if c["mode"] == "REFLEXIVE" else ""),
            style={"color": E.ACTION_COLORS[c["action"]]})),
        ("reward", lambda c: fmt(c["reward"])),
        ("sim", lambda c: fmt(c["similarity"])),
        ("decay", lambda c: fmt(c["decay"])),
        ("boost", lambda c: f"{c['boost']:.1f}"),
        ("weight", lambda c: html.B(f"{c['weight']:.4f}")),
    ])


def history_table(history):
    return table(list(reversed(history))[:25], [
        ("step", lambda h: str(h["step"])),
        ("action", lambda h: html.Span(h["action"],
                                       style={"color": E.ACTION_COLORS[h["action"]]})),
        ("mode", lambda h: h["mode"]),
        ("policy", lambda h: h["policy"]),
        ("reward", lambda h: html.Span(
            fmt(h["reward"]),
            style={"color": "#d1483f" if h["penalised"] else TEXT})),
        ("source", lambda h: html.Span(h["reward_source"], style={"color": MUTED})),
    ])


def render_all(message: str):
    result = SESSION.last_result
    return (decision_panel(result), reward_panel(result), scores_figure(result),
            graph_figure(result), contrib_table(result),
            trace_figure(SESSION.history), history_table(SESSION.history), message)


# ----------------------------------------------------------------------
# Callbacks
# ----------------------------------------------------------------------
@app.callback(
    [Output("decision", "children"), Output("reward", "children"),
     Output("scores-fig", "figure"), Output("graph-fig", "figure"),
     Output("contrib-table", "children"), Output("trace-fig", "figure"),
     Output("history-table", "children"), Output("message", "children")],
    [Input("run-btn", "n_clicks"), Input("load-btn", "n_clicks"),
     Input("reward-btn", "n_clicks"), Input("teach-btn", "n_clicks"),
     Input("upload-memory", "contents")],
    [State("source", "value"), State("profile", "value"), State("seed", "value"),
     State("manual-reward", "value"), State("expert-action", "value")] +
    [State(f"on-{m}", "value") for m in E.MODALITY_ORDER] +
    [State(f"f-{key}", "value")
     for m in E.MODALITY_ORDER for key in E.MODALITIES[m]] +
    [State(f"p-{key}", "value") for key, *_ in PARAM_SPEC],
)
def handle(run_clicks, load_clicks, reward_clicks, teach_clicks, upload,
           source, profile, seed_text, manual_text, expert_action, *rest):
    toggles = rest[:len(E.MODALITY_ORDER)]
    offset = len(E.MODALITY_ORDER)
    feature_keys = [(m, key) for m in E.MODALITY_ORDER for key in E.MODALITIES[m]]
    feature_values = rest[offset:offset + len(feature_keys)]
    param_values = rest[offset + len(feature_keys):]

    # Sliders push straight into the live config, so a parameter change takes
    # effect on the very next step.
    for (key, *_), value in zip(PARAM_SPEC, param_values):
        if value is None:
            continue
        setattr(SESSION.cfg, key, int(value) if key == "top_k" else float(value))
        if key in ("risk_bias", "action_threshold"):
            SESSION.state[key] = float(value)

    trigger = ctx.triggered_id
    message = ""

    def parse_reward():
        try:
            return float(manual_text) if manual_text and manual_text.strip() else None
        except ValueError:
            return None

    if trigger == "load-btn":
        try:
            seed = int(seed_text) if seed_text and seed_text.strip() else None
        except ValueError:
            seed = None
        if source == "preset":
            SESSION.reset(memory=build_preset_memory(profile), profile=profile, seed=seed)
            message = f"Loaded preset bank: {len(SESSION.memory)} experiences."
        else:
            SESSION.reset(memory=E.MemorySystem(), profile=profile, seed=seed)
            message = "Started from scratch with empty memory."
        SESSION.apply_profile(profile)

    elif trigger == "upload-memory" and upload:
        try:
            _, payload = upload.split(",", 1)
            data = json.loads(base64.b64decode(payload).decode("utf-8"))
            records = data.get("memory", data)
            SESSION.reset(memory=E.MemorySystem.from_json_obj(records), profile=profile)
            message = f"Imported {len(SESSION.memory)} experiences."
        except Exception as exc:
            message = f"Import failed: {exc}"

    elif trigger == "reward-btn":
        value = parse_reward()
        message = (SESSION.apply_reward(value)["message"] if value is not None
                   else "Enter a reward between 0 and 1 first.")

    elif trigger == "teach-btn":
        message = SESSION.teach_expert(expert_action, parse_reward())["message"]

    elif trigger == "run-btn":
        percepts = {}
        for (modality, key), value in zip(feature_keys, feature_values):
            index = E.MODALITY_ORDER.index(modality)
            if "on" not in (toggles[index] or []):
                continue
            percepts.setdefault(modality, {})[key] = value
        if not percepts:
            message = "Enable at least one modality before running a step."
        else:
            SESSION.run_step(percepts, manual_reward=parse_reward())

    return render_all(message)


@app.callback(
    [Output(f"val-{key}", "children") for key, *_ in PARAM_SPEC],
    [Input(f"p-{key}", "value") for key, *_ in PARAM_SPEC],
)
def show_param_values(*values):
    return [str(int(v)) if key == "top_k" else f"{float(v):.3f}"
            for (key, *_), v in zip(PARAM_SPEC, values)]


@app.callback(
    Output("download-memory", "data"),
    Input("export-btn", "n_clicks"),
    prevent_initial_call=True,
)
def export_memory(_clicks):
    if not _clicks:
        return no_update
    return dict(
        content=json.dumps({"memory": SESSION.memory.to_json_obj(),
                            "profile": SESSION.profile,
                            "config": SESSION.cfg.to_dict()}, indent=2),
        filename="mpcs_memory.json",
    )


if __name__ == "__main__":
    print("MPCS v2 dashboard (Dash/Plotly) — http://127.0.0.1:8757/")
    app.run(debug=False, port=8757)

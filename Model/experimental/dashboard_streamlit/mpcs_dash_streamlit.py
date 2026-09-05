"""
MPCS v2 dashboard — Variant B: Streamlit
-----------------------------------------
Same cognition as the other variants (mcps_engine), different front-end.
Streamlit gives the sidebar and layout for free; the cost is that it re-runs
this whole script on every interaction, so the session lives in
st.session_state and is built exactly once.

Requires:  pip install streamlit
Run:       streamlit run mcps_dash_streamlit.py
"""

from __future__ import annotations

import json
import os
import sys

import streamlit as st

# The engine lives in ../core; add it to the path so this runs from anywhere.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))

import mcps_engine as E
from mcps_preset_v2 import PROFILE_CONFIGS, build_preset_memory


st.set_page_config(page_title="MPCS v2 — Cognitive Dashboard",
                   layout="wide", page_icon="🧠")

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


# ----------------------------------------------------------------------
# Session — built once. Rebuilding it per rerun would silently wipe memory
# on every widget interaction, which is the classic Streamlit trap.
# ----------------------------------------------------------------------
def get_session() -> E.Session:
    if "mcps" not in st.session_state:
        session = E.Session()
        session.reset(memory=build_preset_memory("balanced"), profile="balanced")
        st.session_state.mcps = session
        st.session_state.notice = (
            f"Loaded preset bank: {len(session.memory)} experiences."
        )
    return st.session_state.mcps


def load_memory(source: str, profile: str, seed, uploaded) -> str:
    session = get_session()
    if source == "Preset bank (70 experiences)":
        session.reset(memory=build_preset_memory(profile), profile=profile, seed=seed)
        message = f"Loaded preset bank: {len(session.memory)} experiences."
    elif source == "Import JSON":
        if uploaded is None:
            return "Upload a JSON file to import."
        data = json.loads(uploaded.getvalue().decode("utf-8"))
        records = data.get("memory", data)
        session.reset(memory=E.MemorySystem.from_json_obj(records),
                      profile=profile, seed=seed)
        message = f"Imported {len(session.memory)} experiences."
    else:
        session.reset(memory=E.MemorySystem(), profile=profile, seed=seed)
        message = "Started from scratch with empty memory."
    session.apply_profile(profile)
    return message


session = get_session()


# ----------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------
with st.sidebar:
    st.title("MPCS v2")
    st.caption("Multimodal cognitive simulator")

    st.subheader("Memory source")
    source = st.selectbox("Source", [
        "Preset bank (70 experiences)", "Start from scratch", "Import JSON",
    ], label_visibility="collapsed")
    profile = st.selectbox("Profile", list(PROFILE_CONFIGS),
                           help="\n".join(f"{k}: {v['description']}"
                                          for k, v in PROFILE_CONFIGS.items()))
    seed_text = st.text_input("Seed", placeholder="blank = random")
    uploaded = st.file_uploader("Memory JSON", type="json") \
        if source == "Import JSON" else None

    if st.button("Load memory", use_container_width=True):
        try:
            seed = int(seed_text) if seed_text.strip() else None
        except ValueError:
            seed = None
        st.session_state.notice = load_memory(source, profile, seed, uploaded)
        st.rerun()

    st.download_button(
        "Export memory",
        data=json.dumps({"memory": session.memory.to_json_obj(),
                         "profile": session.profile,
                         "config": session.cfg.to_dict()}, indent=2),
        file_name="mcps_memory.json", mime="application/json",
        use_container_width=True,
    )

    st.subheader("Parameters")
    for key, label, lo, hi, step_size in PARAM_SPEC:
        current = getattr(session.cfg, key)
        if key == "top_k":
            value = st.slider(label, int(lo), int(hi), int(current), int(step_size))
        else:
            value = st.slider(label, float(lo), float(hi), float(current), float(step_size))
        setattr(session.cfg, key, value)
        if key in ("risk_bias", "action_threshold"):
            session.state[key] = float(value)

    st.subheader("Reward & teaching")
    manual_text = st.text_input("Manual reward (0–1)",
                                placeholder="blank = derive from memory")
    col_a, col_b = st.columns(2)
    if col_a.button("Apply to last", use_container_width=True):
        try:
            st.session_state.notice = session.apply_reward(float(manual_text))["message"]
        except (TypeError, ValueError):
            st.session_state.notice = "Reward must be a number between 0 and 1."
        st.rerun()
    expert_action = st.selectbox("Expert action", E.ACTIONS)
    if col_b.button("Teach expert", use_container_width=True):
        try:
            expert_reward = float(manual_text) if manual_text.strip() else None
        except ValueError:
            expert_reward = None
        st.session_state.notice = session.teach_expert(expert_action, expert_reward)["message"]
        st.rerun()

    if st.session_state.get("notice"):
        st.info(st.session_state.notice)


# ----------------------------------------------------------------------
# Percept input
# ----------------------------------------------------------------------
st.subheader("Sensory input")
st.caption("Uncheck a modality to remove that channel entirely — "
           "the system reasons from what remains.")

percepts: dict[str, dict[str, str]] = {}
columns = st.columns(len(E.MODALITY_ORDER))
for column, modality in zip(columns, E.MODALITY_ORDER):
    with column:
        enabled = st.checkbox(
            f"**{modality}**", value=True, key=f"on-{modality}",
            help=f"channel confidence {E.MODALITY_CONFIDENCE[modality]:.2f}",
        )
        features = {}
        for key, options in E.MODALITIES[modality].items():
            features[key] = st.selectbox(
                key.replace("_", " "), options,
                key=f"f-{key}", disabled=not enabled,
            )
        if enabled:
            percepts[modality] = features

run_col, rand_col, _ = st.columns([1, 1, 4])
if run_col.button("Run step", type="primary", use_container_width=True):
    if not percepts:
        st.session_state.notice = "Enable at least one modality before running a step."
    else:
        try:
            manual = float(manual_text) if manual_text.strip() else None
        except ValueError:
            manual = None
        session.run_step(percepts, manual_reward=manual)
        st.session_state.notice = ""
    st.rerun()

result = session.last_result


# ----------------------------------------------------------------------
# Decision, reward, scores
# ----------------------------------------------------------------------
def fmt(value) -> str:
    return "—" if value is None else f"{value:.3f}"


if result is None:
    st.info("No step run yet. Choose a percept above and press **Run step**.")
    st.stop()

left, middle, right = st.columns(3)

with left:
    st.markdown("##### Decision")
    color = E.ACTION_COLORS[result["action"]]
    st.markdown(
        f"<span style='background:{color};color:#fff;padding:6px 16px;"
        f"border-radius:999px;font-weight:700;font-size:17px'>"
        f"{result['action'].upper()}</span>",
        unsafe_allow_html=True,
    )
    st.caption(f"{result['mode']} · {result['policy']} · step {result['step']}")
    st.metric("Novelty", fmt(result["novelty"]))
    st.metric("Action threshold", fmt(result["state"]["action_threshold"]))
    st.caption(
        f"epsilon {fmt(result['epsilon'])} · memory {result['memory_size']} · "
        f"seen verbatim: {'yes' if result['dlcbf_hit'] else 'no'}"
    )
    st.caption("active channels: " + (", ".join(result["active_modalities"]) or "none"))
    if result["reflex_rule_label"]:
        st.success(f"Reflex rule {result['reflex_rule']}: {result['reflex_rule_label']}")
    if result["policy"] == "HESITATE":
        st.warning(
            f"Best score {fmt(result['scores'][result['best_action']])} fell below "
            f"threshold {fmt(result['threshold'])} — fell back to observe."
        )

with middle:
    st.markdown("##### Reward derivation")
    st.caption(f"source: `{result['reward_source']}`")
    if result["reward_mean"] is not None:
        st.write(f"memory mean **{fmt(result['reward_mean'])}** "
                 f"over {len(result['contributions'])} memories")
        st.write(f"+ sampled variance → **{fmt(result['reward'])}**")
    elif result["reward_source"] == "cold-start":
        st.write(f"no relevant memory — neutral prior **{fmt(result['reward'])}**")
    else:
        st.write(f"reward **{fmt(result['reward'])}**")
    if result["penalty"]:
        p = result["penalty"]
        st.error(
            f"Off-recommendation: memory advised **{p['recommended']}**, "
            f"took **{p['taken']}**.\n\n"
            f"margin {fmt(p['margin'])} × support conf {fmt(p['confidence'])} "
            f"→ penalty {fmt(p['penalty'])}\n\n"
            f"{fmt(p['before'])} → {fmt(p['after'])}"
        )

with right:
    st.markdown("##### Action scores")
    for action in E.ACTIONS:
        score = result["scores"][action]
        support = result["supports"].get(action, 0.0)
        label = f"**{action}**" if action == result["action"] else action
        suffix = " ←" if action == result["action"] else ""
        st.caption(f"{label}{suffix} — {fmt(score)} (support {support:.2f})")
        st.progress(min(1.0, max(0.0, score)))
    st.caption("Actions with support 0.00 sit at the 0.50 default — "
               "that is an absence of evidence, not a judgement.")


# ----------------------------------------------------------------------
# Memory contribution graph
# ----------------------------------------------------------------------
st.markdown("##### Memory contribution graph")
st.caption("Which past experiences produced this decision. Strong contributors "
           "sit closer to the centre; edge thickness is similarity × decay × boost.")

graph = result["graph"]
if graph["empty"]:
    st.info("No memories contributed — the reward came from a cold-start prior.")
else:
    W, H = 900, 420
    cx, cy, sx, sy = W / 2, H / 2, W * 0.40, H * 0.40
    max_weight = max((e["weight"] for e in graph["edges"]), default=1e-9) or 1e-9

    def px(node):
        return cx + node["x"] * sx

    def py(node):
        return cy + node["y"] * sy

    parts = []
    for edge in graph["edges"]:
        src = next(n for n in graph["nodes"] if n["id"] == edge["source"])
        ratio = edge["weight"] / max_weight
        parts.append(
            f'<line x1="{px(src):.1f}" y1="{py(src):.1f}" x2="{cx}" y2="{cy}" '
            f'stroke="{edge["color"]}" stroke-width="{1 + 7 * ratio:.2f}" '
            f'stroke-opacity="{0.25 + 0.6 * ratio:.2f}">'
            f'<title>{edge["tooltip"]}</title></line>'
        )
    for node in graph["nodes"]:
        if node["kind"] == "percept":
            parts.append(
                f'<circle cx="{cx}" cy="{cy}" r="34" fill="{node["color"]}" '
                f'stroke="#fff" stroke-width="2"/>'
                f'<text x="{cx}" y="{cy - 2}" text-anchor="middle" fill="#fff" '
                f'font-size="11" font-weight="700">NOW</text>'
                f'<text x="{cx}" y="{cy + 12}" text-anchor="middle" fill="#fff" '
                f'font-size="9">{(node["action"] or "").upper()}</text>'
            )
            continue
        radius = 9 + 13 * node["radius"]
        if node["is_expert"]:
            parts.append(
                f'<circle cx="{px(node):.1f}" cy="{py(node):.1f}" r="{radius + 4:.1f}" '
                f'fill="none" stroke="#ffd166" stroke-width="2"/>'
            )
        tooltip = (
            f'step {node["step"]} — {node["action"]} ({node["mode"]}) | '
            f'reward {node["reward"]:.2f} | sim {node["similarity"]:.2f} '
            f'× decay {node["decay"]:.2f} × boost {node["boost"]:.1f} '
            f'= {node["weight"]:.3f}'
        )
        parts.append(
            f'<circle cx="{px(node):.1f}" cy="{py(node):.1f}" r="{radius:.1f}" '
            f'fill="{node["color"]}" stroke="#0d1017" stroke-width="1.5">'
            f'<title>{tooltip}</title></circle>'
            f'<text x="{px(node):.1f}" y="{py(node) + 4:.1f}" text-anchor="middle" '
            f'fill="#fff" font-size="10" font-weight="600">{node["reward"]:.2f}</text>'
            f'<text x="{px(node):.1f}" y="{py(node) + radius + 13:.1f}" '
            f'text-anchor="middle" fill="#8b94a7" font-size="9">s{node["step"]}</text>'
        )

    banner = ""
    if result["penalty"]:
        banner = (
            f'<text x="14" y="24" fill="#d1483f" font-size="12" font-weight="600">'
            f'memory advised {result["penalty"]["recommended"]} — '
            f'{result["action"]} was taken instead</text>'
        )
    st.markdown(
        f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-height:440px">'
        f'{banner}{"".join(parts)}</svg>',
        unsafe_allow_html=True,
    )

    legend = " ".join(
        f'<span style="margin-right:14px"><span style="display:inline-block;'
        f'width:9px;height:9px;border-radius:50%;background:{c};'
        f'margin-right:4px"></span>{a}</span>'
        for a, c in E.ACTION_COLORS.items()
    )
    st.markdown(f'<div style="font-size:12px;color:#8b94a7">{legend}</div>',
                unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Tables and trace
# ----------------------------------------------------------------------
table_col, trace_col = st.columns([3, 2])

with table_col:
    st.markdown("##### Contributing memories")
    if result["contributions"]:
        st.dataframe(
            [{
                "step": c["step"],
                "action": c["action"],
                "reward": round(c["reward"], 3),
                "similarity": round(c["similarity"], 3),
                "decay": round(c["decay"], 3),
                "boost": round(c["boost"], 2),
                "weight": round(c["weight"], 4),
                "origin": c["mode"],
                "expert": c["is_expert"],
            } for c in result["contributions"]],
            use_container_width=True, hide_index=True,
        )
    else:
        st.caption("No contributing memories.")

with trace_col:
    st.markdown("##### Reward & threshold trace")
    if session.history:
        st.line_chart(
            {
                "reward": [h["reward"] for h in session.history],
                "threshold": [h["threshold"] for h in session.history],
            },
            height=220,
        )
    else:
        st.caption("No steps yet.")

st.markdown("##### Step history")
if session.history:
    st.dataframe(
        [{
            "step": h["step"], "action": h["action"], "mode": h["mode"],
            "policy": h["policy"], "reward": round(h["reward"], 3),
            "source": h["reward_source"], "penalised": h["penalised"],
        } for h in reversed(session.history)],
        use_container_width=True, hide_index=True, height=260,
    )

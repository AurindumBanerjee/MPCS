"""
MPCS v2 dashboard — Variant A: local web app, standard library only
--------------------------------------------------------------------
Serves a single self-contained page from http.server and drives the shared
mpcs_engine behind a small JSON API. No third-party packages, no CDN
requests: the whole UI is inline in this file.

What it shows that the old Tk window could not: which memories contributed to
the decision and how strongly, drawn as a percept-centred node-link graph that
redraws every step.

Run:
    python MPCS_Test.py
    python MPCS_Test.py --port 8765 --no-browser
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# The engine lives in ../core; add it to the path so this runs from anywhere.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))

import mpcs_engine as E
from mpcs_preset_v2 import PROFILE_CONFIGS, build_preset_memory


# ----------------------------------------------------------------------
# Session state, guarded because ThreadingHTTPServer handles requests
# on separate threads.
# ----------------------------------------------------------------------
_lock = threading.Lock()
_session = E.Session()


def _reset_session(source: str, profile: str, seed, imported=None) -> str:
    global _session
    cfg = _session.cfg
    _session = E.Session(cfg=cfg, profile=profile,
                         seed=seed if seed is not None else None)
    if source == "preset":
        _session.reset(memory=build_preset_memory(profile), profile=profile, seed=seed)
        message = f"Loaded preset bank: {len(_session.memory)} experiences (profile {profile})."
    elif source == "import" and imported is not None:
        _session.reset(memory=E.MemorySystem.from_json_obj(imported),
                       profile=profile, seed=seed)
        message = f"Imported {len(_session.memory)} experiences."
    else:
        _session.reset(memory=E.MemorySystem(), profile=profile, seed=seed)
        message = "Started from scratch with empty memory."
    _session.apply_profile(profile)
    return message


def _snapshot(message: str = "") -> dict:
    return {
        "message": message,
        "step": _session.step,
        "memory_size": len(_session.memory),
        "profile": _session.profile,
        "state": dict(_session.state),
        "config": _session.cfg.to_dict(),
        "history": _session.history[-40:],
        "result": _sanitise(_session.last_result),
    }


def _sanitise(result):
    """Drop the raw summary tuple, which is not JSON-serialisable."""
    if result is None:
        return None
    return {k: v for k, v in result.items() if k != "summary"}


# ----------------------------------------------------------------------
# API handlers
# ----------------------------------------------------------------------
def api_meta(_payload) -> dict:
    return {
        "modalities": E.MODALITIES,
        "modality_order": list(E.MODALITY_ORDER),
        "modality_confidence": E.MODALITY_CONFIDENCE,
        "actions": E.ACTIONS,
        "action_colors": E.ACTION_COLORS,
        "reflex_rules": E.REFLEX_RULE_LABELS,
        "profiles": {k: v["description"] for k, v in PROFILE_CONFIGS.items()},
        "config": _session.cfg.to_dict(),
    }


def api_step(payload) -> dict:
    percepts = payload.get("percepts") or {}
    raw = payload.get("manual_reward")
    manual = None
    if raw not in (None, ""):
        try:
            manual = float(raw)
        except (TypeError, ValueError):
            manual = None
    if not any(percepts.values()):
        return _snapshot("Enable at least one modality before running a step.")
    _session.run_step(percepts, manual_reward=manual)
    return _snapshot("")


def api_config(payload) -> dict:
    cfg = _session.cfg
    for key, value in (payload.get("config") or {}).items():
        if not hasattr(cfg, key):
            continue
        current = getattr(cfg, key)
        try:
            if isinstance(current, bool):
                setattr(cfg, key, bool(value))
            elif isinstance(current, int):
                setattr(cfg, key, int(value))
            else:
                setattr(cfg, key, float(value))
        except (TypeError, ValueError):
            continue
    # risk_bias and action_threshold live in state as well; keep them in step.
    for key in ("risk_bias", "action_threshold", "novelty_threshold"):
        if key in (payload.get("config") or {}):
            _session.state[key] = getattr(cfg, key)
    return _snapshot("Parameters updated.")


def api_reset(payload) -> dict:
    seed = payload.get("seed")
    try:
        seed = int(seed) if seed not in (None, "") else None
    except (TypeError, ValueError):
        seed = None
    message = _reset_session(
        payload.get("source", "scratch"),
        payload.get("profile", "balanced"),
        seed,
        payload.get("memory"),
    )
    return _snapshot(message)


def api_reward(payload) -> dict:
    try:
        reward = float(payload.get("reward"))
    except (TypeError, ValueError):
        return _snapshot("Reward must be a number between 0 and 1.")
    outcome = _session.apply_reward(reward)
    return _snapshot(outcome["message"])


def api_teach(payload) -> dict:
    raw = payload.get("reward")
    reward = None
    if raw not in (None, ""):
        try:
            reward = float(raw)
        except (TypeError, ValueError):
            reward = None
    outcome = _session.teach_expert(payload.get("action", ""), reward)
    return _snapshot(outcome["message"])


def api_export(_payload) -> dict:
    return {
        "memory": _session.memory.to_json_obj(),
        "profile": _session.profile,
        "config": _session.cfg.to_dict(),
    }


ROUTES = {
    "/api/meta": api_meta,
    "/api/step": api_step,
    "/api/config": api_config,
    "/api/reset": api_reset,
    "/api/reward": api_reward,
    "/api/teach": api_teach,
    "/api/export": api_export,
}


# ----------------------------------------------------------------------
# HTTP server
# ----------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass  # keep the console clean; the dashboard is the interface

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send(PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/meta":
            with _lock:
                body = json.dumps(api_meta(None)).encode("utf-8")
            self._send(body, "application/json")
        elif path == "/api/export":
            with _lock:
                body = json.dumps(api_export(None), indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Disposition",
                             'attachment; filename="mpcs_memory.json"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send(b"not found", "text/plain", 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        handler = ROUTES.get(path)
        if handler is None:
            self._send(b"not found", "text/plain", 404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(b'{"message":"bad request"}', "application/json", 400)
            return
        with _lock:
            try:
                result = handler(payload)
            except Exception as exc:  # surface engine errors in the UI
                result = _snapshot(f"Error: {exc}")
        self._send(json.dumps(result).encode("utf-8"), "application/json")


# ----------------------------------------------------------------------
# The page
# ----------------------------------------------------------------------
PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MPCS v2 — Cognitive Dashboard</title>
<style>
  :root {
    --bg: #10131a; --panel: #171b24; --panel-2: #1d2230; --line: #2a3040;
    --text: #e6e9ef; --muted: #8b94a7; --accent: #4c8dff;
    --ignore:#8a8f98; --observe:#2f7fd1; --approach:#2aa36b;
    --alert:#e0902b; --withdraw:#d1483f;
  }
  * { box-sizing: border-box; }
  body {
    margin:0; background:var(--bg); color:var(--text);
    font:14px/1.5 "Segoe UI", system-ui, sans-serif;
    display:grid; grid-template-columns: 300px 1fr; min-height:100vh;
  }
  aside {
    background:var(--panel); border-right:1px solid var(--line);
    padding:16px; overflow-y:auto; height:100vh; position:sticky; top:0;
  }
  main { padding:18px 22px; overflow-x:hidden; }
  h1 { font-size:18px; margin:0 0 4px; letter-spacing:.2px; }
  h2 { font-size:12px; text-transform:uppercase; letter-spacing:.8px;
       color:var(--muted); margin:20px 0 8px; font-weight:600; }
  .sub { color:var(--muted); font-size:12px; margin:0 0 14px; }
  label { display:block; font-size:12px; color:var(--muted); margin:8px 0 3px; }
  select, input[type=text], input[type=number] {
    width:100%; background:var(--panel-2); color:var(--text);
    border:1px solid var(--line); border-radius:6px; padding:6px 8px; font-size:13px;
  }
  input[type=range] { width:100%; accent-color:var(--accent); }
  .rowv { display:flex; justify-content:space-between; font-size:12px; color:var(--muted); }
  .rowv b { color:var(--text); font-weight:600; }
  button {
    background:var(--accent); color:#fff; border:0; border-radius:6px;
    padding:8px 12px; font-size:13px; cursor:pointer; font-weight:600;
  }
  button.ghost { background:var(--panel-2); border:1px solid var(--line); color:var(--text); }
  button:hover { filter:brightness(1.1); }
  .btnrow { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:14px; }
  .card {
    background:var(--panel); border:1px solid var(--line);
    border-radius:10px; padding:14px;
  }
  .card h3 { margin:0 0 10px; font-size:12px; text-transform:uppercase;
             letter-spacing:.7px; color:var(--muted); font-weight:600; }
  .modality { border:1px solid var(--line); border-radius:8px; padding:10px; background:var(--panel); }
  .modality header { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
  .modality header span { font-weight:600; text-transform:capitalize; font-size:13px; }
  .modality header small { color:var(--muted); margin-left:auto; font-size:11px; }
  .modality.off { opacity:.42; }
  .action-badge {
    display:inline-block; padding:5px 14px; border-radius:999px;
    font-weight:700; letter-spacing:.5px; font-size:15px; color:#fff;
  }
  .pill { display:inline-block; padding:2px 9px; border-radius:999px;
          background:var(--panel-2); border:1px solid var(--line);
          font-size:11px; color:var(--muted); margin-right:6px; }
  .bar { height:9px; background:var(--panel-2); border-radius:5px; overflow:hidden; }
  .bar > i { display:block; height:100%; border-radius:5px; }
  .scoreline { display:grid; grid-template-columns:78px 1fr 46px 52px;
               gap:8px; align-items:center; margin-bottom:7px; font-size:12px; }
  .scoreline .sup { color:var(--muted); font-size:11px; text-align:right; }
  .reward-flow { font-size:13px; line-height:1.9; }
  .reward-flow code { background:var(--panel-2); padding:2px 7px;
                      border-radius:4px; font-size:12px; }
  .warn { color:var(--withdraw); font-weight:600; }
  table { width:100%; border-collapse:collapse; font-size:12px; }
  th, td { text-align:left; padding:5px 8px; border-bottom:1px solid var(--line); }
  th { color:var(--muted); font-weight:600; font-size:11px;
       text-transform:uppercase; letter-spacing:.5px; }
  .msg { min-height:18px; color:var(--accent); font-size:12px; margin:10px 0 0; }
  .legend { display:flex; gap:12px; flex-wrap:wrap; font-size:11px; color:var(--muted); }
  .legend i { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:4px; }
  .scroll { max-height:260px; overflow-y:auto; }
  svg text { font-family:"Segoe UI", system-ui, sans-serif; }
  .empty { color:var(--muted); font-size:12px; font-style:italic; padding:18px 0; text-align:center; }
</style>
</head>
<body>
<aside>
  <h1>MPCS v2</h1>
  <p class="sub">Multimodal cognitive simulator</p>

  <h2>Memory source</h2>
  <select id="source">
    <option value="scratch">Start from scratch</option>
    <option value="preset" selected>Preset bank (70 experiences)</option>
    <option value="import">Import JSON…</option>
  </select>
  <input type="file" id="importFile" accept="application/json" style="display:none">

  <label>Profile</label>
  <select id="profile"></select>

  <label>Seed <small style="color:var(--muted)">(blank = random)</small></label>
  <input type="text" id="seed" placeholder="e.g. 42">

  <div class="btnrow">
    <button id="applySource">Load memory</button>
    <button class="ghost" id="exportBtn">Export</button>
  </div>

  <h2>Parameters</h2>
  <div id="params"></div>

  <h2>Reward &amp; teaching</h2>
  <label>Manual reward (0–1, blank = derive from memory)</label>
  <input type="text" id="manualReward" placeholder="blank = from memory">
  <div class="btnrow">
    <button class="ghost" id="applyReward">Apply to last</button>
  </div>
  <label>Expert action</label>
  <select id="expertAction"></select>
  <div class="btnrow">
    <button class="ghost" id="teachBtn">Teach expert</button>
  </div>
  <p class="msg" id="message"></p>
</aside>

<main>
  <div class="grid" style="margin-bottom:14px">
    <div class="card" style="grid-column:1/-1">
      <h3>Sensory input — uncheck a modality to remove that channel entirely</h3>
      <div class="grid" id="inputs"></div>
      <div class="btnrow">
        <button id="runStep">Run step</button>
        <button class="ghost" id="randomise">Randomise percept</button>
      </div>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <h3>Decision</h3>
      <div id="decision"><p class="empty">No step run yet.</p></div>
    </div>
    <div class="card">
      <h3>Reward derivation</h3>
      <div id="reward" class="reward-flow"><p class="empty">No step run yet.</p></div>
    </div>
    <div class="card">
      <h3>Action scores</h3>
      <div id="scores"><p class="empty">No step run yet.</p></div>
    </div>
  </div>

  <div class="grid" style="margin-top:14px">
    <div class="card" style="grid-column:1/-1">
      <h3>Memory contribution graph — which experiences produced this decision</h3>
      <div id="graph"></div>
      <div class="legend" id="legend"></div>
    </div>
  </div>

  <div class="grid" style="margin-top:14px">
    <div class="card">
      <h3>Contributing memories</h3>
      <div class="scroll"><table id="contribTable"></table></div>
    </div>
    <div class="card">
      <h3>Reward &amp; threshold trace</h3>
      <div id="trace"></div>
    </div>
    <div class="card">
      <h3>Step history</h3>
      <div class="scroll"><table id="historyTable"></table></div>
    </div>
  </div>
</main>

<script>
const $ = id => document.getElementById(id);
let META = null, STATE = null;

const PARAM_SPEC = [
  ["top_k",              "Top-k memories",      1,    20,   1],
  ["time_decay",         "Time decay base",     0.80, 1.00, 0.005],
  ["reward_variance",    "Reward variance",     0.00, 0.30, 0.01],
  ["penalty_strength",   "Penalty strength",    0.00, 2.00, 0.05],
  ["support_saturation", "Support saturation",  0.25, 6.00, 0.25],
  ["risk_bias",          "Risk bias (explore)", 0.00, 1.00, 0.01],
  ["action_threshold",   "Action threshold",    0.00, 1.00, 0.01],
  ["learning_rate",      "Learning rate",       0.00, 0.20, 0.005],
  ["expert_weight_boost","Expert boost",        1.00, 6.00, 0.25],
  ["reflex_memory_boost","Reflex memory boost", 1.00, 6.00, 0.25],
];

async function post(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body || {})
  });
  return res.json();
}

// ---------- setup ----------
async function init() {
  META = await (await fetch("/api/meta")).json();

  $("profile").innerHTML = Object.entries(META.profiles)
    .map(([k, d]) => `<option value="${k}" title="${d}">${k}</option>`).join("");
  $("expertAction").innerHTML = META.actions
    .map(a => `<option value="${a}">${a}</option>`).join("");

  $("inputs").innerHTML = META.modality_order.map(m => {
    const conf = META.modality_confidence[m];
    const rows = Object.entries(META.modalities[m]).map(([key, opts]) => `
      <label>${key.replace(/_/g, " ")}</label>
      <select data-mod="${m}" data-key="${key}">
        ${opts.map(o => `<option value="${o}">${o}</option>`).join("")}
      </select>`).join("");
    return `<div class="modality" id="mod-${m}">
      <header>
        <input type="checkbox" class="modtoggle" data-mod="${m}" checked>
        <span>${m}</span><small>confidence ${conf.toFixed(2)}</small>
      </header>${rows}</div>`;
  }).join("");

  document.querySelectorAll(".modtoggle").forEach(cb => cb.onchange = () => {
    $("mod-" + cb.dataset.mod).classList.toggle("off", !cb.checked);
  });

  $("params").innerHTML = PARAM_SPEC.map(([key, label, lo, hi, stepv]) => `
    <label>${label}</label>
    <div class="rowv"><span></span><b id="val-${key}"></b></div>
    <input type="range" id="p-${key}" min="${lo}" max="${hi}" step="${stepv}">
  `).join("");

  PARAM_SPEC.forEach(([key]) => {
    const el = $("p-" + key);
    el.value = META.config[key];
    $("val-" + key).textContent = fmtParam(key, META.config[key]);
    el.oninput = () => $("val-" + key).textContent = fmtParam(key, el.value);
    el.onchange = async () => {
      const patch = {}; patch[key] = el.value;
      render(await post("/api/config", {config: patch}));
    };
  });

  $("legend").innerHTML = META.actions.map(a =>
    `<span><i style="background:${META.action_colors[a]}"></i>${a}</span>`
  ).join("") + `<span style="margin-left:auto">edge thickness = contribution weight
   (similarity × decay × boost)</span>`;

  bindControls();
  render(await post("/api/reset", {source: "preset", profile: "balanced"}));
}

function fmtParam(key, v) {
  return key === "top_k" ? String(parseInt(v, 10)) : Number(v).toFixed(3);
}

function bindControls() {
  $("source").onchange = () => {
    if ($("source").value === "import") $("importFile").click();
  };
  $("importFile").onchange = async ev => {
    const file = ev.target.files[0];
    if (!file) return;
    const data = JSON.parse(await file.text());
    render(await post("/api/reset", {
      source: "import", profile: $("profile").value,
      seed: $("seed").value, memory: data.memory || data
    }));
  };
  $("applySource").onclick = async () => {
    if ($("source").value === "import") { $("importFile").click(); return; }
    render(await post("/api/reset", {
      source: $("source").value, profile: $("profile").value, seed: $("seed").value
    }));
  };
  $("exportBtn").onclick = () => window.location = "/api/export";
  $("runStep").onclick = async () => {
    render(await post("/api/step", {
      percepts: collectPercepts(), manual_reward: $("manualReward").value.trim()
    }));
  };
  $("randomise").onclick = () => {
    document.querySelectorAll("#inputs select").forEach(sel => {
      sel.selectedIndex = Math.floor(Math.random() * sel.options.length);
    });
  };
  $("applyReward").onclick = async () => {
    render(await post("/api/reward", {reward: $("manualReward").value.trim()}));
  };
  $("teachBtn").onclick = async () => {
    render(await post("/api/teach", {
      action: $("expertAction").value, reward: $("manualReward").value.trim()
    }));
  };
}

function collectPercepts() {
  const percepts = {};
  META.modality_order.forEach(m => {
    const on = document.querySelector(`.modtoggle[data-mod="${m}"]`).checked;
    if (!on) return;
    const features = {};
    document.querySelectorAll(`select[data-mod="${m}"]`).forEach(sel => {
      features[sel.dataset.key] = sel.value;
    });
    percepts[m] = features;
  });
  return percepts;
}

// ---------- render ----------
function render(snap) {
  STATE = snap;
  $("message").textContent = snap.message || "";
  PARAM_SPEC.forEach(([key]) => {
    const el = $("p-" + key);
    if (document.activeElement !== el) {
      el.value = snap.config[key];
      $("val-" + key).textContent = fmtParam(key, snap.config[key]);
    }
  });
  renderDecision(snap);
  renderReward(snap);
  renderScores(snap);
  renderGraph(snap);
  renderContribTable(snap);
  renderTrace(snap);
  renderHistory(snap);
}

function renderDecision(snap) {
  const r = snap.result;
  if (!r) { $("decision").innerHTML = `<p class="empty">No step run yet.</p>`; return; }
  const color = META.action_colors[r.action];
  const reflex = r.reflex_rule_label
    ? `<div style="margin-top:8px"><span class="pill">rule ${r.reflex_rule}</span>${r.reflex_rule_label}</div>` : "";
  const hesitated = r.policy === "HESITATE"
    ? `<div style="margin-top:8px" class="warn">Best score ${fmt(r.scores[r.best_action])}
       was below threshold ${fmt(r.threshold)} — fell back to observe.</div>` : "";
  $("decision").innerHTML = `
    <div><span class="action-badge" style="background:${color}">${r.action.toUpperCase()}</span></div>
    <div style="margin-top:10px">
      <span class="pill">${r.mode}</span><span class="pill">${r.policy}</span>
      <span class="pill">step ${r.step}</span>
    </div>
    <div style="margin-top:10px" class="rowv"><span>novelty</span><b>${fmt(r.novelty)}</b></div>
    <div class="rowv"><span>epsilon</span><b>${fmt(r.epsilon)}</b></div>
    <div class="rowv"><span>action threshold</span><b>${fmt(r.state.action_threshold)}</b></div>
    <div class="rowv"><span>memory size</span><b>${snap.memory_size}</b></div>
    <div class="rowv"><span>seen verbatim before</span><b>${r.dlcbf_hit ? "yes" : "no"}</b></div>
    <div class="rowv"><span>active channels</span><b>${r.active_modalities.join(", ") || "none"}</b></div>
    ${reflex}${hesitated}`;
}

function renderReward(snap) {
  const r = snap.result;
  if (!r) { $("reward").innerHTML = `<p class="empty">No step run yet.</p>`; return; }
  let html = `<div><span class="pill">${r.reward_source}</span></div>`;
  if (r.reward_mean !== null && r.reward_mean !== undefined) {
    html += `<div>memory mean <code>${fmt(r.reward_mean)}</code>
             over ${r.contributions.length} memories</div>`;
    html += `<div>+ sampled variance → <code>${fmt(r.reward)}</code></div>`;
  } else if (r.reward_source === "cold-start") {
    html += `<div>no relevant memory — neutral prior <code>${fmt(r.reward)}</code></div>`;
  } else {
    html += `<div>reward <code>${fmt(r.reward)}</code></div>`;
  }
  if (r.penalty) {
    const p = r.penalty;
    html += `<div class="warn" style="margin-top:8px">
      Off-recommendation: memory advised <b>${p.recommended}</b>, took <b>${p.taken}</b>.</div>
      <div>margin <code>${fmt(p.margin)}</code> × support conf <code>${fmt(p.confidence)}</code>
      → penalty <code>${fmt(p.penalty)}</code></div>
      <div><code>${fmt(p.before)}</code> → <code>${fmt(p.after)}</code></div>`;
  }
  $("reward").innerHTML = html;
}

function renderScores(snap) {
  const r = snap.result;
  if (!r) { $("scores").innerHTML = `<p class="empty">No step run yet.</p>`; return; }
  $("scores").innerHTML = META.actions.map(a => {
    const score = r.scores[a], support = r.supports[a] || 0;
    const chosen = a === r.action, advised = r.penalty && r.penalty.recommended === a;
    const mark = chosen ? " ←" : (advised ? " ✓advised" : "");
    return `<div class="scoreline">
      <span style="${chosen ? "font-weight:700" : ""}">${a}${mark}</span>
      <div class="bar"><i style="width:${(score * 100).toFixed(0)}%;
        background:${META.action_colors[a]}; opacity:${support > 0 ? 1 : 0.35}"></i></div>
      <span>${fmt(score)}</span>
      <span class="sup">w=${support.toFixed(2)}</span>
    </div>`;
  }).join("") + `<div style="color:var(--muted);font-size:11px;margin-top:6px">
    Faded bars have no supporting memory — the 0.50 is a default, not a judgement.</div>`;
}

function renderGraph(snap) {
  const r = snap.result;
  const box = $("graph");
  if (!r || !r.graph || r.graph.empty) {
    box.innerHTML = `<p class="empty">No memories contributed to this decision
      — the reward came from a cold-start prior.</p>`;
    return;
  }
  const W = 900, H = 420, cx = W / 2, cy = H / 2, SX = W * 0.40, SY = H * 0.40;
  const g = r.graph;
  const px = n => cx + n.x * SX, py = n => cy + n.y * SY;
  const maxW = Math.max(...g.edges.map(e => e.weight), 1e-9);

  const edges = g.edges.map(e => {
    const src = g.nodes.find(n => n.id === e.source);
    const width = 1 + 7 * (e.weight / maxW);
    return `<line x1="${px(src)}" y1="${py(src)}" x2="${cx}" y2="${cy}"
      stroke="${e.color}" stroke-width="${width.toFixed(2)}"
      stroke-opacity="${(0.25 + 0.6 * (e.weight / maxW)).toFixed(2)}">
      <title>${e.tooltip}</title></line>`;
  }).join("");

  const nodes = g.nodes.map(n => {
    if (n.kind === "percept") {
      return `<g><circle cx="${cx}" cy="${cy}" r="34" fill="${n.color}"
        stroke="#fff" stroke-width="2"/>
        <text x="${cx}" y="${cy - 2}" text-anchor="middle" fill="#fff"
          font-size="11" font-weight="700">NOW</text>
        <text x="${cx}" y="${cy + 12}" text-anchor="middle" fill="#fff"
          font-size="9">${(n.action || "").toUpperCase()}</text>
        <title>current percept — ${n.modalities.join(", ")}</title></g>`;
    }
    const rad = 9 + 13 * n.radius;
    const ring = n.is_expert
      ? `<circle cx="${px(n)}" cy="${py(n)}" r="${rad + 4}" fill="none"
          stroke="#ffd166" stroke-width="2"/>` : "";
    const reflexMark = n.mode === "REFLEXIVE"
      ? `<circle cx="${px(n) + rad * 0.75}" cy="${py(n) - rad * 0.75}" r="4"
          fill="#fff" stroke="${n.color}" stroke-width="1.5"/>` : "";
    const tip = `step ${n.step} — ${n.action} (${n.mode})
reward ${fmt(n.reward)}
similarity ${fmt(n.similarity)} × decay ${fmt(n.decay)} × boost ${n.boost.toFixed(1)} = ${n.weight.toFixed(3)}
age ${n.age} steps`;
    return `<g>${ring}
      <circle cx="${px(n)}" cy="${py(n)}" r="${rad}" fill="${n.color}"
        stroke="#0d1017" stroke-width="1.5"/>${reflexMark}
      <text x="${px(n)}" y="${py(n) + 4}" text-anchor="middle" fill="#fff"
        font-size="10" font-weight="600">${fmt(n.reward)}</text>
      <text x="${px(n)}" y="${py(n) + rad + 13}" text-anchor="middle"
        fill="#8b94a7" font-size="9">s${n.step}</text>
      <title>${tip}</title></g>`;
  }).join("");

  const note = r.penalty
    ? `<text x="14" y="24" fill="#d1483f" font-size="12" font-weight="600">
       memory advised ${r.penalty.recommended} — ${r.action} was taken instead</text>` : "";

  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%"
    style="max-height:430px">${note}${edges}${nodes}</svg>`;
}

function renderContribTable(snap) {
  const r = snap.result;
  const rows = (r && r.contributions) || [];
  if (!rows.length) { $("contribTable").innerHTML =
    `<tr><td class="empty">No contributing memories.</td></tr>`; return; }
  $("contribTable").innerHTML =
    `<tr><th>step</th><th>action</th><th>rew</th><th>sim</th>
         <th>decay</th><th>boost</th><th>weight</th></tr>` +
    rows.map(c => `<tr>
      <td>${c.step}</td>
      <td><span style="color:${META.action_colors[c.action]}">${c.action}</span>
          ${c.is_expert ? '<span class="pill">expert</span>' : ""}
          ${c.mode === "REFLEXIVE" ? '<span class="pill">reflex</span>' : ""}</td>
      <td>${fmt(c.reward)}</td><td>${fmt(c.similarity)}</td>
      <td>${fmt(c.decay)}</td><td>${c.boost.toFixed(1)}</td>
      <td><b>${c.weight.toFixed(3)}</b></td></tr>`).join("");
}

function renderTrace(snap) {
  const h = snap.history || [];
  if (!h.length) { $("trace").innerHTML = `<p class="empty">No steps yet.</p>`; return; }
  const W = 320, H = 130, pad = 6;
  const xs = i => pad + (W - 2 * pad) * (h.length === 1 ? 0.5 : i / (h.length - 1));
  const ys = v => H - pad - (H - 2 * pad) * v;
  const line = (key, color) => `<polyline fill="none" stroke="${color}"
    stroke-width="2" points="${h.map((e, i) =>
      `${xs(i).toFixed(1)},${ys(e[key] ?? 0.5).toFixed(1)}`).join(" ")}"/>`;
  const dots = h.map((e, i) => e.penalised
    ? `<circle cx="${xs(i).toFixed(1)}" cy="${ys(e.reward).toFixed(1)}" r="3"
        fill="#d1483f"/>` : "").join("");
  $("trace").innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%">
      <line x1="${pad}" y1="${ys(0.5)}" x2="${W - pad}" y2="${ys(0.5)}"
        stroke="#2a3040" stroke-dasharray="3 3"/>
      ${line("reward", "#4c8dff")}${line("threshold", "#2aa36b")}${dots}
    </svg>
    <div class="legend"><span><i style="background:#4c8dff"></i>reward</span>
      <span><i style="background:#2aa36b"></i>action threshold</span>
      <span><i style="background:#d1483f"></i>penalised step</span></div>`;
}

function renderHistory(snap) {
  const h = (snap.history || []).slice().reverse();
  if (!h.length) { $("historyTable").innerHTML =
    `<tr><td class="empty">No steps yet.</td></tr>`; return; }
  $("historyTable").innerHTML =
    `<tr><th>step</th><th>action</th><th>policy</th><th>reward</th><th>source</th></tr>` +
    h.map(e => `<tr>
      <td>${e.step}</td>
      <td><span style="color:${META.action_colors[e.action]}">${e.action}</span></td>
      <td>${e.policy}</td>
      <td${e.penalised ? ' class="warn"' : ""}>${fmt(e.reward)}</td>
      <td style="color:var(--muted)">${e.reward_source}</td></tr>`).join("");
}

const fmt = v => (v === null || v === undefined) ? "—" : Number(v).toFixed(3);

init();
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="MPCS v2 dashboard (stdlib web).")
    parser.add_argument("--port", type=int, default=8756)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    _reset_session("preset", "balanced", None)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"MPCS v2 dashboard running at {url}")
    print("Press Ctrl+C to stop.")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

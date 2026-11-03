"""Generate high-contrast, publication-grade figures & empirical benchmark plots for the MPCS-LocalKG Monograph.

Outputs into report/figures/:
  - fig1_cognitive_hierarchy.{svg,png,pdf}
  - fig2_extraction_pipeline.{svg,png,pdf}
  - fig3_memory_indexing_tide.{svg,png,pdf}
  - fig4_dual_persona_flowchart.{svg,png,pdf}
  - fig5_benchmark_plots.{svg,png,pdf}
"""

from __future__ import annotations

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

FIG_DIR = Path(r"D:\MyStuff\GitHub\MPCS\report\figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Clean academic typography with full Unicode math glyph coverage (DejaVu Sans primary)
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Segoe UI"],
    "axes.edgecolor": "#334155",
    "axes.linewidth": 1.15,
    "figure.facecolor": "#ffffff",
    "savefig.facecolor": "#ffffff",
})


def draw_box(ax, x, y, w, h, title="", lines=None, bg="#f8fafc", border="#334155",
             header_bg=None, header_fg="#ffffff", title_fg="#0f172a", text_fg="#1e293b",
             title_size=10.5, text_size=8.8, lw=1.7, radius=0.014):
    """Draw a high-contrast rounded box with optional colored header bar and well-spaced multi-line text."""
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.0,rounding_size={radius}",
        facecolor=bg, edgecolor=border, linewidth=lw, zorder=2
    )
    ax.add_patch(box)

    if header_bg:
        hh = min(0.056, h * 0.25)
        hbox = FancyBboxPatch(
            (x, y + h - hh), w, hh,
            boxstyle=f"round,pad=0.0,rounding_size={radius}",
            facecolor=header_bg, edgecolor=border, linewidth=lw, zorder=3
        )
        ax.add_patch(hbox)
        ax.text(x + w / 2, y + h - hh / 2, title, ha="center", va="center",
                fontsize=title_size, fontweight="bold", color=header_fg, zorder=4)
        body_top = y + h - hh - 0.008
    else:
        if title:
            title_band = min(0.044, h * 0.30)
            ax.text(x + w / 2, y + h - title_band * 0.52, title, ha="center", va="center",
                    fontsize=title_size, fontweight="bold", color=title_fg, zorder=4)
            body_top = y + h - title_band - 0.004
        else:
            body_top = y + h - 0.010

    if lines:
        n = len(lines)
        body_bot = y + 0.010
        avail = max(body_top - body_bot, 0.01)
        step = avail / n
        for idx, line in enumerate(lines):
            ly = body_top - (idx + 0.5) * step
            if isinstance(line, tuple):
                txt, col, weight = line
            else:
                txt, col, weight = line, text_fg, "normal"
            ax.text(x + w / 2, ly, txt, ha="center", va="center",
                    fontsize=text_size, fontweight=weight, color=col, zorder=4)


def draw_arrow(ax, x1, y1, x2, y2, color="#1e293b", lw=2.3, style="-|>", rad=0.0, label="", label_pos=(0, 0)):
    arr = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style, mutation_scale=16,
        linewidth=lw, color=color,
        connectionstyle=f"arc3,rad={rad}", zorder=5
    )
    ax.add_patch(arr)
    if label:
        lx = (x1 + x2) / 2 + label_pos[0]
        ly = (y1 + y2) / 2 + label_pos[1]
        ax.text(lx, ly, label, ha="center", va="center", fontsize=8.8,
                fontweight="bold", color=color,
                bbox=dict(boxstyle="round,pad=0.22", facecolor="#ffffff", edgecolor=color, lw=1.1),
                zorder=6)


def save_all(fig, stem: str):
    for ext in ("svg", "pdf", "png"):
        out = FIG_DIR / f"{stem}.{ext}"
        fig.savefig(out, dpi=300 if ext == "png" else None, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print(f"[OK] Saved {stem}.{{svg,pdf,png}}")


# ==========================================================================
# FIGURE 1: MPCS Dual-Process Cognitive Architecture & Semantic Foraging
# ==========================================================================
def build_fig1():
    fig, ax = plt.subplots(figsize=(15.5, 8.2))
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.5, 0.968, "FIGURE 1: MPCS DUAL-PROCESS COGNITIVE ARCHITECTURE & SEMANTIC FORAGING",
            ha="center", va="center", fontsize=14, fontweight="bold", color="#0f172a")
    ax.text(0.5, 0.935, "Neuro-Symbolic Loop: Multimodal Z-Number Binding  ->  System 1 Fast Gating  ->  Damasio VAD  ->  System 2 TIDE Activation",
            ha="center", va="center", fontsize=10, color="#475569")

    # Column 1: Afferent Input
    draw_box(ax, 0.015, 0.05, 0.225, 0.85, title="1. MULTIMODAL AFFERENT",
             header_bg="#0284c7", border="#0284c7", bg="#f0f9ff", title_size=10.5)

    channels = [
        ("Vision Channel (c = 1.00)", "object_type, motion, color", 0.72),
        ("Touch Channel (c = 0.95)", "contact, thermal, texture", 0.585),
        ("Audio Channel (c = 0.90)", "sound_type, audio_intensity", 0.45),
        ("Smell Channel (c = 0.70)", "odor_type, pleasantness", 0.315),
    ]
    for c_title, c_sub, cy in channels:
        draw_box(ax, 0.028, cy, 0.199, 0.11, title=c_title,
                 lines=[(c_sub, "#334155", "normal")],
                 bg="#ffffff", border="#0284c7", title_fg="#0369a1", title_size=9.2, text_size=8.4, lw=1.4)

    draw_box(ax, 0.028, 0.075, 0.199, 0.21, title="Afferent Z-Number Tuple",
             lines=[
                 ("Z = (Value, Confidence)", "#0f172a", "bold"),
                 ("Sim_Z(Q, M) = Sum min(c_q, c_m)", "#0369a1", "bold"),
                 ("Malleable: Absent slots skipped", "#475569", "normal"),
             ],
             bg="#e0f2fe", border="#0369a1", title_fg="#0c4a6e", title_size=9.4, text_size=8.2, lw=1.6)

    # Column 2 Top: System 1
    draw_box(ax, 0.285, 0.50, 0.33, 0.40, title="2A. SYSTEM 1: FAST GATING & REFLEXES",
             header_bg="#059669", border="#059669", bg="#ecfdf5", title_size=10.5)

    draw_box(ax, 0.30, 0.655, 0.142, 0.175, title="dlCBF Hash Gate",
             lines=[
                 ("4 x 1024 Buckets", "#0f172a", "bold"),
                 ("16-bit BLAKE2b", "#334155", "normal"),
                 ("8.8 KB | 17 us", "#047857", "bold"),
             ],
             bg="#ffffff", border="#059669", title_fg="#065f46", title_size=9.2, text_size=8.3, lw=1.4)

    draw_box(ax, 0.458, 0.655, 0.142, 0.175, title="HyST (G5) Filter",
             lines=[
                 ("Hard Safety Slots", "#0f172a", "bold"),
                 ("Soft Ordinal Span", "#334155", "normal"),
                 ("1.2% Unsafe Rate", "#047857", "bold"),
             ],
             bg="#ffffff", border="#059669", title_fg="#065f46", title_size=9.2, text_size=8.3, lw=1.4)

    draw_box(ax, 0.30, 0.52, 0.30, 0.115, title="Deterministic Safety Reflex Rules",
             lines=[
                 ("thermal=hot / contact=impact -> WITHDRAW (< 1 ms)", "#b91c1c", "bold"),
                 ("odor=smoke / sound=alarm -> ALERT (Zero Deliberation)", "#065f46", "normal"),
             ],
             bg="#ffffff", border="#10b981", title_fg="#064e3b", title_size=9.0, text_size=7.9, lw=1.4)

    # Column 2 Bottom: Damasio Somatic Markers
    draw_box(ax, 0.285, 0.05, 0.33, 0.41, title="2B. DAMASIO SOMATIC MARKERS (VAD)",
             header_bg="#d97706", border="#d97706", bg="#fffbeb", title_size=10.5)

    draw_box(ax, 0.30, 0.165, 0.142, 0.225, title="3D VAD Affect",
             lines=[
                 ("Valence V in [-1, 1]", "#92400e", "bold"),
                 ("Pleasure vs Distress", "#475569", "normal"),
                 ("Arousal A in [0, 1]", "#b45309", "bold"),
                 ("Peak Urgency Signal", "#475569", "normal"),
                 ("Dominance D in [0, 1]", "#92400e", "bold"),
             ],
             bg="#ffffff", border="#d97706", title_fg="#78350f", title_size=9.2, text_size=8.0, lw=1.4)

    draw_box(ax, 0.458, 0.165, 0.142, 0.225, title="Salience Gain",
             lines=[
                 ("Seed Modulation:", "#0f172a", "bold"),
                 ("Gain = 1 + 0.8 * A", "#b45309", "bold"),
                 ("Stakes Spread:", "#0f172a", "bold"),
                 ("max(V_a) - min(V_a)", "#334155", "normal"),
                 ("Boosts Urgent Seeds", "#047857", "bold"),
             ],
             bg="#ffffff", border="#d97706", title_fg="#78350f", title_size=9.2, text_size=8.0, lw=1.4)

    draw_box(ax, 0.30, 0.07, 0.30, 0.075, title="",
             lines=[
                 ("SHMF (G7) Auto-Relax + KERL (G8) Near-Miss Guard", "#78350f", "bold"),
             ],
             bg="#fef3c7", border="#d97706", text_size=8.2, lw=1.4)

    # Column 3: System 2 TIDE & Foraging
    draw_box(ax, 0.66, 0.05, 0.325, 0.85, title="3. SYSTEM 2: TIDE DELIBERATION (G9)",
             header_bg="#6d28d9", border="#6d28d9", bg="#f5f3ff", title_size=10.5)

    draw_box(ax, 0.675, 0.61, 0.295, 0.22, title="ACT-R Spreading Activation & Pruning",
             lines=[
                 ("A_j^(h+1) = A_j^(h) + Sum (A_i*y/deg(i))*w_e*(1+dt)^-0.2", "#4c1d95", "bold"),
                 ("Hops H = 3  |  Decay y = 0.50  |  Max Active = 80", "#1e293b", "normal"),
                 ("Typed Edges: Object(1.0), Place(1.0), Action(0.7)", "#334155", "normal"),
                 ("Dynamic Prune Cutoff: Floor = 0.05 x max(Seed)", "#be123c", "bold"),
             ],
             bg="#ffffff", border="#7c3aed", title_fg="#4c1d95", title_size=9.4, text_size=8.0, lw=1.4)

    draw_box(ax, 0.675, 0.31, 0.295, 0.275, title="Hills Semantic Patch Foraging & Routing",
             header_bg="#4338ca", border="#4338ca", bg="#eef2ff", title_size=9.4)

    draw_box(ax, 0.687, 0.328, 0.13, 0.185, title="Confident Core",
             lines=[
                 ("theta_c = 0.45*Max", "#0369a1", "bold"),
                 ("DIRECT Route:", "#0f172a", "bold"),
                 ("97.3% Clean Acc", "#047857", "bold"),
                 ("Acute Triage", "#475569", "normal"),
             ],
             bg="#ffffff", border="#0284c7", title_fg="#0369a1", title_size=8.8, text_size=7.9, lw=1.4)

    draw_box(ax, 0.828, 0.328, 0.13, 0.185, title="Exploratory",
             lines=[
                 ("theta_e = 0.18*Max", "#be185d", "bold"),
                 ("SUBGRAPH Route:", "#0f172a", "bold"),
                 ("76.1% Clean Acc", "#6d28d9", "bold"),
                 ("Differential KG", "#475569", "normal"),
             ],
             bg="#ffffff", border="#db2777", title_fg="#9d174d", title_size=8.8, text_size=7.9, lw=1.4)

    draw_box(ax, 0.675, 0.07, 0.295, 0.215, title="Anytime Budget & Passive Verification",
             lines=[
                 ("Urgent Budget B=3: Reads top 2.2 / 25.4 seeds", "#0f172a", "bold"),
                 ("Clean Acc Jumps: 64.8% (Full) -> 71.9% (B=3)!", "#047857", "bold"),
                 ("Unsafe Error Rate: 1.2% Invariant across all B", "#047857", "bold"),
                 ("Passive Thread Agreement: 73.2% Clean / 80.3% Noisy", "#4c1d95", "bold"),
             ],
             bg="#ffffff", border="#059669", title_fg="#065f46", title_size=9.2, text_size=8.0, lw=1.5)

    # Arrows connecting columns
    draw_arrow(ax, 0.24, 0.68, 0.285, 0.68, color="#0284c7", lw=2.5)
    draw_arrow(ax, 0.24, 0.26, 0.285, 0.26, color="#d97706", lw=2.5)
    draw_arrow(ax, 0.615, 0.68, 0.66, 0.68, color="#059669", lw=2.5)
    draw_arrow(ax, 0.615, 0.26, 0.66, 0.26, color="#d97706", lw=2.5)

    save_all(fig, "fig1_cognitive_hierarchy")


# ==========================================================================
# FIGURE 2: LocalKG Clinical & Affective Extraction Pipeline
# ==========================================================================
def build_fig2():
    fig, ax = plt.subplots(figsize=(15.5, 7.6))
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.5, 0.968, "FIGURE 2: LOCALKG CLINICAL & AFFECTIVE EXTRACTION PIPELINE",
            ha="center", va="center", fontsize=14, fontweight="bold", color="#0f172a")
    ax.text(0.5, 0.935, "Multi-Book PDF Parsing  ->  Air-Gapped Ollama Extraction  ->  Deterministic Validation & VAD Weighting  ->  1,106-Node KG",
            ha="center", va="center", fontsize=10, color="#475569")

    # Stage 1: Raw Sources
    draw_box(ax, 0.015, 0.05, 0.215, 0.85, title="1. CORPUS & OCR SANITIZATION",
             header_bg="#1e293b", border="#334155", bg="#f8fafc", title_size=10.0)

    draw_box(ax, 0.028, 0.67, 0.189, 0.15, title="Hahnemann (1820s)",
             lines=[
                 ("Materia Medica Pura (742 pp)", "#0f172a", "bold"),
                 ("Primary Proving Observations", "#475569", "normal"),
             ],
             bg="#ffffff", border="#475569", title_fg="#0f172a", title_size=9.3, text_size=8.3)

    draw_box(ax, 0.028, 0.495, 0.189, 0.15, title="Boericke Manual",
             lines=[
                 ("Pocket Manual (1,069 pp)", "#0f172a", "bold"),
                 ("Font Flags: Bold(3), Italic(2)", "#0369a1", "bold"),
             ],
             bg="#ffffff", border="#475569", title_fg="#0f172a", title_size=9.3, text_size=8.3)

    draw_box(ax, 0.028, 0.29, 0.189, 0.18, title="PubMed / MeSH Layer",
             lines=[
                 ("21 Peer-Reviewed Studies", "#047857", "bold"),
                 ("12 Remedies | RCTs & Reviews", "#0f172a", "bold"),
                 ("79 Clinical Condition Nodes", "#0369a1", "bold"),
             ],
             bg="#ecfdf5", border="#059669", title_fg="#065f46", title_size=9.3, text_size=8.2)

    draw_box(ax, 0.028, 0.075, 0.189, 0.19, title="OCR Sanitizer Engine",
             lines=[
                 ("clean_ocr_text() Pipeline", "#0f172a", "bold"),
                 ("Strips '(aft. 6 h.)' & \\ufffd", "#b91c1c", "bold"),
                 ("Zero Non-ASCII Noise", "#047857", "bold"),
             ],
             bg="#ffffff", border="#0284c7", title_fg="#0369a1", title_size=9.3, text_size=8.2)

    # Stage 2: LLM Extraction
    draw_box(ax, 0.26, 0.05, 0.225, 0.85, title="2. OLLAMA & VALIDATORS",
             header_bg="#0284c7", border="#0284c7", bg="#f0f9ff", title_size=10.0)

    draw_box(ax, 0.273, 0.65, 0.199, 0.17, title="Chunk Consolidation",
             lines=[
                 ("~2,600 chars per chunk", "#0f172a", "bold"),
                 ("Prepends ### Remedy: Section", "#0369a1", "bold"),
                 ("Preserves **bold** & _italic_", "#475569", "normal"),
             ],
             bg="#ffffff", border="#0284c7", title_fg="#0369a1", title_size=9.3, text_size=8.2)

    draw_box(ax, 0.273, 0.445, 0.199, 0.18, title="Air-Gapped Ollama SLM",
             lines=[
                 ("qwen2.5:7b-instruct (Local)", "#0f172a", "bold"),
                 ("Pydantic ChunkExtraction", "#0369a1", "bold"),
                 ("SHA256 DiskLLMCache", "#4338ca", "bold"),
             ],
             bg="#ffffff", border="#0284c7", title_fg="#0369a1", title_size=9.3, text_size=8.2)

    draw_box(ax, 0.273, 0.24, 0.199, 0.18, title="Quote & Grade Validator",
             lines=[
                 ("Verbatim Substring Check", "#047857", "bold"),
                 ("Markup Overrides LLM Grade", "#b91c1c", "bold"),
                 ("Rejects Hallucinated Quotes", "#475569", "normal"),
             ],
             bg="#ffffff", border="#059669", title_fg="#065f46", title_size=9.3, text_size=8.2)

    draw_box(ax, 0.273, 0.075, 0.199, 0.14, title="Modality Harvester",
             lines=[
                 ("AGGRAVATED_BY (< Worse)", "#b91c1c", "bold"),
                 ("AMELIORATED_BY (> Better)", "#047857", "bold"),
             ],
             bg="#fffbeb", border="#d97706", title_fg="#92400e", title_size=9.3, text_size=8.2)

    # Stage 3: VAD & Regression Weighting
    draw_box(ax, 0.515, 0.05, 0.225, 0.85, title="3. AFFECT & REGRESSION",
             header_bg="#059669", border="#059669", bg="#ecfdf5", title_size=10.0)

    draw_box(ax, 0.528, 0.61, 0.199, 0.21, title="VAD Affective Pooling",
             lines=[
                 ("Valence V = Mean(Tokens)", "#0f172a", "bold"),
                 ("Arousal A = Max(Tokens)", "#b91c1c", "bold"),
                 ("Dominance D = Mean(Tokens)", "#0f172a", "bold"),
                 ("Peak Arousal Drives Urgency", "#047857", "bold"),
             ],
             bg="#ffffff", border="#059669", title_fg="#065f46", title_size=9.3, text_size=8.2)

    draw_box(ax, 0.528, 0.40, 0.199, 0.185, title="Adjective Severity Score",
             lines=[
                 ("SEVERITY_ADJECTIVES Lexicon", "#0f172a", "bold"),
                 ("violent(0.95), severe(0.82)", "#475569", "normal"),
                 ("S_adj = 0.75*Peak + 0.25*Mean", "#047857", "bold"),
             ],
             bg="#ffffff", border="#059669", title_fg="#065f46", title_size=9.3, text_size=8.2)

    draw_box(ax, 0.528, 0.075, 0.199, 0.30, title="Linear Regression Weight",
             lines=[
                 ("W = 3.0 x [ 0.40*(G/3)", "#0f172a", "bold"),
                 ("          + 0.30*S_adj", "#0f172a", "bold"),
                 ("          + 0.20*A_peak", "#0f172a", "bold"),
                 ("          + 0.10*Conf ]", "#0f172a", "bold"),
                 ("Continuous Scale W in [1, 3]", "#047857", "bold"),
             ],
             bg="#fef3c7", border="#d97706", title_fg="#92400e", title_size=9.3, text_size=8.4, lw=1.7)

    # Stage 4: 9-Entity Knowledge Graph
    draw_box(ax, 0.77, 0.05, 0.215, 0.85, title="4. 9-ENTITY LOCALKG GRAPH",
             header_bg="#6d28d9", border="#6d28d9", bg="#f5f3ff", title_size=10.0)

    entities = [
        ("1. Medicine (42 Hubs)", "#0284c7", 0.75),
        ("2. Affective Symptom", "#7c3aed", 0.665),
        ("3. Cognitive Domain (7)", "#059669", 0.58),
        ("4. Physical Symptom", "#db2777", 0.495),
        ("5. Modality (Agg / Amel)", "#d97706", 0.41),
        ("6. Body Region (23)", "#ea580c", 0.325),
        ("7. Clinical Condition (79)", "#0891b2", 0.24),
        ("8. Sensation & 9. Etiology", "#be123c", 0.155),
    ]
    for e_txt, e_col, ey in entities:
        draw_box(ax, 0.783, ey, 0.189, 0.068, title="",
                 lines=[(e_txt, e_col, "bold")],
                 bg="#ffffff", border=e_col, text_size=8.6, lw=1.4)

    draw_box(ax, 0.783, 0.068, 0.189, 0.072, title="",
             lines=[
                 ("1,106 Nodes  |  2,024 Links", "#4c1d95", "bold"),
             ],
             bg="#ede9fe", border="#6d28d9", text_size=8.8, lw=1.6)

    # Connecting Arrows
    draw_arrow(ax, 0.23, 0.47, 0.26, 0.47, color="#1e293b", lw=2.4)
    draw_arrow(ax, 0.485, 0.47, 0.515, 0.47, color="#0284c7", lw=2.4)
    draw_arrow(ax, 0.74, 0.47, 0.77, 0.47, color="#059669", lw=2.4)

    save_all(fig, "fig2_extraction_pipeline")


# ==========================================================================
# FIGURE 3: Multi-Layer Retrieval & Spreading Activation Cascade
# ==========================================================================
def build_fig3():
    fig, ax = plt.subplots(figsize=(15.5, 8.8))
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.5, 0.968, "FIGURE 3: MULTI-LAYER PERCEPTUAL RETRIEVAL & SPREADING ACTIVATION CASCADE",
            ha="center", va="center", fontsize=14, fontweight="bold", color="#0f172a")
    ax.text(0.5, 0.935, "Progressive Funnel on Bank v3 (700 Records):  Layer 1 dlCBF  ->  Layer 2 HMGI + HyST (SHMF)  ->  Layer 3 KERL + TIDE",
            ha="center", va="center", fontsize=10, color="#475569")

    # Query Box at Top
    draw_box(ax, 0.22, 0.815, 0.56, 0.095, title="Incoming Perceptual Query Q  (Vision, Audio, Touch, Smell, Place)",
             lines=[("Canonical Summary Tuple of Z-Numbers:  (feature, value, modality_confidence)", "#0369a1", "bold")],
             bg="#e0f2fe", border="#0284c7", title_fg="#0f172a", title_size=10.2, text_size=9.0, lw=1.8)

    draw_arrow(ax, 0.50, 0.815, 0.50, 0.765, color="#0284c7", lw=2.4)

    # Layer 1: dlCBF
    draw_box(ax, 0.035, 0.555, 0.93, 0.21, title="LAYER 1: d-LEFT COUNTING BLOOM FILTER (dlCBF EXACT MEMBERSHIP GATE)",
             header_bg="#0284c7", border="#0284c7", bg="#f0f9ff", title_size=10.2)

    draw_box(ax, 0.055, 0.575, 0.28, 0.135, title="Hash Structure",
             lines=[
                 ("4 Subtables x 256/1024 Buckets", "#0f172a", "bold"),
                 ("Deep Space: 8.8 KB (12.8 B/rec)", "#0369a1", "bold"),
             ],
             bg="#ffffff", border="#0284c7", title_fg="#0369a1", title_size=9.4, text_size=8.5)

    draw_box(ax, 0.36, 0.575, 0.28, 0.135, title="Query Speed & Gate Rate",
             lines=[
                 ("Mean Latency: 0.017 ms (17 us)", "#047857", "bold"),
                 ("Blocks 61.9% Clean / 85.4% Noisy", "#b91c1c", "bold"),
             ],
             bg="#ffffff", border="#0284c7", title_fg="#0369a1", title_size=9.4, text_size=8.5)

    draw_box(ax, 0.665, 0.575, 0.28, 0.135, title="Architectural Role in G4-G9",
             lines=[
                 ("Used as O(1) Seen-Before Hint", "#0f172a", "bold"),
                 ("Never blocks near-miss retrieval!", "#047857", "bold"),
             ],
             bg="#ecfdf5", border="#059669", title_fg="#065f46", title_size=9.4, text_size=8.5)

    draw_arrow(ax, 0.50, 0.555, 0.50, 0.505, color="#059669", lw=2.4)

    # Layer 2: HMGI + HyST + SHMF
    draw_box(ax, 0.035, 0.285, 0.93, 0.22, title="LAYER 2: PARTITIONED HARD/SOFT FILTERING WITH AUTO-RELAXATION (G5 HyST -> G6 HMGI -> G7 SHMF)",
             header_bg="#059669", border="#059669", bg="#ecfdf5", title_size=10.2)

    draw_box(ax, 0.055, 0.305, 0.28, 0.145, title="Stage 2A: HMGI Modality Cut",
             lines=[
                 ("Scans active-modality buckets", "#0f172a", "bold"),
                 ("700 -> 636.7 records scanned", "#047857", "bold"),
                 ("Zero accuracy loss (Exact)", "#475569", "normal"),
             ],
             bg="#ffffff", border="#059669", title_fg="#065f46", title_size=9.4, text_size=8.3)

    draw_box(ax, 0.36, 0.305, 0.28, 0.145, title="Stage 2B: HyST Hard/Soft Split",
             lines=[
                 ("Hard Safety Slots: Exact Match", "#b91c1c", "bold"),
                 ("Soft Slots: Ordinal Closeness", "#0f172a", "bold"),
                 ("Unsafe drops 31.2% -> 1.2%!", "#047857", "bold"),
             ],
             bg="#ffffff", border="#059669", title_fg="#065f46", title_size=9.4, text_size=8.3)

    draw_box(ax, 0.665, 0.305, 0.28, 0.145, title="Stage 2C: SHMF Auto-Relax",
             lines=[
                 ("If strict filter empty & not urgent:", "#0f172a", "normal"),
                 ("Re-runs divergent (discount=0.6)", "#0369a1", "bold"),
                 ("Clean Acc jumps 64.0% -> 75.6%!", "#047857", "bold"),
             ],
             bg="#ffffff", border="#059669", title_fg="#065f46", title_size=9.4, text_size=8.3)

    draw_arrow(ax, 0.50, 0.285, 0.50, 0.235, color="#6d28d9", lw=2.4)

    # Layer 3: KERL + TIDE
    draw_box(ax, 0.035, 0.015, 0.93, 0.22, title="LAYER 3: NEAR-MISS GUARD & TIME-BOUNDED SPREADING ACTIVATION (G8 KERL -> G9 TIDE)",
             header_bg="#6d28d9", border="#6d28d9", bg="#f5f3ff", title_size=10.2)

    draw_box(ax, 0.055, 0.035, 0.28, 0.145, title="KERL Near-Miss Guard",
             lines=[
                 ("Requires decisive modality cover", "#0f172a", "bold"),
                 ("Fuses Semantic + Affect + Graph", "#4c1d95", "bold"),
                 ("Clean Unsafe: 1.7% | Acc: 75.0%", "#047857", "bold"),
             ],
             bg="#ffffff", border="#6d28d9", title_fg="#4c1d95", title_size=9.4, text_size=8.3)

    draw_box(ax, 0.36, 0.035, 0.28, 0.145, title="TIDE Spreading Activation",
             lines=[
                 ("3-Hop Typed Episode Graph", "#0f172a", "bold"),
                 ("Sufficiency Route: DIRECT 97.3%", "#047857", "bold"),
                 ("SUBGRAPH 76.1% | UNGROUNDED", "#4c1d95", "bold"),
             ],
             bg="#ffffff", border="#6d28d9", title_fg="#4c1d95", title_size=9.4, text_size=8.3)

    draw_box(ax, 0.665, 0.035, 0.28, 0.145, title="Anytime Deadline (B=3 Urgent)",
             lines=[
                 ("Reads top 2.2 / 25.4 candidates", "#0f172a", "bold"),
                 ("Urgent Acc: 71.9% (vs 64.8% Full)", "#047857", "bold"),
                 ("Passive Check Agreement: 73.2%", "#0369a1", "bold"),
             ],
             bg="#ffffff", border="#6d28d9", title_fg="#4c1d95", title_size=9.4, text_size=8.3)

    save_all(fig, "fig3_memory_indexing_tide")


# ==========================================================================
# FIGURE 4: Dual-Persona Query Routing & Subgraph Edge Partitioning
# ==========================================================================
def build_fig4():
    fig, ax = plt.subplots(figsize=(15.5, 8.6))
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.5, 0.968, "FIGURE 4: DUAL-PERSONA QUERY ROUTING & SUBGRAPH EDGE PARTITIONING",
            ha="center", va="center", fontsize=14, fontweight="bold", color="#0f172a")
    ax.text(0.5, 0.935, "In-Browser TIDE Spreading Activation over 1,106 Nodes & 2,024 Links:  Confident Core vs. Exploratory Expansion",
            ha="center", va="center", fontsize=10, color="#475569")

    # Top Row: Query -> Seed -> Spread
    draw_box(ax, 0.035, 0.735, 0.27, 0.16, title="1. Clinical Symptom Query",
             lines=[
                 ('"throbbing headache worse noise"', "#0f172a", "bold"),
                 ("Tokenized & Matched against", "#475569", "normal"),
                 ("1,106 Nodes in LocalKG", "#0369a1", "bold"),
             ],
             bg="#f0f9ff", border="#0284c7", title_fg="#0369a1", title_size=9.6, text_size=8.4)

    draw_arrow(ax, 0.305, 0.815, 0.355, 0.815, color="#0284c7", lw=2.4)

    draw_box(ax, 0.355, 0.735, 0.29, 0.16, title="2. Affect-Boosted Seed Energy",
             lines=[
                 ("Seed(s) = (Hits/|Q|) x (1 + 0.8*A)", "#0f172a", "bold"),
                 ("          x (Weight / 2.0)", "#0f172a", "bold"),
                 ("High-Arousal Symptoms Dominate", "#b45309", "bold"),
             ],
             bg="#fffbeb", border="#d97706", title_fg="#92400e", title_size=9.6, text_size=8.4)

    draw_arrow(ax, 0.645, 0.815, 0.695, 0.815, color="#d97706", lw=2.4)

    draw_box(ax, 0.695, 0.735, 0.27, 0.16, title="3. 2-Hop Spreading Activation",
             lines=[
                 ("E(v) = max_{u in N(v)} [E(u)*y / deg(u)]", "#4c1d95", "bold"),
                 ("Hop Decay y = 0.58", "#0f172a", "bold"),
                 ("Degree-Normalized Hub Control", "#475569", "normal"),
             ],
             bg="#f5f3ff", border="#6d28d9", title_fg="#4c1d95", title_size=9.6, text_size=8.4)

    # Branching Arrows to Personas
    draw_arrow(ax, 0.83, 0.735, 0.27, 0.625, color="#059669", lw=2.4, rad=-0.10,
               label="CONFIDENT PERSONA (Acute Triage)", label_pos=(-0.06, 0.025))
    draw_arrow(ax, 0.83, 0.735, 0.73, 0.625, color="#db2777", lw=2.4, rad=0.04,
               label="EXPLORATORY PERSONA (Differential)", label_pos=(0.04, 0.025))

    # Middle Row: Two Persona Boxes
    draw_box(ax, 0.045, 0.355, 0.43, 0.265, title="CONFIDENT CORE GATING (PATCH EXPLOITATION)",
             header_bg="#059669", border="#059669", bg="#ecfdf5", title_size=9.8)

    draw_box(ax, 0.065, 0.375, 0.39, 0.175, title="",
             lines=[
                 ("Cutoff Threshold:  theta_conf = 0.45 x max(SeedScore)", "#065f46", "bold"),
                 ("- Prunes > 95% of peripheral associative nodes", "#0f172a", "normal"),
                 ("- Isolates highest-grade keynote Remedies & Symptoms", "#0f172a", "normal"),
                 ("- Best for acute emergency & unmistakable keynotes", "#047857", "bold"),
             ],
             bg="#ffffff", border="#10b981", text_size=8.6, lw=1.4)

    draw_box(ax, 0.525, 0.355, 0.43, 0.265, title="EXPLORATORY EXPANSION (CROSS-PATCH TRAVERSAL)",
             header_bg="#db2777", border="#db2777", bg="#fdf2f8", title_size=9.8)

    draw_box(ax, 0.545, 0.375, 0.39, 0.175, title="",
             lines=[
                 ("Cutoff Threshold:  theta_expl = 0.18 x max(SeedScore)", "#9d174d", "bold"),
                 ("- Retains secondary modalities, regions & conditions", "#0f172a", "normal"),
                 ("- Surfaces comparative & complementary remedy hubs", "#0f172a", "normal"),
                 ("- Best for chronic multi-system differential diagnosis", "#be185d", "bold"),
             ],
             bg="#ffffff", border="#f472b6", text_size=8.6, lw=1.4)

    draw_arrow(ax, 0.26, 0.355, 0.35, 0.265, color="#059669", lw=2.2)
    draw_arrow(ax, 0.74, 0.355, 0.65, 0.265, color="#db2777", lw=2.2)

    # Bottom Row: Topological Edge Partitioning
    draw_box(ax, 0.035, 0.03, 0.93, 0.235, title="4. TOPOLOGICAL EDGE PARTITIONING & 60 FPS HARDWARE-ACCELERATED CANVAS",
             header_bg="#1e293b", border="#334155", bg="#f8fafc", title_size=10.0)

    draw_box(ax, 0.055, 0.05, 0.28, 0.15, title="Internal Subgraph Edges (E_int)",
             lines=[
                 ("u in V_active  AND  v in V_active", "#065f46", "bold"),
                 ("Solid Emerald Green (#06D6A0)", "#047857", "bold"),
                 ("Width: 2.6 px  |  Alpha: 0.96", "#334155", "normal"),
             ],
             bg="#ecfdf5", border="#059669", title_fg="#065f46", title_size=9.2, text_size=8.3)

    draw_box(ax, 0.36, 0.05, 0.28, 0.15, title="External Bridging Edges (E_ext)",
             lines=[
                 ("Exactly ONE endpoint in V_active", "#9d174d", "bold"),
                 ("Dashed Electric Pink (#FF79C6)", "#be185d", "bold"),
                 ("Dash [5, 3]  |  Alpha: 0.92", "#334155", "normal"),
             ],
             bg="#fdf2f8", border="#db2777", title_fg="#9d174d", title_size=9.2, text_size=8.3)

    draw_box(ax, 0.665, 0.05, 0.28, 0.15, title="3 Visualizer Builds Generated",
             lines=[
                 ("1. Simple TIDE (kg_full_materia_medica)", "#0369a1", "bold"),
                 ("2. Dual-Persona (kg_full_..._cleaned)", "#4c1d95", "bold"),
                 ("3. Pure KG Showcase (docs/kg_full_...)", "#0f172a", "bold"),
             ],
             bg="#ffffff", border="#0284c7", title_fg="#0369a1", title_size=9.2, text_size=8.1)

    save_all(fig, "fig4_dual_persona_flowchart")


# ==========================================================================
# FIGURE 5: Empirical Quantitative Benchmark Plots (2x2 Publication Grid)
# ==========================================================================
def build_fig5():
    fig, axes = plt.subplots(2, 2, figsize=(15.0, 10.2))
    fig.subplots_adjust(hspace=0.36, wspace=0.24, top=0.90, bottom=0.07)

    fig.suptitle("FIGURE 5: EMPIRICAL QUANTITATIVE BENCHMARK SUITE (BANK V3: 700 RECORDS, 960 QUERIES)",
                 fontsize=14, fontweight="bold", color="#0f172a", y=0.965)

    # ------------------------------------------------------------------
    # Panel A: Clean vs Noisy Accuracy across Indexing & MPCS Generations
    # ------------------------------------------------------------------
    ax = axes[0, 0]
    models = ["Exact\nKNN", "BM25\nIndex", "dlCBF\nGate", "B2\nBase v2", "G4\nCore v2", "G5\nHyST", "G7\nSHMF", "G8\nKERL", "G9\nTIDE"]
    clean_acc = [94.8, 94.4, 50.2, 79.6, 34.2, 64.0, 75.6, 75.0, 75.0]
    noisy_acc = [87.9, 88.1, 29.4, 73.3, 34.6, 46.7, 68.1, 67.7, 67.7]

    x = np.arange(len(models))
    w = 0.38
    b1 = ax.bar(x - w/2, clean_acc, w, label="Clean Queries (480)", color="#0284c7", edgecolor="#0f172a", linewidth=0.8)
    b2 = ax.bar(x + w/2, noisy_acc, w, label="Noisy Queries (480)", color="#38bdf8", edgecolor="#0f172a", linewidth=0.8)

    ax.set_title("(A) Action Recommendation Accuracy: Clean vs. Noisy (%)", fontsize=11.2, fontweight="bold", color="#0f172a", pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=8.6, fontweight="bold", color="#1e293b")
    ax.set_ylabel("Accuracy (%)", fontsize=10, fontweight="bold", color="#1e293b")
    ax.set_ylim(0, 114)
    ax.grid(axis="y", linestyle="--", alpha=0.4, color="#94a3b8")
    ax.legend(loc="upper right", frameon=True, facecolor="#ffffff", edgecolor="#cbd5e1", fontsize=8.8)

    for bar in b1:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 1.5, f"{h:.1f}", ha="center", va="bottom", fontsize=7.4, fontweight="bold", color="#0369a1")
    for bar in b2:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 1.5, f"{h:.1f}", ha="center", va="bottom", fontsize=7.4, color="#0284c7")

    # ------------------------------------------------------------------
    # Panel B: Safety Contraindication Error Rate (Unsafe Action %)
    # ------------------------------------------------------------------
    ax = axes[0, 1]
    gen_models = ["G1\nBasic", "G2\nBloom", "G4\nCore v2", "G6\nHMGI", "G7\nSHMF", "G8\nKERL", "G9\nTIDE", "G5\nHyST", "TIDE\n(B=3)"]
    unsafe_clean = [47.0, 62.0, 31.2, 31.2, 2.1, 1.7, 1.7, 1.2, 1.2]
    unsafe_noisy = [41.0, 60.0, 30.4, 30.4, 3.8, 3.8, 3.8, 1.2, 1.2]

    x2 = np.arange(len(gen_models))
    b3 = ax.bar(x2 - w/2, unsafe_clean, w, label="Clean Unsafe %", color="#e11d48", edgecolor="#0f172a", linewidth=0.8)
    b4 = ax.bar(x2 + w/2, unsafe_noisy, w, label="Noisy Unsafe %", color="#fb7185", edgecolor="#0f172a", linewidth=0.8)

    ax.set_title("(B) Safety Violation Rate (Unsafe Action % - Lower is Safer)", fontsize=11.2, fontweight="bold", color="#0f172a", pad=10)
    ax.set_xticks(x2)
    ax.set_xticklabels(gen_models, fontsize=8.6, fontweight="bold", color="#1e293b")
    ax.set_ylabel("Unsafe Error Rate (%)", fontsize=10, fontweight="bold", color="#1e293b")
    ax.set_ylim(0, 72)
    ax.grid(axis="y", linestyle="--", alpha=0.4, color="#94a3b8")
    ax.legend(loc="upper right", frameon=True, facecolor="#ffffff", edgecolor="#cbd5e1", fontsize=8.8)

    for bar in b3:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 1.2, f"{h:.1f}%", ha="center", va="bottom", fontsize=7.4, fontweight="bold", color="#be123c")

    # ------------------------------------------------------------------
    # Panel C: TIDE Anytime Budget Curve (The "Less-is-More" Foraging Effect)
    # ------------------------------------------------------------------
    ax = axes[1, 0]
    budgets = ["B=3\n(2.2 read)", "B=5\n(3.3 read)", "B=10\n(5.6 read)", "B=20\n(9.2 read)", "B=50\n(14.4 read)", "Full\n(25.4 read)"]
    tide_clean_acc = [71.9, 70.6, 67.9, 67.3, 65.4, 64.8]
    tide_noisy_acc = [50.8, 49.6, 48.5, 47.3, 46.9, 46.2]
    tide_agree_clean = [73.2, 71.8, 76.1, 75.9, 77.1, 100.0]

    xb = np.arange(len(budgets))
    ax.plot(xb, tide_clean_acc, marker="o", linewidth=2.6, markersize=8, color="#059669", label="Urgent Clean Accuracy (%)")
    ax.plot(xb, tide_noisy_acc, marker="s", linewidth=2.6, markersize=7, color="#0284c7", label="Urgent Noisy Accuracy (%)")
    ax.plot(xb, tide_agree_clean, marker="^", linewidth=2.0, linestyle="--", markersize=7, color="#7c3aed", label="Passive Full-Read Agreement (%)")

    for i, txt in enumerate(tide_clean_acc):
        ax.annotate(f"{txt:.1f}%", (xb[i], tide_clean_acc[i] - 5.2), ha="center", fontsize=8.2, fontweight="bold", color="#065f46")
    for i, txt in enumerate(tide_noisy_acc):
        ax.annotate(f"{txt:.1f}%", (xb[i], tide_noisy_acc[i] - 5.2), ha="center", fontsize=8.2, fontweight="bold", color="#0369a1")
    for i, txt in enumerate(tide_agree_clean):
        ax.annotate(f"{txt:.1f}%", (xb[i], tide_agree_clean[i] + 2.4), ha="center", fontsize=8.0, fontweight="bold", color="#6d28d9")

    ax.set_title("(C) TIDE Anytime Budget Curve: Accuracy & Passive Agreement", fontsize=11.2, fontweight="bold", color="#0f172a", pad=10)
    ax.set_xticks(xb)
    ax.set_xticklabels(budgets, fontsize=8.6, fontweight="bold", color="#1e293b")
    ax.set_ylabel("Percentage (%)", fontsize=10, fontweight="bold", color="#1e293b")
    ax.set_ylim(25, 110)
    ax.grid(True, linestyle="--", alpha=0.4, color="#94a3b8")
    ax.legend(loc="lower left", frameon=True, facecolor="#ffffff", edgecolor="#cbd5e1", fontsize=8.5)

    # ------------------------------------------------------------------
    # Panel D: TIDE Sufficiency Routing & Deep Memory Footprint
    # ------------------------------------------------------------------
    ax = axes[1, 1]
    routes = ["DIRECT Route\n(7.7% Cln / 4.2% Nsy)", "SUBGRAPH Route\n(88.8% Cln / 90.4% Nsy)", "UNGROUNDED\n(3.5% Cln / 5.4% Nsy)"]
    r_clean_acc = [97.3, 76.1, 0.0]
    r_noisy_acc = [90.0, 69.8, 11.5]

    xr = np.arange(len(routes))
    b5 = ax.bar(xr - w/2, r_clean_acc, w, label="Clean Accuracy on Route (%)", color="#6d28d9", edgecolor="#0f172a", linewidth=0.8)
    b6 = ax.bar(xr + w/2, r_noisy_acc, w, label="Noisy Accuracy on Route (%)", color="#a855f7", edgecolor="#0f172a", linewidth=0.8)

    for bar in b5:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 1.8, f"{h:.1f}%", ha="center", va="bottom", fontsize=8.6, fontweight="bold", color="#4c1d95")
    for bar in b6:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 1.8, f"{h:.1f}%", ha="center", va="bottom", fontsize=8.6, fontweight="bold", color="#6d28d9")

    ax.set_title("(D) TIDE Epistemic Sufficiency Routing Accuracy (Urgent Off)", fontsize=11.2, fontweight="bold", color="#0f172a", pad=10)
    ax.set_xticks(xr)
    ax.set_xticklabels(routes, fontsize=8.5, fontweight="bold", color="#1e293b")
    ax.set_ylabel("Accuracy on Route (%)", fontsize=10, fontweight="bold", color="#1e293b")
    ax.set_ylim(0, 114)
    ax.grid(axis="y", linestyle="--", alpha=0.4, color="#94a3b8")
    ax.legend(loc="upper right", frameon=True, facecolor="#ffffff", edgecolor="#cbd5e1", fontsize=8.8)

    save_all(fig, "fig5_benchmark_plots")


if __name__ == "__main__":
    build_fig1()
    build_fig2()
    build_fig3()
    build_fig4()
    build_fig5()
    print("All 5 high-contrast figure suites generated successfully.")

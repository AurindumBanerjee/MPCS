"""Generate and extract all 17 PNG figures for the updated MPCS & LocalKG deck.

Outputs into report/PPT/figures/:
  - 4 copied raster assets from report/figures/
  - 10 300-DPI vector diagram/chart crops extracted from report/BTP_Report.pdf
  - 3 300-DPI Matplotlib charts loaded dynamically from docs/ablation_and_indexing_study.json
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # type: ignore[no-redef]


REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_FIG_DIR = REPO_ROOT / "report" / "figures"
PDF_PATH = REPO_ROOT / "report" / "BTP_Report.pdf"
STUDY_JSON_PATH = REPO_ROOT / "docs" / "ablation_and_indexing_study.json"
OUT_DIR = REPO_ROOT / "report" / "PPT" / "figures"

# Palette and typography matching the warm slide theme
BG_WHITE = "#FFFFFF"
INK_DARK = "#16140F"
MUTED_TEXT = "#5C5649"
GRID_COLOR = "#E5E2D8"
STEEL_BLUE = "#2E5B88"
OCHRE = "#B86B28"
CRIMSON = "#B83A2E"
EMERALD = "#2B6E46"
HIGHLIGHT_GREEN_BG = "#EDF6F0"
HIGHLIGHT_RED_BG = "#FDF0EE"
HIGHLIGHT_BLUE_BG = "#EEF4FA"

COPY_ASSETS = (
    "iitj_logo.png",
    "kg_single_remedy.png",
    "kg_full.png",
    "ui_pipeline.png",
)

# Verified against page text/word/drawing bounding boxes in report/BTP_Report.pdf
PDF_CLIP_SPECS: tuple[tuple[str, int, tuple[float, float, float, float]], ...] = (
    ("fig01_architecture.png", 14, (72.0, 332.0, 534.0, 640.5)),
    ("fig02_cognitive_step.png", 17, (117.5, 396.0, 488.5, 489.5)),
    ("fig03_retrieval_cascade.png", 18, (121.0, 235.5, 458.0, 555.5)),
    ("fig04_localkg_pipeline.png", 23, (118.0, 101.0, 484.0, 234.5)),
    ("fig05_kg_edge_stats.png", 25, (76.0, 58.0, 528.0, 259.0)),
    ("fig06_persona_partition.png", 28, (104.0, 343.0, 504.0, 475.0)),
    ("fig07_bridge_stages.png", 29, (110.0, 543.0, 496.0, 637.5)),
    ("fig08_bankv3_acc_unsafe.png", 32, (71.0, 61.0, 537.5, 391.5)),
    ("fig09_bankv3_tide_budget.png", 33, (108.0, 382.0, 501.0, 556.5)),
    ("fig12_mmkg_tide_budget.png", 37, (101.0, 381.0, 507.0, 544.5)),
)


def configure_matplotlib_style() -> None:
    """Configure clean warm publication styling without em-dashes."""
    plt.rcParams.update(
        {
            "figure.facecolor": BG_WHITE,
            "axes.facecolor": BG_WHITE,
            "axes.edgecolor": INK_DARK,
            "axes.labelcolor": INK_DARK,
            "axes.linewidth": 0.9,
            "xtick.color": INK_DARK,
            "ytick.color": INK_DARK,
            "text.color": INK_DARK,
            "font.family": "sans-serif",
            "font.sans-serif": ["Segoe UI", "Arial", "DejaVu Sans"],
            "axes.titlesize": 13.5,
            "axes.labelsize": 10.5,
            "xtick.labelsize": 9.2,
            "ytick.labelsize": 9.2,
            "legend.fontsize": 9.2,
            "savefig.facecolor": BG_WHITE,
            "savefig.dpi": 300,
        }
    )


def style_axes(ax: plt.Axes, grid_axis: str = "y") -> None:
    """Apply crisp spines, subtle gridlines, and ink-dark ticks."""
    ax.set_facecolor(BG_WHITE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(INK_DARK)
    ax.spines["bottom"].set_color(INK_DARK)
    ax.set_axisbelow(True)
    ax.grid(axis=grid_axis, color=GRID_COLOR, linestyle="--", linewidth=0.75, alpha=0.9)
    ax.tick_params(colors=INK_DARK, length=3.5, width=0.8)


def copy_raster_assets(src_dir: Path, dst_dir: Path) -> list[Path]:
    """Copy existing raster PNG figures into the PPT figures directory."""
    written: list[Path] = []
    for fname in COPY_ASSETS:
        src = src_dir / fname
        if not src.exists():
            raise FileNotFoundError(f"Missing source figure: {src}")
        dst = dst_dir / fname
        shutil.copy2(src, dst)
        written.append(dst)
    return written


def extract_pdf_figures(pdf_path: Path, dst_dir: Path, dpi: int = 300) -> list[Path]:
    """Extract verified vector/text clip boxes from report/BTP_Report.pdf at 300 DPI."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"Missing PDF report: {pdf_path}")

    written: list[Path] = []
    doc = fitz.open(str(pdf_path))
    try:
        for fname, page_idx, coords in PDF_CLIP_SPECS:
            page = doc[page_idx]
            clip = fitz.Rect(*coords)
            pix = page.get_pixmap(dpi=dpi, clip=clip, alpha=False)
            out_path = dst_dir / fname
            pix.save(str(out_path))
            written.append(out_path)
    finally:
        doc.close()
    return written


def load_study_data(json_path: Path) -> dict[str, Any]:
    """Load verified MMKG evaluation results from docs/ablation_and_indexing_study.json."""
    if not json_path.exists():
        raise FileNotFoundError(f"Missing study JSON: {json_path}")
    with json_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def plot_study_a_mmkg(data: dict[str, Any], out_path: Path) -> None:
    """Generate fig10_mmkg_study_a.png comparing indexing and MPCS methods on MMKG."""
    study_a = data["study_a_extended_indexing_mmkg"]
    ds = data["dataset_stats"]

    ordered_keys: list[tuple[str, str]] = [
        ("Exact KNN (Cosine)", "Exact\nKNN"),
        ("BM25 Inverted Index", "BM25"),
        ("dlCBF Gate", "dlCBF\nGate"),
        ("Cuckoo Filter Gate", "Cuckoo\nFilter Gate"),
        ("SimHash LSH (64-bit)", "SimHash\nLSH"),
        ("Slot Inverted Bitset", "Slot Inv.\nBitset"),
        ("NSW Proximity Graph", "NSW\nGraph"),
        ("B2 Global Top-5", "MPCS\nB2"),
        ("G5 HyST", "G5\nHyST"),
        ("G7 SHMF", "G7\nSHMF"),
        ("G9 TIDE", "G9\nTIDE"),
    ]

    labels = [disp for _, disp in ordered_keys]
    clean_acc = [float(study_a[k]["clean_acc"]) for k, _ in ordered_keys]
    noisy_acc = [float(study_a[k]["noisy_acc"]) for k, _ in ordered_keys]
    clean_unsafe = [float(study_a[k]["clean_unsafe"]) for k, _ in ordered_keys]

    x = np.arange(len(labels), dtype=float)
    bar_w = 0.26

    fig, ax = plt.subplots(figsize=(12.4, 5.5))
    try:
        style_axes(ax, grid_axis="y")

        b1 = ax.bar(x - bar_w, clean_acc, width=bar_w, color=STEEL_BLUE, edgecolor=INK_DARK, linewidth=0.4, label="Clean Accuracy (%)")
        b2 = ax.bar(x, noisy_acc, width=bar_w, color=OCHRE, edgecolor=INK_DARK, linewidth=0.4, label="Noisy Accuracy (%)")
        b3 = ax.bar(x + bar_w, clean_unsafe, width=bar_w, color=CRIMSON, edgecolor=INK_DARK, linewidth=0.4, label="Clean Unsafe Error (%)")

        # Vertical bar value labels prevent adjacent-column overlap across 11 methods
        for bars in (b1, b2, b3):
            for rect in bars:
                val = rect.get_height()
                ax.text(
                    rect.get_x() + rect.get_width() / 2.0,
                    val + 1.3,
                    f"{val:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=7.6,
                    color=INK_DARK,
                    rotation=90,
                )

        # Separator between classical/approximate indexing methods and MPCS generations
        ax.axvline(6.5, color=MUTED_TEXT, linestyle=":", linewidth=1.1, zorder=2)
        ax.text(3.0, 108.5, "Indexing Baselines", ha="center", va="bottom", fontsize=9.2, fontweight="bold", color=STEEL_BLUE)
        ax.text(8.5, 108.5, "MPCS Generations", ha="center", va="bottom", fontsize=9.2, fontweight="bold", color=OCHRE)

        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8.8)
        ax.set_ylabel("Percentage (%)", fontweight="bold")
        ax.set_ylim(0, 116)
        ax.set_yticks(range(0, 101, 20))

        ax.set_title(
            f"Study A: Perceptual Indexing vs. MPCS Generations on MMKG (N={ds['total_occurrences']}, {ds['clean_query_count']} queries/split)",
            fontfamily="Georgia",
            fontweight="bold",
            fontsize=13.0,
            pad=28,
            loc="left",
            color=INK_DARK,
        )
        ax.legend(
            loc="upper right",
            bbox_to_anchor=(1.0, 1.07),
            ncol=3,
            frameon=True,
            facecolor=BG_WHITE,
            edgecolor=GRID_COLOR,
        )

        fig.tight_layout()
        fig.savefig(str(out_path), dpi=300, bbox_inches="tight")
    finally:
        plt.close(fig)


def plot_study_b1_mmkg(data: dict[str, Any], out_path: Path) -> None:
    """Generate fig11_mmkg_study_b1.png showing Study B1 G9 TIDE 8-variant ablation."""
    rows = data["study_b_mpcs_tide_ablation_mmkg"]

    label_map = {
        "Full G9 TIDE (Urgent=False)": "Full G9 TIDE (Urgent=False)",
        "w/o TIDE Spread (hops=0, w_g=0)": "w/o TIDE Spread (hops=0)",
        "w/o VAD Affect & Salience (salience_gain=0, affect=False)": "w/o VAD Affect & Salience",
        "w/o KERL Near-Miss Guard": "w/o KERL Near-Miss Guard",
        "w/o SHMF Auto-Relaxation": "w/o SHMF Auto-Relaxation",
        "w/o HyST Hard Slots (Soft Only)": "w/o HyST Hard Slots (Soft Only)",
        "w/o Expert Grade Boost (boost=1.0)": "w/o Expert Grade Boost",
        "w/o Full-Read (Urgent B=3)": "w/o Full-Read (Urgent B=3)",
    }

    labels = [label_map.get(r["variant"], r["variant"]) for r in rows]
    clean_acc = [float(r["clean_acc"]) for r in rows]
    noisy_acc = [float(r["noisy_acc"]) for r in rows]
    clean_unsafe = [float(r["clean_unsafe"]) for r in rows]
    clean_lat = [float(r["clean_lat_ms"]) for r in rows]

    y = np.arange(len(rows), dtype=float)
    bar_h = 0.25

    fig, ax = plt.subplots(figsize=(11.4, 6.0))
    try:
        style_axes(ax, grid_axis="x")

        # Subtle highlight bands for key diagnostic rows
        for idx, r in enumerate(rows):
            if "Urgent B=3" in r["variant"]:
                ax.axhspan(idx - 0.44, idx + 0.44, color=HIGHLIGHT_GREEN_BG, zorder=0)
            elif "Hard Slots" in r["variant"]:
                ax.axhspan(idx - 0.44, idx + 0.44, color=HIGHLIGHT_RED_BG, zorder=0)
            elif "Full G9 TIDE" in r["variant"]:
                ax.axhspan(idx - 0.44, idx + 0.44, color=HIGHLIGHT_BLUE_BG, zorder=0)

        b1 = ax.barh(y - bar_h, clean_acc, height=bar_h, color=STEEL_BLUE, edgecolor=INK_DARK, linewidth=0.4, label="Clean Accuracy (%)")
        b2 = ax.barh(y, noisy_acc, height=bar_h, color=OCHRE, edgecolor=INK_DARK, linewidth=0.4, label="Noisy Accuracy (%)")
        b3 = ax.barh(y + bar_h, clean_unsafe, height=bar_h, color=CRIMSON, edgecolor=INK_DARK, linewidth=0.4, label="Clean Unsafe Error (%)")

        for bars in (b1, b2, b3):
            for rect in bars:
                val = rect.get_width()
                ax.text(
                    val + 1.0,
                    rect.get_y() + rect.get_height() / 2.0,
                    f"{val:.1f}%",
                    ha="left",
                    va="center",
                    fontsize=7.8,
                    color=INK_DARK,
                )

        # Callouts grounded directly in JSON values
        urgent_idx = next(i for i, r in enumerate(rows) if "Urgent B=3" in r["variant"])
        hard_idx = next(i for i, r in enumerate(rows) if "Hard Slots" in r["variant"])
        full_idx = next(i for i, r in enumerate(rows) if "Full G9 TIDE" in r["variant"])

        ax.text(
            99.0,
            urgent_idx - 0.02,
            f"Best: {clean_acc[urgent_idx]:.1f}% Clean / {noisy_acc[urgent_idx]:.1f}% Noisy",
            ha="left",
            va="center",
            fontsize=8.3,
            fontweight="bold",
            color=EMERALD,
            bbox=dict(boxstyle="round,pad=0.25", facecolor=BG_WHITE, edgecolor=EMERALD, linewidth=0.8),
        )
        ax.text(
            32.0,
            hard_idx,
            f"Collapse: {clean_acc[hard_idx]:.1f}% acc, {clean_lat[hard_idx]:.2f} ms scan",
            ha="left",
            va="center",
            fontsize=8.2,
            fontweight="bold",
            color=CRIMSON,
            bbox=dict(boxstyle="round,pad=0.25", facecolor=BG_WHITE, edgecolor=CRIMSON, linewidth=0.8),
        )
        ax.text(
            52.0,
            full_idx,
            f"Full-read baseline: {clean_acc[full_idx]:.1f}% Clean",
            ha="left",
            va="center",
            fontsize=8.2,
            fontweight="bold",
            color=STEEL_BLUE,
            bbox=dict(boxstyle="round,pad=0.25", facecolor=BG_WHITE, edgecolor=STEEL_BLUE, linewidth=0.8),
        )

        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=9.1)
        for tick_lbl, r in zip(ax.get_yticklabels(), rows):
            if "Urgent B=3" in r["variant"] or "Hard Slots" in r["variant"] or "Full G9 TIDE" in r["variant"]:
                tick_lbl.set_fontweight("bold")

        ax.invert_yaxis()
        ax.set_xlabel("Percentage (%)", fontweight="bold")
        ax.set_xlim(0, 128)
        ax.set_xticks(range(0, 101, 20))

        ax.set_title(
            "Study B1: MPCS G9 TIDE 8-Variant Component Ablation on MMKG",
            fontfamily="Georgia",
            fontweight="bold",
            fontsize=13.0,
            pad=26,
            loc="left",
            color=INK_DARK,
        )
        ax.legend(
            loc="upper right",
            bbox_to_anchor=(1.0, 1.07),
            ncol=3,
            frameon=True,
            facecolor=BG_WHITE,
            edgecolor=GRID_COLOR,
        )

        fig.tight_layout()
        fig.savefig(str(out_path), dpi=300, bbox_inches="tight")
    finally:
        plt.close(fig)


def plot_study_c_mmkg(data: dict[str, Any], out_path: Path) -> None:
    """Generate fig13_mmkg_study_c.png showing Study C PersonaQueryEngine 8-variant ablation."""
    rows = data["study_c_personakg_ablation_mmkg"]
    ds = data["dataset_stats"]

    label_map = {
        "Full Exploratory Persona (theta=0.35)": "Full Exploratory (theta=0.35)",
        "Full Confident Persona (theta=0.70)": "Full Confident (theta=0.70)",
        "w/o 2-Hop Spreading Activation (hops=0)": "w/o Spreading Act. (hops=0)",
        "w/o 2nd Hop (hops=1)": "w/o 2nd Hop (hops=1)",
        "w/o VAD Arousal & Grade Multiplier (mu_v=1.0)": "w/o VAD & Grade (mu_v=1.0)",
        "w/o Clinical Synonym Expansion": "w/o Clinical Synonyms",
        "w/o Edge-Weight Modulation (uniform w_uv=1.0)": "w/o Edge-Weight (w_uv=1.0)",
        "w/o Precomputed Inverted Index (Linear Scan)": "w/o Inverted Index (Linear Scan)",
    }

    labels = [label_map.get(r["variant"], r["variant"]) for r in rows]
    top1 = [float(r["remedy_top1_pct"]) for r in rows]
    top3 = [float(r["remedy_top3_pct"]) for r in rows]
    top1_hits = [str(r["remedy_top1_hits"]) for r in rows]
    top3_hits = [str(r["remedy_top3_hits"]) for r in rows]

    y = np.arange(len(rows), dtype=float)
    bar_h = 0.34

    fig, ax = plt.subplots(figsize=(11.4, 5.8))
    try:
        style_axes(ax, grid_axis="x")

        for idx, r in enumerate(rows):
            if "mu_v=1.0" in r["variant"]:
                ax.axhspan(idx - 0.43, idx + 0.43, color=HIGHLIGHT_GREEN_BG, zorder=0)
            elif "Exploratory" in r["variant"] or "hops=1" in r["variant"]:
                ax.axhspan(idx - 0.43, idx + 0.43, color=HIGHLIGHT_BLUE_BG, zorder=0)
            elif "Linear Scan" in r["variant"]:
                ax.axhspan(idx - 0.43, idx + 0.43, color=HIGHLIGHT_RED_BG, zorder=0)

        b1 = ax.barh(y - bar_h / 2.0, top1, height=bar_h, color=STEEL_BLUE, edgecolor=INK_DARK, linewidth=0.4, label="Top-1 Remedy Recall (%)")
        b2 = ax.barh(y + bar_h / 2.0, top3, height=bar_h, color=OCHRE, edgecolor=INK_DARK, linewidth=0.4, label="Top-3 Remedy Recall (%)")

        for rect, hits in zip(b1, top1_hits):
            val = rect.get_width()
            ax.text(
                val + 1.0,
                rect.get_y() + rect.get_height() / 2.0,
                f"{val:.1f}% ({hits})",
                ha="left",
                va="center",
                fontsize=8.1,
                color=INK_DARK,
            )

        for rect, hits in zip(b2, top3_hits):
            val = rect.get_width()
            ax.text(
                val + 1.0,
                rect.get_y() + rect.get_height() / 2.0,
                f"{val:.1f}% ({hits})",
                ha="left",
                va="center",
                fontsize=8.1,
                color=INK_DARK,
            )

        mu_idx = next(i for i, r in enumerate(rows) if "mu_v=1.0" in r["variant"])
        exp_idx = next(i for i, r in enumerate(rows) if "Exploratory" in r["variant"])
        lin_idx = next(i for i, r in enumerate(rows) if "Linear Scan" in r["variant"])

        ax.text(
            106.0,
            mu_idx,
            f"Peak: {top1[mu_idx]:.1f}% / {top3[mu_idx]:.1f}%",
            ha="left",
            va="center",
            fontsize=8.3,
            fontweight="bold",
            color=EMERALD,
            bbox=dict(boxstyle="round,pad=0.25", facecolor=BG_WHITE, edgecolor=EMERALD, linewidth=0.8),
        )
        ax.text(
            106.0,
            exp_idx,
            f"Matches hops=1 ({top1[exp_idx]:.1f}% / {top3[exp_idx]:.1f}%)",
            ha="left",
            va="center",
            fontsize=8.0,
            fontweight="bold",
            color=STEEL_BLUE,
            bbox=dict(boxstyle="round,pad=0.25", facecolor=BG_WHITE, edgecolor=STEEL_BLUE, linewidth=0.8),
        )
        ax.text(
            106.0,
            lin_idx,
            f"Linear Scan ({top1[lin_idx]:.1f}% / {top3[lin_idx]:.1f}%)",
            ha="left",
            va="center",
            fontsize=8.0,
            fontweight="bold",
            color=CRIMSON,
            bbox=dict(boxstyle="round,pad=0.25", facecolor=BG_WHITE, edgecolor=CRIMSON, linewidth=0.8),
        )

        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=9.1)
        for tick_lbl, r in zip(ax.get_yticklabels(), rows):
            if any(k in r["variant"] for k in ("mu_v=1.0", "Exploratory", "hops=1", "Linear Scan")):
                tick_lbl.set_fontweight("bold")

        ax.invert_yaxis()
        ax.set_xlabel("Remedy Recall (%)", fontweight="bold")
        ax.set_xlim(0, 134)
        ax.set_xticks(range(0, 101, 20))

        ax.set_title(
            f"Study C: PersonaQueryEngine Ablation on {ds['graph_nodes']:,}-Node MMKG (40 Queries)",
            fontfamily="Georgia",
            fontweight="bold",
            fontsize=13.0,
            pad=26,
            loc="left",
            color=INK_DARK,
        )
        ax.legend(
            loc="upper right",
            bbox_to_anchor=(1.0, 1.07),
            ncol=2,
            frameon=True,
            facecolor=BG_WHITE,
            edgecolor=GRID_COLOR,
        )

        fig.tight_layout()
        fig.savefig(str(out_path), dpi=300, bbox_inches="tight")
    finally:
        plt.close(fig)


def inspect_dimensions(paths: list[Path]) -> list[tuple[str, int, int]]:
    """Read pixel dimensions of every generated PNG with explicit context-managed close."""
    dims: list[tuple[str, int, int]] = []
    for p in sorted(paths, key=lambda x: x.name):
        with Image.open(p) as im:
            w, h = im.size
        dims.append((p.name, w, h))
    return dims


def main() -> None:
    """Create all 17 PPT figures and print verified filenames and pixel dimensions."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    configure_matplotlib_style()

    all_paths: list[Path] = []
    all_paths.extend(copy_raster_assets(REPORT_FIG_DIR, OUT_DIR))
    all_paths.extend(extract_pdf_figures(PDF_PATH, OUT_DIR, dpi=300))

    study_data = load_study_data(STUDY_JSON_PATH)
    chart_specs = (
        ("fig10_mmkg_study_a.png", plot_study_a_mmkg),
        ("fig11_mmkg_study_b1.png", plot_study_b1_mmkg),
        ("fig13_mmkg_study_c.png", plot_study_c_mmkg),
    )
    for fname, fn in chart_specs:
        out_path = OUT_DIR / fname
        fn(study_data, out_path)
        all_paths.append(out_path)

    dims = inspect_dimensions(all_paths)
    print(f"Generated {len(dims)} figures in {OUT_DIR}:")
    for name, w, h in dims:
        print(f"  {name}: {w}x{h}")


if __name__ == "__main__":
    main()

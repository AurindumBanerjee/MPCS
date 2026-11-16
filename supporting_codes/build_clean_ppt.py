"""Build the spacious 18-slide presentation at report/PPT/BTP_PPT_Clean.pptx.

Follows the clean, airy formatting principles of the reference internship deck:
- Pure white (#FFFFFF) title slide without card clutter
- Section-numbered badge + top-right progress stepper dots on content slides
- Keeps the project's warm color scheme (#F2F1EC, #2E5B88, #B86B28, #2B6E46, #B83A2E)
- 1 large plot/visual or 1 focused table per slide with short, scannable points
- Preserves user wording edits (e.g., clean 'Indexing & Filtering' / 'Scoring, Spreading & Routing')
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import build_updated_ppt as U

REPO_ROOT = U.REPO_ROOT
TEMPLATE_PPTX = U.TEMPLATE_PPTX
OUTPUT_PPTX = REPO_ROOT / "report" / "PPT" / "BTP_PPT_Clean.pptx"
FIGURES_DIR = U.FIGURES_DIR

SECTIONS = [
    (1, "Motivation"),
    (2, "Market"),
    (3, "Solution"),
    (4, "Results"),
]


def add_clean_header(
    sb: U.SlideBuilder,
    sec_num: int,
    sec_label: str,
    title: str,
    accent: str = U.BLUE,
    title_pt: float = 24.0,
) -> None:
    """Render reference-inspired numbered section badge, short title, stepper dots, and footer."""
    # Section number square badge
    sb.add_rect(U.LEFT, 0.50, 0.42, 0.42, fill=U.INK, rounded=True, adj_val=15000, label="sec_badge")
    sb.add_textbox(
        U.LEFT, 0.55, 0.42, 0.34,
        [U.ParaSpec([U.RunSpec(str(sec_num), font=U.FONT_SANS, size_pt=13.5, color="FFFFFF", bold=True)], align="ctr", line_pct=100, space_after_pt=0.0)],
        label="sec_num",
    )
    # Short title
    sb.add_textbox(
        U.LEFT + 0.54, 0.48, 7.60, 0.46,
        [U.ParaSpec([U.RunSpec(title, font=U.FONT_SERIF, size_pt=title_pt, color=U.INK, bold=True, spc=-20)], line_pct=110, space_after_pt=0.0)],
        is_title_ph=True, label="title",
    )
    # Top-right progress stepper (4 sections)
    dot_start_x = 10.62
    sb.add_textbox(
        8.80, 0.58, 1.72, 0.24,
        [U.ParaSpec([U.RunSpec(sec_label.upper(), font=U.FONT_SANS, size_pt=10.0, color=accent, bold=True, spc=90)], align="r", line_pct=100, space_after_pt=0.0)],
        label="sec_step_lbl",
    )
    for idx, _ in SECTIONS:
        dx = dot_start_x + (idx - 1) * 0.44
        is_cur = idx == sec_num
        fill_c = accent if is_cur else "D9D6C8"
        sb.add_rect(dx, 0.56, 0.28, 0.28, fill=fill_c, rounded=True, adj_val=50000, label=f"step_dot_{idx}")
        if is_cur:
            sb.add_textbox(
                dx, 0.58, 0.28, 0.24,
                [U.ParaSpec([U.RunSpec(str(idx), font=U.FONT_SANS, size_pt=10.0, color="FFFFFF", bold=True)], align="ctr", line_pct=100, space_after_pt=0.0)],
                label=f"step_num_{idx}",
            )

    # Footer
    sb.add_textbox(
        U.LEFT, 6.84, 6.50, 0.22,
        [U.ParaSpec([U.RunSpec("MPCS & LOCALKG  |  B.TECH PROJECT, IIT JODHPUR", font=U.FONT_SANS, size_pt=10.5, color=U.MUTED, spc=80)], line_pct=105, space_after_pt=0.0)],
        label="footer_left",
    )
    sb.add_textbox(
        11.88, 6.84, 0.80, 0.22,
        [U.ParaSpec([U.RunSpec(f"{sb.slide_num:02d}", font=U.FONT_SANS, size_pt=10.5, color=U.MUTED, bold=True, spc=80)], align="r", line_pct=105, space_after_pt=0.0)],
        label="footer_num",
    )


def to_xml_white_bg(sb: U.SlideBuilder) -> bytes:
    """Serialize slide XML with pure white (#FFFFFF) background for Slide 1."""
    body = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<p:sld xmlns:a="{U.NS_A}" xmlns:r="{U.NS_R}" xmlns:p="{U.NS_P}">'
        f'<p:cSld name="{sb.name}">'
        f'<p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></p:bgPr></p:bg>'
        f'<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        f'<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        f'{"".join(sb.shapes_xml)}'
        f'</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
    )
    return body.encode("utf-8")


def build_slides(mmkg: dict, bank: dict) -> list[tuple[U.SlideBuilder, str]]:
    """Construct 18 spacious slides following the reference presentation style."""
    slides: list[tuple[U.SlideBuilder, str]] = []

    ds = mmkg["dataset_stats"]
    sa = mmkg["study_a_extended_indexing_mmkg"]
    sb1 = {row["variant"]: row for row in mmkg["study_b_mpcs_tide_ablation_mmkg"]}
    sb2 = mmkg["study_b_anytime_budgets_mmkg"]
    sb3 = mmkg["study_b_sufficiency_routing_mmkg"]
    sc = {row["variant"]: row for row in mmkg["study_c_personakg_ablation_mmkg"]}

    b3_gen = bank["indexing_schemes"]
    b3_tide = bank["tide_clean"]

    # ------------------------------------------------------------------
    # Slide 01: Pure White Title Slide (Reference Style)
    # ------------------------------------------------------------------
    s = U.SlideBuilder(1, "Slide 1")
    s.add_image_box(
        6.15, 0.90, 1.03, 1.14,
        FIGURES_DIR / "iitj_logo.png",
        "IIT Jodhpur Crest",
        in_card=False, pad_in=0.0, label="iitj_logo",
    )
    s.add_textbox(
        1.10, 2.35, 11.13, 0.90,
        [U.ParaSpec([U.RunSpec("MPCS & LocalKG", font=U.FONT_SERIF, size_pt=48.0, color=U.INK, bold=True, spc=-40)], align="ctr", line_pct=105, space_after_pt=0.0)],
        is_title_ph=True, label="main_title",
    )
    s.add_textbox(
        1.10, 3.35, 11.13, 0.72,
        [
            U.ParaSpec([U.RunSpec("Cognitive Model of Convergent & Divergent Thinking", font=U.FONT_SANS, size_pt=17.0, color=U.BLUE, bold=True)], align="ctr", line_pct=115, space_after_pt=4.0),
            U.ParaSpec([U.RunSpec("Contemplation, Reflection & Self-Correction on a Homeopathy Knowledge Graph", font=U.FONT_SANS, size_pt=13.5, color=U.MUTED)], align="ctr", line_pct=115, space_after_pt=0.0),
        ],
        label="subtitle",
    )
    s.add_textbox(
        2.00, 4.75, 9.33, 1.65,
        [
            U.ParaSpec([U.RunSpec("by", font=U.FONT_SANS, size_pt=12.0, color=U.MUTED)], align="ctr", line_pct=115, space_after_pt=4.0),
            U.ParaSpec([U.RunSpec("Aurindum Banerjee (B23CS1006)  &  Lokesh Motwani (B23CS1033)", font=U.FONT_SERIF, size_pt=17.0, color=U.INK, bold=True)], align="ctr", line_pct=115, space_after_pt=12.0),
            U.ParaSpec([U.RunSpec("under the supervision of", font=U.FONT_SANS, size_pt=12.0, color=U.MUTED)], align="ctr", line_pct=115, space_after_pt=4.0),
            U.ParaSpec([U.RunSpec("Dr. Romi Banerjee  |  Dept. of CSE, IIT Jodhpur", font=U.FONT_SERIF, size_pt=15.0, color=U.CHARCOAL, bold=True)], align="ctr", line_pct=115, space_after_pt=0.0),
        ],
        label="authors",
    )
    notes1 = (
        "Welcome everyone. Today we present our B.Tech project under Dr. Romi Banerjee: "
        "'Cognitive Model of Convergent and Divergent Thinking' - implemented as MPCS and LocalKG. "
        "Our aim is to design a model of contemplation following cognitive theories for reflection and self-correction, "
        "and expand it to a smart Homeopathy support tool over a self-built clinical Knowledge Graph."
    )
    slides.append((s, notes1))

    # ------------------------------------------------------------------
    # Slide 02: Why Model Contemplation? (Spacious 2-card)
    # ------------------------------------------------------------------
    s = U.SlideBuilder(2, "Slide 2")
    add_clean_header(s, 1, "Motivation", "Why Model Contemplation?", accent=U.BLUE)

    s.add_card(
        U.LEFT, 1.45, 5.80, 3.30,
        title="Convergent Thinking",
        bullets=[
            "Focuses to one decisive, safe action",
            "Replicates fast System-1 reflex control",
            "Enforces strict safety slot constraints",
        ],
        accent=U.BLUE, title_size=17.5, bullet_size=15.0, label="conv_card",
    )
    s.add_card(
        6.88, 1.45, 5.80, 3.30,
        title="Divergent Thinking",
        bullets=[
            "Explores related sensory & clinical associations",
            "Supports System-2 deliberation on novel inputs",
            "Reflects & self-corrects via reward feedback",
        ],
        accent=U.OCHRE, title_size=17.5, bullet_size=15.0, label="div_card",
    )
    s.add_card(
        U.LEFT, 5.05, U.CONTENT_W, 1.35,
        body_paras=[
            U.ParaSpec([
                U.RunSpec("Core Cognitive Goal: ", font=U.FONT_SERIF, size_pt=15.5, color=U.INK, bold=True),
                U.RunSpec("Imitate human sensory-percept understanding to build AI that contemplates, reflects, and self-corrects.", font=U.FONT_SANS, size_pt=14.5, color=U.CHARCOAL),
            ], line_pct=125, space_after_pt=0.0)
        ],
        accent=U.EMERALD, accent_side="left", label="cog_goal",
    )
    notes2 = (
        "Why was this work done? Our project starts from cognitive modeling: designing an AI model of contemplation "
        "for reflection and self-correction. Originally, we imitated how humans understand sensory percepts and alternate "
        "between convergent thinking - narrowing down to one safe, fast action - and divergent thinking - exploring "
        "related associations before deciding, then learning from reward feedback."
    )
    slides.append((s, notes2))

    # ------------------------------------------------------------------
    # Slide 03: Expanding to Homeopathy & The Dataset Gap
    # ------------------------------------------------------------------
    s = U.SlideBuilder(3, "Slide 3")
    add_clean_header(s, 1, "Motivation", "Homeopathy Expansion & Data Gap", accent=U.CRIMSON)

    s.add_card(
        U.LEFT, 1.45, 5.80, 3.30,
        title="Why Homeopathy?",
        bullets=[
            "Maps experiences & symptoms to remedies",
            "Tests partial inputs -> related nodes & conditions",
            "Rich modalities & proving grades (1, 2, 3)",
        ],
        accent=U.BLUE, title_size=17.5, bullet_size=15.0, label="hom_why",
    )
    s.add_card(
        6.88, 1.45, 5.80, 3.30,
        title="The Dataset Barrier",
        bullets=[
            "No accessible structured Homeopathy dataset",
            "Built LocalKG: Materia Medica + cited PubMed",
            "Added filtering & constraints for fast KG queries",
        ],
        accent=U.CRIMSON, title_size=17.5, bullet_size=15.0, label="hom_gap",
    )
    s.add_card(
        U.LEFT, 5.05, U.CONTENT_W, 1.35,
        body_paras=[
            U.ParaSpec([
                U.RunSpec("Final Target: ", font=U.FONT_SERIF, size_pt=15.5, color=U.INK, bold=True),
                U.RunSpec("Combine TIDE + LocalKG into a free-text tool that builds multi-class subgraphs for symptom understanding.", font=U.FONT_SANS, size_pt=14.5, color=U.CHARCOAL),
            ], line_pct=125, space_after_pt=0.0)
        ],
        accent=U.OCHRE, accent_side="left", label="hom_target",
    )
    notes3 = (
        "Next, we expanded our cognitive model to Homeopathy: mapping symptoms and experiences to remedies, and handling "
        "partial inputs to surface related symptoms, remedies, and conditions. We hit an immediate barrier: no usable "
        "Homeopathy dataset was publicly accessible. So we constructed LocalKG ourselves from Materia Medica Pura and "
        "cited PubMed abstracts, and added filtering and constraint layers to our cognitive model for fast KG querying."
    )
    slides.append((s, notes3))

    # ------------------------------------------------------------------
    # Slide 04: Existing Market Landscape
    # ------------------------------------------------------------------
    s = U.SlideBuilder(4, "Slide 4")
    add_clean_header(s, 2, "Market", "What Exists Today: Static & Brittle", accent=U.OCHRE)

    s.add_image_box(
        U.LEFT, 1.45, 3.85, 4.40,
        FIGURES_DIR / "market_homeopathy_uk.jpeg",
        "Homeopathy UK static articles",
        header="1. Homeopathy UK",
        caption="Static condition articles; no reasoning.",
        accent=U.MUTED, label="mkt_uk",
    )
    s.add_image_box(
        4.74, 1.45, 3.85, 4.40,
        FIGURES_DIR / "market_omm_simple.jpeg",
        "Open Materia Medica simple query",
        header="2. Open Materia Medica",
        caption="Token match works on simple queries.",
        accent=U.BLUE, label="mkt_omm_ok",
    )
    s.add_image_box(
        8.83, 1.45, 3.85, 4.40,
        FIGURES_DIR / "market_omm_failed.jpeg",
        "Open Materia Medica failure case",
        header="3. Multi-Symptom Failure",
        caption="Adding ', dilated pupils' returns 0 matches.",
        accent=U.CRIMSON, label="mkt_omm_fail",
    )
    s.add_card(
        U.LEFT, 6.00, U.CONTENT_W, 0.65,
        body_paras=[
            U.ParaSpec([
                U.RunSpec("Gap: ", font=U.FONT_SERIF, size_pt=14.0, color=U.INK, bold=True),
                U.RunSpec("Existing tools fail on partial or multi-symptom inputs and offer zero graph traversal or safety constraints.", font=U.FONT_SANS, size_pt=13.5, color=U.CHARCOAL),
            ], line_pct=115, space_after_pt=0.0)
        ],
        accent=U.OCHRE, accent_side="left", label="mkt_gap",
    )
    notes4 = (
        "Looking at existing market tools: Homeopathy UK only offers static condition articles with zero symptom reasoning. "
        "Open Materia Medica performs simple token matching against memory - it handles a single-clause query like 'violent "
        "throbbing headache with high fever' and returns Belladonna, but adding ', dilated pupils' returns zero matches "
        "even though that phrase appears inside Belladonna's own description."
    )
    slides.append((s, notes4))

    # ------------------------------------------------------------------
    # Slide 05: Our Solution - Architecture (Big Diagram)
    # ------------------------------------------------------------------
    s = U.SlideBuilder(5, "Slide 5")
    add_clean_header(s, 3, "Solution", "Neuro-Symbolic Architecture", accent=U.BLUE)

    s.add_image_box(
        U.LEFT, 1.40, 7.80, 5.20,
        FIGURES_DIR / "fig_arch_grouped.png",
        "Grouped neuro-symbolic architecture",
        accent=U.BLUE, label="arch_img",
    )
    s.add_card(
        8.68, 1.40, 4.00, 1.60,
        title="1. MPCS Agent",
        bullets=["Sensory percepts + reflexes", "2-stage retrieval + self-correction"],
        accent=U.BLUE, title_size=15.0, bullet_size=13.5, label="sol_1",
    )
    s.add_card(
        8.68, 3.20, 4.00, 1.60,
        title="2. LocalKG",
        bullets=[f"{ds['graph_nodes']:,} nodes, {ds['graph_links']:,} edges", "Convergent & Divergent modes"],
        accent=U.OCHRE, title_size=15.0, bullet_size=13.5, label="sol_2",
    )
    s.add_card(
        8.68, 5.00, 4.00, 1.60,
        title="3. TIDE + LocalKG Tool",
        bullets=["Free-text & partial queries", "Multi-class subgraphs (~4 ms)"],
        accent=U.EMERALD, title_size=15.0, bullet_size=13.5, label="sol_3",
    )
    notes5 = (
        "Here is our unified solution. The MPCS agent handles sensory percepts, 7 priority reflex rules, two-stage retrieval, "
        "and online reward self-correction. LocalKG stores 1,106 nodes and 2,024 cited edges extracted from Materia Medica Pura "
        "and PubMed. The Bridge connects free-text or partial symptom queries to both systems in ~4 ms."
    )
    slides.append((s, notes5))

    # ------------------------------------------------------------------
    # Slide 06: Two-Stage Retrieval Cascade (Preserves User Wording)
    # ------------------------------------------------------------------
    s = U.SlideBuilder(6, "Slide 6")
    add_clean_header(s, 3, "Solution", "Two-Stage Retrieval Cascade", accent=U.BLUE)

    s.add_image_box(
        U.LEFT, 1.40, 6.45, 5.20,
        FIGURES_DIR / "fig_cascade_grouped.png",
        "Grouped 6-layer retrieval cascade",
        accent=U.BLUE, label="cas_img",
    )
    s.add_card(
        7.30, 1.40, 5.38, 2.45,
        title="Indexing & Filtering",
        bullets=[
            "dlCBF: O(d) exact-repeat gate (9.2 KB)",
            "HMGI: Modality-gated partitions",
            "HyST: Hard-slot safety filtering",
            "SHMF: Auto-relaxation on empty buckets",
        ],
        accent=U.BLUE, title_size=16.0, bullet_size=13.8, label="cas_1",
    )
    s.add_card(
        7.30, 4.10, 5.38, 2.50,
        title="Scoring, Spreading & Routing",
        bullets=[
            "KERL: Near-miss guard & relevance",
            "TIDE: 3-hop affect-weighted spreading",
            "Anytime cutoff: B candidates or 2 ms",
            "Sufficiency routing for fast vs. deep search",
        ],
        accent=U.OCHRE, title_size=16.0, bullet_size=13.8, label="cas_2",
    )
    notes6 = (
        "To speed up querying and enforce safety on graph-style data, we separated retrieval into two stages. "
        "First, Indexing & Filtering narrows candidates via dlCBF, HMGI, hard safety slots in HyST, and SHMF auto-relaxation. "
        "Second, Scoring, Spreading & Routing applies KERL's near-miss guard and TIDE's bounded spreading activation."
    )
    slides.append((s, notes6))

    # ------------------------------------------------------------------
    # Slide 07: Self-Built Homeopathy KG (LocalKG)
    # ------------------------------------------------------------------
    s = U.SlideBuilder(7, "Slide 7")
    add_clean_header(s, 3, "Solution", "Building LocalKG: Hybrid Extraction", accent=U.OCHRE)

    s.add_image_box(
        U.LEFT, 1.40, 6.10, 2.85,
        FIGURES_DIR / "fig04_localkg_pipeline.png",
        "LocalKG ingestion pipeline",
        header="Ingestion & VAD Weighting",
        accent=U.OCHRE, label="lkg_p",
    )
    s.add_table(
        U.LEFT, 4.48, 6.10,
        [1.75, 0.90, 0.90, 0.90, 1.65],
        ["Method", "Recall", "Prec.", "F1", "Failed"],
        [
            ["Rule-based", "61.5%", "4.0%", "7.5%", "0"],
            ["Model (120B)", "80.8%", "4.9%", "9.2%", "24 (21%)"],
            ["Hybrid (Ours)", "80.8%", "5.4%", "10.1%", "0"],
        ],
        row_h_in=0.45, header_h_in=0.48, font_pt=12.0,
        alignments=["l", "ctr", "ctr", "ctr", "ctr"],
        highlight_rows={2: U.EMERALD_TINT}, bold_rows={2},
        label="lkg_tbl",
    )
    s.add_card(
        7.05, 1.40, 5.63, 4.95,
        title="Why Hybrid Extraction Works",
        bullets=[
            "Pure LLM failed schema checks on 21% of chunks",
            "Rules propose verbatim quotes; LLM audits them",
            "Fallback keeps failed batches at 0",
            "VAD affect + proving grade compute weight W",
            f"Final graph: {ds['graph_nodes']:,} nodes, {ds['graph_links']:,} cited edges",
        ],
        accent=U.EMERALD, title_size=16.5, bullet_size=14.2, label="lkg_why",
    )
    notes7 = (
        "Because no Homeopathy KG existed, we built LocalKG from Materia Medica Pura and 21 PubMed abstracts. "
        "Pure LLM extraction failed schema validation on 21% of archaic chunks. Our Hybrid extractor proposes "
        "verbatim-grounded candidates with rules, audits them with the model, and achieves 80.8% recall with zero failures."
    )
    slides.append((s, notes7))

    # ------------------------------------------------------------------
    # Slide 08: Dual-Persona Graph Subgraphs (Big Visual)
    # ------------------------------------------------------------------
    s = U.SlideBuilder(8, "Slide 8")
    add_clean_header(s, 3, "Solution", "Convergent & Divergent Graph Search", accent=U.EMERALD)

    s.add_image_box(
        U.LEFT, 1.40, 7.60, 5.20,
        FIGURES_DIR / "kg_single_remedy.png",
        "Arnica montana multi-class subgraph",
        header="Multi-Class Subgraph (Arnica montana: 59 Nodes, 93 Edges)",
        accent=U.BLUE, label="arnica_img",
    )
    s.add_card(
        8.50, 1.40, 4.18, 2.45,
        title="Dual-Persona Querying",
        bullets=[
            "Convergent (theta=0.70): 1.43 ms (2.56x faster)",
            "Divergent (theta=0.35): 1.95 ms (1.87x faster)",
            "Linear scan baseline: 3.65 ms",
        ],
        accent=U.BLUE, title_size=15.5, bullet_size=13.5, label="qe_card",
    )
    s.add_card(
        8.50, 4.05, 4.18, 2.55,
        title="Partial-Input Reasoning",
        bullets=[
            "Inverted token index seeds partial queries",
            "Spreads across Medicine, Symptom & Modality",
            "Every link carries a verbatim source quote",
        ],
        accent=U.EMERALD, title_size=15.5, bullet_size=13.5, label="qe_part",
    )
    notes8 = (
        "Here is how PersonaQueryEngine turns free-text or partial symptom inputs into multi-class subgraphs. "
        "A single threshold theta switches between Convergent mode (theta=0.70, 1.43 ms, 2.56x faster than linear scan) "
        "for core facts, and Divergent mode (theta=0.35, 1.95 ms) for broader differential remedies."
    )
    slides.append((s, notes8))

    # ------------------------------------------------------------------
    # Slide 09: Main Results - Bank v3 Accuracy & Safety (1 Big Plot)
    # ------------------------------------------------------------------
    s = U.SlideBuilder(9, "Slide 9")
    add_clean_header(s, 4, "Results", "Main Results: 26x Safer on Bank v3", accent=U.EMERALD)

    s.add_image_box(
        U.LEFT, 1.40, 7.80, 5.20,
        FIGURES_DIR / "fig08_bankv3_acc_unsafe.png",
        "Bank v3 accuracy and unsafe error across generations",
        accent=U.BLUE, label="b3_plot",
    )
    s.add_kpi_card(
        8.68, 1.40, 4.00, 1.55,
        "26x Safer",
        f"Unsafe errors drop {b3_gen['G4: Core v2 (Per-Action Z)']['unsafe_clean']:.1f}% -> {b3_gen['G5: HyST (Hard Slot + Soft Kernel)']['unsafe_clean']:.1f}%",
        accent=U.EMERALD, value_size=26.0, caption_size=13.0, label="b3_k1",
    )
    s.add_kpi_card(
        8.68, 3.18, 4.00, 1.55,
        f"{b3_gen['G7: SHMF (Auto-Relaxed Filter)']['accuracy_clean']:.1f}% Clean Acc",
        f"G7 SHMF recovers 18.3% empty ({b3_gen['G9: TIDE (Spreading Activation)']['accuracy_clean']:.1f}% TIDE)",
        accent=U.BLUE, value_size=26.0, caption_size=13.0, label="b3_k2",
    )
    s.add_kpi_card(
        8.68, 4.96, 4.00, 1.64,
        "3.91 ms Bridge",
        "p95 5.41 ms on 1 CPU core; 38/38 tests pass",
        accent=U.INK, value_size=26.0, caption_size=13.0, label="b3_k3",
    )
    notes9 = (
        "Moving to our experimental results: on the 700-episode Bank v3 benchmark, HyST hard-slot constraints cut unsafe "
        "actions 26-fold from 31.2% down to 1.2%. SHMF auto-relaxation recovers the 18.3% empty queries to hit 75.6% clean "
        "accuracy (75.0% in G9 TIDE), while the integrated Bridge runs in 3.91 ms with all 38 unit and integration tests passing."
    )
    slides.append((s, notes9))

    # ------------------------------------------------------------------
    # Slide 10: Anytime TIDE on Bank v3 (1 Big Plot)
    # ------------------------------------------------------------------
    s = U.SlideBuilder(10, "Slide 10")
    add_clean_header(s, 4, "Results", "Anytime TIDE: Less Reading Beats Full Scan", accent=U.OCHRE)

    s.add_image_box(
        U.LEFT, 1.40, 8.10, 5.20,
        FIGURES_DIR / "fig09_bankv3_tide_budget.png",
        "Bank v3 TIDE accuracy vs budget",
        accent=U.OCHRE, label="b3_tide_plot",
    )
    s.add_card(
        8.95, 1.40, 3.73, 5.20,
        title="Urgent Mode Findings",
        bullets=[
            f"B=3 achieves {b3_tide['B=3']['accuracy_pct']:.1f}% clean accuracy",
            f"Reads only {b3_tide['B=3']['read_ratio']} candidates",
            f"Beats full read ({b3_tide['full']['accuracy_pct']:.1f}%) by +7.1 pp",
            "Unsafe rate stays at 1.2% across all budgets",
        ],
        accent=U.OCHRE, title_size=16.5, bullet_size=14.0, label="b3_tide_pts",
    )
    notes10 = (
        "In TIDE's urgent anytime mode on Bank v3, reading just 2.2 out of 25.4 candidates at budget B=3 reaches 71.9% "
        "accuracy - outperforming a full bucket read at 64.8% while keeping unsafe actions fixed at 1.2%."
    )
    slides.append((s, notes10))

    # ------------------------------------------------------------------
    # Slide 11: Comparison Study A (MMKG) - 1 Big Plot
    # ------------------------------------------------------------------
    s = U.SlideBuilder(11, "Slide 11")
    add_clean_header(s, 4, "Results", "Study A (MMKG): Indexing vs. MPCS Plot", accent=U.BLUE)

    s.add_image_box(
        U.LEFT, 1.40, 12.03, 3.85,
        FIGURES_DIR / "fig10_mmkg_study_a.png",
        "Study A comparison chart on MMKG",
        accent=U.BLUE, label="sa_plot_big",
    )
    s.add_kpi_card(
        U.LEFT, 5.42, 3.85, 1.18,
        f"{sa['dlCBF Gate']['clean_acc']:.1f}% Clean",
        "dlCBF / Cuckoo in 0.02 ms (45.7% noisy)",
        accent=U.EMERALD, value_size=22.0, caption_size=12.5, label="sa_c1",
    )
    s.add_kpi_card(
        4.74, 5.42, 3.85, 1.18,
        f"{sa['Slot Inverted Bitset']['noisy_acc']:.1f}% Noisy",
        f"Slot Bitset best noisy ({sa['Slot Inverted Bitset']['space_kb']:.1f} KB)",
        accent=U.BLUE, value_size=22.0, caption_size=12.5, label="sa_c2",
    )
    s.add_kpi_card(
        8.83, 5.42, 3.85, 1.18,
        "71% Scan Cut",
        f"NSW scans {sa['NSW Proximity Graph']['scanned_clean']:.0f}/953 ({sa['NSW Proximity Graph']['clean_acc']:.1f}% clean)",
        accent=U.OCHRE, value_size=22.0, caption_size=12.5, label="sa_c3",
    )
    notes11 = (
        "Next, we evaluated everything directly on our 953 Materia Medica KG occurrences. Study A compares 7 indexing structures "
        "against MPCS generations. Exact hash gates (dlCBF and Cuckoo) hit 95.0% clean accuracy in 0.02 ms but drop to 45.7% under "
        "1-feature noise. Slot Inverted Bitset leads noisy robustness at 77.7%, and NSW Graph cuts scans by 71%."
    )
    slides.append((s, notes11))

    # ------------------------------------------------------------------
    # Slide 12: Comparison Study A (MMKG) - Clean Metrics Table
    # ------------------------------------------------------------------
    s = U.SlideBuilder(12, "Slide 12")
    add_clean_header(s, 4, "Results", "Study A (MMKG): Indexing Metrics", accent=U.BLUE)

    sa_order = [
        ("Exact KNN (Cosine)", "Exact KNN (Cosine)"),
        ("BM25 Inverted Index", "BM25 Inverted Index"),
        ("dlCBF Gate", "dlCBF Gate"),
        ("Cuckoo Filter Gate", "Cuckoo Filter Gate"),
        ("SimHash LSH (64-bit)", "SimHash LSH (64-bit)"),
        ("Slot Inverted Bitset", "Slot Inverted Bitset"),
        ("NSW Proximity Graph", "NSW Proximity Graph"),
        ("B2 Global Top-5", "MPCS B2 (Global Top-5)"),
        ("G5 HyST", "MPCS G5 (HyST)"),
        ("G9 TIDE", "MPCS G9 (TIDE, Urgent=False)"),
    ]
    sa_rows = [
        [
            label,
            f"{sa[k]['space_kb']:.1f} KB",
            f"{sa[k]['scanned_clean']:.0f}",
            f"{sa[k]['latency_mean_ms']:.3f} ms",
            f"{sa[k]['clean_acc']:.1f}%",
            f"{sa[k]['noisy_acc']:.1f}%",
            f"{sa[k]['clean_unsafe']:.1f}%",
        ]
        for k, label in sa_order
    ]
    s.add_table(
        U.LEFT, 1.40, U.CONTENT_W,
        [3.53, 1.35, 1.35, 1.50, 1.45, 1.45, 1.40],
        ["Indexing / Model", "Memory", "Scanned", "Latency", "Clean Acc", "Noisy Acc", "Unsafe"],
        sa_rows,
        row_h_in=0.46, header_h_in=0.50, font_pt=12.0,
        alignments=["l", "r", "r", "r", "r", "r", "r"],
        highlight_rows={2: U.EMERALD_TINT, 5: U.BLUE_TINT, 9: U.OCHRE_TINT},
        bold_rows={2, 5, 9},
        label="sa_tbl_full",
    )
    notes12 = (
        "Here is the full numeric comparison table for Study A on 300 clean and 300 noisy MMKG queries. Notice that "
        "unconstrained G9 TIDE (Urgent=False) scores 42.3% here - Study B1 next shows exactly why."
    )
    slides.append((s, notes12))

    # ------------------------------------------------------------------
    # Slide 13: Ablation Study B1 (MMKG) - 1 Big Plot
    # ------------------------------------------------------------------
    s = U.SlideBuilder(13, "Slide 13")
    add_clean_header(s, 4, "Results", "Study B1 (MMKG): G9 TIDE Ablation Plot", accent=U.OCHRE)

    s.add_image_box(
        U.LEFT, 1.40, 8.20, 5.20,
        FIGURES_DIR / "fig11_mmkg_study_b1.png",
        "Study B1 G9 TIDE 8-variant ablation chart",
        accent=U.OCHRE, label="sb1_plot_big",
    )
    s.add_kpi_card(
        9.05, 1.40, 3.63, 1.58,
        f"{sb1['w/o Full-Read (Urgent B=3)']['clean_acc']:.1f}% Clean",
        f"Urgent B=3 (+48.3 pp clean, {sb1['w/o Full-Read (Urgent B=3)']['noisy_acc']:.1f}% noisy)",
        accent=U.EMERALD, value_size=26.0, caption_size=12.5, label="sb1_c1",
    )
    s.add_kpi_card(
        9.05, 3.20, 3.63, 1.58,
        f"{sb1['w/o HyST Hard Slots (Soft Only)']['clean_acc']:.1f}% Acc",
        "Removing HyST collapses acc (5.1x slower)",
        accent=U.CRIMSON, value_size=26.0, caption_size=12.5, label="sb1_c2",
    )
    s.add_card(
        9.05, 5.00, 3.63, 1.60,
        title="Why Urgent B=3 Wins",
        bullets=["_head_a averages k=5 in full-read", "B=3 sets k=1, avoiding 'observe' dilution"],
        accent=U.BLUE, title_size=14.5, bullet_size=12.5, label="sb1_c3",
    )
    notes13 = (
        "Study B1 ablates all 8 components of MPCS G9 TIDE on MMKG. Removing HyST hard slots collapses accuracy to 12.7% "
        "and slows execution 5.1x. Conversely, setting Urgent B=3 jumps clean accuracy by +48.3 points to 91.0% because "
        "kerl_layer._head_a avoids averaging over k=5 candidates diluted by frequent 'observe' records."
    )
    slides.append((s, notes13))

    # ------------------------------------------------------------------
    # Slide 14: Ablation Study B1 (MMKG) - Clean Metrics Table
    # ------------------------------------------------------------------
    s = U.SlideBuilder(14, "Slide 14")
    add_clean_header(s, 4, "Results", "Study B1 (MMKG): Ablation Metrics", accent=U.OCHRE)

    sb1_order = [
        ("Full G9 TIDE (Urgent=False)", "Full G9 TIDE (Urgent=False)"),
        ("w/o TIDE Spread (hops=0, w_g=0)", "w/o TIDE Spread (hops=0)"),
        ("w/o VAD Affect & Salience (salience_gain=0, affect=False)", "w/o VAD Affect & Salience"),
        ("w/o KERL Near-Miss Guard", "w/o KERL Near-Miss Guard"),
        ("w/o SHMF Auto-Relaxation", "w/o SHMF Auto-Relaxation"),
        ("w/o HyST Hard Slots (Soft Only)", "w/o HyST Hard Slots (Soft Only)"),
        ("w/o Expert Grade Boost (boost=1.0)", "w/o Expert Grade Boost"),
        ("w/o Full-Read (Urgent B=3)", "w/o Full-Read (Urgent B=3)"),
    ]
    sb1_rows = [
        [
            lbl,
            f"{sb1[k]['clean_acc']:.1f}%",
            f"{sb1[k]['clean_unsafe']:.1f}%",
            f"{sb1[k]['clean_lat_ms']:.2f} ms",
            f"{sb1[k]['noisy_acc']:.1f}%",
            f"{sb1[k]['noisy_unsafe']:.1f}%",
        ]
        for k, lbl in sb1_order
    ]
    s.add_table(
        U.LEFT, 1.45, U.CONTENT_W,
        [4.28, 1.55, 1.55, 1.55, 1.55, 1.55],
        ["G9 TIDE Variant", "Clean Acc", "Clean Unsafe", "Clean Lat", "Noisy Acc", "Noisy Unsafe"],
        sb1_rows,
        row_h_in=0.52, header_h_in=0.54, font_pt=12.5,
        alignments=["l", "r", "r", "r", "r", "r"],
        highlight_rows={5: U.CRIMSON_TINT, 7: U.EMERALD_TINT},
        bold_rows={5, 7},
        label="sb1_tbl_full",
    )
    notes14 = (
        "Here are all 8 ablation variants from Study B1 side by side. Unsafe errors drop from 26.0% to 11.7% under Urgent B=3, "
        "while removing HyST drops clean accuracy to 12.7% and pushes latency to 34.48 ms."
    )
    slides.append((s, notes14))

    # ------------------------------------------------------------------
    # Slide 15: Studies B2 & B3 (MMKG Anytime & Routing)
    # ------------------------------------------------------------------
    s = U.SlideBuilder(15, "Slide 15")
    add_clean_header(s, 4, "Results", "Studies B2 & B3: Budgets & Routing", accent=U.BLUE)

    s.add_image_box(
        U.LEFT, 1.40, 6.10, 3.00,
        FIGURES_DIR / "fig12_mmkg_tide_budget.png",
        "MMKG Study B2 TIDE accuracy vs budget",
        header="Anytime Budget Curve (Urgent=True)",
        accent=U.BLUE, label="sb2_plot",
    )
    s.add_card(
        U.LEFT, 4.62, 6.10, 1.98,
        title="Key Takeaways",
        bullets=[
            "Buckets average 67.3 candidates (452 percepts)",
            "B=3 achieves peak 91.0% clean / 78.7% noisy",
            "B=10 minimizes unsafe error to 3.9%",
            "80.3% escalate to SUBGRAPH for context",
        ],
        accent=U.OCHRE, title_size=15.0, bullet_size=12.8, label="sb2_pts",
    )
    b2_rows = [
        [b_lbl, sb2["clean"][b_lbl]["read_ratio"], f"{sb2['clean'][b_lbl]['accuracy_pct']:.1f}%", f"{sb2['noisy'][b_lbl]['accuracy_pct']:.1f}%", f"{sb2['clean'][b_lbl]['unsafe_pct']:.1f}%", f"{sb2['clean'][b_lbl]['decision_latency_ms']:.2f}"]
        for b_lbl in ["B=3", "B=5", "B=10", "B=20", "B=50", "Full"]
    ]
    tbl_end = s.add_table(
        7.00, 1.40, 5.68,
        [0.78, 1.05, 0.95, 0.95, 0.95, 1.00],
        ["Budget", "Read/Avail", "Clean", "Noisy", "Unsafe", "Lat(ms)"],
        b2_rows,
        row_h_in=0.40, header_h_in=0.44, font_pt=11.0,
        alignments=["l", "ctr", "r", "r", "r", "r"],
        highlight_rows={0: U.EMERALD_TINT, 2: U.BLUE_TINT, 5: U.CRIMSON_TINT},
        bold_rows={0, 2},
        label="sb2_tbl",
    )
    b3_rows = [
        [m, f"{sb3['clean'][m]['count']} ({sb3['clean'][m]['share_pct']:.1f}%)", f"{sb3['clean'][m]['accuracy_pct']:.1f}%", f"{sb3['noisy'][m]['accuracy_pct']:.1f}%"]
        for m in ["DIRECT", "SUBGRAPH", "UNGROUNDED"]
    ]
    s.add_table(
        7.00, tbl_end + 0.25, 5.68,
        [1.58, 1.50, 1.30, 1.30],
        ["Route", "Share", "Clean Acc", "Noisy Acc"],
        b3_rows,
        row_h_in=0.40, header_h_in=0.44, font_pt=11.0,
        alignments=["l", "ctr", "r", "r"],
        highlight_rows={0: U.BLUE_TINT, 1: U.OCHRE_TINT},
        label="sb3_tbl",
    )
    notes15 = (
        "Studies B2 and B3 sweep candidate budget B and sufficiency routing on MMKG. Clean accuracy degrades monotonically "
        "from 91.0% at B=3 down to 44.0% on Full Read, while B=10 achieves the lowest unsafe rate of 3.9%. "
        "Under routing, 19.7% resolve DIRECT and 80.3% take SUBGRAPH with zero ungrounded failures."
    )
    slides.append((s, notes15))

    # ------------------------------------------------------------------
    # Slide 16: Ablation Study C (PersonaQueryEngine) - 1 Big Plot
    # ------------------------------------------------------------------
    s = U.SlideBuilder(16, "Slide 16")
    add_clean_header(s, 4, "Results", "Study C (MMKG): PersonaEngine Plot", accent=U.EMERALD)

    s.add_image_box(
        U.LEFT, 1.40, 8.20, 5.20,
        FIGURES_DIR / "fig13_mmkg_study_c.png",
        "Study C PersonaQueryEngine 8-variant ablation chart",
        accent=U.EMERALD, label="sc_plot_big",
    )
    s.add_kpi_card(
        9.05, 1.40, 3.63, 1.58,
        "80% / 90%",
        "Top-1 / Top-3 with mu_v=1.0 (fixes Grade-3 hub bias)",
        accent=U.EMERALD, value_size=26.0, caption_size=12.5, label="sc_c1",
    )
    s.add_kpi_card(
        9.05, 3.20, 3.63, 1.58,
        "hops = 1",
        "Matches hops=2 (60%/80%) & saves 13% latency",
        accent=U.BLUE, value_size=26.0, caption_size=12.5, label="sc_c2",
    )
    s.add_card(
        9.05, 5.00, 3.63, 1.60,
        title="Edge Weight Clamping",
        bullets=["All 2,024 links in [1.0, 2.95]", "min(1.0, w) clamps all to 1.0"],
        accent=U.OCHRE, title_size=14.5, bullet_size=12.5, label="sc_c3",
    )
    notes16 = (
        "Study C ablates PersonaQueryEngine across 40 clinical queries times 10 runs on the 1,106-node MMKG graph. "
        "Zero-hop spreading yields 0% recall, while 1-hop matches 2-hop at 60% Top-1 / 80% Top-3 and saves 13% latency. "
        "Setting mu_v=1.0 lifts Top-1 recall to 80% and Top-3 to 90% by removing Grade-3 polychrest hub bias."
    )
    slides.append((s, notes16))

    # ------------------------------------------------------------------
    # Slide 17: Ablation Study C - Clean Metrics Table
    # ------------------------------------------------------------------
    s = U.SlideBuilder(17, "Slide 17")
    add_clean_header(s, 4, "Results", "Study C (MMKG): Persona Ablation Table", accent=U.EMERALD)

    sc_order = [
        ("Full Exploratory Persona (theta=0.35)", "Full Exploratory Persona (theta=0.35)"),
        ("Full Confident Persona (theta=0.70)", "Full Confident Persona (theta=0.70)"),
        ("w/o 2-Hop Spreading Activation (hops=0)", "w/o Spreading Activation (hops=0)"),
        ("w/o 2nd Hop (hops=1)", "w/o 2nd Hop (hops=1)"),
        ("w/o VAD Arousal & Grade Multiplier (mu_v=1.0)", "w/o VAD & Grade Multiplier (mu_v=1.0)"),
        ("w/o Clinical Synonym Expansion", "w/o Clinical Synonym Expansion"),
        ("w/o Edge-Weight Modulation (uniform w_uv=1.0)", "w/o Edge-Weight Modulation (w_uv=1.0)"),
        ("w/o Precomputed Inverted Index (Linear Scan)", "w/o Inverted Index (Linear Scan)"),
    ]
    sc_rows = [
        [
            lbl,
            f"{sc[k]['mean_kept_nodes']:.1f} ({sc[k]['mean_pruned_pct']:.1f}%)",
            f"{sc[k]['remedy_top1_pct']:.1f}%",
            f"{sc[k]['remedy_top3_pct']:.1f}%",
            f"{sc[k]['mean_lat_ms']:.2f} ms",
            f"{sc[k]['speedup_vs_linear']:.2f}x",
        ]
        for k, lbl in sc_order
    ]
    s.add_table(
        U.LEFT, 1.45, U.CONTENT_W,
        [4.53, 1.90, 1.35, 1.35, 1.50, 1.40],
        ["PersonaEngine Variant (400 Calls)", "Kept (Pruned)", "Top-1", "Top-3", "Mean Lat", "Speedup"],
        sc_rows,
        row_h_in=0.52, header_h_in=0.54, font_pt=12.5,
        alignments=["l", "ctr", "r", "r", "r", "r"],
        highlight_rows={3: U.BLUE_TINT, 4: U.EMERALD_TINT, 7: U.CRIMSON_TINT},
        bold_rows={3, 4},
        label="sc_tbl_full",
    )
    notes17 = (
        "Here are the complete Study C numbers across all 400 calls per variant: notice that Confident mode prunes 99.4% "
        "of nodes on multi-symptom queries, whereas Exploratory mode with mu_v=1.0 reaches 80.0% Top-1 and 90.0% Top-3 recall."
    )
    slides.append((s, notes17))

    # ------------------------------------------------------------------
    # Slide 18: What We Achieved, Limitations & Next Steps
    # ------------------------------------------------------------------
    s = U.SlideBuilder(18, "Slide 18")
    add_clean_header(s, 4, "Results", "Achieved vs. Remaining & Next Steps", accent=U.INK)

    s.add_card(
        U.LEFT, 1.45, 5.80, 3.45,
        title="What We Achieved",
        bullets=[
            "Convergent/divergent contemplation loop + self-correction",
            "Self-built cited Homeopathy KG (1,106n / 2,024e)",
            "26x safer Bank v3; 91.0% MMKG TIDE at B=3",
            "80% Top-1 / 90% Top-3 MMKG remedy recall",
            "3.91 ms CPU bridge; 38/38 tests pass",
        ],
        accent=U.EMERALD, title_size=16.5, bullet_size=13.5, label="ach_card",
    )
    s.add_card(
        6.88, 1.45, 5.80, 3.45,
        title="What Remains / Limitations",
        bullets=[
            "Full-read _head_a (k=5) dilutes dense MMKG buckets",
            "min(1.0, edge_w) clamps [1.0, 2.95] edge weights",
            "Regex percept projection; synthetic Bank v3",
            "Small keynote gold set (26 keynotes / 8 remedies)",
            "Historical source text, not clinical evidence",
        ],
        accent=U.CRIMSON, title_size=16.5, bullet_size=13.5, label="rem_card",
    )
    s.add_card(
        U.LEFT, 5.15, U.CONTENT_W, 1.35,
        body_paras=[
            U.ParaSpec([
                U.RunSpec("Next Steps: ", font=U.FONT_SERIF, size_pt=15.0, color=U.INK, bold=True),
                U.RunSpec("1. Global top-k voting   2. Degree & w_uv/w_max normalization   3. UMLS / SNOMED CT linking   4. Learned bridge thresholds", font=U.FONT_SANS, size_pt=13.5, color=U.CHARCOAL),
            ], line_pct=125, space_after_pt=0.0)
        ],
        accent=U.BLUE, accent_side="left", label="next_card",
    )
    notes18 = (
        "To conclude: we delivered a working cognitive model of convergent and divergent thinking, built an original cited "
        "Homeopathy Knowledge Graph where no dataset existed, and validated safety, speed, and recall across synthetic and "
        "MMKG benchmarks. Our ablations also identified exact improvements for future work: global top-k voting, degree and "
        "edge-weight normalization, UMLS/SNOMED CT entity linking, and learned bridge thresholds. Thank you."
    )
    slides.append((s, notes18))

    return slides


def build_clean_pptx() -> Path:
    """Assemble and verify report/PPT/BTP_PPT_Clean.pptx."""
    mmkg = U.load_json(U.MMKG_JSON)
    bank = U.load_json(U.BANK_JSON)
    slides = build_slides(mmkg, bank)
    num_slides = len(slides)

    OUTPUT_PPTX.parent.mkdir(parents=True, exist_ok=True)
    preserved_prefixes = ("ppt/fonts/", "ppt/notesMasters/", "ppt/slideLayouts/", "ppt/slideMasters/", "ppt/theme/")
    preserved_exact = {"_rels/.rels", "docProps/core.xml", "ppt/presProps.xml", "ppt/viewProps.xml", "ppt/tableStyles.xml"}

    media_files = {media_name for sb, _ in slides for _, media_name in sb.image_rels}

    with zipfile.ZipFile(TEMPLATE_PPTX, "r") as zin, zipfile.ZipFile(OUTPUT_PPTX, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            name = item.filename
            if name.endswith("/"):
                continue
            if name in preserved_exact or name.startswith(preserved_prefixes):
                data = zin.read(name)
                if name.endswith(".xml") and ("slideMaster" in name or "slideLayout" in name or "theme1" in name):
                    data = U.rewrite_font_references(data)
                zout.writestr(name, data)

        zout.writestr("[Content_Types].xml", U.build_content_types_xml(num_slides))
        zout.writestr("docProps/app.xml", U.build_app_xml(num_slides, zin.read("docProps/app.xml")))
        zout.writestr("ppt/presentation.xml", U.build_presentation_xml(num_slides, zin.read("ppt/presentation.xml")))
        zout.writestr("ppt/_rels/presentation.xml.rels", U.build_presentation_rels_xml(num_slides))

        for idx, (sb, notes_text) in enumerate(slides, start=1):
            slide_xml = to_xml_white_bg(sb) if idx == 1 else sb.to_xml()
            zout.writestr(f"ppt/slides/slide{idx}.xml", slide_xml)
            zout.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", sb.to_rels_xml())
            notes_xml, notes_rels = U.build_notes_xml(idx, notes_text)
            zout.writestr(f"ppt/notesSlides/notesSlide{idx}.xml", notes_xml)
            zout.writestr(f"ppt/notesSlides/_rels/notesSlide{idx}.xml.rels", notes_rels)

        for media_name in sorted(media_files):
            img_path = FIGURES_DIR / media_name
            with open(img_path, "rb") as fh:
                zout.writestr(f"ppt/media/{media_name}", fh.read())

    U.verify_pptx(OUTPUT_PPTX, num_slides)
    return OUTPUT_PPTX


if __name__ == "__main__":
    out = build_clean_pptx()
    print(f"Built and verified {out} (18 slides)")

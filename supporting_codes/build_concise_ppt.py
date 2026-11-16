"""Build the concise 12-slide presentation at report/PPT/BTP_PPT_Concise.pptx.

Reuses OOXML builder, style validators, and verification helpers from
build_updated_ppt.py while preserving report/PPT/BTP_PPT.pptx and
report/PPT/MPCS and LocalKG.pptx untouched.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import build_updated_ppt as U

REPO_ROOT = U.REPO_ROOT
TEMPLATE_PPTX = U.TEMPLATE_PPTX
OUTPUT_PPTX = REPO_ROOT / "report" / "PPT" / "BTP_PPT_Concise.pptx"
FIGURES_DIR = U.FIGURES_DIR


def build_slides(mmkg: dict, bank: dict) -> list[tuple[U.SlideBuilder, str]]:
    """Construct all 12 concise slides with synced speaker notes."""
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
    # Slide 01: Title Slide
    # ------------------------------------------------------------------
    s = U.SlideBuilder(1, "Slide 1")
    s.add_image_box(
        6.12, 0.85, 1.09, 1.20,
        FIGURES_DIR / "iitj_logo.png",
        "IIT Jodhpur Crest",
        in_card=False, pad_in=0.0, label="iitj_logo",
    )
    s.add_rect(5.87, 2.25, 1.60, 0.045, fill=U.BLUE, label="title_rule")
    s.add_textbox(
        1.20, 2.50, 10.93, 0.25,
        [U.ParaSpec([U.RunSpec("B.TECH PROJECT PRESENTATION  |  IIT JODHPUR", font=U.FONT_SANS, size_pt=11.0, color=U.MUTED, bold=True, spc=150)], align="ctr", line_pct=110, space_after_pt=0.0)],
        label="title_eyebrow",
    )
    s.add_textbox(
        1.20, 2.95, 10.93, 0.85,
        [U.ParaSpec([U.RunSpec("MPCS & LocalKG", font=U.FONT_SERIF, size_pt=44.0, color=U.INK, bold=True, spc=-40)], align="ctr", line_pct=105, space_after_pt=0.0)],
        is_title_ph=True, label="main_title",
    )
    s.add_textbox(
        1.20, 3.85, 10.93, 0.72,
        [
            U.ParaSpec([U.RunSpec("COGNITIVE MODEL OF CONVERGENT AND DIVERGENT THINKING", font=U.FONT_SANS, size_pt=14.0, color=U.CHARCOAL, bold=True, spc=70)], align="ctr", line_pct=120, space_after_pt=4.0),
            U.ParaSpec([U.RunSpec("Contemplation, Reflection & Self-Correction Applied to a Grounded Homeopathy Knowledge Graph", font=U.FONT_SANS, size_pt=12.0, color=U.MUTED)], align="ctr", line_pct=120, space_after_pt=0.0),
        ],
        label="subtitle",
    )
    s.add_rect(2.85, 5.20, 7.63, 1.15, fill=U.CARD_BG, border=U.CARD_BORDER, rounded=True, adj_val=3000, label="author_card")
    s.add_textbox(
        3.05, 5.38, 7.23, 0.80,
        [
            U.ParaSpec([U.RunSpec("Aurindum Banerjee (B23CS1006)  &  Lokesh Motwani (B23CS1033)", font=U.FONT_SERIF, size_pt=16.0, color=U.INK, bold=True)], align="ctr", line_pct=120, space_after_pt=5.0),
            U.ParaSpec([U.RunSpec("Dept. of Computer Science & Engineering  |  Supervisor: Dr. Romi Banerjee", font=U.FONT_SANS, size_pt=11.5, color=U.MUTED)], align="ctr", line_pct=115, space_after_pt=0.0),
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
    # Slide 02: Problem & Cognitive Modeling Motivation
    # ------------------------------------------------------------------
    s = U.SlideBuilder(2, "Slide 2")
    s.add_chrome("PROBLEM & MOTIVATION", "Cognitive Contemplation & The Homeopathy Data Gap", accent=U.CRIMSON)

    s.add_card(
        U.LEFT, 1.48, 5.88, 3.65,
        title="Why Model Contemplation?",
        bullets=[
            "Goal: AI reflection & self-correction from cognition",
            "Replicate human sensory-percept understanding",
            "Convergent thinking: focus to one safe action",
            "Divergent thinking: explore related associations",
        ],
        accent=U.BLUE, title_size=16.5, bullet_size=13.8, label="cog_card",
    )
    s.add_card(
        6.80, 1.48, 5.88, 3.65,
        title="Expanding to Homeopathy & Data Gap",
        bullets=[
            "Map symptoms & experiences to remedies",
            "Support partial inputs -> related nodes & conditions",
            "Gap: no accessible, structured Homeopathy dataset",
            "Built LocalKG: Materia Medica + cited PubMed",
        ],
        accent=U.CRIMSON, title_size=16.5, bullet_size=13.8, label="llm_card",
    )
    s.add_card(
        U.LEFT, 5.32, U.CONTENT_W, 1.30,
        title="Core Project Objectives",
        body_paras=[
            U.ParaSpec(
                [
                    U.RunSpec("1. ", font=U.FONT_SERIF, size_pt=13.5, color=U.BLUE, bold=True),
                    U.RunSpec("Sensory percept + self-correction loop   ", font=U.FONT_SANS, size_pt=13.0, color=U.CHARCOAL),
                    U.RunSpec("2. ", font=U.FONT_SERIF, size_pt=13.5, color=U.BLUE, bold=True),
                    U.RunSpec("Self-built cited Homeopathy KG   ", font=U.FONT_SANS, size_pt=13.0, color=U.CHARCOAL),
                    U.RunSpec("3. ", font=U.FONT_SERIF, size_pt=13.5, color=U.BLUE, bold=True),
                    U.RunSpec("Fast filtering & constraint layers   ", font=U.FONT_SANS, size_pt=13.0, color=U.CHARCOAL),
                    U.RunSpec("4. ", font=U.FONT_SERIF, size_pt=13.5, color=U.BLUE, bold=True),
                    U.RunSpec("Free-text -> multi-class subgraph tool", font=U.FONT_SANS, size_pt=13.0, color=U.CHARCOAL),
                ],
                line_pct=125, space_after_pt=0.0,
            )
        ],
        accent=U.EMERALD, accent_side="left", title_size=15.0, label="obj_card",
    )
    notes2 = (
        "Why was this work done? Our project's core aim is designing a cognitive model of contemplation - specifically "
        "convergent and divergent thinking - to improve AI reflection and self-correction. Originally, we modeled how humans "
        "understand sensory percepts and alternate between convergent action selection and divergent exploration. "
        "We then expanded this model to Homeopathy: mapping symptoms to remedies and answering partial inputs with related "
        "symptoms, remedies, and conditions. Because no accessible Homeopathy dataset existed, we built LocalKG ourselves from "
        "Materia Medica Pura and PubMed abstracts, and added filtering and constraint layers to speed up KG-style querying."
    )
    slides.append((s, notes2))

    # ------------------------------------------------------------------
    # Slide 03: Existing Market Landscape
    # ------------------------------------------------------------------
    s = U.SlideBuilder(3, "Slide 3")
    s.add_chrome("MARKET LANDSCAPE", "Existing Tools: Static Articles & Brittle Token Search", accent=U.OCHRE)

    s.add_image_box(
        U.LEFT, 1.48, 3.85, 4.15,
        FIGURES_DIR / "market_homeopathy_uk.jpeg",
        "Homeopathy UK static condition articles",
        header="1. Homeopathy UK (Articles)",
        caption="Condition directory only; zero symptom-modality reasoning or citations.",
        accent=U.MUTED, label="mkt_uk",
    )
    s.add_image_box(
        4.74, 1.48, 3.85, 4.15,
        FIGURES_DIR / "market_omm_simple.jpeg",
        "Open Materia Medica simple query success",
        header="2. Open Materia Medica (Simple)",
        caption="Token matching handles simple queries ('violent throbbing headache').",
        accent=U.BLUE, label="mkt_omm_ok",
    )
    s.add_image_box(
        8.83, 1.48, 3.85, 4.15,
        FIGURES_DIR / "market_omm_failed.jpeg",
        "Open Materia Medica multi-symptom failure",
        header="3. Open Materia Medica (Fails)",
        caption="Adding ', dilated pupils' yields 0 matches despite exact text in Belladonna.",
        accent=U.CRIMSON, label="mkt_omm_fail",
    )
    s.add_card(
        U.LEFT, 5.82, U.CONTENT_W, 0.80,
        body_paras=[
            U.ParaSpec(
                [
                    U.RunSpec("The Market Gap: ", font=U.FONT_SERIF, size_pt=14.0, color=U.INK, bold=True),
                    U.RunSpec(
                        "Static articles and keyword search fail on partial or multi-symptom inputs; no open Homeopathy KG or convergent/divergent reasoning tool existed.",
                        font=U.FONT_SANS, size_pt=13.0, color=U.CHARCOAL,
                    ),
                ],
                line_pct=120, space_after_pt=0.0,
            )
        ],
        accent=U.OCHRE, accent_side="left", label="mkt_gap",
    )
    notes3 = (
        "Let us look at what exists in the market today. Left: portals like Homeopathy UK only offer static condition articles "
        "with no interactive symptom reasoning. Center: Open Materia Medica performs local substring/token matching, which works "
        "on simple queries like 'violent throbbing headache with high fever' and returns Belladonna. Right: simply appending "
        "', dilated pupils' causes it to return zero matches - even though 'dilated pupils' appears verbatim in Belladonna's own "
        "portrait! This proves why we need structured multi-symptom graph traversal and safety-aware retrieval."
    )
    slides.append((s, notes3))

    # ------------------------------------------------------------------
    # Slide 04: Solution Overview (Updated Grouped Architecture Figure)
    # ------------------------------------------------------------------
    s = U.SlideBuilder(4, "Slide 4")
    s.add_chrome("OUR SOLUTION", "Neuro-Symbolic Architecture: MPCS + LocalKG + Bridge", accent=U.BLUE)

    s.add_image_box(
        U.LEFT, 1.48, 7.65, 5.10,
        FIGURES_DIR / "fig_arch_grouped.png",
        "Grouped neuro-symbolic architecture with 2-layer retrieval",
        accent=U.BLUE, label="arch_grouped",
    )
    s.add_card(
        8.52, 1.48, 4.16, 1.56,
        title="1. MPCS Agent (Model/)",
        bullets=[
            "Sensory percepts + 7 fast reflex rules",
            "2-stage retrieval: Filter then Score/Route",
            "Reflection & self-correction via reward/tau",
        ],
        accent=U.BLUE, title_size=14.5, bullet_size=12.5, label="sol_mpcs",
    )
    s.add_card(
        8.52, 3.22, 4.16, 1.62,
        title="2. LocalKG (LocalKG/)",
        bullets=[
            f"Self-built KG: {ds['graph_nodes']:,} nodes, {ds['graph_links']:,} edges",
            "Materia Medica Pura + 21 PubMed texts",
            "Convergent (0.70) & Divergent (0.35)",
        ],
        accent=U.OCHRE, title_size=14.5, bullet_size=12.5, label="sol_lkg",
    )
    s.add_card(
        8.52, 5.02, 4.16, 1.56,
        title="3. TIDE + LocalKG Support Tool",
        bullets=[
            "Accepts free-text & partial symptom inputs",
            "Builds multi-class subgraphs (~4 ms)",
            "Stage-1 red-flag guard + cited remedies",
        ],
        accent=U.EMERALD, title_size=14.5, bullet_size=12.5, label="sol_bridge",
    )
    notes4 = (
        "To close that gap, we built a three-part neuro-symbolic system shown in our updated architecture diagram. "
        "On the left, the MPCS cognitive agent checks 7 fast reflex rules first, then runs a two-stage retrieval pipeline: "
        "a blue Indexing and Filtering stage followed by an ochre Scoring, Spreading, and Routing stage, updating rewards and "
        "hesitation threshold tau online. On the right, LocalKG converts Materia Medica Pura and 21 PubMed records into a "
        "1,106-node, 2,024-edge graph weighted by VAD affect and proving grade. The Bridge joins them with an emergency halt and cited output."
    )
    slides.append((s, notes4))

    # ------------------------------------------------------------------
    # Slide 05: MPCS 6-Layer Retrieval Cascade (Updated Grouped Cascade)
    # ------------------------------------------------------------------
    s = U.SlideBuilder(5, "Slide 5")
    s.add_chrome("MPCS RETRIEVAL", "Two-Stage Retrieval Cascade: Filter First, Then Bound", accent=U.BLUE)

    s.add_image_box(
        U.LEFT, 1.48, 6.25, 5.10,
        FIGURES_DIR / "fig_cascade_grouped.png",
        "Grouped 6-layer retrieval cascade",
        accent=U.BLUE, label="cascade_grouped",
    )
    s.add_card(
        7.12, 1.48, 5.56, 2.40,
        title="Blue Stage: Indexing & Filtering",
        bullets=[
            "dlCBF: O(d) fingerprint hint in 9.2 KB / 0.02 ms",
            "HMGI: Modality-gated bucket partition scan",
            "HyST: Hard-slot safety drops unsafe mismatches",
            "SHMF: Auto-relaxes when strict filter returns empty",
        ],
        accent=U.BLUE, title_size=15.5, bullet_size=13.0, label="cas_blue",
    )
    s.add_card(
        7.12, 4.06, 5.56, 2.52,
        title="Brown Stage: Scoring, Spreading & Routing",
        bullets=[
            "KERL: Near-miss guard + fused semantic relevance",
            "TIDE: Affect-seeded 3-hop spreading activation",
            "Anytime Deadline: Stops at budget B or 2 ms cutoff",
            "Sufficiency Router: Routes confident vs. subgraph cases",
        ],
        accent=U.OCHRE, title_size=15.5, bullet_size=13.0, label="cas_brown",
    )
    notes5 = (
        "Why does MPCS outperform standard KNN or BM25 on safety and latency? Look at our grouped cascade diagram. "
        "The blue Indexing and Filtering block narrows memory via dlCBF and HMGI, then enforces hard-slot safety in HyST - "
        "so a hot-surface memory can never be confused with a cold one - while SHMF relaxes softly if no exact match exists. "
        "That filtered candidate set enters the brown Scoring, Spreading, and Routing block: KERL guards against near-misses, "
        "and TIDE performs 3-hop affect-weighted spreading under a strict candidate budget B and 2 ms deadline."
    )
    slides.append((s, notes5))

    # ------------------------------------------------------------------
    # Slide 06: LocalKG Ingestion & Dual-Persona Query Engine
    # ------------------------------------------------------------------
    s = U.SlideBuilder(6, "Slide 6")
    s.add_chrome("LOCALKG & QUERY ENGINE", "Hybrid Cited Extraction & Dual-Persona Subgraph Search", accent=U.OCHRE)

    s.add_image_box(
        U.LEFT, 1.48, 6.20, 2.45,
        FIGURES_DIR / "fig04_localkg_pipeline.png",
        "LocalKG ingestion pipeline",
        header="Hybrid Ingestion + VAD Weighting",
        accent=U.OCHRE, label="lkg_pipe",
    )
    s.add_image_box(
        7.05, 1.48, 5.63, 3.25,
        FIGURES_DIR / "kg_single_remedy.png",
        "Arnica montana single-remedy subgraph",
        header="Arnica montana (59 Nodes, 93 Cited Edges)",
        accent=U.BLUE, label="lkg_arnica",
    )
    s.add_table(
        U.LEFT, 4.10, 6.20,
        [1.80, 0.90, 0.90, 0.90, 1.70],
        ["Extractor", "Recall", "Prec.", "F1", "Failed Chunks"],
        [
            ["Rule-based", "61.5%", "4.0%", "7.5%", "0"],
            ["Model (120B)", "80.8%", "4.9%", "9.2%", "24 (21%)"],
            ["Hybrid (Ours)", "80.8%", "5.4%", "10.1%", "0 (fallback)"],
        ],
        row_h_in=0.42, header_h_in=0.44, font_pt=11.0,
        alignments=["l", "ctr", "ctr", "ctr", "ctr"],
        highlight_rows={2: U.EMERALD_TINT}, bold_rows={2},
        label="tbl_extract",
    )
    s.add_card(
        7.05, 4.90, 5.63, 1.72,
        title="PersonaQueryEngine Speed & Control",
        bullets=[
            "Inverted token index + 2-hop threshold pruning",
            "Confident (theta=0.70): 1.43 ms (2.56x vs. 3.65 ms scan)",
            "Exploratory (theta=0.35): 1.95 ms (1.87x speedup)",
        ],
        accent=U.EMERALD, title_size=14.5, bullet_size=12.5, label="lkg_persona",
    )
    notes6 = (
        "For LocalKG, pure LLM extraction failed schema validation on 21% of archaic Materia Medica chunks. Our Hybrid extractor "
        "proposes rule-grounded candidates first and audits them with gpt-oss-120b, matching 80.8% keynote recall with zero failed "
        "batches and exact source quotes. Each symptom is scored by VAD affect and linear weight W. At query time, PersonaQueryEngine "
        "uses an inverted token index with a single threshold theta: Confident mode runs in 1.43 ms (2.56x faster than linear scan), "
        "while Exploratory mode expands wider differential subgraphs in 1.95 ms."
    )
    slides.append((s, notes6))

    # ------------------------------------------------------------------
    # Slide 07: Main Results - Bank v3 & Integration
    # ------------------------------------------------------------------
    s = U.SlideBuilder(7, "Slide 7")
    s.add_chrome("MAIN RESULTS: BANK V3", "26x Safer Decisions & Sub-4 ms End-to-End Execution", accent=U.EMERALD)

    s.add_image_box(
        U.LEFT, 1.48, 5.55, 3.85,
        FIGURES_DIR / "fig08_bankv3_acc_unsafe.png",
        "Bank v3 accuracy and unsafe error across generations",
        header="Bank v3 (700 Episodes, 480 Queries/Split)",
        accent=U.BLUE, label="b3_acc",
    )
    s.add_image_box(
        6.40, 1.48, 6.28, 2.55,
        FIGURES_DIR / "fig09_bankv3_tide_budget.png",
        "Bank v3 TIDE accuracy vs budget",
        header="TIDE Anytime Budget (Urgent Mode)",
        accent=U.OCHRE, label="b3_tide",
    )
    s.add_kpi_card(
        6.40, 4.20, 3.04, 1.15,
        "26x Safer",
        f"Unsafe rate {b3_gen['G4: Core v2 (Per-Action Z)']['unsafe_clean']:.1f}% (G4) -> {b3_gen['G5: HyST (Hard Slot + Soft Kernel)']['unsafe_clean']:.1f}% (HyST)",
        accent=U.EMERALD, value_size=24.0, caption_size=11.5, label="kpi_unsafe",
    )
    s.add_kpi_card(
        9.64, 4.20, 3.04, 1.15,
        f"{b3_gen['G7: SHMF (Auto-Relaxed Filter)']['accuracy_clean']:.1f}% Acc",
        f"G7 SHMF recovers 18.3% empty ({b3_gen['G9: TIDE (Spreading Activation)']['accuracy_clean']:.1f}% TIDE)",
        accent=U.BLUE, value_size=24.0, caption_size=11.5, label="kpi_shmf",
    )
    s.add_kpi_card(
        6.40, 5.48, 3.04, 1.15,
        f"{b3_tide['B=3']['accuracy_pct']:.1f}% at B=3",
        f"Reads {b3_tide['B=3']['read_ratio']} vs {b3_tide['full']['accuracy_pct']:.1f}% full read",
        accent=U.OCHRE, value_size=24.0, caption_size=11.5, label="kpi_tide",
    )
    s.add_kpi_card(
        9.64, 5.48, 3.04, 1.15,
        "3.91 ms",
        "Mean bridge latency (p95 5.41 ms); 38/38 tests pass",
        accent=U.INK, value_size=24.0, caption_size=11.5, label="kpi_bridge",
    )
    s.add_card(
        U.LEFT, 5.48, 5.55, 1.15,
        body_paras=[
            U.ParaSpec([
                U.RunSpec("Key Finding: ", font=U.FONT_SERIF, size_pt=13.0, color=U.INK, bold=True),
                U.RunSpec("HyST hard slots drop unsafe errors 26-fold; TIDE maintains 1.2% unsafe error across all budgets.", font=U.FONT_SANS, size_pt=12.0, color=U.CHARCOAL),
            ], line_pct=120, space_after_pt=0.0)
        ],
        accent=U.BLUE, accent_side="left", label="b3_note",
    )
    notes7 = (
        "Here are our headline results on the 700-episode Bank v3 benchmark and the integrated bridge. "
        "First, adding HyST hard-slot constraints cuts unsafe actions 26-fold, from 31.2% in G4 down to 1.2%. "
        "Second, SHMF automatic relaxation recovers the 18.3% of queries where strict filtering emptied the bucket, "
        "lifting clean accuracy to 75.6% (and 75.0% in G9 TIDE). Third, in urgent anytime mode, reading just the top 2.2 "
        "candidates at B=3 yields 71.9% accuracy - beating a full read at 64.8%. End-to-end bridge latency averages 3.91 ms."
    )
    slides.append((s, notes7))

    # ------------------------------------------------------------------
    # Slide 08: Study A - Extended Perceptual Indexing on MMKG
    # ------------------------------------------------------------------
    s = U.SlideBuilder(8, "Slide 8")
    s.add_chrome("COMPARISON STUDY A (MMKG, N=953)", "Extended Perceptual Indexing vs. MPCS Generations", accent=U.BLUE)

    s.add_image_box(
        U.LEFT, 1.48, 6.20, 3.55,
        FIGURES_DIR / "fig10_mmkg_study_a.png",
        "Study A comparison chart on MMKG",
        accent=U.BLUE, label="img_sa",
    )
    sa_order = [
        ("Exact KNN (Cosine)", "Exact KNN"),
        ("BM25 Inverted Index", "BM25"),
        ("dlCBF Gate", "dlCBF Gate"),
        ("Cuckoo Filter Gate", "Cuckoo Gate"),
        ("SimHash LSH (64-bit)", "SimHash LSH"),
        ("Slot Inverted Bitset", "Slot Bitset"),
        ("NSW Proximity Graph", "NSW Graph"),
        ("B2 Global Top-5", "MPCS B2"),
        ("G5 HyST", "G5 HyST"),
        ("G9 TIDE", "G9 TIDE"),
    ]
    sa_rows = []
    for key, short in sa_order:
        r = sa[key]
        sa_rows.append([
            short,
            f"{r['space_kb']:.1f}",
            f"{r['latency_mean_ms']:.3f}",
            f"{r['clean_acc']:.1f}%",
            f"{r['noisy_acc']:.1f}%",
            f"{r['clean_unsafe']:.1f}%",
        ])
    s.add_table(
        7.02, 1.48, 5.66,
        [1.46, 0.80, 0.90, 0.84, 0.84, 0.82],
        ["Method", "KB", "Lat (ms)", "Clean", "Noisy", "Unsafe"],
        sa_rows,
        row_h_in=0.41, header_h_in=0.44, font_pt=10.8,
        alignments=["l", "r", "r", "r", "r", "r"],
        highlight_rows={2: U.EMERALD_TINT, 5: U.BLUE_TINT, 9: U.OCHRE_TINT},
        bold_rows={2, 5, 9},
        label="tbl_sa",
    )
    s.add_kpi_card(
        U.LEFT, 5.20, 1.98, 1.40,
        f"{sa['dlCBF Gate']['clean_acc']:.1f}%",
        "dlCBF / Cuckoo clean (drops to 45.7% noisy)",
        accent=U.EMERALD, value_size=21.0, caption_size=11.0, label="sa_k1",
    )
    s.add_kpi_card(
        2.76, 5.20, 1.98, 1.40,
        f"{sa['Slot Inverted Bitset']['noisy_acc']:.1f}%",
        f"Slot Bitset best noisy ({sa['Slot Inverted Bitset']['space_kb']:.1f} KB)",
        accent=U.BLUE, value_size=21.0, caption_size=11.0, label="sa_k2",
    )
    s.add_kpi_card(
        4.87, 5.20, 1.98, 1.40,
        "71% Cut",
        f"NSW scans {sa['NSW Proximity Graph']['scanned_clean']:.0f}/953 ({sa['NSW Proximity Graph']['clean_acc']:.1f}% clean)",
        accent=U.OCHRE, value_size=21.0, caption_size=11.0, label="sa_k3",
    )
    notes8 = (
        "Turning to our new evaluation directly on the 953 Materia Medica KG clinical occurrences: "
        "Study A benchmarks 7 perceptual indexing structures alongside MPCS generations on 300 clean and 300 noisy queries. "
        "Exact hash gates (dlCBF and Cuckoo Filter) reach 95.0% clean accuracy in just 0.02 ms, but drop to 45.7% under a single noisy "
        "attribute because they only recognize exact repeats. Slot Inverted Bitset leads noisy robustness at 77.7% in 48.9 KB, and NSW Graph "
        "cuts candidate scans by 71%. Crucially, default G9 TIDE (Urgent=False) hits 42.3% here - which Study B explains next."
    )
    slides.append((s, notes8))

    # ------------------------------------------------------------------
    # Slide 09: Study B1 - MPCS G9 TIDE Component Ablation (MMKG)
    # ------------------------------------------------------------------
    s = U.SlideBuilder(9, "Slide 9")
    s.add_chrome("ABLATION STUDY B1 (MMKG)", "MPCS G9 TIDE: Hard Slots Are Essential, Full-Read Dilutes", accent=U.OCHRE)

    s.add_image_box(
        U.LEFT, 1.48, 6.20, 3.65,
        FIGURES_DIR / "fig11_mmkg_study_b1.png",
        "Study B1 G9 TIDE 8-variant ablation chart",
        accent=U.OCHRE, label="img_sb1",
    )
    sb1_order = [
        ("Full G9 TIDE (Urgent=False)", "Full G9 TIDE (Urgent=False)"),
        ("w/o TIDE Spread (hops=0, w_g=0)", "w/o TIDE Spread"),
        ("w/o VAD Affect & Salience (salience_gain=0, affect=False)", "w/o VAD Affect"),
        ("w/o KERL Near-Miss Guard", "w/o KERL Guard"),
        ("w/o SHMF Auto-Relaxation", "w/o SHMF Relax"),
        ("w/o HyST Hard Slots (Soft Only)", "w/o HyST Hard Slots"),
        ("w/o Expert Grade Boost (boost=1.0)", "w/o Expert Boost"),
        ("w/o Full-Read (Urgent B=3)", "w/o Full-Read (Urgent B=3)"),
    ]
    sb1_rows = []
    for key, short in sb1_order:
        r = sb1[key]
        sb1_rows.append([
            short,
            f"{r['clean_acc']:.1f}%",
            f"{r['noisy_acc']:.1f}%",
            f"{r['clean_unsafe']:.1f}%",
            f"{r['clean_lat_ms']:.2f}",
        ])
    s.add_table(
        7.02, 1.48, 5.66,
        [2.46, 0.80, 0.80, 0.80, 0.80],
        ["TIDE Variant", "Clean", "Noisy", "Unsafe", "Lat(ms)"],
        sb1_rows,
        row_h_in=0.44, header_h_in=0.44, font_pt=10.8,
        alignments=["l", "r", "r", "r", "r"],
        highlight_rows={5: U.CRIMSON_TINT, 7: U.EMERALD_TINT},
        bold_rows={5, 7},
        label="tbl_sb1",
    )
    s.add_kpi_card(
        U.LEFT, 5.30, 3.02, 1.30,
        f"{sb1['w/o Full-Read (Urgent B=3)']['clean_acc']:.1f}%",
        f"Urgent B=3 (+48.3 pp clean, {sb1['w/o Full-Read (Urgent B=3)']['noisy_acc']:.1f}% noisy)",
        accent=U.EMERALD, value_size=24.0, caption_size=11.5, label="sb1_k1",
    )
    s.add_kpi_card(
        3.83, 5.30, 3.02, 1.30,
        f"{sb1['w/o HyST Hard Slots (Soft Only)']['clean_acc']:.1f}%",
        f"Removing HyST collapses acc (5.1x slower: {sb1['w/o HyST Hard Slots (Soft Only)']['clean_lat_ms']:.1f} ms)",
        accent=U.CRIMSON, value_size=24.0, caption_size=11.5, label="sb1_k2",
    )
    s.add_card(
        7.02, 5.62, 5.66, 0.98,
        body_paras=[
            U.ParaSpec([
                U.RunSpec("Root Cause (kerl_layer.py): ", font=U.FONT_SERIF, size_pt=12.5, color=U.INK, bold=True),
                U.RunSpec("_head_a averages k=5 candidates per action in full-read; Urgent B=3 sets k=1, preventing majority 'observe' dilution.", font=U.FONT_SANS, size_pt=11.5, color=U.CHARCOAL),
            ], line_pct=118, space_after_pt=0.0)
        ],
        accent=U.BLUE, accent_side="left", label="sb1_note",
    )
    notes9 = (
        "Study B1 ablates all 8 components of MPCS G9 TIDE on the MMKG dataset. Two findings stand out. "
        "First, removing HyST hard slots collapses accuracy to 12.7% and slows latency 5.1x (to 34.48 ms) because soft-only "
        "scanning loses structural constraints. Second, replacing unconstrained full-bucket reading with Urgent B=3 jumps clean "
        "accuracy by +48.3 percentage points - from 42.7% to 91.0% - and noisy accuracy to 78.7%, while cutting unsafe errors "
        "from 26.0% to 11.7%. Code inspection in kerl_layer.py confirms why: _head_a averages rewards over k=5 candidates per action, "
        "allowing frequent 'observe' records (495/953) to dilute exact matches unless Urgent mode sets k=1."
    )
    slides.append((s, notes9))

    # ------------------------------------------------------------------
    # Slide 10: Study B2 & B3 - Anytime Budgets & Sufficiency Routing
    # ------------------------------------------------------------------
    s = U.SlideBuilder(10, "Slide 10")
    s.add_chrome("STUDIES B2 & B3 (MMKG)", "Anytime Budget Scaling & Sufficiency Routing", accent=U.BLUE)

    s.add_image_box(
        U.LEFT, 1.48, 6.15, 3.00,
        FIGURES_DIR / "fig12_mmkg_tide_budget.png",
        "MMKG Study B2 TIDE accuracy vs budget",
        header="Anytime Budget Curve (Urgent=True)",
        accent=U.BLUE, label="img_sb2",
    )
    s.add_card(
        U.LEFT, 4.66, 6.15, 1.94,
        title="Why Smaller Budgets Win on MMKG",
        bullets=[
            "Buckets average 67.3 candidates across 452 percepts",
            "B=3 reads 2.8/67.3 top-activated matches (91.0%)",
            "B=10 minimizes unsafe error to 3.9% (79.0% acc)",
            "SUBGRAPH handles 80.3% of queries needing context",
        ],
        accent=U.OCHRE, title_size=14.5, bullet_size=12.2, label="sb2_take",
    )
    b2_rows = []
    for b_lbl in ["B=3", "B=5", "B=10", "B=20", "B=50", "Full"]:
        rc = sb2["clean"][b_lbl]
        rn = sb2["noisy"][b_lbl]
        b2_rows.append([
            b_lbl,
            rc["read_ratio"],
            f"{rc['accuracy_pct']:.1f}%",
            f"{rn['accuracy_pct']:.1f}%",
            f"{rc['unsafe_pct']:.1f}%",
            f"{rc['decision_latency_ms']:.2f}",
        ])
    tbl_end = s.add_table(
        7.00, 1.48, 5.68,
        [0.78, 1.05, 0.95, 0.95, 0.95, 1.00],
        ["Budget", "Read/Avail", "Clean", "Noisy", "Unsafe", "Lat(ms)"],
        b2_rows,
        row_h_in=0.40, header_h_in=0.42, font_pt=10.8,
        alignments=["l", "ctr", "r", "r", "r", "r"],
        highlight_rows={0: U.EMERALD_TINT, 2: U.BLUE_TINT, 5: U.CRIMSON_TINT},
        bold_rows={0, 2},
        label="tbl_sb2",
    )
    b3_rows = []
    for mode in ["DIRECT", "SUBGRAPH", "UNGROUNDED"]:
        rc = sb3["clean"][mode]
        rn = sb3["noisy"][mode]
        b3_rows.append([
            mode,
            f"{rc['count']} ({rc['share_pct']:.1f}%)",
            f"{rc['accuracy_pct']:.1f}%",
            f"{rn['accuracy_pct']:.1f}%",
        ])
    s.add_table(
        7.00, tbl_end + 0.25, 5.68,
        [1.58, 1.50, 1.30, 1.30],
        ["Route (Urgent=False)", "Share", "Clean Acc", "Noisy Acc"],
        b3_rows,
        row_h_in=0.40, header_h_in=0.42, font_pt=10.8,
        alignments=["l", "ctr", "r", "r"],
        highlight_rows={0: U.BLUE_TINT, 1: U.OCHRE_TINT},
        label="tbl_sb3",
    )
    notes10 = (
        "Studies B2 and B3 sweep the candidate budget B and sufficiency routing on MMKG. Because 953 clinical occurrences map "
        "into 452 unique percepts, each bucket averages 67.3 candidates. Accuracy degrades monotonically as B grows: 91.0% at B=3, "
        "87.0% at B=5, 79.0% at B=10 (where unsafe error hits its minimum of 3.9%), down to 44.0% on Full Read. Under Study B3 "
        "routing, 19.7% take the DIRECT fast path and 80.3% escalate to SUBGRAPH with zero ungrounded failures."
    )
    slides.append((s, notes10))

    # ------------------------------------------------------------------
    # Slide 11: Study C - PersonaQueryEngine Ablation (MMKG)
    # ------------------------------------------------------------------
    s = U.SlideBuilder(11, "Slide 11")
    s.add_chrome("ABLATION STUDY C (MMKG)", "PersonaQueryEngine: 1-Hop Sufficiency & Hub Bias", accent=U.EMERALD)

    s.add_image_box(
        U.LEFT, 1.48, 6.20, 3.65,
        FIGURES_DIR / "fig13_mmkg_study_c.png",
        "Study C PersonaQueryEngine 8-variant ablation chart",
        accent=U.EMERALD, label="img_sc",
    )
    sc_order = [
        ("Full Exploratory Persona (theta=0.35)", "Exploratory (theta=0.35)"),
        ("Full Confident Persona (theta=0.70)", "Confident (theta=0.70)"),
        ("w/o 2-Hop Spreading Activation (hops=0)", "w/o Spreading (hops=0)"),
        ("w/o 2nd Hop (hops=1)", "w/o 2nd Hop (hops=1)"),
        ("w/o VAD Arousal & Grade Multiplier (mu_v=1.0)", "w/o VAD & Grade (mu_v=1.0)"),
        ("w/o Clinical Synonym Expansion", "w/o Synonyms"),
        ("w/o Edge-Weight Modulation (uniform w_uv=1.0)", "w/o Edge-Weight (w_uv=1)"),
        ("w/o Precomputed Inverted Index (Linear Scan)", "Linear Scan Baseline"),
    ]
    sc_rows = []
    for key, short in sc_order:
        r = sc[key]
        sc_rows.append([
            short,
            f"{r['mean_pruned_pct']:.1f}%",
            f"{r['remedy_top1_pct']:.1f}%",
            f"{r['remedy_top3_pct']:.1f}%",
            f"{r['mean_lat_ms']:.2f}",
        ])
    s.add_table(
        7.02, 1.48, 5.66,
        [2.46, 0.80, 0.80, 0.80, 0.80],
        ["Variant (400 Calls)", "Pruned", "Top-1", "Top-3", "Lat(ms)"],
        sc_rows,
        row_h_in=0.44, header_h_in=0.44, font_pt=10.8,
        alignments=["l", "r", "r", "r", "r"],
        highlight_rows={3: U.BLUE_TINT, 4: U.EMERALD_TINT, 7: U.CRIMSON_TINT},
        bold_rows={3, 4},
        label="tbl_sc",
    )
    s.add_kpi_card(
        U.LEFT, 5.30, 3.02, 1.30,
        f"{sc['w/o VAD Arousal & Grade Multiplier (mu_v=1.0)']['remedy_top1_pct']:.0f}% / {sc['w/o VAD Arousal & Grade Multiplier (mu_v=1.0)']['remedy_top3_pct']:.0f}%",
        "Top-1 / Top-3 with mu_v=1.0 (fixes Grade-3 hub bias)",
        accent=U.EMERALD, value_size=22.0, caption_size=11.5, label="sc_k1",
    )
    s.add_kpi_card(
        3.83, 5.30, 3.02, 1.30,
        "hops = 1",
        f"Matches hops=2 ({sc['w/o 2nd Hop (hops=1)']['remedy_top1_pct']:.0f}% / {sc['w/o 2nd Hop (hops=1)']['remedy_top3_pct']:.0f}%) & saves 13% latency",
        accent=U.BLUE, value_size=22.0, caption_size=11.5, label="sc_k2",
    )
    s.add_card(
        7.02, 5.62, 5.66, 0.98,
        body_paras=[
            U.ParaSpec([
                U.RunSpec("Edge-Weight Saturation: ", font=U.FONT_SERIF, size_pt=12.5, color=U.INK, bold=True),
                U.RunSpec("All 2,024 MMKG edges lie in [1.0, 2.95], so min(1.0, edge_w) clamps every link identically to 1.0.", font=U.FONT_SANS, size_pt=11.5, color=U.CHARCOAL),
            ], line_pct=118, space_after_pt=0.0)
        ],
        accent=U.OCHRE, accent_side="left", label="sc_note",
    )
    notes11 = (
        "Study C ablates PersonaQueryEngine across 40 clinical queries times 10 runs on the 1,106-node MMKG graph. "
        "Removing spreading activation (hops=0) drops remedy recall to 0%, proving graph traversal is indispensable. "
        "Yet hops=1 matches hops=2 identically at 60% Top-1 and 80% Top-3 while saving 13% latency, because MMKG is a "
        "bipartite Remedy-Symptom star topology. Most strikingly, setting mu_v=1.0 lifts Top-1 recall from 60% to 80% and "
        "Top-3 to 90% by eliminating Grade-3 polychrest hub bias. Finally, uniform w_uv=1.0 has zero effect because min(1.0, edge_w) "
        "in persona_engine.py clamps all [1.0, 2.95] MMKG edges to 1.0."
    )
    slides.append((s, notes11))

    # ------------------------------------------------------------------
    # Slide 12: What We Achieved, What Remains & Future Work
    # ------------------------------------------------------------------
    s = U.SlideBuilder(12, "Slide 12")
    s.add_chrome("CONCLUSION & OUTLOOK", "What We Achieved, What Remains & Next Steps", accent=U.INK)

    s.add_card(
        U.LEFT, 1.48, 5.88, 3.60,
        title="What We Achieved",
        bullets=[
            "26x unsafe-action drop on Bank v3 (31.2% -> 1.2%)",
            "91.0% MMKG TIDE accuracy at Urgent B=3 (5.67 ms)",
            "80% Top-1 / 90% Top-3 MMKG remedy recall (mu_v=1.0)",
            "80.8% hybrid extraction recall with 0 failed chunks",
            "3.91 ms end-to-end CPU bridge; 38/38 tests pass",
        ],
        accent=U.EMERALD, title_size=16.0, bullet_size=13.2, label="done_card",
    )
    s.add_card(
        6.80, 1.48, 5.88, 3.60,
        title="What Remains / Limitations",
        bullets=[
            "Full-read _head_a (k=5) dilutes dense MMKG buckets (42.7%)",
            "min(1.0, edge_w) saturates [1.0, 2.95] graph edge weights",
            "Heuristic regex percept projection; synthetic Bank v3",
            "Small keynote gold set (26 keynotes / 8 remedies)",
            "Historical source text, not validated clinical evidence",
        ],
        accent=U.CRIMSON, title_size=16.0, bullet_size=13.2, label="gap_card",
    )
    s.add_card(
        U.LEFT, 5.28, U.CONTENT_W, 1.32,
        title="Immediate Future Work",
        body_paras=[
            U.ParaSpec(
                [
                    U.RunSpec("1. ", font=U.FONT_SERIF, size_pt=13.5, color=U.BLUE, bold=True),
                    U.RunSpec("Global top-k voting inside HyST/TIDE   ", font=U.FONT_SANS, size_pt=12.8, color=U.CHARCOAL),
                    U.RunSpec("2. ", font=U.FONT_SERIF, size_pt=13.5, color=U.BLUE, bold=True),
                    U.RunSpec("Degree & w_uv/w_max normalization   ", font=U.FONT_SANS, size_pt=12.8, color=U.CHARCOAL),
                    U.RunSpec("3. ", font=U.FONT_SERIF, size_pt=13.5, color=U.BLUE, bold=True),
                    U.RunSpec("UMLS / SNOMED CT entity linking   ", font=U.FONT_SANS, size_pt=12.8, color=U.CHARCOAL),
                    U.RunSpec("4. ", font=U.FONT_SERIF, size_pt=13.5, color=U.BLUE, bold=True),
                    U.RunSpec("Learn bridge thresholds from clinician feedback", font=U.FONT_SANS, size_pt=12.8, color=U.CHARCOAL),
                ],
                line_pct=125, space_after_pt=0.0,
            )
        ],
        accent=U.BLUE, accent_side="left", title_size=15.0, label="next_card",
    )
    notes12 = (
        "To wrap up with an honest assessment of what we achieved and what remains: we delivered an auditable, sub-4 ms "
        "neuro-symbolic decision loop that cut unsafe actions 26-fold on Bank v3, hit 91.0% MMKG accuracy under Urgent B=3, "
        "reached 80% Top-1 / 90% Top-3 remedy recall, and passed all 38 unit and bridge tests. On the limitation side, "
        "our ablations exposed why full-read averaging (k=5) hurts dense MMKG buckets, why edge weights saturate at 1.0, and "
        "why a larger clinical gold set and UMLS/SNOMED normalization are the clear next steps. Thank you, and we welcome questions."
    )
    slides.append((s, notes12))

    return slides


def build_concise_pptx() -> Path:
    """Assemble and verify report/PPT/BTP_PPT_Concise.pptx."""
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
            zout.writestr(f"ppt/slides/slide{idx}.xml", sb.to_xml())
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
    out = build_concise_pptx()
    print(f"Built and verified {out} (12 slides)")

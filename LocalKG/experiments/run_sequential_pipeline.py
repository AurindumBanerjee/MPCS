from __future__ import annotations

"""Automated Sequential Knowledge Graph Pipeline (Arnica -> Belladonna -> Full Materia Medica).

Executes the 3-stage extraction & visualization workflow sequentially without manual
intervention unless an unrecoverable error occurs:
  Stage 1: Arnica montana (Boericke + Hahnemann + PubMed/MeSH references in docs/)
           -> data/extracted/kg_arnica_montana.jsonl
           -> data/extracted/kg_arnica_montana.html
           -> data/extracted/kg_arnica_montana.graph.json
  Stage 2: Belladonna (Boericke + Hahnemann + PubMed/MeSH references in docs/)
           -> data/extracted/kg_belladonna.jsonl
           -> data/extracted/kg_belladonna.html
           -> data/extracted/kg_belladonna.graph.json
  Stage 3: Entire Materia Medica (Hahnemann Vol. II + Boericke polychrests + PubMed)
           -> data/extracted/kg_full_materia_medica.jsonl
           -> data/extracted/kg_full_materia_medica.html
           -> data/extracted/kg_full_materia_medica.graph.json
           (incrementally saved and re-exported after every remedy chapter!)

Strictly enforces the machine-wide CPU & resource rules:
  1. Checks CPU load before starting and between stages; waits 60s if load > 60%.
  2. Acquires and updates D:\\MyStuff\\GitHub\\.heavy-job.lock, deleting it immediately on exit/failure.
  3. Runs a single sequential worker (workers=1) with OLLAMA_NUM_THREAD=6 and OMP_NUM_THREADS=4.
"""

import atexit
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Cap thread pools before importing numeric libraries
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"
os.environ["OPENBLAS_NUM_THREADS"] = "4"
os.environ["NUMEXPR_NUM_THREADS"] = "4"
os.environ["OLLAMA_NUM_THREAD"] = "6"

# Ensure LocalKG/src is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
LOCALKG_ROOT = REPO_ROOT / "LocalKG"
sys.path.insert(0, str(LOCALKG_ROOT / "src"))

from lkg.build_remedy import LOCK_PATH, append_pubmed_literature_to_extracted
from lkg.config import DATA_DIR
from lkg.extract.extractor import ExtractionPipeline
from lkg.ingest.chunker import create_chunks_from_parsed
from lkg.ingest.parse_pdf import (
    HAHNEMANN_VOL2_RANGES,
    parse_boericke_pages,
    parse_hahnemann_remedy_pages,
)
from lkg.llm.ollama_client import OllamaClient
from lkg.viz.graph_viz import export_interactive_html

BOERICKE_PDF = REPO_ROOT / "extraction_KRAG" / "homeopathy-kg" / "data" / "Materia_medica.pdf"
HAHNEMANN_PDF = REPO_ROOT / "docs" / "Materia Medica Samuel Hahnemann.pdf"
PUBMED_JSON = REPO_ROOT / "docs" / "Arnica_and_Belladonna_PubMed_Records.json"
STATUS_FILE = DATA_DIR / "extracted" / "sequential_pipeline_status.json"
OLLAMA_EXE = Path(r"D:\MyStuff\Installations\Ollama\ollama.exe")
OLLAMA_MODELS_DIR = r"D:\MyStuff\Installations\Ollama_Models"
_spawned_ollama_proc: subprocess.Popen | None = None


def ensure_ollama_running(client: OllamaClient) -> dict[str, Any]:
    """Ensure local Ollama server is running; if not, spawn it with constrained CPU threads."""
    global _spawned_ollama_proc
    health = client.health_check()
    if health.get("status") == "ok":
        return health

    if OLLAMA_EXE.exists():
        log_status("init", f"Ollama not running on localhost:11434; starting {OLLAMA_EXE} serve...")
        env = os.environ.copy()
        env["OLLAMA_MODELS"] = OLLAMA_MODELS_DIR
        env["OLLAMA_NUM_PARALLEL"] = "1"
        env["OMP_NUM_THREADS"] = "6"
        creationflags = 0x00004000 | 0x08000000 if sys.platform == "win32" else 0  # BELOW_NORMAL | CREATE_NO_WINDOW
        _spawned_ollama_proc = subprocess.Popen(
            [str(OLLAMA_EXE), "serve"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        for _ in range(15):
            time.sleep(1.0)
            health = client.health_check()
            if health.get("status") == "ok":
                return health
    return health


def cleanup_resources() -> None:
    """Release lock and stop Ollama if we spawned it."""
    global _spawned_ollama_proc
    release_lock()
    if _spawned_ollama_proc is not None:
        try:
            _spawned_ollama_proc.terminate()
            _spawned_ollama_proc.wait(timeout=5)
        except Exception:
            pass
        _spawned_ollama_proc = None


def lower_process_priority() -> None:
    """Set current process to BELOW_NORMAL_PRIORITY_CLASS on Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.kernel32.SetPriorityClass(handle, BELOW_NORMAL_PRIORITY_CLASS)
        except Exception:
            pass


def get_cpu_load() -> float:
    """Check current total CPU load percentage on Windows via Win32 GetSystemTimes."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            i1, k1, u1 = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
            i2, k2, u2 = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
            ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i1), ctypes.byref(k1), ctypes.byref(u1))
            time.sleep(0.5)
            ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i2), ctypes.byref(k2), ctypes.byref(u2))
            ft = lambda f: (f.dwHighDateTime << 32) | f.dwLowDateTime
            di = ft(i2) - ft(i1)
            dt = (ft(k2) - ft(k1)) + (ft(u2) - ft(u1))
            if dt > 0:
                return max(0.0, min(100.0, 100.0 * (1.0 - di / dt)))
        except Exception:
            pass
    return 25.0


def wait_for_cpu_headroom(threshold: float = 60.0) -> float:
    """Wait in 60s intervals if CPU usage is above threshold."""
    while True:
        load = get_cpu_load()
        if load <= threshold:
            return load
        log_status("waiting_cpu", f"CPU load {load:.1f}% > {threshold}%, sleeping 60s...")
        time.sleep(60)


def update_lock(stage: str) -> None:
    """Write single-line lock file D:\\MyStuff\\GitHub\\.heavy-job.lock."""
    line = (
        f"repo=MPCS/LocalKG | start={time.strftime('%Y-%m-%d %H:%M:%S')} "
        f"| job={stage} | cmd=python LocalKG/experiments/run_sequential_pipeline.py\n"
    )
    LOCK_PATH.write_text(line, encoding="utf-8")


def release_lock() -> None:
    """Remove lock file immediately on completion or failure."""
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
    except Exception:
        pass


atexit.register(cleanup_resources)


def log_status(stage: str, message: str, **extra: Any) -> None:
    """Write live progress JSON and print timestamped status line."""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "timestamp": ts,
        "stage": stage,
        "message": message,
        **extra,
    }
    try:
        STATUS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    print(f"[{ts}] [{stage}] {message}", flush=True)


def consolidate_remedy_records(
    records: list[dict[str, Any]],
    remedy_name: str,
    source_id: str,
    target_chars: int = 2400,
) -> list[dict[str, Any]]:
    """Group short section records of a remedy into rich, multi-section records (~2400 chars)
    so each remedy takes 2-4 high-yield LLM calls while preserving section context.
    """
    consolidated: list[dict[str, Any]] = []
    buf_texts: list[str] = []
    buf_sections: list[str] = []
    buf_page: int = 1
    buf_len = 0

    for rec in records:
        sec = rec.get("section", "General")
        txt = rec.get("marked_text", "").strip()
        if not txt:
            continue
        tagged = f"[{sec}] {txt}"
        if buf_len + len(tagged) > target_chars and buf_texts:
            primary_sec = "Mind" if "Mind" in buf_sections else buf_sections[0]
            consolidated.append({
                "source_id": rec.get("source_id", source_id),
                "remedy_name": remedy_name,
                "section": primary_sec,
                "page": buf_page,
                "marked_text": "\n\n".join(buf_texts),
            })
            buf_texts = []
            buf_sections = []
            buf_len = 0

        if not buf_texts:
            buf_page = rec.get("page", 1)
        buf_texts.append(tagged)
        buf_sections.append(sec)
        buf_len += len(tagged)

    if buf_texts:
        primary_sec = "Mind" if "Mind" in buf_sections else buf_sections[0]
        consolidated.append({
            "source_id": source_id,
            "remedy_name": remedy_name,
            "section": primary_sec,
            "page": buf_page,
            "marked_text": "\n\n".join(buf_texts),
        })

    return consolidated


def prepare_single_remedy_chunks(
    remedy_name: str,
    boericke_pages_0: list[int],
    hahnemann_range_0: tuple[int, int],
    slug: str,
) -> Path:
    """Parse Boericke + Hahnemann pages for a single remedy and write consolidated chunks JSONL."""
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz  # type: ignore

    records: list[dict[str, Any]] = []

    if BOERICKE_PDF.exists():
        b_doc = fitz.open(BOERICKE_PDF)
        b_recs = parse_boericke_pages(
            b_doc,
            page_indices=boericke_pages_0,
            source_key="boericke_pocket_manual",
            forced_remedy=remedy_name,
        )
        records.extend(
            consolidate_remedy_records(
                b_recs,
                remedy_name=remedy_name,
                source_id="source:boericke_pocket_manual",
                target_chars=2400,
            )
        )
        b_doc.close()

    if HAHNEMANN_PDF.exists():
        h_doc = fitz.open(HAHNEMANN_PDF)
        h_recs = parse_hahnemann_remedy_pages(
            h_doc,
            start_page_0=hahnemann_range_0[0],
            end_page_0=hahnemann_range_0[1],
            remedy_name=remedy_name,
            source_key="hahnemann_materia_medica_pura",
            max_pages_per_remedy=6,
        )
        records.extend(
            consolidate_remedy_records(
                h_recs,
                remedy_name=remedy_name,
                source_id="source:hahnemann_materia_medica_pura",
                target_chars=2600,
            )
        )
        h_doc.close()

    parsed_path = DATA_DIR / "parsed" / f"parsed_{slug}.jsonl"
    parsed_path.parent.mkdir(parents=True, exist_ok=True)
    with open(parsed_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    chunks_path = DATA_DIR / "chunks" / f"chunks_{slug}.jsonl"
    create_chunks_from_parsed(parsed_path, output_path=chunks_path, max_chunk_chars=3000)
    return chunks_path


def run_remedy_stage(
    stage_label: str,
    remedy_name: str,
    slug: str,
    boericke_pages_0: list[int],
    hahnemann_range_0: tuple[int, int],
    client: OllamaClient,
) -> Path:
    """Execute extraction, PubMed merge, and HTML KG export for a single remedy."""
    cpu_load = wait_for_cpu_headroom(60.0)
    update_lock(f"{stage_label}:{remedy_name}")
    log_status(stage_label, f"Preparing chunks for {remedy_name} (CPU={cpu_load:.1f}%)")

    chunks_path = prepare_single_remedy_chunks(
        remedy_name=remedy_name,
        boericke_pages_0=boericke_pages_0,
        hahnemann_range_0=hahnemann_range_0,
        slug=slug,
    )
    total_chunks = sum(1 for ln in chunks_path.read_text(encoding="utf-8").splitlines() if ln.strip())
    log_status(stage_label, f"Prepared {total_chunks} consolidated chunks for {remedy_name}")

    run_id = f"kg_{slug}"
    pipeline = ExtractionPipeline(llm_client=client, run_id=run_id, workers=1)

    done_count = 0

    def on_progress(res: dict[str, Any]) -> None:
        nonlocal done_count
        done_count += 1
        occ_cnt = len(res.get("occurrences", []))
        log_status(
            stage_label,
            f"[{remedy_name}] Chunk {done_count}/{total_chunks} ({res.get('section')}) -> {occ_cnt} occurrences",
            remedy=remedy_name,
            chunks_done=done_count,
            chunks_total=total_chunks,
            stats=pipeline.stats,
        )

    extracted_file = pipeline.run_on_chunks_file(chunks_path, progress=on_progress)

    # Append supplementary PubMed & MeSH records from docs/ (idempotent check)
    existing_text = extracted_file.read_text(encoding="utf-8") if extracted_file.exists() else ""
    if "chunk:pmid_" not in existing_text:
        added_pm = append_pubmed_literature_to_extracted(remedy_name, PUBMED_JSON, extracted_file)
        log_status(stage_label, f"Appended {added_pm} PubMed/MeSH literature records for {remedy_name}")

    html_out = DATA_DIR / "extracted" / f"kg_{slug}.html"
    title = f"{remedy_name} — Cognitive-Affective & Clinical Knowledge Graph (MPCS LocalKG v2)"
    export_interactive_html([extracted_file], output_html=html_out, title=title)
    log_status(
        stage_label,
        f"Completed {remedy_name} KG -> {html_out}",
        extracted_jsonl=str(extracted_file),
        html_path=str(html_out),
        stats=pipeline.stats,
    )
    return extracted_file


def run_full_materia_medica_stage(
    client: OllamaClient,
    prior_extracted_files: list[Path],
) -> Path:
    """Stage 3: Run across the full Materia Medica (all remedies in Hahnemann Vol. II + Boericke),
    reusing Arnica and Belladonna already extracted in Stages 1-2, and saving + re-exporting
    the full interactive KG after every remedy chapter.
    """
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz  # type: ignore

    stage_label = "Stage3_Full_Materia_Medica"
    full_run_id = "kg_full_materia_medica"
    full_extracted_file = DATA_DIR / "extracted" / f"{full_run_id}.jsonl"
    full_html_out = DATA_DIR / "extracted" / f"{full_run_id}.html"

    # Seed full_extracted_file with records from Arnica & Belladonna if not already present
    existing_chunk_ids: set[str] = set()
    if full_extracted_file.exists():
        for ln in full_extracted_file.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                try:
                    existing_chunk_ids.add(json.loads(ln).get("chunk_id", ""))
                except Exception:
                    pass

    with open(full_extracted_file, "a", encoding="utf-8") as fout:
        for pfile in prior_extracted_files:
            if pfile.exists():
                for ln in pfile.read_text(encoding="utf-8").splitlines():
                    if not ln.strip():
                        continue
                    rec = json.loads(ln)
                    cid = rec.get("chunk_id", "")
                    if cid and cid not in existing_chunk_ids:
                        fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        existing_chunk_ids.add(cid)

    # Export initial combined KG (Arnica + Belladonna) right away
    export_interactive_html(
        [full_extracted_file],
        output_html=full_html_out,
        title="Full Materia Medica — Cognitive-Affective & Clinical Knowledge Graph (MPCS LocalKG v2)",
    )

    # Prepare chunks for all remaining remedies in Hahnemann's Materia Medica Pura Vol. II
    h_doc = fitz.open(HAHNEMANN_PDF) if HAHNEMANN_PDF.exists() else None
    b_doc = fitz.open(BOERICKE_PDF) if BOERICKE_PDF.exists() else None

    # Boericke page ranges (0-indexed) for the major remedies corresponding to Hahnemann + key polychrests
    boericke_remedy_pages: dict[str, list[int]] = {
        "Aconitum napellus": [20, 21, 22, 23],
        "Ambra grisea": [49, 50],
        "Argentum metallicum": [79, 80],
        "Arsenicum album": [90, 91, 92, 93, 94],
        "Asarum europaeum": [101, 102],
        "Bryonia alba": [146, 147, 148, 149],
        "Camphora": [174, 175],
        "Carbo vegetabilis": [184, 185, 186],
        "Carbo animalis": [181, 182],
        "Chamomilla": [202, 203, 204],
        "Conium maculatum": [244, 245, 246],
        "Drosera rotundifolia": [274, 275],
        "Ferrum metallicum": [296, 297, 298],
        "Hyoscyamus niger": [353, 354, 355],
        "Ignatia amara": [360, 361, 362],
        "Ipecacuanha": [369, 370, 371],
        "Gelsemium sempervirens": [312, 313, 314],
        "Lachesis mutus": [399, 400, 401, 402],
        "Lycopodium clavatum": [423, 424, 425, 426],
        "Mercurius solubilis": [447, 448, 449, 450],
        "Natrum muriaticum": [473, 474, 475, 476],
        "Nux vomica": [492, 493, 494, 495],
        "Phosphorus": [522, 523, 524, 525],
        "Pulsatilla nigricans": [551, 552, 553, 554],
        "Rhus toxicodendron": [568, 569, 570],
        "Sepia officinalis": [597, 598, 599, 600],
        "Silicea": [605, 606, 607, 608],
        "Stramonium": [623, 624, 625],
        "Sulphur": [633, 634, 635, 636],
        "Veratrum album": [674, 675, 676],
    }

    hahnemann_lookup = {rem: (s, e) for s, e, rem in HAHNEMANN_VOL2_RANGES}

    # Build ordered list of remedies to process in Stage 3 (skipping Arnica & Belladonna which are already done)
    stage3_remedies: list[str] = []
    for _, _, rem in HAHNEMANN_VOL2_RANGES:
        if rem not in ("Arnica montana", "Belladonna"):
            stage3_remedies.append(rem)
    for rem in boericke_remedy_pages:
        if rem not in stage3_remedies and rem not in ("Arnica montana", "Belladonna"):
            stage3_remedies.append(rem)

    pipeline = ExtractionPipeline(llm_client=client, run_id=full_run_id, workers=1)

    for idx, rem_name in enumerate(stage3_remedies, start=1):
        cpu_load = wait_for_cpu_headroom(60.0)
        update_lock(f"{stage_label}:{rem_name}_{idx}_of_{len(stage3_remedies)}")
        slug = rem_name.lower().replace(" ", "_")

        rem_records: list[dict[str, Any]] = []
        if b_doc is not None and rem_name in boericke_remedy_pages:
            b_recs = parse_boericke_pages(
                b_doc,
                page_indices=boericke_remedy_pages[rem_name],
                source_key="boericke_pocket_manual",
                forced_remedy=rem_name,
            )
            rem_records.extend(
                consolidate_remedy_records(
                    b_recs,
                    remedy_name=rem_name,
                    source_id="source:boericke_pocket_manual",
                    target_chars=2600,
                )
            )

        if h_doc is not None and rem_name in hahnemann_lookup:
            s_p, e_p = hahnemann_lookup[rem_name]
            h_recs = parse_hahnemann_remedy_pages(
                h_doc,
                start_page_0=s_p,
                end_page_0=e_p,
                remedy_name=rem_name,
                source_key="hahnemann_materia_medica_pura",
                max_pages_per_remedy=5,
            )
            rem_records.extend(
                consolidate_remedy_records(
                    h_recs,
                    remedy_name=rem_name,
                    source_id="source:hahnemann_materia_medica_pura",
                    target_chars=2800,
                )
            )

        if not rem_records:
            continue

        parsed_rem = DATA_DIR / "parsed" / f"parsed_full_{slug}.jsonl"
        with open(parsed_rem, "w", encoding="utf-8") as f:
            for r in rem_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        chunks_rem = DATA_DIR / "chunks" / f"chunks_full_{slug}.jsonl"
        create_chunks_from_parsed(parsed_rem, output_path=chunks_rem, max_chunk_chars=3000)

        # Rewrite chunk IDs to be unique per remedy in the full run
        rewritten_chunks: list[dict[str, Any]] = []
        for ln in chunks_rem.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            c = json.loads(ln)
            c["chunk_id"] = f"chunk:{slug}:{c['chunk_id'].split(':')[-1]}"
            rewritten_chunks.append(c)
        with open(chunks_rem, "w", encoding="utf-8") as f:
            for c in rewritten_chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

        log_status(
            stage_label,
            f"[{idx}/{len(stage3_remedies)}] Extracting {rem_name} ({len(rewritten_chunks)} chunks, CPU={cpu_load:.1f}%)",
            remedy=rem_name,
            remedy_index=idx,
            remedy_total=len(stage3_remedies),
        )

        pipeline.run_on_chunks_file(chunks_rem)

        # Re-export the growing Full Materia Medica HTML graph after each remedy!
        export_interactive_html(
            [full_extracted_file],
            output_html=full_html_out,
            title="Full Materia Medica — Cognitive-Affective & Clinical Knowledge Graph (MPCS LocalKG v2)",
        )
        log_status(
            stage_label,
            f"[{idx}/{len(stage3_remedies)}] Updated {full_html_out.name} after {rem_name}",
            remedy=rem_name,
            remedy_index=idx,
            remedy_total=len(stage3_remedies),
            stats=pipeline.stats,
        )

    if h_doc is not None:
        h_doc.close()
    if b_doc is not None:
        b_doc.close()

    return full_extracted_file


def main() -> None:
    lower_process_priority()

    # Check if an external lock is active (<60 min old)
    if LOCK_PATH.exists():
        age_min = (time.time() - LOCK_PATH.stat().st_mtime) / 60.0
        content = LOCK_PATH.read_text(encoding="utf-8").strip()
        if age_min < 60.0 and "MPCS/LocalKG" not in content:
            raise RuntimeError(f"Another repo holds .heavy-job.lock ({age_min:.1f}m old): {content}")

    try:
        client = OllamaClient()
        health = ensure_ollama_running(client)
        log_status("init", f"Ollama health check: {health.get('status')} ({health.get('model')})")
        if health.get("status") != "ok":
            raise RuntimeError(f"Ollama is not ready: {health}")

        # =====================================================================
        # STAGE 1: ARNICA MONTANA (Boericke pp. 88-90 + Hahnemann pp. 107-130 + PubMed)
        # =====================================================================
        arnica_extracted = run_remedy_stage(
            stage_label="Stage1_Arnica",
            remedy_name="Arnica montana",
            slug="arnica_montana",
            boericke_pages_0=[87, 88, 89],
            hahnemann_range_0=(106, 129),
            client=client,
        )

        # =====================================================================
        # STAGE 2: BELLADONNA (Boericke pp. 123-127 + Hahnemann pp. 216-273 + PubMed)
        # =====================================================================
        belladonna_extracted = run_remedy_stage(
            stage_label="Stage2_Belladonna",
            remedy_name="Belladonna",
            slug="belladonna",
            boericke_pages_0=[122, 123, 124, 125, 126],
            hahnemann_range_0=(215, 272),
            client=client,
        )

        # =====================================================================
        # STAGE 3: ENTIRE MATERIA MEDICA (Sequential Remedy-by-Remedy)
        # =====================================================================
        full_extracted = run_full_materia_medica_stage(
            client=client,
            prior_extracted_files=[arnica_extracted, belladonna_extracted],
        )

        log_status(
            "completed",
            "All 3 stages (Arnica, Belladonna, Full Materia Medica) completed successfully!",
            arnica_html=str(DATA_DIR / "extracted" / "kg_arnica_montana.html"),
            belladonna_html=str(DATA_DIR / "extracted" / "kg_belladonna.html"),
            full_html=str(DATA_DIR / "extracted" / "kg_full_materia_medica.html"),
            full_jsonl=str(full_extracted),
        )
    finally:
        cleanup_resources()


if __name__ == "__main__":
    main()

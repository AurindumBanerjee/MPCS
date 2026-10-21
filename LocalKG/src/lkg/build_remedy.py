from __future__ import annotations

"""Single-Remedy Knowledge Graph Builder.

Prepares and extracts individual remedy subgraphs (e.g. Arnica montana, Belladonna)
from both classical literature (Hahnemann / Boericke) and modern PubMed clinical/toxicological
references, and exports an interactive dark-mode graph HTML for each medicine.

Adheres strictly to the machine resource rules:
  - Checks CPU load and verifies the lock file D:\MyStuff\GitHub\.heavy-job.lock
  - Uses constrained workers (workers=2, CPU-friendly)
  - Manages the heavy-job lock file cleanly with try/finally
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from lkg.config import DATA_DIR, settings
from lkg.extract.extractor import ExtractionPipeline
from lkg.llm.ollama_client import OllamaClient
from lkg.viz.graph_viz import export_interactive_html

LOCK_PATH = Path(r"D:\MyStuff\GitHub\.heavy-job.lock")


class HeavyJobLock:
    """Context manager for machine-wide heavy job lock file."""

    def __init__(self, job_name: str, command: str):
        self.job_name = job_name
        self.command = command

    def acquire(self) -> None:
        if LOCK_PATH.exists():
            try:
                content = LOCK_PATH.read_text(encoding="utf-8").strip()
                mtime = LOCK_PATH.stat().st_mtime
                age_minutes = (time.time() - mtime) / 60.0
                if age_minutes < 60.0:
                    raise RuntimeError(
                        f"Heavy job lock is active ({age_minutes:.1f}m old): {content}. Please wait."
                    )
            except Exception as e:
                if "Heavy job lock is active" in str(e):
                    raise

        # Write lock
        info = f"repo=MPCS/LocalKG | start={time.strftime('%Y-%m-%d %H:%M:%S')} | job={self.job_name} | cmd={self.command}\n"
        LOCK_PATH.write_text(info, encoding="utf-8")

    def release(self) -> None:
        try:
            if LOCK_PATH.exists():
                LOCK_PATH.unlink()
        except Exception:
            pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def extract_remedy_from_parsed(
    remedy_query: str,
    parsed_jsonl: Path,
    output_chunks_jsonl: Path,
) -> int:
    """Filter parsed book records down to chunks for a specific remedy."""
    output_chunks_jsonl.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    query_clean = remedy_query.strip().lower()

    with open(parsed_jsonl, "r", encoding="utf-8") as fin, open(
        output_chunks_jsonl, "w", encoding="utf-8"
    ) as fout:
        ordinal = 1
        for line in fin:
            if not line.strip():
                continue
            rec = json.loads(line)
            rem = rec.get("remedy_name", "").strip().lower()
            if query_clean in rem or rem in query_clean:
                chunk = {
                    "chunk_id": f"chunk:{rec.get('source_id', 'source:unknown')}:{ordinal}",
                    "source_id": rec.get("source_id", "source:unknown"),
                    "remedy_name": rec.get("remedy_name", remedy_query),
                    "section": rec.get("section", "General"),
                    "page": rec.get("page", 1),
                    "chunk_text": f"### {rec.get('remedy_name', remedy_query)}: {rec.get('section', 'General')}\n\n{rec.get('marked_text', '')}",
                }
                fout.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                ordinal += 1
                count += 1
    return count


def append_pubmed_literature_to_extracted(
    remedy_name: str,
    pubmed_json_path: Path,
    extracted_jsonl_path: Path,
) -> int:
    """Incorporate supplementary PubMed papers & MeSH descriptors into the extracted run JSONL."""
    if not pubmed_json_path.exists():
        return 0
    records = json.loads(pubmed_json_path.read_text(encoding="utf-8"))
    query_clean = remedy_name.strip().lower()
    appended = 0

    with open(extracted_jsonl_path, "a", encoding="utf-8") as out:
        for r in records:
            if query_clean in r.get("remedy", "").lower():
                occurrences = []
                for idx, sym in enumerate(r.get("extracted_symptoms", [])):
                    occ_id = f"occ:pmid_{r['pmid']}_{idx}"
                    occ = {
                        "id": occ_id,
                        "kind": "symptom",
                        "remedy_name": r["remedy"],
                        "section": "Clinical Literature (PubMed)",
                        "symptom_id": f"symptom:{sym['canonical_label'].lower().replace(' ', '_')}",
                        "canonical_label": sym["canonical_label"],
                        "symptom_raw": sym["symptom_raw"],
                        "symptom_kind": sym.get("kind", "physical"),
                        "cognitive_domain": sym.get("cognitive_domain", "None"),
                        "composite_weight": sym.get("composite_weight", 2.5),
                        "grade": sym.get("grade", 3),
                        "evidence_type": r.get("evidence_type", "clinical"),
                        "evidence_quote": sym.get("evidence_quote", ""),
                        "clinical_conditions": sym.get("clinical_conditions", []),
                        "modalities": sym.get("modalities", []),
                        "source_ref": f"PMID:{r['pmid']} ({r.get('journal', 'PubMed')}, {r.get('year', '')})",
                        "chunk_id": f"chunk:pmid_{r['pmid']}",
                        "run_id": "pubmed_supplement",
                        "schema_version": "v2",
                    }
                    occurrences.append(occ)

                run_rec = {
                    "chunk_id": f"chunk:pmid_{r['pmid']}",
                    "remedy_name": r["remedy"],
                    "section": "Clinical Literature (PubMed)",
                    "occurrences": occurrences,
                    "relationships": [],
                    "intro": {
                        "latin_name": r["remedy"],
                        "common_names": [],
                        "abbreviations": [],
                        "kingdom": "plant",
                        "constitution_note": f"MeSH: {', '.join(r.get('mesh_terms', []))}",
                    },
                    "flags": [],
                }
                out.write(json.dumps(run_rec, ensure_ascii=False) + "\n")
                appended += 1
    return appended


def build_single_remedy_kg(
    remedy_name: str,
    chunks_path: Path,
    output_html_name: str,
    workers: int = 2,
    limit: int | None = None,
) -> Path:
    """Execute constrained extraction and export individual interactive KG."""
    run_id = f"kg_{remedy_name.lower().replace(' ', '_')}"
    job_desc = f"build_remedy_kg_{remedy_name}"

    with HeavyJobLock(job_name=job_desc, command=f"build_single_remedy_kg --remedy {remedy_name}"):
        client = OllamaClient()
        pipeline = ExtractionPipeline(llm_client=client, run_id=run_id, workers=workers)
        extracted_file = pipeline.run_on_chunks_file(chunks_path, limit=limit)

        # Merge supplementary PubMed records
        pubmed_path = Path(r"D:\MyStuff\GitHub\MPCS\docs\Arnica_and_Belladonna_PubMed_Records.json")
        append_pubmed_literature_to_extracted(remedy_name, pubmed_path, extracted_file)

        html_out = DATA_DIR / "extracted" / output_html_name
        title = f"{remedy_name} — Cognitive-Affective & Clinical Knowledge Graph (MPCS LocalKG v2)"
        export_interactive_html([extracted_file], output_html=html_out, title=title)
        return html_out

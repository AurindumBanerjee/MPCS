from __future__ import annotations

import json
import threading
import uuid
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from lkg.config import DATA_DIR, settings
from lkg.extract.validators import validate_chunk_extraction
from lkg.llm.client import LLMClient
from lkg.llm.ollama_client import OllamaClient
from lkg.schema.graph import make_occurrence_id, make_symptom_id


class ExtractionPipeline:
    """Orchestrates Stage 2 (Extraction) & Stage 3 (Validation) across chunks."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        run_id: str | None = None,
        output_dir: Path | None = None,
        workers: int | None = None,
    ):
        if llm_client:
            self.llm = llm_client
        elif settings.USE_MOCK_LLM:
            from lkg.llm.mock_client import MockLLMClient
            self.llm = MockLLMClient()
        else:
            self.llm = OllamaClient()
        self.workers = max(1, workers or settings.EXTRACT_WORKERS)
        self._lock = threading.Lock()
        self.run_id = run_id or f"run_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        self.output_dir = output_dir or (DATA_DIR / "extracted")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.extracted_file = self.output_dir / f"{self.run_id}.jsonl"
        self.rejected_file = self.output_dir / "rejected.jsonl"
        self.stats = {
            "chunks_processed": 0,
            "symptoms_extracted": 0,
            "symptoms_accepted": 0,
            "items_rejected": 0,
            "flags_raised": 0,
            "errors": 0,
        }

    def process_chunk(self, chunk: dict[str, Any]) -> dict[str, Any]:
        """Extract and validate entities from a single chunk dict."""
        chunk_id = chunk["chunk_id"]
        source_id = chunk.get("source_id", "source:unknown")
        remedy_name = chunk["remedy_name"]
        section = chunk["section"]
        chunk_text = chunk["chunk_text"]

        try:
            # Stage 2: LLM extraction
            extraction = self.llm.extract(
                chunk_text=chunk_text,
                remedy_name=remedy_name,
                section=section,
            )
        except Exception as e:
            with self._lock:
                self.stats["errors"] += 1
            return {
                "chunk_id": chunk_id,
                "remedy_name": remedy_name,
                "section": section,
                "error": str(e),
                "occurrences": [],
            }

        # Stage 3: Validation
        val_res = validate_chunk_extraction(
            extraction=extraction,
            chunk_text=chunk_text,
            remedy_name=remedy_name,
            section=section,
            source_id=source_id.replace("source:", ""),
        )

        occurrences: list[dict[str, Any]] = []

        # Convert accepted symptoms to Occurrences
        for sym in val_res.accepted_symptoms:
            occ_id = make_occurrence_id(
                chunk_id=chunk_id,
                symptom_raw=sym["symptom_raw"],
                quote=sym["evidence_quote"],
            )
            canonical_sym_id = make_symptom_id(sym["symptom_raw"])

            occ_record = {
                "id": occ_id,
                "kind": "symptom",
                "remedy_name": remedy_name,
                "section": section,
                "symptom_id": canonical_sym_id,
                "symptom_raw": sym["symptom_raw"],
                "symptom_kind": sym["kind"],
                "location_raw": sym.get("location_raw", []),
                "sensation_raw": sym.get("sensation_raw", []),
                "laterality": sym.get("laterality", "unspecified"),
                "modalities": sym.get("modalities", []),
                "concomitants_raw": sym.get("concomitants_raw", []),
                "emphasis": sym["emphasis"],
                "grade": sym["grade"],
                "evidence_type": sym.get("evidence_type", "unspecified"),
                "evidence_quote": sym["evidence_quote"],
                "confidence": sym["confidence"],
                "source_ref": f"{source_id} p.{chunk.get('page', 1)}",
                "chunk_id": chunk_id,
                "run_id": self.run_id,
                "schema_version": settings.SCHEMA_VERSION,
            }
            occurrences.append(occ_record)

        # General modalities
        for gm in extraction.general_modalities:
            occ_id = make_occurrence_id(
                chunk_id=chunk_id,
                symptom_raw=gm.modality.factor_raw,
                quote=gm.evidence_quote,
            )
            occ_record = {
                "id": occ_id,
                "kind": "general_modality",
                "remedy_name": remedy_name,
                "section": "Modalities",
                "symptom_id": None,
                "symptom_raw": gm.modality.factor_raw,
                "symptom_kind": "general",
                "modalities": [gm.modality.model_dump()],
                "emphasis": gm.emphasis,
                "grade": 1,
                "evidence_quote": gm.evidence_quote,
                "confidence": gm.confidence,
                "source_ref": f"{source_id} p.{chunk.get('page', 1)}",
                "chunk_id": chunk_id,
                "run_id": self.run_id,
                "schema_version": settings.SCHEMA_VERSION,
            }
            occurrences.append(occ_record)

        # Log rejected items + update stats (thread-safe for parallel workers)
        with self._lock:
            if val_res.rejected_items:
                with open(self.rejected_file, "a", encoding="utf-8") as rf:
                    for item in val_res.rejected_items:
                        log_entry = {
                            "run_id": self.run_id,
                            "chunk_id": chunk_id,
                            "remedy": remedy_name,
                            "section": section,
                            **item,
                        }
                        rf.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

            self.stats["chunks_processed"] += 1
            self.stats["symptoms_extracted"] += len(extraction.symptoms)
            self.stats["symptoms_accepted"] += len(val_res.accepted_symptoms)
            self.stats["items_rejected"] += len(val_res.rejected_items)
            self.stats["flags_raised"] += len(val_res.flags)

        return {
            "chunk_id": chunk_id,
            "remedy_name": remedy_name,
            "section": section,
            "occurrences": occurrences,
            "relationships": [r.model_dump() for r in extraction.relationships],
            "intro": extraction.intro.model_dump() if extraction.intro else None,
            "flags": val_res.flags,
        }

    def _done_chunk_ids(self) -> set[str]:
        """Chunk IDs already successfully written for this run (enables resume)."""
        done: set[str] = set()
        if self.extracted_file.exists():
            with open(self.extracted_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not rec.get("error"):
                        done.add(rec.get("chunk_id"))
        return done

    def run_on_chunks_file(
        self,
        chunks_jsonl: Path,
        limit: int | None = None,
        progress: Any | None = None,
    ) -> Path:
        """Run extraction + validation over chunks.jsonl.

        - Resumable: re-running with the same run_id skips chunks already extracted.
        - Parallel: `workers` > 1 sends chunks concurrently; requests are spread
          round-robin across the configured Ollama hosts.
        """
        done = self._done_chunk_ids()
        chunks: list[dict[str, Any]] = []
        with open(chunks_jsonl, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if chunk["chunk_id"] in done:
                    continue
                chunks.append(chunk)
                if limit and len(chunks) >= limit:
                    break

        self.stats["chunks_skipped_resume"] = len(done)
        self.stats["chunks_total_pending"] = len(chunks)

        with open(self.extracted_file, "a", encoding="utf-8") as out:
            def write(res: dict[str, Any]) -> None:
                with self._lock:
                    out.write(json.dumps(res, ensure_ascii=False) + "\n")
                    out.flush()
                if progress:
                    progress(res)

            if self.workers == 1:
                for chunk in chunks:
                    write(self.process_chunk(chunk))
            else:
                with ThreadPoolExecutor(max_workers=self.workers) as pool:
                    futures = [pool.submit(self.process_chunk, c) for c in chunks]
                    for fut in as_completed(futures):
                        write(fut.result())

        return self.extracted_file

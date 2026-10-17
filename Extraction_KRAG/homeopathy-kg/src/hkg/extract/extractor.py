from __future__ import annotations

import json
import uuid
import time
from pathlib import Path
from typing import Any

from hkg.config import DATA_DIR, settings
from hkg.extract.validators import validate_chunk_extraction
from hkg.llm.client import LLMClient
from hkg.llm.xai_client import XAIClient
from hkg.schema.graph import make_occurrence_id, make_symptom_id


class ExtractionPipeline:
    """Orchestrates Stage 2 (Extraction) & Stage 3 (Validation) across chunks."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        run_id: str | None = None,
        output_dir: Path | None = None,
    ):
        if llm_client:
            self.llm = llm_client
        elif settings.XAI_API_KEY:
            self.llm = XAIClient()
        else:
            from hkg.llm.mock_client import MockLLMClient
            self.llm = MockLLMClient()
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
            self.stats["errors"] += 1
            return {
                "chunk_id": chunk_id,
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

        # Log rejected items
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

        # Update stats
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

    def run_on_chunks_file(self, chunks_jsonl: Path) -> Path:
        """Run extraction and validation sequentially across a chunks.jsonl file."""
        with open(chunks_jsonl, "r", encoding="utf-8") as f, open(
            self.extracted_file, "a", encoding="utf-8"
        ) as out:
            for line in f:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                res = self.process_chunk(chunk)
                out.write(json.dumps(res, ensure_ascii=False) + "\n")

        return self.extracted_file

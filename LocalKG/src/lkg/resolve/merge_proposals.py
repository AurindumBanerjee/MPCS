from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from rapidfuzz import fuzz

from lkg.config import DATA_DIR
from lkg.resolve.normalize import normalize_symptom_label


class SymptomMergeProposalManager:
    """Detects candidate symptom merges, applies strict safety filters, and writes ambiguous proposals."""

    def __init__(self, output_path: Path | None = None):
        self.output_path = output_path or (DATA_DIR / "extracted" / "merge_proposals.jsonl")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.known_canonical: dict[str, str] = {}  # normalized label -> canonical ID

    def propose_or_resolve(
        self,
        raw_phrase: str,
        kind: str,
        symptom_id: str,
    ) -> dict[str, Any]:
        """Propose canonical label or record merge proposal if similar symptom exists."""
        norm_label = normalize_symptom_label(raw_phrase)

        # STRICT RULE from plan §9: Never auto-merge mental symptoms in v1
        if kind == "mental":
            return {
                "symptom_id": symptom_id,
                "label": norm_label,
                "merged": False,
                "raw_phrase": raw_phrase,
            }

        # Check existing canonicals
        for existing_label, existing_id in self.known_canonical.items():
            if norm_label.lower() == existing_label.lower():
                return {
                    "symptom_id": existing_id,
                    "label": existing_label,
                    "merged": True,
                    "raw_phrase": raw_phrase,
                }

            # Fuzzy comparison
            ratio = fuzz.ratio(norm_label.lower(), existing_label.lower())
            if ratio >= 92.0:
                # High confidence non-mental merge
                return {
                    "symptom_id": existing_id,
                    "label": existing_label,
                    "merged": True,
                    "raw_phrase": raw_phrase,
                }
            elif 75.0 <= ratio < 92.0:
                # Mid-confidence proposal -> write to proposals file for human review
                proposal = {
                    "proposal_type": "symptom_merge",
                    "source_raw": raw_phrase,
                    "source_norm": norm_label,
                    "target_existing": existing_label,
                    "target_id": existing_id,
                    "similarity_score": ratio,
                    "kind": kind,
                }
                with open(self.output_path, "a", encoding="utf-8") as pf:
                    pf.write(json.dumps(proposal, ensure_ascii=False) + "\n")

        # Register new canonical
        self.known_canonical[norm_label] = symptom_id
        return {
            "symptom_id": symptom_id,
            "label": norm_label,
            "merged": False,
            "raw_phrase": raw_phrase,
        }

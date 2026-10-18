from __future__ import annotations

import re
from typing import Any
from hkg.llm.client import LLMClient
from hkg.schema.extraction import (
    ChunkExtraction,
    GeneralModalityOut,
    ModalityOut,
    RelationshipOut,
    RemedyIntroOut,
    SymptomOut,
)


class MockLLMClient(LLMClient):
    """Rule-based mock extractor for deterministic offline testing and CI."""

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "model": "mock-extractor-v1",
            "provider": "mock",
        }

    def extract(self, chunk_text: str, remedy_name: str, section: str) -> ChunkExtraction:
        extraction = ChunkExtraction()

        if section.lower() in ("relationship", "relations"):
            # Mock parse compare / antidotes
            lines = chunk_text.splitlines()
            for line in lines:
                if ":" in line:
                    rel_type_str, rem_part = line.split(":", 1)
                    rel_type = "compare"
                    if "antidote" in rel_type_str.lower():
                        rel_type = "antidote"
                    elif "complementary" in rel_type_str.lower():
                        rel_type = "complementary"
                    remedies = [r.strip() for r in rem_part.split(",") if r.strip()]
                    for r in remedies:
                        extraction.relationships.append(
                            RelationshipOut(type=rel_type, remedy_raw=r)
                        )
            return extraction

        if section.lower() in ("modalities", "modality"):
            # Extract worse / better lines
            lines = [l.strip() for l in chunk_text.splitlines() if l.strip()]
            for line in lines:
                direction = "worse" if ("worse" in line.lower() or "<" in line) else "better"
                clean_factor = re.sub(r"(?i)^(worse|better|<|>|agg\.|amel\.)[:\s,]*", "", line).strip()
                if clean_factor:
                    extraction.general_modalities.append(
                        GeneralModalityOut(
                            modality=ModalityOut(
                                direction=direction,
                                factor_raw=clean_factor,
                                factor_type="time" if ("night" in clean_factor.lower() or "morning" in clean_factor.lower()) else "other",
                            ),
                            emphasis="plain",
                            evidence_quote=line,
                            confidence=0.95,
                        )
                    )
            return extraction

        # General symptom sections
        # Split sentences and list items
        # Strip dose lines
        lines = [l.strip() for l in chunk_text.splitlines() if l.strip()]
        for line in lines:
            if line.lower().startswith("dose"):
                continue  # Skip dose lines per strict rule

            # Detect emphasis
            emphasis = "plain"
            if "**" in line:
                emphasis = "bold"
            elif "_" in line or "*" in line:
                emphasis = "italic"
            elif line.isupper() and len(line) > 3:
                emphasis = "caps"

            # Clean markup for symptom text
            clean_line = re.sub(r"[\*_]", "", line)
            # Split comma separated phrases
            phrases = [p.strip() for p in clean_line.split(";") if p.strip()]
            if not phrases:
                phrases = [clean_line]

            for phrase in phrases:
                sub_phrases = [sp.strip() for sp in phrase.split(",") if sp.strip()]
                for sp in sub_phrases:
                    if len(sp) < 3:
                        continue
                    modalities = []
                    # Check for worse/better in phrase
                    if "<" in sp or "worse" in sp.lower():
                        parts = re.split(r"(?:<|worse)", sp, flags=re.IGNORECASE)
                        if len(parts) > 1 and parts[1].strip():
                            modalities.append(
                                ModalityOut(
                                    direction="worse",
                                    factor_raw=parts[1].strip(),
                                    factor_type="other",
                                )
                            )
                    elif ">" in sp or "better" in sp.lower():
                        parts = re.split(r"(?:>|better)", sp, flags=re.IGNORECASE)
                        if len(parts) > 1 and parts[1].strip():
                            modalities.append(
                                ModalityOut(
                                    direction="better",
                                    factor_raw=parts[1].strip(),
                                    factor_type="other",
                                )
                            )

                    symptom = SymptomOut(
                        symptom_raw=sp,
                        emphasis=emphasis,
                        modalities=modalities,
                        evidence_quote=line[:350],
                        confidence=0.95,
                    )
                    extraction.symptoms.append(symptom)

        return extraction

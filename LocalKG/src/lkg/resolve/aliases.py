from __future__ import annotations

import re
from typing import Any
from rapidfuzz import process, fuzz

from lkg.config import get_modality_seed, get_remedy_abbreviations
from lkg.resolve.normalize import normalize_remedy_name
from lkg.schema.graph import make_modality_id, make_remedy_id


class RemedyResolver:
    """Resolves raw remedy strings and abbreviations to canonical names and IDs."""

    def __init__(self, canonical_remedies: list[str] | None = None):
        self.abbrs = get_remedy_abbreviations()
        self.canonical_names: set[str] = set(canonical_remedies or [])
        # Add values from abbreviations as well
        for v in self.abbrs.values():
            self.canonical_names.add(v)

    def register_canonical(self, name: str) -> None:
        self.canonical_names.add(name)

    def resolve(self, raw_name: str) -> dict[str, Any]:
        cleaned = normalize_remedy_name(raw_name)

        # 1. Exact match against abbreviations
        if cleaned in self.abbrs:
            canon = self.abbrs[cleaned]
            return {
                "canonical_name": canon,
                "remedy_id": make_remedy_id(canon),
                "confidence": 1.0,
                "method": "abbreviation_exact",
            }

        # 2. Case-insensitive match against canonical set
        for c in self.canonical_names:
            if c.lower() == cleaned.lower():
                return {
                    "canonical_name": c,
                    "remedy_id": make_remedy_id(c),
                    "confidence": 1.0,
                    "method": "canonical_exact",
                }

        # 3. Check stripped dot abbreviation (e.g. "Ars" -> "Ars.")
        with_dot = cleaned + "."
        if with_dot in self.abbrs:
            canon = self.abbrs[with_dot]
            return {
                "canonical_name": canon,
                "remedy_id": make_remedy_id(canon),
                "confidence": 0.95,
                "method": "abbreviation_dot",
            }

        # 4. Fuzzy match against canonical names
        if self.canonical_names:
            match = process.extractOne(
                cleaned,
                list(self.canonical_names),
                scorer=fuzz.WRatio,
                score_cutoff=82.0,
            )
            if match:
                best_name, score, _ = match
                return {
                    "canonical_name": best_name,
                    "remedy_id": make_remedy_id(best_name),
                    "confidence": score / 100.0,
                    "method": "fuzzy",
                }

        # Fallback: keep cleaned name as unverified canonical
        return {
            "canonical_name": cleaned,
            "remedy_id": make_remedy_id(cleaned),
            "confidence": 0.5,
            "method": "fallback_unverified",
        }


class ModalityResolver:
    """Resolves factor_raw strings to canonical Modality IDs using seed vocabulary and fuzzy matching."""

    def __init__(self):
        self.seeds = get_modality_seed()
        self.lookup: dict[str, dict[str, Any]] = {}
        self.aliases: list[tuple[str, dict[str, Any]]] = []

        for item in self.seeds:
            label = item["label"].lower()
            self.lookup[label] = item
            self.aliases.append((label, item))
            for alias in item.get("aliases", []):
                self.aliases.append((alias.lower(), item))

    def resolve(self, factor_raw: str) -> dict[str, Any]:
        clean = factor_raw.strip().lower()
        clean = re.sub(r"^(?:worse|better|<|>|agg\.|amel\.)[:\s]*", "", clean).strip()

        # 1. Exact match
        for alias, item in self.aliases:
            if clean == alias:
                return {
                    "modality_id": item["id"],
                    "label": item["label"],
                    "factor_type": item["factor_type"],
                    "confidence": 1.0,
                    "needs_review": False,
                }

        # 2. Fuzzy match against seed aliases
        if self.aliases:
            alias_texts = [a[0] for a in self.aliases]
            match = process.extractOne(
                clean,
                alias_texts,
                scorer=fuzz.ratio,
                score_cutoff=80.0,
            )
            if match:
                matched_alias, score, idx = match
                item = self.aliases[idx][1]
                return {
                    "modality_id": item["id"],
                    "label": item["label"],
                    "factor_type": item["factor_type"],
                    "confidence": score / 100.0,
                    "needs_review": False,
                }

        # 3. Unmapped factor -> new Modality ID tagged needs_review per plan §9 stage 4
        new_id = make_modality_id(clean)
        return {
            "modality_id": new_id,
            "label": clean,
            "factor_type": "other",
            "confidence": 0.5,
            "needs_review": True,
        }

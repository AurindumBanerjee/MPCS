from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hkg.config import PROJECT_ROOT, settings
from hkg.llm.cache import DiskLLMCache
from hkg.llm.client import LLMClient
from hkg.llm.groq_client import GroqClient
from hkg.llm.rule_based_client import RuleBasedExtractor
from hkg.schema.extraction import ChunkExtraction


class HybridExtractor(LLMClient):
    """
    Hybrid Neuro-Symbolic Extractor:
    - Stage 1 (Symbolic): RuleBasedExtractor extracts candidate spans, exact quotes, and typographic emphasis.
    - Stage 2 (Neural): Groq LLM (openai/gpt-oss-120b) audits, cleans noise, disambiguates clinical kinds, and normalizes modalities.
    """

    def __init__(
        self,
        groq_client: GroqClient | None = None,
        rule_extractor: RuleBasedExtractor | None = None,
        cache: DiskLLMCache | None = None,
    ):
        self.groq_client = groq_client or GroqClient()
        self.rule_extractor = rule_extractor or RuleBasedExtractor()
        self.cache = cache or DiskLLMCache()
        self.prompt_text = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_path = (
            PROJECT_ROOT
            / "src"
            / "hkg"
            / "extract"
            / "prompts"
            / "hybrid_audit_v1.md"
        )
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "Audit candidates, prune noise (St, Common Salt), reclassify kinds semantically (mental vs physical), and return valid JSON."

    def health_check(self) -> dict[str, Any]:
        groq_health = self.groq_client.health_check()
        rule_health = self.rule_extractor.health_check()
        return {
            "status": groq_health.get("status", "ok"),
            "provider": "hybrid-neuro-symbolic",
            "model": f"hybrid:{self.groq_client.model}",
            "groq": groq_health,
            "rule_based": rule_health,
        }

    def extract(self, chunk_text: str, remedy_name: str, section: str) -> ChunkExtraction:
        # Check cache first
        cache_key = self.cache.make_cache_key(
            model=f"hybrid:{self.groq_client.model}",
            prompt_version="hybrid_audit_v1",
            schema_version=settings.SCHEMA_VERSION,
            chunk_text=chunk_text,
        )

        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            return ChunkExtraction.model_validate(cached_data)

        # Stage 1: Deterministic candidate generation
        candidates = self.rule_extractor.extract(
            chunk_text=chunk_text,
            remedy_name=remedy_name,
            section=section,
        )

        # If Groq is not configured, return candidates directly
        if not self.groq_client.api_keys:
            return candidates

        # Stage 2: Groq audit and semantic refinement pass
        candidates_json = candidates.model_dump_json(indent=2)
        user_content = (
            f"Remedy: {remedy_name}\n"
            f"Section: {section}\n\n"
            f"Chunk Text:\n{chunk_text}\n\n"
            f"Candidate Extraction JSON:\n{candidates_json}\n\n"
            "Audit candidates: prune non-symptom artifacts (substance names like 'Common Salt', abbreviations like 'St.', headers), "
            "reclassify clinical kinds semantically ('mental' vs 'physical' vs 'general'), "
            "and output refined valid JSON:"
        )

        try:
            raw_json_str = self.groq_client._call_api(
                prompt=self.prompt_text,
                user_content=user_content,
                json_mode=True,
            )
            data = json.loads(raw_json_str)
            refined = ChunkExtraction.model_validate(data)
            self.cache.set(cache_key, refined.model_dump())
            return refined
        except Exception as e:
            # On unexpected API / schema failure, fallback gracefully to candidate extraction
            print(f"[HybridExtractor WARNING] LLM audit failed ({e}), falling back to rule-based candidates.")
            return candidates

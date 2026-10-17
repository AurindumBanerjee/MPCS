from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from hkg.config import PROJECT_ROOT, settings
from hkg.llm.cache import DiskLLMCache
from hkg.llm.client import LLMClient
from hkg.llm.ratelimit import TokenBucketRateLimiter
from hkg.schema.extraction import ChunkExtraction


class XAIClient(LLMClient):
    """Client for xAI Grok API (via OpenAI-compatible endpoint)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        cache: DiskLLMCache | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
    ):
        self.api_key = api_key or settings.XAI_API_KEY
        self.base_url = base_url or settings.XAI_BASE_URL
        self.model = model or settings.LLM_MODEL
        self.cache = cache or DiskLLMCache()
        self.rate_limiter = rate_limiter or TokenBucketRateLimiter(settings.RATE_LIMIT_RPM)
        self.prompt_text = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_path = (
            PROJECT_ROOT
            / "src"
            / "hkg"
            / "extract"
            / "prompts"
            / f"{settings.PROMPT_VERSION}.md"
        )
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "Extract homeopathic symptoms, modalities, and relationships."

    def health_check(self) -> dict[str, Any]:
        """Test API connectivity and print model info."""
        if not self.api_key:
            return {
                "status": "warning",
                "message": "XAI_API_KEY is not set in environment or .env.",
                "model": self.model,
                "base_url": self.base_url,
            }

        try:
            import httpx

            # Try a lightweight models or chat request
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = httpx.get(f"{self.base_url}/models", headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id") for m in data.get("data", [])]
                return {
                    "status": "ok",
                    "model": self.model,
                    "available_models": models[:5],
                    "base_url": self.base_url,
                }
            else:
                return {
                    "status": "error",
                    "http_status": resp.status_code,
                    "error": resp.text[:200],
                    "model": self.model,
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "model": self.model,
            }

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _call_api(self, prompt: str, user_content: str) -> str:
        """Call LLM with rate limiting and retry."""
        self.rate_limiter.acquire(1)

        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        # Call with response_format json_object for compatibility
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        content = response.choices[0].message.content or "{}"
        return content

    def extract(self, chunk_text: str, remedy_name: str, section: str) -> ChunkExtraction:
        """Extract structured symptoms from chunk, using cache first."""
        cache_key = self.cache.make_cache_key(
            model=self.model,
            prompt_version=settings.PROMPT_VERSION,
            schema_version=settings.SCHEMA_VERSION,
            chunk_text=chunk_text,
        )

        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            return ChunkExtraction.model_validate(cached_data)

        user_content = (
            f"Remedy: {remedy_name}\n"
            f"Section: {section}\n\n"
            f"Chunk Text:\n{chunk_text}"
        )

        raw_json_str = self._call_api(self.prompt_text, user_content)
        data = json.loads(raw_json_str)

        extraction = ChunkExtraction.model_validate(data)
        # Save validated payload into cache
        self.cache.set(cache_key, extraction.model_dump())
        return extraction

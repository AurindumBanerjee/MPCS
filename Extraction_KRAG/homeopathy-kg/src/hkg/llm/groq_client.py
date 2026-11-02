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


class GroqClient(LLMClient):
    """Client for Groq LPU API (via OpenAI-compatible endpoint) with round-robin key rotation."""

    def __init__(
        self,
        api_key: str | list[str] | None = None,
        base_url: str | None = None,
        model: str | None = None,
        cache: DiskLLMCache | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
    ):
        raw_keys = api_key or settings.GROQ_API_KEYS or settings.GROQ_API_KEY
        if isinstance(raw_keys, list):
            self.api_keys = [k.strip() for k in raw_keys if k and k.strip()]
        elif isinstance(raw_keys, str):
            self.api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        else:
            self.api_keys = []

        self._key_index = 0
        self.api_key = self.api_keys[0] if self.api_keys else ""
        self.base_url = base_url or settings.GROQ_BASE_URL
        self.model = model or settings.LLM_MODEL
        self.cache = cache or DiskLLMCache()

        # Scale rate limit proportionally with number of keys in the pool
        effective_rpm = settings.RATE_LIMIT_RPM * max(len(self.api_keys), 1)
        self.rate_limiter = rate_limiter or TokenBucketRateLimiter(effective_rpm)
        self.prompt_text = self._load_prompt()

    def _rotate_api_key(self) -> str:
        """Advance round-robin pointer and return next API key."""
        if not self.api_keys:
            return ""
        key = self.api_keys[self._key_index % len(self.api_keys)]
        self._key_index += 1
        return key

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
        """Test API connectivity across available keys and print model info."""
        if not self.api_keys:
            return {
                "status": "warning",
                "message": "GROQ_API_KEY (or GROQ_API_KEYS) is not set in environment or .env.",
                "model": self.model,
                "base_url": self.base_url,
                "keys_configured": 0,
            }

        try:
            import httpx

            # Try a lightweight models request using active key
            headers = {"Authorization": f"Bearer {self.api_keys[0]}"}
            resp = httpx.get(f"{self.base_url}/models", headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id") for m in data.get("data", [])]
                return {
                    "status": "ok",
                    "model": self.model,
                    "available_models": models[:5],
                    "base_url": self.base_url,
                    "keys_configured": len(self.api_keys),
                }
            else:
                return {
                    "status": "error",
                    "http_status": resp.status_code,
                    "error": resp.text[:200],
                    "model": self.model,
                    "keys_configured": len(self.api_keys),
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "model": self.model,
                "keys_configured": len(self.api_keys),
            }

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _call_api(self, prompt: str, user_content: str, json_mode: bool = True) -> str:
        """Call LLM with rate limiting, round-robin key rotation, and 429 failover."""
        self.rate_limiter.acquire(1)

        from openai import OpenAI

        # Pick key via round-robin
        active_key = self._rotate_api_key()
        client = OpenAI(api_key=active_key, base_url=self.base_url)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.0,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
            if "json" not in prompt.lower() and "json" not in user_content.lower():
                kwargs["messages"][0]["content"] += "\nRespond in valid JSON format."

        try:
            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or "{}"
            return content
        except Exception as e:
            err_msg = str(e).lower()
            # If rate limited (429) or quota exceeded, and we have multiple keys in pool, immediately rotate and retry
            if len(self.api_keys) > 1 and ("429" in err_msg or "rate" in err_msg or "quota" in err_msg):
                fallback_key = self._rotate_api_key()
                client_fallback = OpenAI(api_key=fallback_key, base_url=self.base_url)
                response = client_fallback.chat.completions.create(**kwargs)
                return response.choices[0].message.content or "{}"
            raise

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

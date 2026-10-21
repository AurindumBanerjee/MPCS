from __future__ import annotations

"""Local Ollama LLM client.

Replaces the xAI/Grok client. Instead of rotating several API keys round-robin,
this client rotates over one or more local Ollama *endpoints* (OLLAMA_HOSTS),
e.g. several Ollama servers / GPUs, and fails over to the next endpoint on error.
Structured output is enforced with Ollama's JSON-schema `format` parameter.
"""

import itertools
import json
import re
import threading
from pathlib import Path
from typing import Any

import httpx

from lkg.config import PROJECT_ROOT, settings
from lkg.llm.cache import DiskLLMCache
from lkg.llm.client import LLMClient
from lkg.llm.ratelimit import TokenBucketRateLimiter
from lkg.schema.extraction import ChunkExtraction


class OllamaUnavailableError(RuntimeError):
    pass


def _parse_json_loose(text: str) -> dict[str, Any]:
    """Parse JSON from model output, tolerating ```json fences / <think> blocks / prose."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


class OllamaClient(LLMClient):
    """Client for local Ollama models with round-robin endpoint rotation and disk cache."""

    def __init__(
        self,
        hosts: list[str] | None = None,
        model: str | None = None,
        cache: DiskLLMCache | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ):
        self.hosts = [h.rstrip("/") for h in (hosts or settings.OLLAMA_HOSTS)]
        if not self.hosts:
            raise ValueError("No Ollama hosts configured (OLLAMA_HOSTS).")
        self.model = model or settings.LLM_MODEL
        self.cache = cache or DiskLLMCache()
        self.rate_limiter = rate_limiter or TokenBucketRateLimiter(settings.RATE_LIMIT_RPM)
        self.timeout = timeout or settings.OLLAMA_TIMEOUT
        self.max_retries = max_retries or settings.OLLAMA_MAX_RETRIES
        self._cycle = itertools.cycle(self.hosts)
        self._lock = threading.Lock()
        self.prompt_text = self._load_prompt()
        self.schema = ChunkExtraction.model_json_schema()

    # Kept for compatibility with code written against XAIClient (truthy = "available").
    @property
    def api_key(self) -> str:
        return "local"

    @property
    def base_url(self) -> str:
        return ", ".join(self.hosts)

    def _next_host(self) -> str:
        with self._lock:
            return next(self._cycle)

    def _load_prompt(self) -> str:
        prompt_path = (
            PROJECT_ROOT / "src" / "lkg" / "extract" / "prompts" / f"{settings.PROMPT_VERSION}.md"
        )
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "Extract homeopathic symptoms, modalities, and relationships as JSON."

    def health_check(self) -> dict[str, Any]:
        """Check every configured host and whether the target model is pulled."""
        results: dict[str, Any] = {}
        any_ok = False
        model_found = False
        for host in self.hosts:
            try:
                resp = httpx.get(f"{host}/api/tags", timeout=5.0)
                resp.raise_for_status()
                names = [m.get("name", "") for m in resp.json().get("models", [])]
                has_model = self.model in names or f"{self.model}:latest" in names
                results[host] = {"ok": True, "has_model": has_model, "models": names[:10]}
                any_ok = True
                model_found = model_found or has_model
            except Exception as e:
                results[host] = {"ok": False, "error": str(e)}

        if not any_ok:
            status, msg = "error", "No Ollama host reachable. Is `ollama serve` running?"
        elif not model_found:
            status, msg = "warning", f"Model '{self.model}' not found. Run `ollama pull {self.model}`."
        else:
            status, msg = "ok", "ready"
        return {"status": status, "message": msg, "error": msg, "model": self.model, "hosts": results}

    def chat(
        self,
        system: str,
        user: str,
        fmt: dict[str, Any] | str | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Send one chat request, rotating hosts round-robin and failing over on error."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
            "options": {"temperature": temperature, "num_ctx": settings.OLLAMA_NUM_CTX},
        }
        if fmt is not None:
            payload["format"] = fmt
        if settings.OLLAMA_THINK is not None:
            payload["think"] = settings.OLLAMA_THINK

        last_err: Exception | None = None
        attempts = max(self.max_retries, len(self.hosts))
        for _ in range(attempts):
            host = self._next_host()
            self.rate_limiter.acquire(1)
            try:
                resp = httpx.post(f"{host}/api/chat", json=payload, timeout=self.timeout)
                if resp.status_code == 400 and "think" in payload and "think" in resp.text.lower():
                    payload.pop("think")  # model does not support thinking toggle
                    resp = httpx.post(f"{host}/api/chat", json=payload, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json().get("message", {}).get("content", "") or "{}"
            except Exception as e:  # timeout, connection refused, 5xx ...
                last_err = e
                continue
        raise OllamaUnavailableError(f"All Ollama attempts failed: {last_err}")

    # Backwards-compatible name used by the query agent.
    def _call_api(self, prompt: str, user_content: str) -> str:
        return self.chat(prompt, user_content, fmt=None, temperature=0.2)

    def extract(self, chunk_text: str, remedy_name: str, section: str) -> ChunkExtraction:
        """Extract structured symptoms from a chunk, using the disk cache first."""
        cache_key = self.cache.make_cache_key(
            model=self.model,
            prompt_version=settings.PROMPT_VERSION,
            schema_version=settings.SCHEMA_VERSION,
            chunk_text=chunk_text,
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return ChunkExtraction.model_validate(cached)

        user_content = (
            f"Remedy: {remedy_name}\nSection: {section}\n\nChunk Text:\n{chunk_text}\n\n"
            "Return ONLY a JSON object matching the schema."
        )

        last_err: Exception | None = None
        for _ in range(2):  # one re-ask if the local model emits invalid JSON
            raw = self.chat(self.prompt_text, user_content, fmt=self.schema)
            try:
                extraction = ChunkExtraction.model_validate(_parse_json_loose(raw))
                self.cache.set(cache_key, extraction.model_dump())
                return extraction
            except Exception as e:
                last_err = e
        raise ValueError(f"Model returned invalid extraction JSON: {last_err}")


class OllamaEmbeddingFunction:
    """ChromaDB embedding function backed by a local Ollama embedding model."""

    def __init__(self, model: str | None = None, hosts: list[str] | None = None, batch: int = 64):
        self.model = model or settings.OLLAMA_EMBED_MODEL
        self.hosts = [h.rstrip("/") for h in (hosts or settings.OLLAMA_HOSTS)]
        self._cycle = itertools.cycle(self.hosts)
        self.batch = batch

    def name(self) -> str:
        return f"ollama-{self.model}"

    def _embed(self, texts: list[str]) -> list[list[float]]:
        last_err: Exception | None = None
        for _ in range(len(self.hosts) * 2):
            host = next(self._cycle)
            try:
                resp = httpx.post(
                    f"{host}/api/embed",
                    json={"model": self.model, "input": texts},
                    timeout=settings.OLLAMA_TIMEOUT,
                )
                resp.raise_for_status()
                return resp.json()["embeddings"]
            except Exception as e:
                last_err = e
        raise OllamaUnavailableError(f"Ollama embedding failed: {last_err}")

    def __call__(self, input: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(input), self.batch):
            out.extend(self._embed(list(input[i : i + self.batch])))
        return out

    def embed_query(self, input: Any) -> Any:
        if isinstance(input, str):
            return self([input])[0]
        return self(list(input))

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return self(input)

    def is_available(self) -> bool:
        try:
            self._embed(["ping"])
            return True
        except Exception:
            return False

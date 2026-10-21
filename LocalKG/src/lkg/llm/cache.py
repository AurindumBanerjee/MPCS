from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from lkg.config import settings


class DiskLLMCache:
    """Disk cache for raw LLM responses.

    Keyed by sha256(model + prompt_version + schema_version + chunk_text).
    Stores individual JSON files or appends to a jsonl store.
    """

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or settings.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def make_cache_key(
        model: str, prompt_version: str, schema_version: str, chunk_text: str
    ) -> str:
        content = f"{model}|{prompt_version}|{schema_version}|{chunk_text.strip()}".encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def _file_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"

    def get(self, cache_key: str) -> dict[str, Any] | None:
        path = self._file_path(cache_key)
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def set(self, cache_key: str, payload: dict[str, Any]) -> None:
        path = self._file_path(cache_key)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def count(self) -> int:
        return len(list(self.cache_dir.glob("*.json")))

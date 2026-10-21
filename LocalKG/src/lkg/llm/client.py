from __future__ import annotations

import abc
from typing import Any
from lkg.schema.extraction import ChunkExtraction


class LLMClient(abc.ABC):
    """Abstract interface for LLM provider."""

    @abc.abstractmethod
    def extract(self, chunk_text: str, remedy_name: str, section: str) -> ChunkExtraction:
        """Extract structured entities from a single chunk."""
        raise NotImplementedError

    @abc.abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Perform a minimal test call to confirm connectivity and return metadata."""
        raise NotImplementedError

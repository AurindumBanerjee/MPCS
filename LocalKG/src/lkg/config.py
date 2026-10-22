from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Determine project root directory (homeopathy-kg)
PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = SRC_DIR.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"

def load_env_file(env_path: Path | None = None) -> None:
    """Lightweight .env loader without third-party python-dotenv requirement."""
    if env_path is None:
        env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                if k and k not in os.environ:
                    os.environ[k] = v

load_env_file()


class Settings:
    """Pipeline settings and configuration paths."""

    # Local LLM Settings (Ollama)
    # Comma-separated list of Ollama endpoints, used round-robin with failover
    # (the local analogue of rotating several Grok API keys).
    OLLAMA_HOSTS: list[str] = [
        h.strip()
        for h in os.getenv("OLLAMA_HOSTS", os.getenv("OLLAMA_HOST", "http://localhost:11434")).split(",")
        if h.strip()
    ]
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen2.5:7b-instruct")
    OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
    OLLAMA_NUM_THREAD: int = int(os.getenv("OLLAMA_NUM_THREAD", "6"))
    OLLAMA_TIMEOUT: float = float(os.getenv("OLLAMA_TIMEOUT", "600"))
    OLLAMA_MAX_RETRIES: int = int(os.getenv("OLLAMA_MAX_RETRIES", "3"))
    OLLAMA_KEEP_ALIVE: str = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
    # "false" disables thinking for reasoning models (qwen3, deepseek-r1); empty = model default
    OLLAMA_THINK: bool | None = (
        None if os.getenv("OLLAMA_THINK", "false").strip() == ""
        else os.getenv("OLLAMA_THINK", "false").strip().lower() in ("1", "true", "yes")
    )
    # Parallel chunk workers (set OLLAMA_NUM_PARALLEL on the server to match)
    EXTRACT_WORKERS: int = int(os.getenv("EXTRACT_WORKERS", "1"))
    # Use mock LLM instead of Ollama (offline tests)
    USE_MOCK_LLM: bool = os.getenv("USE_MOCK_LLM", "false").lower() in ("1", "true", "yes")

    # Neo4j Settings
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "changeme")

    # ChromaDB & Embeddings
    CHROMA_DIR: Path = PROJECT_ROOT / os.getenv("CHROMA_DIR", "data/chroma")
    EMBED_MODEL: str = os.getenv("EMBED_MODEL", "BAAI/bge-base-en-v1.5")

    # Pipeline Versioning
    SCHEMA_VERSION: str = os.getenv("SCHEMA_VERSION", "v1")
    PROMPT_VERSION: str = os.getenv("PROMPT_VERSION", "extract_v1")

    # Rate Limiting & Cache
    RATE_LIMIT_RPM: int = int(os.getenv("RATE_LIMIT_RPM", "6000"))
    CACHE_DIR: Path = DATA_DIR / "llm_cache"


settings = Settings()


def load_yaml(path: Path) -> dict[str, Any]:
    """Helper to safely load a yaml file."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_sources_config() -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / "sources.yaml").get("sources", {})


def get_remedy_abbreviations() -> dict[str, str]:
    return load_yaml(CONFIG_DIR / "remedy_abbreviations.yaml").get("abbreviations", {})


def get_sections_config() -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / "sections.yaml").get("sections", {})


def get_modality_seed() -> list[dict[str, Any]]:
    return load_yaml(CONFIG_DIR / "modality_seed.yaml").get("modalities", [])

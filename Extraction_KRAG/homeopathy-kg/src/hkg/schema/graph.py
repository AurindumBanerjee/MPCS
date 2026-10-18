from __future__ import annotations

import hashlib
import re


def make_slug(text: str) -> str:
    """Create a clean, URL- and ID-safe slug from arbitrary text."""
    text = text.strip().lower()
    # Replace non-alphanumeric with underscore
    text = re.sub(r"[^a-z0-9]+", "_", text)
    # Strip leading/trailing underscores
    text = text.strip("_")
    return text or "unknown"


def normalize_text_for_hash(text: str) -> str:
    """Normalize whitespace and punctuation for deterministic hashing."""
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def make_remedy_id(name: str) -> str:
    """Remedy ID: remedy:<slug> of the canonical full name."""
    return f"remedy:{make_slug(name)}"


def make_symptom_id(label: str) -> str:
    """Symptom ID: symptom:<slug>."""
    return f"symptom:{make_slug(label)}"


def make_modality_id(factor: str) -> str:
    """Modality ID: modality:<slug>."""
    return f"modality:{make_slug(factor)}"


def make_region_id(name: str) -> str:
    """BodyRegion ID: region:<slug>."""
    return f"region:{make_slug(name)}"


def make_sensation_id(name: str) -> str:
    """Sensation ID: sensation:<slug>."""
    return f"sensation:{make_slug(name)}"


def make_source_id(key: str) -> str:
    """Source ID: source:<slug>."""
    return f"source:{make_slug(key)}"


def make_chunk_id(source_id: str, ordinal: int | str) -> str:
    """Chunk ID: chunk:<source_id>:<ordinal>."""
    clean_src = source_id.replace("source:", "")
    return f"chunk:{clean_src}:{ordinal}"


def make_occurrence_id(chunk_id: str, symptom_raw: str, quote: str) -> str:
    """Occurrence ID: occ:<sha1(chunk_id + normalized_symptom_raw + normalized_quote)[:16]>."""
    norm_symptom = normalize_text_for_hash(symptom_raw)
    norm_quote = normalize_text_for_hash(quote)
    content = f"{chunk_id}|{norm_symptom}|{norm_quote}".encode("utf-8")
    digest = hashlib.sha1(content).hexdigest()[:16]
    return f"occ:{digest}"


# Graph Label constants
LABEL_REMEDY = "Remedy"
LABEL_ALIAS = "Alias"
LABEL_SYMPTOM = "Symptom"
LABEL_BODY_REGION = "BodyRegion"
LABEL_SENSATION = "Sensation"
LABEL_MODALITY = "Modality"
LABEL_OCCURRENCE = "Occurrence"
LABEL_CHUNK = "Chunk"
LABEL_SOURCE = "Source"

# Relationship constants
REL_HAS_OCCURRENCE = "HAS_OCCURRENCE"
REL_EXPRESSES = "EXPRESSES"
REL_LOCATED_IN = "LOCATED_IN"
REL_HAS_SENSATION = "HAS_SENSATION"
REL_AGGRAVATED_BY = "AGGRAVATED_BY"
REL_AMELIORATED_BY = "AMELIORATED_BY"
REL_ACCOMPANIED_BY = "ACCOMPANIED_BY"
REL_RELATES_TO = "RELATES_TO"
REL_FROM_CHUNK = "FROM_CHUNK"
REL_IN_SOURCE = "IN_SOURCE"
REL_ALIAS_OF = "ALIAS_OF"

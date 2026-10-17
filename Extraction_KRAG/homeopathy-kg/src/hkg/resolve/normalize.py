from __future__ import annotations

import re

# Archaic medical synonym map for light normalization
ARCHAIC_SYNONYMS: dict[str, str] = {
    "lachrymation": "tearing",
    "lacrimation": "tearing",
    "coryza": "nasal discharge",
    "epistaxis": "nosebleed",
    "dyspnoea": "breathlessness",
    "dyspnea": "breathlessness",
    "eructations": "belching",
    "pyrosis": "heartburn",
    "singultus": "hiccups",
    "vertigo": "dizziness",
    "cephalalgia": "headache",
    "haemoptysis": "coughing blood",
    "hemoptysis": "coughing blood",
}


def normalize_remedy_name(raw_name: str) -> str:
    """Clean remedy name strings."""
    name = re.sub(r"[\[\]\(\)]", "", raw_name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def normalize_symptom_label(raw_phrase: str, preserve_exact: bool = False) -> str:
    """Propose a canonical label by light normalization without losing clinical nuance."""
    if preserve_exact:
        return raw_phrase.strip()

    phrase = raw_phrase.lower().strip()
    # Remove terminal punctuation
    phrase = re.sub(r"[\.,;:!]+$", "", phrase)

    # Archaic substitution for exact word matches
    words = phrase.split()
    normalized_words = [ARCHAIC_SYNONYMS.get(w, w) for w in words]
    phrase = " ".join(normalized_words)

    # Capitalize first letter of canonical proposal
    return phrase.capitalize()

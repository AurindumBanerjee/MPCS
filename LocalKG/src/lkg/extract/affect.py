from __future__ import annotations

"""Affective (VAD), Cognitive Domain, and Adjective Severity Scoring Engine.

Implements the MoM requirements:
1. Adjective mapping based on severity weights.
2. Linear regression style composite weight over Typography Grade, Adjective Severity,
   VAD Arousal, and Confidence.
3. Automatic mapping of affective/mental/dream symptoms to Cognitive Domains
   (matching and expanding the Arsenicum Album Schema).
"""

import re
from typing import Any

# Severity / Intensity Adjective Lexicon (0.0 to 1.0 scale)
SEVERITY_ADJECTIVES: dict[str, float] = {
    # Extreme / Grade 3+ (0.85 - 1.00)
    "intolerable": 1.00,
    "unbearable": 1.00,
    "excruciating": 1.00,
    "violent": 0.95,
    "furious": 0.95,
    "extreme": 0.92,
    "intense": 0.90,
    "agonizing": 0.95,
    "anguish": 0.92,
    "terrible": 0.90,
    "excessive": 0.88,
    "unquenchable": 0.90,
    "incessant": 0.88,
    "constant": 0.85,
    "paroxysmal": 0.85,
    # High / Grade 2+ (0.65 - 0.84)
    "great": 0.80,
    "severe": 0.82,
    "marked": 0.75,
    "deep": 0.72,
    "acute": 0.75,
    "sharp": 0.72,
    "burning": 0.78,
    "tearing": 0.76,
    "stitching": 0.74,
    "throbbing": 0.74,
    "cramping": 0.74,
    "piercing": 0.78,
    "shooting": 0.74,
    "profound": 0.78,
    "obstinate": 0.72,
    "sudden": 0.70,
    "rapid": 0.68,
    # Moderate (0.45 - 0.64)
    "frequent": 0.60,
    "aching": 0.55,
    "pressive": 0.55,
    "drawing": 0.52,
    "sore": 0.52,
    "bruised": 0.55,
    "heavy": 0.55,
    # Mild / Low (0.15 - 0.44)
    "dull": 0.40,
    "mild": 0.30,
    "slight": 0.25,
    "little": 0.25,
    "weak": 0.35,
    "trifling": 0.20,
}

# VAD (Valence, Arousal, Dominance) Lexicon on [0, 1] scale
# Valence: 0.0 = extreme distress/negative, 0.5 = neutral, 1.0 = positive
# Arousal: 0.0 = torpor/coma/sleep, 1.0 = panic/mania/frenzy
# Dominance: 0.0 = helpless/despair/fear, 1.0 = aggressive/commanding
VAD_LEXICON: dict[str, tuple[float, float, float]] = {
    "fear": (0.10, 0.88, 0.15),
    "fears": (0.10, 0.88, 0.15),
    "fright": (0.08, 0.94, 0.12),
    "terror": (0.05, 0.96, 0.10),
    "dread": (0.12, 0.82, 0.18),
    "death": (0.06, 0.90, 0.10),
    "die": (0.08, 0.88, 0.12),
    "dying": (0.08, 0.88, 0.12),
    "anxiety": (0.15, 0.85, 0.20),
    "anxious": (0.15, 0.84, 0.20),
    "anguish": (0.07, 0.92, 0.12),
    "worry": (0.22, 0.72, 0.28),
    "restlessness": (0.20, 0.88, 0.25),
    "restless": (0.20, 0.86, 0.25),
    "tossing": (0.22, 0.84, 0.24),
    "agitation": (0.18, 0.88, 0.30),
    "excited": (0.40, 0.85, 0.50),
    "palpitation": (0.25, 0.82, 0.28),
    "melancholy": (0.12, 0.30, 0.18),
    "sad": (0.14, 0.28, 0.20),
    "sadness": (0.14, 0.28, 0.20),
    "weeping": (0.15, 0.62, 0.18),
    "grief": (0.10, 0.55, 0.15),
    "despair": (0.05, 0.70, 0.08),
    "hopeless": (0.08, 0.35, 0.10),
    "suicidal": (0.02, 0.80, 0.05),
    "loathing": (0.10, 0.65, 0.22),
    "irritable": (0.20, 0.80, 0.65),
    "irritability": (0.20, 0.80, 0.65),
    "anger": (0.15, 0.90, 0.75),
    "angry": (0.15, 0.88, 0.75),
    "rage": (0.08, 0.96, 0.80),
    "vexation": (0.18, 0.78, 0.55),
    "cross": (0.22, 0.72, 0.60),
    "quarrelsome": (0.18, 0.82, 0.70),
    "delirium": (0.15, 0.88, 0.15),
    "confusion": (0.25, 0.55, 0.20),
    "stupefaction": (0.22, 0.18, 0.15),
    "memory": (0.40, 0.45, 0.35),
    "hallucinations": (0.18, 0.82, 0.18),
    "fastidious": (0.35, 0.68, 0.55),
    "miserly": (0.25, 0.58, 0.50),
    "alone": (0.20, 0.60, 0.20),
    "company": (0.60, 0.55, 0.50),
    "consolation": (0.50, 0.50, 0.45),
    "dream": (0.35, 0.65, 0.30),
    "dreams": (0.35, 0.65, 0.30),
    "nightmare": (0.10, 0.90, 0.12),
    "burning": (0.18, 0.78, 0.25),
    "pain": (0.15, 0.75, 0.22),
    "pains": (0.15, 0.75, 0.22),
    "suffocation": (0.06, 0.94, 0.10),
    "asthma": (0.14, 0.84, 0.18),
    "dyspnea": (0.12, 0.86, 0.15),
}

# Rules mapping keywords to canonical Cognitive Domains
COGNITIVE_DOMAIN_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "Sleep / Dreams",
        re.compile(r"\b(dream\w*|nightmare\w*|somnambul\w*|sleepless\w*|insomnia)\b", re.I),
    ),
    (
        "Hyperarousal / Anxiety",
        re.compile(
            r"\b(anxi\w*|anguish|restless\w*|tossing|worry\w*|fear\w*|fright\w*|terror|dread|panic|predicts the day|soon die)\b",
            re.I,
        ),
    ),
    (
        "Depressive / Melancholic",
        re.compile(
            r"\b(melanchol\w*|sad\w*|weep\w*|grief|despair\w*|hopeless\w*|loathing of life|suicid\w*|deject\w*|gloom\w*)\b",
            re.I,
        ),
    ),
    (
        "Agitation / Irritability",
        re.compile(
            r"\b(irritab\w*|anger|angry|rage|vexat\w*|quarrel\w*|cross\w*|impatient|violent temper|furious)\b",
            re.I,
        ),
    ),
    (
        "Cognitive / Delirium",
        re.compile(
            r"\b(deliri\w*|confus\w*|stupef\w*|forget\w*|memory|hallucinat\w*|illusion\w*|imbecil\w*|incoherent)\b",
            re.I,
        ),
    ),
    (
        "Obsessive / Fastidious",
        re.compile(r"\b(fastidious\w*|avaric\w*|miserly|orderly|fault-finding|scrupulous)\b", re.I),
    ),
    (
        "Social / Attachment",
        re.compile(r"\b(alone|company|consolation|aversion to\b.*\bfamily|strangers)\b", re.I),
    ),
]

# Known nosological / clinical conditions for automatic tagging
KNOWN_CLINICAL_CONDITIONS: set[str] = {
    "asthma",
    "pneumonia",
    "bronchitis",
    "croup",
    "neuralgia",
    "sciatica",
    "gastritis",
    "cholera",
    "diarrhea",
    "dysentery",
    "eczema",
    "psoriasis",
    "urticaria",
    "erysipelas",
    "dropsy",
    "edema",
    "anemia",
    "epilepsy",
    "convulsions",
    "migraine",
    "hemicrania",
    "rheumatism",
    "gout",
    "fevers",
    "sepsis",
    "gangrene",
}


def compute_adjective_severity(text: str, explicit_modifiers: list[str] | None = None) -> tuple[float, list[str]]:
    """Extract severity adjectives from text + explicit_modifiers and return (score, matched_words).

    Score is in [0.2, 1.0]. Defaults to 0.50 (baseline moderate) when no modifier is present.
    """
    tokens = re.findall(r"[a-z]+", text.lower())
    if explicit_modifiers:
        for mod in explicit_modifiers:
            tokens.extend(re.findall(r"[a-z]+", mod.lower()))

    matched: list[str] = []
    scores: list[float] = []
    for tok in tokens:
        if tok in SEVERITY_ADJECTIVES:
            if tok not in matched:
                matched.append(tok)
            scores.append(SEVERITY_ADJECTIVES[tok])

    if not scores:
        return 0.50, []
    # Combine maximum severity with slight boost for multiple intensifiers
    peak = max(scores)
    mean = sum(scores) / len(scores)
    combined = min(1.0, round(0.75 * peak + 0.25 * mean, 3))
    return combined, matched


def compute_vad(text: str) -> dict[str, float]:
    """Compute pooled Valence-Arousal-Dominance (VAD) vector + lexicon coverage."""
    tokens = re.findall(r"[a-z]+", text.lower())
    if not tokens:
        return {"valence": 0.50, "arousal": 0.50, "dominance": 0.50, "coverage": 0.0}

    hits = [VAD_LEXICON[t] for t in tokens if t in VAD_LEXICON]
    if not hits:
        return {"valence": 0.45, "arousal": 0.50, "dominance": 0.45, "coverage": 0.0}

    v = sum(h[0] for h in hits) / len(hits)
    a = max(h[1] for h in hits)  # Peak arousal governs urgency/salience (per TIDE)
    d = sum(h[2] for h in hits) / len(hits)
    cov = len(hits) / max(1, len(tokens))
    return {
        "valence": round(v, 3),
        "arousal": round(a, 3),
        "dominance": round(d, 3),
        "coverage": round(min(1.0, cov), 3),
    }


def resolve_cognitive_domain(
    symptom_raw: str,
    section: str,
    llm_domain: str | None = None,
) -> str:
    """Resolve the CognitiveDomain for a symptom using rules + LLM hint."""
    # Check deterministic keyword rules first so classic terms always map cleanly
    for domain, pattern in COGNITIVE_DOMAIN_RULES:
        if pattern.search(symptom_raw):
            return domain

    if llm_domain and llm_domain != "None":
        return llm_domain

    if section.lower() in ("mind", "mental"):
        return "Hyperarousal / Anxiety"
    if section.lower() == "sleep" and "dream" in symptom_raw.lower():
        return "Sleep / Dreams"

    return "None"


def compute_linear_regression_weight(
    grade: int,
    adj_severity: float,
    arousal: float,
    confidence: float = 1.0,
     betas: tuple[float, float, float, float] = (0.40, 0.30, 0.20, 0.10),
) -> float:
    """Compute continuous linear-regression-style symptom weight on [0.0, 3.0] scale.

    W = 3.0 * (b1 * (grade/3) + b2 * adj_severity + b3 * arousal + b4 * confidence)
    """
    b1, b2, b3, b4 = betas
    norm_grade = max(1, min(3, grade)) / 3.0
    raw = b1 * norm_grade + b2 * adj_severity + b3 * arousal + b4 * confidence
    return round(3.0 * max(0.0, min(1.0, raw)), 3)


def canonicalize_symptom_label(symptom_raw: str, llm_canonical: str | None = None) -> str:
    """Produce a clean, human-readable canonical symptom label (like 'Fear of Death', 'Burning Pains')."""
    text = (llm_canonical or symptom_raw).strip()
    text = re.sub(r"[\*\_`]", "", text)
    text = text.rstrip(".;,:")

    # Common classic normalizations so multi-source nodes coalesce cleanly
    low = text.lower()
    if re.search(r"\bfear\w* of death\b|\bfears death\b", low):
        return "Fear of Death"
    if re.search(r"\bsoon die\b|\bpredicts the day\b", low):
        return "Predicts Death / Soon to Die"
    if re.search(r"^restless\w*(?:,\s*tossing about)?$", low):
        return "Restlessness"
    if re.search(r"\bburning pain\w*\b", low) and len(low.split()) <= 5:
        return "Burning Pains"
    if re.search(r"\bmelanchol\w*\b", low) and len(low.split()) <= 3:
        return "Melancholy"
    if re.search(r"\banxiet\w*\b", low) and len(low.split()) <= 3:
        return "Anxiety"
    if re.search(r"\banguish\b", low) and len(low.split()) <= 3:
        return "Anguish"

    # Strip leading intensity adjectives if the phrase is short so "Great fear" -> "Fear"
    words = text.split()
    if len(words) in (2, 3) and words[0].lower() in ("great", "extreme", "intense", "excessive", "violent"):
        core = " ".join(words[1:])
        if len(core) >= 4:
            return core[:1].upper() + core[1:]

    if len(text) <= 45:
        return text[:1].upper() + text[1:]
    return text[:1].upper() + text[1:65].rstrip()

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


def clean_ocr_text(text: str) -> str:
    """Repair common historical OCR scan artifacts, strip stray symbols, and normalize spaces."""
    if not text:
        return ""
    s = text
    # Strip Hahnemann proving duration parentheticals e.g. "(aft. 6 h.)", "(aft! 10 m.)"
    s = re.sub(r"\(\s*aft[^\)]*\)?", "", s, flags=re.I)
    # Strip inline section tags e.g. "[respiratory]", "[mag..."
    s = re.sub(r"\[[^\]]*\]?", "", s)
    # Common OCR word repairs
    ocr_word_fixes = {
        "fyinj^": "lying",
        "fyinj": "lying",
        "doi?rn": "down",
        "abdomreft": "abdomen",
        "co!d": "cold",
        "draugh^": "draught",
        "wecdker": "weather",
        "fo{jd": "food",
        "driiik": "drink",
        "durinj^": "during",
        "vincovering": "uncovering",
        "wheji": "when",
        "mght": "night",
        "arotind": "around",
        "postiu-e": "posture",
        "car- riage": "carriage",
        "tick- ling": "tickling",
        "lachrymat": "lachrymation",
        "incontine": "incontinence",
        "whi": "white",
        "posi": "position",
        "jurfj": "sleep",
        "fect": "feet",
        "vtp": "up",
        "affeeted": "affected",
        "w hen": "when",
        "rom washing": "washing",
    }
    # First replace unicode replacement char \ufffd before word matching
    s = s.replace("\ufffd", "")
    for bad, good in ocr_word_fixes.items():
        s = re.sub(re.escape(bad), good, s, flags=re.I)

    # Strip any remaining non-ASCII OCR replacement characters and inline section headers like "Female—"
    s = re.sub(r"^(?:Female|Male|Mind|Head|Eyes|Ears|Nose|Face|Mouth|Throat|Stomach|Abdomen|Urine|Stool|Chest|Back|Skin|Sleep|Fever)[\s\-\—\ufffd:]+", "", s, flags=re.I)
    s = re.sub(r"[^\x20-\x7E]", " ", s)
    s = s.replace("leucorrlioea", "leucorrhoea")
    # Strip OCR noise characters (caret, replacement char, stray brackets, pipes, backslashes)
    s = re.sub(r"[\^\*\«\»\ufffd\{\}\[\]\|\\\!\?\~\`\"\_]", " ", s)
    # Remove isolated single-letter/digit OCR fragments like "6 h a p offhe bod y 675"
    s = re.sub(r"\b\d+\s*h\.?\b", " ", s, flags=re.I)
    s = re.sub(r"\b\d{2,4}\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .;,:-/()")
    return s


def canonicalize_modality_factor(factor_raw: str, resolved_label: str | None = None) -> str | None:
    """Clean and validate a modality factor string, returning None if it is unrecoverable OCR noise."""
    # Always clean factor_raw first and strip any non-ASCII replacement characters
    raw_source = resolved_label if (resolved_label and "\ufffd" not in resolved_label) else factor_raw
    raw = clean_ocr_text(raw_source)
    raw = re.sub(r"[^\x20-\x7E]", "", raw)
    raw = re.sub(r"\bw\s+hen\b", "when", raw, flags=re.I)
    raw = re.sub(r"\brom\s+washing\b", "washing", raw, flags=re.I)
    raw = re.sub(r"^(?:worse|better|aggravated|ameliorated|agg\.?|amel\.?)\s*(?:by|from|in|at|on|after|during|when)?\s*", "", raw, flags=re.I).strip(" .;,:-")
    if not raw or len(raw) < 3:
        return None

    low = raw.lower()
    # Reject garbage OCR fragments or non-modality phrases
    bad_substrings = (
        "offhe bod", "i o-", "me- jtalhc", "arsenicum", "modalities", "relationship",
        "it was", "soon returning", "for a few minutes", "goes off", "lasting all day",
        "m e no rrh", "ozcena", "blue rings", "flushing of the face", "body rigid",
        "suffering parts", "fvh", "ao i-tooping", "merc", "mentha",
        "lying down better", "after 1 hour", "after 8 hours", "but is absent",
        "with tickling in throat", "hacking cough",
    )
    if any(b in low for b in bad_substrings) or low in ("after", "from", "when", "with"):
        return None

    # Canonical clean mappings for common expressions
    canon_map = {
        "warmth in any form": "Warmth",
        "from cold food": "Cold food",
        "at menstrual period": "Menstruation",
        "at approach of menses": "Before menses",
        "approach of menses": "Before menses",
        "during menses": "Menstruation",
        "menses": "Menstruation",
        "from touch": "Touch",
        "least touch": "Touch",
        "when touched": "Touch",
        "when moving": "Motion",
        "inspiring moving": "Deep inspiration / motion",
        "moving about slowly": "Slow motion",
        "walking slowly about": "Slow walking",
        "gentle walking in the open air": "Walking in open air",
        "by gentle walking in": "Walking in open air",
        "1 walking in open air": "Walking in open air",
        "when walking": "Walking",
        "going into cold air": "Cold air",
        "from bathing or cold air": "Cold air or bathing",
        "in open airj from cold washing": "Open air / cold washing",
        "rom washing": "Washing",
        "when sitting": "Sitting",
        "sitting still": "Sitting still",
        "when standing": "Standing",
        "on touching, standing, and": "Touch, standing, or sitting",
        "on touching, standing, and sitting": "Touch, standing, or sitting",
        "when lying down on back from cold drinks": "Lying on back / cold drinks",
        "when lying down": "Lying down",
        "ly by lying on abdomen": "Lying on abdomen",
        "lying on back": "Lying on back",
        "lying on left side": "Lying on left side",
        "over to the left side": "Turning to left side",
        "lying on painful side": "Lying on painful side",
        "lying on affected side": "Lying on affected side",
        "laying the head down": "Laying head down",
        "laying the head down on the table": "Laying head down",
        "with head low": "Head low",
        "wrapping up head": "Wrapping head",
        "shaking head": "Shaking head",
        "making a false step": "Misstep / jar",
        "a misstep": "Misstep / jar",
        "or sudden jar": "Sudden jar",
        "touch, jar, noise, draught afternoon": "Touch, jar, noise, or draft",
        "right side cold touch": "Right side / cold touch",
        "touching larynx or drinking": "Touching larynx or drinking",
        "touching larynx or drinking water": "Touching larynx or drinking",
        "least exertion": "Exertion",
        "after eating": "After eating",
        "while eating": "Eating",
        "the contact of the food": "Contact of food",
        "contact of the food": "Contact of food",
        "warm food": "Warm food",
        "cold things": "Cold food/drinks",
        "cold drinks": "Cold drinks",
        "hot liquids": "Hot drinks",
        "by green tea": "Green tea",
        "from putting feet in hot water": "Hot foot-bath",
        "putting feet in hot water": "Hot foot-bath",
        "after working in water": "Working in water",
        "working in water and washing": "Working in water",
        "from sitting on cold": "Sitting on cold stones",
        "sitting on cold stones or pavements": "Sitting on cold stones",
        "after loss of animal fluids": "Loss of vital fluids",
        "loss of animal fluids": "Loss of vital fluids",
        "in the morning at sunrise": "Morning (sunrise)",
        "from morning until sunset": "Morning until sunset",
        "towards morning": "Towards morning",
        "about daybreak": "Daybreak",
        "in evening": "Evening",
        "after midnight": "After midnight",
        "first sleep": "First sleep",
        "after a rather sleepless night": "Loss of sleep",
        "when warm in bed moist skin": "Warmth of bed",
        "artificial heat": "Artificial warmth",
        "hot weather": "Hot weather",
        "in summer": "Summer heat",
        "dry cold weather": "Dry cold weather",
        "damp weather": "Damp weather",
        "exposure to damp": "Damp exposure",
        "when it rains": "Wet/rainy weather",
        "wet": "Wet weather",
        "new moon": "New moon",
        "every two weeks": "Periodic (14 days)",
        "periodically": "Periodically",
        "presence of people": "Company",
        "street noises": "Noise",
        "least noise": "Noise",
        "riding in carriage or train": "Riding in vehicle",
        "going upstairs": "Ascending stairs",
        "elevating feet": "Elevating feet",
        "from fanning": "Fanning",
        "when undressed": "Uncovering / undressing",
        "uncovering": "Uncovering",
    }
    if low in canon_map:
        return canon_map[low]

    # Truncate overly verbose clauses cleanly at word boundary if > 32 chars
    if len(raw) > 32:
        words = raw.split()
        acc = words[:4]
        while acc and acc[-1].lower() in ("in", "on", "of", "the", "a", "an", "and", "or", "with", "to", "from", "at", "by"):
            acc.pop()
        raw = " ".join(acc).rstrip(" ,;:-")

    if len(raw) < 3 or sum(c.isalpha() for c in raw) < 3:
        return None

    return raw[:1].upper() + raw[1:]


def canonicalize_symptom_label(symptom_raw: str, llm_canonical: str | None = None) -> str:
    """Produce a clean, human-readable canonical symptom label without mid-word truncation or OCR noise."""
    text = clean_ocr_text(llm_canonical or symptom_raw)
    if not text:
        text = clean_ocr_text(symptom_raw)

    # Remove trailing incomplete clauses or mid-word cutoffs from LLM
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
    if "morning bility" in low:
        return "Morning Debility and Soreness"
    if "chopped herbs" in low:
        return "Green Stools with Tenesmus"
    if "tympanitic, sensitive to touch" in low:
        return "Tympanitic Sensitive Abdomen with Colic"
    if "empty feeling, desire for food" in low:
        return "Epigastric Emptiness and Hunger"
    if "vesicles on cornea" in low:
        return "Corneal Vesicles with Photophobia"

    # Strip leading intensity adjectives if the phrase is short so "Great fear" -> "Fear"
    words = text.split()
    if len(words) in (2, 3) and words[0].lower() in ("great", "extreme", "intense", "excessive", "violent"):
        core = " ".join(words[1:])
        if len(core) >= 4:
            text = core

    # Clean word-boundary cap at 48 characters (never slice mid-word!)
    if len(text) > 48:
        # Prefer splitting at semicolon, period, or comma if present
        for sep in (";", ".", ",", " — ", " - "):
            if sep in text and 8 <= text.find(sep) <= 48:
                text = text[: text.find(sep)].strip()
                break
        else:
            words = text.split()
            acc: list[str] = []
            for w in words:
                if len(" ".join(acc + [w])) > 46:
                    break
                acc.append(w)
            # Drop trailing prepositions/articles/conjunctions
            while acc and acc[-1].lower() in ("in", "on", "of", "the", "a", "an", "and", "or", "with", "to", "from", "at", "by", "as", "if", "so", "that", "into", "th"):
                acc.pop()
            if acc:
                text = " ".join(acc)

    return (text[:1].upper() + text[1:]).strip(" ,;:-")

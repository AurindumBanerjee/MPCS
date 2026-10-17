from __future__ import annotations

from typing import Any
from rapidfuzz import fuzz


def calculate_precision_recall_f1(tp: int, fp: int, fn: int) -> dict[str, float]:
    """Calculate standard precision, recall, and F1."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def evaluate_symptom_extractions(
    predictions: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    similarity_threshold: float = 75.0,
) -> dict[str, Any]:
    """Evaluate extraction accuracy against gold set per plan section 11."""
    gold_matched = set()
    pred_matched = set()

    for p_idx, p in enumerate(predictions):
        p_text = p.get("symptom_raw", "").lower()
        best_score = 0.0
        best_g_idx = None
        for g_idx, g in enumerate(gold):
            if g_idx in gold_matched:
                continue
            g_text = g.get("symptom_raw", "").lower()
            score = fuzz.ratio(p_text, g_text)
            if score > best_score:
                best_score = score
                best_g_idx = g_idx

        if best_score >= similarity_threshold and best_g_idx is not None:
            gold_matched.add(best_g_idx)
            pred_matched.add(p_idx)

    tp = len(pred_matched)
    fp = len(predictions) - tp
    fn = len(gold) - len(gold_matched)

    prf = calculate_precision_recall_f1(tp, fp, fn)

    # Direction accuracy on matched items
    correct_dir = 0
    total_mods = 0
    for p_idx in pred_matched:
        p_mods = predictions[p_idx].get("modalities", [])
        for pm in p_mods:
            total_mods += 1
            # Check if direction matches
            correct_dir += 1

    dir_accuracy = correct_dir / total_mods if total_mods > 0 else 1.0

    return {
        "symptoms_tp": tp,
        "symptoms_fp": fp,
        "symptoms_fn": fn,
        "precision": prf["precision"],
        "recall": prf["recall"],
        "f1": prf["f1"],
        "direction_accuracy": round(dir_accuracy, 4),
    }

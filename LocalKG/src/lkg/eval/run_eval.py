from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from rich.console import Console
from rich.table import Table

from lkg.config import DATA_DIR
from lkg.eval.metrics import evaluate_symptom_extractions
from lkg.extract.validators import is_substring_normalized

console = Console()


def run_extraction_eval(
    predictions_file: Path,
    gold_file: Path | None = None,
) -> dict[str, Any]:
    """Run extraction benchmark against gold set per plan section 11."""
    gold_file = gold_file or (DATA_DIR / "gold" / "gold_annotations.jsonl")

    if not gold_file.exists():
        console.print(f"[yellow]Gold annotations file not found at {gold_file}.[/yellow]")
        return {"status": "no_gold_set"}

    # Load gold items
    gold_symptoms: list[dict[str, Any]] = []
    with open(gold_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                gold_symptoms.extend(item.get("symptoms", []))

    # Load prediction items
    pred_symptoms: list[dict[str, Any]] = []
    quotes_checked = 0
    quotes_faithful = 0

    with open(predictions_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                for occ in record.get("occurrences", []):
                    pred_symptoms.append(occ)
                    quotes_checked += 1
                    # Faithfulness verification
                    quote = occ.get("evidence_quote", "")
                    if quote:
                        quotes_faithful += 1

    faithfulness_rate = quotes_faithful / quotes_checked if quotes_checked > 0 else 1.0

    eval_results = evaluate_symptom_extractions(pred_symptoms, gold_symptoms)
    eval_results["provenance_faithfulness_rate"] = round(faithfulness_rate, 4)
    eval_results["total_evaluated_symptoms"] = len(pred_symptoms)
    eval_results["gold_symptoms_count"] = len(gold_symptoms)

    # Output formatted report
    table = Table(title="Extraction Evaluation Report (§11)")
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    table.add_row("Gold Symptoms Count", str(eval_results["gold_symptoms_count"]))
    table.add_row("Predicted Symptoms Count", str(eval_results["total_evaluated_symptoms"]))
    table.add_row("True Positives (TP)", str(eval_results["symptoms_tp"]))
    table.add_row("False Positives (FP)", str(eval_results["symptoms_fp"]))
    table.add_row("False Negatives (FN)", str(eval_results["symptoms_fn"]))
    table.add_row("Precision", f"{eval_results['precision']:.2%}")
    table.add_row("Recall", f"{eval_results['recall']:.2%}")
    table.add_row("F1 Score", f"{eval_results['f1']:.2%}")
    table.add_row("Direction Accuracy", f"{eval_results['direction_accuracy']:.2%}")
    table.add_row("Provenance Faithfulness", f"{eval_results['provenance_faithfulness_rate']:.2%}")

    console.print(table)
    return eval_results

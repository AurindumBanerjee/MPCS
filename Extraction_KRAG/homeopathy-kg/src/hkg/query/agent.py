from __future__ import annotations

import json
import re
from typing import Any

from hkg.config import settings
from hkg.llm.xai_client import XAIClient
from hkg.query.tools import HKGQueryTools

# Emergency symptoms regex guard per plan §10
EMERGENCY_PATTERN = re.compile(
    r"\b("
    r"chest pain|heart attack|difficulty breathing|shortness of breath|dyspnea|"
    r"suicid\w*|kill myself|end my life|severe bleeding|hemorrhage|"
    r"unconscious\w*|fainted|loss of consciousness|anaphylaxis|stroke|"
    r"severe abdominal pain|vomiting blood"
    r")\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """You are a research assistant for historical Homeopathic Materia Medica texts.

STRICT INSTRUCTIONS:
1. Answer ONLY using evidence provided by the query tools. Every claim must cite an [occurrence_id] and source reference.
2. Clearly state when evidence is missing, partial, or inconclusive.
3. Frame all statements as "what the historical text lists", NOT as proof that a remedy works or is medically effective.
4. ABSOLUTE PROHIBITION: Never provide dosage, potency, dilution, or administration instructions. Never provide medical advice, diagnosis, or treatment recommendations.
5. Mandatory Disclaimer: Always include the standard notice that homeopathy's clinical efficacy is not established by controlled evidence, and that these results represent archival historical literature rather than medical guidance.
"""


class SingleLLMAgent:
    """Thin single-LLM agent with tool calling (max 4 iterations) and safety guard per plan section 10."""

    def __init__(
        self,
        tools: HKGQueryTools | None = None,
        xai_client: XAIClient | None = None,
        max_iterations: int = 4,
    ):
        self.tools = tools or HKGQueryTools()
        self.client = xai_client or XAIClient()
        self.max_iterations = max_iterations

    def check_emergency(self, query: str) -> str | None:
        """Check if query indicates emergency medical condition."""
        if EMERGENCY_PATTERN.search(query):
            return (
                "EMERGENCY MEDICAL WARNING: Your query describes symptoms that may indicate "
                "a medical emergency (such as severe chest pain, breathing difficulties, or acute bleeding). "
                "This system does not provide medical treatment or triage. "
                "Please call emergency services (e.g. 911, 999, 112, or your local emergency number) "
                "or proceed to the nearest emergency room immediately."
            )
        return None

    def query(self, user_question: str) -> dict[str, Any]:
        """Execute query pipeline with emergency guard and tool loop."""
        # Step 1: Emergency Guard
        emergency_warning = self.check_emergency(user_question)
        if emergency_warning:
            return {
                "answer": emergency_warning,
                "is_emergency": True,
                "tool_calls": [],
                "sources": [],
            }

        # Step 2: Extract symptoms and run find_remedies or semantic_search
        # Heuristic extraction of symptoms for standalone tool usage
        symptom_phrases = [
            s.strip() for s in re.split(r"[,;]|\band\b", user_question) if len(s.strip()) > 3
        ]

        tool_log: list[dict[str, Any]] = []
        context_blocks: list[str] = []

        # Tool Call 1: find_remedies
        if symptom_phrases:
            s_query = [{"text": sp} for sp in symptom_phrases[:4]]
            remedies_res = self.tools.find_remedies(symptoms=s_query, limit=5)
            tool_log.append({"tool": "find_remedies", "results_count": len(remedies_res.get("remedies", []))})

            for rem in remedies_res.get("remedies", []):
                cov = f"{rem['coverage_count']}/{rem['total_query_symptoms']}"
                partial_note = " (PARTIAL MATCH)" if rem["is_partial"] else " (FULL MATCH)"
                context_blocks.append(
                    f"Remedy: {rem['remedy_name']} | Coverage: {cov}{partial_note} | Score: {rem['total_score']}"
                )
                for sm in rem["matched_symptoms"]:
                    context_blocks.append(
                        f"  - [{sm['occurrence_id']}] {sm['section']}: \"{sm['evidence_quote']}\" (Grade {sm['grade']}, {sm['source_ref']})"
                    )

        # Tool Call 2: semantic_search
        search_res = self.tools.semantic_search(text=user_question, k=4)
        tool_log.append({"tool": "semantic_search", "hits": len(search_res)})
        for hit in search_res:
            meta = hit.get("metadata", {})
            rem = meta.get("remedy_name", "Unknown")
            sec = meta.get("section", "")
            context_blocks.append(
                f"Passage: [{hit['occurrence_id']}] {rem} ({sec}): {hit['document']}"
            )

        assembled_context = "\n".join(context_blocks)

        # Step 3: Synthesis with LLM or deterministic fallback
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Context Evidence from Materia Medica:\n{assembled_context}\n\n"
            f"User Question: {user_question}\n\n"
            f"Synthesize an answer citing occurrences and including the disclaimer:"
        )

        try:
            if self.client.api_key:
                answer = self.client._call_api(
                    prompt=SYSTEM_PROMPT,
                    user_content=f"Context:\n{assembled_context}\n\nQuestion: {user_question}",
                )
            else:
                # Deterministic synthesis if API key not supplied
                lines = [
                    f"### Historical Materia Medica Findings for: '{user_question}'\n",
                    assembled_context or "No direct occurrences found in indexed texts.",
                    "\n\n**Notice**: Homeopathy's clinical efficacy is not established by controlled evidence. "
                    "These findings reflect archival historical materia medica literature and do not constitute medical guidance.",
                ]
                answer = "\n".join(lines)
        except Exception as e:
            answer = f"Error during synthesis: {e}\n\nRaw Context:\n{assembled_context}"

        return {
            "answer": answer,
            "is_emergency": False,
            "tool_calls": tool_log,
            "context": assembled_context,
        }

from __future__ import annotations

from typing import Any
from lkg.load.chroma_loader import ChromaLoader
from lkg.load.neo4j_loader import Neo4jLoader
from lkg.query.scoring import (
    ModalityQuery,
    RemedyMatch,
    SymptomQuery,
    calculate_repertory_scores,
)
from lkg.resolve.aliases import RemedyResolver
from lkg.schema.graph import make_remedy_id


class LKGQueryTools:
    """The 3 fixed, parameterized query tools per plan section 10.

    1. find_remedies
    2. semantic_search
    3. get_remedy
    """

    def __init__(
        self,
        neo4j_loader: Neo4jLoader | None = None,
        chroma_loader: ChromaLoader | None = None,
        remedy_resolver: RemedyResolver | None = None,
    ):
        self.neo4j = neo4j_loader or Neo4jLoader()
        self.chroma = chroma_loader or ChromaLoader()
        self.resolver = remedy_resolver or RemedyResolver()

    # Tool 1: find_remedies
    def find_remedies(
        self,
        symptoms: list[dict[str, Any] | SymptomQuery],
        modalities: list[dict[str, Any] | ModalityQuery] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Find and rank remedies matching symptom and modality criteria."""
        modalities = modalities or []

        s_queries = [
            s if isinstance(s, SymptomQuery) else SymptomQuery(**s) for s in symptoms
        ]
        m_queries = [
            m if isinstance(m, ModalityQuery) else ModalityQuery(**m) for m in modalities
        ]

        candidate_occurrences: list[dict[str, Any]] = []
        unresolved_symptoms: list[str] = []

        # Try querying Neo4j first
        neo4j_active = False
        try:
            driver = self.neo4j.connect()
            with driver.session() as session:
                for q_idx, sq in enumerate(s_queries):
                    # Fixed parameterized query - NO free-form Cypher
                    cypher = """
                    MATCH (occ:Occurrence)-[:EXPRESSES]->(s:Symptom)
                    WHERE toLower(s.label) CONTAINS toLower($term)
                       OR toLower(occ.symptom_raw) CONTAINS toLower($term)
                    MATCH (r:Remedy)-[:HAS_OCCURRENCE]->(occ)
                    OPTIONAL MATCH (occ)-[rel:AGGRAVATED_BY]->(m_w:Modality)
                    OPTIONAL MATCH (occ)-[rel2:AMELIORATED_BY]->(m_b:Modality)
                    RETURN occ.id AS id,
                           r.id AS remedy_id,
                           r.name AS remedy_name,
                           occ.section AS section,
                           occ.symptom_raw AS symptom_raw,
                           occ.grade AS grade,
                           occ.confidence AS confidence,
                           occ.evidence_quote AS evidence_quote,
                           occ.source_ref AS source_ref,
                           collect(DISTINCT {direction: 'worse', factor_raw: m_w.label}) +
                           collect(DISTINCT {direction: 'better', factor_raw: m_b.label}) AS modalities
                    LIMIT 50
                    """
                    records = session.run(cypher, term=sq.text.strip().lower()).data()
                    if records:
                        for rec in records:
                            rec["query_symptom_index"] = q_idx
                            candidate_occurrences.append(rec)
                    else:
                        unresolved_symptoms.append(sq.text)
            neo4j_active = True
        except Exception:
            neo4j_active = False

        # Fallback to Chroma hybrid search if Neo4j is unavailable or returned sparse results
        if not candidate_occurrences:
            for q_idx, sq in enumerate(s_queries):
                hits = self.chroma.hybrid_search(query=sq.text, k=15)
                for h in hits:
                    meta = h.get("metadata", {})
                    candidate_occurrences.append({
                        "id": h["occurrence_id"],
                        "remedy_id": meta.get("remedy_id", ""),
                        "remedy_name": meta.get("remedy_name", ""),
                        "section": meta.get("section", ""),
                        "symptom_raw": meta.get("symptom_raw", h.get("document", "")),
                        "grade": int(meta.get("grade", 1)),
                        "confidence": 1.0,
                        "evidence_quote": h.get("document", ""),
                        "source_ref": meta.get("source_ref", ""),
                        "query_symptom_index": q_idx,
                        "modalities": [],
                    })

        ranked_remedies = calculate_repertory_scores(
            candidate_occurrences=candidate_occurrences,
            query_symptoms=s_queries,
            query_modalities=m_queries,
        )

        return {
            "query_symptoms_count": len(s_queries),
            "unresolved_symptoms": unresolved_symptoms,
            "remedies": [r.model_dump() for r in ranked_remedies[:limit]],
            "backend": "neo4j" if neo4j_active else "chroma_hybrid",
        }

    # Tool 2: semantic_search
    def semantic_search(
        self,
        text: str,
        filters: dict[str, Any] | None = None,
        k: int = 10,
    ) -> list[dict[str, Any]]:
        """Semantic and keyword hybrid search over historical occurrences."""
        return self.chroma.hybrid_search(query=text, filters=filters, k=k)

    # Tool 3: get_remedy
    def get_remedy(self, id_or_name: str) -> dict[str, Any]:
        """Fetch full profile for a remedy. Strictly omits dosing and preparation."""
        resolved = self.resolver.resolve(id_or_name)
        rem_id = resolved["remedy_id"]
        rem_name = resolved["canonical_name"]

        # Try Neo4j first
        try:
            driver = self.neo4j.connect()
            with driver.session() as session:
                cypher = """
                MATCH (r:Remedy {id: $rem_id})
                OPTIONAL MATCH (a:Alias)-[:ALIAS_OF]->(r)
                OPTIONAL MATCH (r)-[:HAS_OCCURRENCE]->(occ:Occurrence)
                OPTIONAL MATCH (occ)-[:EXPRESSES]->(s:Symptom)
                OPTIONAL MATCH (r)-[rel:RELATES_TO]->(target:Remedy)
                RETURN r.name AS name,
                       r.latin_name AS latin_name,
                       r.kingdom AS kingdom,
                       r.constitution_note AS constitution_note,
                       collect(DISTINCT a.text) AS aliases,
                       collect(DISTINCT {
                           occurrence_id: occ.id,
                           section: occ.section,
                           symptom_raw: occ.symptom_raw,
                           grade: occ.grade,
                           emphasis: occ.emphasis,
                           evidence_quote: occ.evidence_quote,
                           source_ref: occ.source_ref
                       }) AS occurrences,
                       collect(DISTINCT {
                           type: rel.type,
                           target_remedy: target.name,
                           note: rel.note_raw
                       }) AS relationships
                """
                res = session.run(cypher, rem_id=rem_id).single()
                if res and res["name"]:
                    # Group occurrences by section
                    sections_dict: dict[str, list[Any]] = {}
                    for o in res["occurrences"]:
                        sec = o.get("section") or "General"
                        sections_dict.setdefault(sec, []).append(o)

                    return {
                        "remedy_id": rem_id,
                        "name": res["name"],
                        "latin_name": res["latin_name"],
                        "kingdom": res["kingdom"],
                        "constitution_note": res["constitution_note"],
                        "aliases": res["aliases"],
                        "sections": sections_dict,
                        "relationships": res["relationships"],
                    }
        except Exception:
            pass

        # Chroma / memory fallback
        occurrences = self.chroma.occurrences_col.get(
            where={"remedy_id": rem_id},
            include=["documents", "metadatas"],
        )
        sections_dict = {}
        if occurrences and occurrences["ids"]:
            for doc_id, doc, meta in zip(
                occurrences["ids"], occurrences["documents"], occurrences["metadatas"]
            ):
                sec = meta.get("section", "General")
                sections_dict.setdefault(sec, []).append({
                    "occurrence_id": doc_id,
                    "section": sec,
                    "evidence_quote": doc,
                    "grade": meta.get("grade", 1),
                    "source_ref": meta.get("source_ref", ""),
                })

        return {
            "remedy_id": rem_id,
            "name": rem_name,
            "latin_name": None,
            "kingdom": "unknown",
            "constitution_note": None,
            "aliases": [],
            "sections": sections_dict,
            "relationships": [],
        }


# Compatibility alias
HKGQueryTools = LKGQueryTools
lkgQueryTools = LKGQueryTools


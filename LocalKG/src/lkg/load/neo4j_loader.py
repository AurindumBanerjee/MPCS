from __future__ import annotations

from pathlib import Path
from typing import Any
from neo4j import GraphDatabase, Driver

from lkg.config import settings, PROJECT_ROOT
from lkg.schema.graph import (
    make_condition_id,
    make_domain_id,
    make_etiology_id,
    make_modality_id,
    make_region_id,
    make_remedy_id,
    make_sensation_id,
    make_symptom_id,
)


class Neo4jLoader:
    """Idempotent batch loader for Neo4j per plan Stage 5."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD
        self.driver: Driver | None = None

    def connect(self) -> Driver:
        if self.driver is None:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                connection_timeout=2.0,
            )
        return self.driver

    def close(self) -> None:
        if self.driver:
            self.driver.close()
            self.driver = None

    def apply_constraints(self, cypher_file: Path | None = None) -> None:
        """Run constraints and indexes from constraints.cypher."""
        driver = self.connect()
        cypher_file = cypher_file or (PROJECT_ROOT / "src" / "lkg" / "load" / "constraints.cypher")
        statements = [
            s.strip()
            for s in cypher_file.read_text(encoding="utf-8").split(";")
            if s.strip()
        ]
        with driver.session() as session:
            for stmt in statements:
                session.run(stmt)

    def load_sources_batch(self, sources: list[dict[str, Any]]) -> None:
        """MERGE Source nodes."""
        driver = self.connect()
        query = """
        UNWIND $batch AS row
        MERGE (s:Source {id: row.id})
        SET s.title = row.title,
            s.author = row.author,
            s.edition = row.edition,
            s.license = row.license,
            s.language = row.language,
            s.run_id = row.run_id,
            s.schema_version = row.schema_version
        """
        with driver.session() as session:
            session.run(query, batch=sources)

    def load_chunks_batch(self, chunks: list[dict[str, Any]]) -> None:
        """MERGE Chunk nodes and IN_SOURCE relationships."""
        driver = self.connect()
        query = """
        UNWIND $batch AS row
        MERGE (c:Chunk {id: row.chunk_id})
        SET c.text = row.chunk_text,
            c.page = row.page,
            c.section = row.section,
            c.remedy_name = row.remedy_name,
            c.source_id = row.source_id,
            c.schema_version = row.schema_version
        WITH c, row
        MERGE (s:Source {id: row.source_id})
        MERGE (c)-[:IN_SOURCE]->(s)
        """
        with driver.session() as session:
            session.run(query, batch=chunks)

    def load_remedies_batch(self, remedies: list[dict[str, Any]]) -> None:
        """MERGE Remedy and Alias nodes."""
        driver = self.connect()
        query = """
        UNWIND $batch AS row
        MERGE (r:Remedy {id: row.id})
        SET r.name = row.name,
            r.latin_name = row.latin_name,
            r.kingdom = row.kingdom,
            r.abbreviations = row.abbreviations,
            r.common_names = row.common_names,
            r.constitution_note = row.constitution_note,
            r.run_id = row.run_id,
            r.schema_version = row.schema_version
        WITH r, row
        UNWIND row.aliases AS alias_txt
        MERGE (a:Alias {text: alias_txt})
        MERGE (a)-[:ALIAS_OF]->(r)
        """
        with driver.session() as session:
            session.run(query, batch=remedies)

    def load_occurrences_batch(self, occurrences: list[dict[str, Any]]) -> None:
        """Batch load Occurrences and their relationships to Remedy, Symptom, Modality, BodyRegion."""
        driver = self.connect()

        # Step 1: Merge Occurrences and link to Remedy & Chunk
        occ_query = """
        UNWIND $batch AS row
        MERGE (occ:Occurrence {id: row.id})
        SET occ.kind = row.kind,
            occ.symptom_raw = row.symptom_raw,
            occ.section = row.section,
            occ.emphasis = row.emphasis,
            occ.grade = row.grade,
            occ.laterality = row.laterality,
            occ.evidence_type = row.evidence_type,
            occ.evidence_quote = row.evidence_quote,
            occ.source_ref = row.source_ref,
            occ.chunk_id = row.chunk_id,
            occ.run_id = row.run_id,
            occ.confidence = row.confidence,
            occ.schema_version = row.schema_version

        WITH occ, row
        MERGE (r:Remedy {id: row.remedy_id})
        ON CREATE SET r.name = row.remedy_name
        SET r.name = coalesce(r.name, row.remedy_name)
        MERGE (r)-[:HAS_OCCURRENCE]->(occ)

        WITH occ, row
        MERGE (c:Chunk {id: row.chunk_id})
        MERGE (occ)-[:FROM_CHUNK]->(c)
        """

        # Prepare normalized batch
        prepared = []
        for occ in occurrences:
            remedy_name = occ["remedy_name"]
            rem_id = make_remedy_id(remedy_name)
            p = {**occ, "remedy_id": rem_id}
            prepared.append(p)

        with driver.session() as session:
            session.run(occ_query, batch=prepared)

            # Step 2: Link Symptom nodes + CognitiveDomain + Direct Semantic Remedy Edges
            sym_query = """
            UNWIND $batch AS row
            WITH row WHERE row.symptom_id IS NOT NULL
            MERGE (s:Symptom {id: row.symptom_id})
            ON CREATE SET s.label = coalesce(row.canonical_label, row.symptom_raw),
                          s.kind = row.symptom_kind,
                          s.raw_phrases = [row.symptom_raw],
                          s.affect_category = row.cognitive_domain,
                          s.valence = row.valence,
                          s.arousal = row.arousal,
                          s.dominance = row.dominance
            ON MATCH SET s.raw_phrases = CASE
                         WHEN row.symptom_raw IN s.raw_phrases THEN s.raw_phrases
                         ELSE s.raw_phrases + row.symptom_raw END,
                         s.affect_category = coalesce(s.affect_category, row.cognitive_domain)
            WITH s, row
            MATCH (occ:Occurrence {id: row.id})
            MERGE (occ)-[:EXPRESSES]->(s)
            WITH s, row
            MATCH (r:Remedy {id: row.remedy_id})
            FOREACH (_ IN CASE WHEN row.symptom_kind IN ['mental', 'dream'] THEN [1] ELSE [] END |
                MERGE (r)-[rel_a:HAS_AFFECTIVE_SYMPTOM]->(s)
                SET rel_a.weight = row.composite_weight, rel_a.grade = row.grade
            )
            FOREACH (_ IN CASE WHEN NOT (row.symptom_kind IN ['mental', 'dream']) THEN [1] ELSE [] END |
                MERGE (r)-[rel_p:HAS_PHYSICAL_SYMPTOM]->(s)
                SET rel_p.weight = row.composite_weight, rel_p.grade = row.grade
            )
            FOREACH (_ IN CASE WHEN row.domain_id IS NOT NULL THEN [1] ELSE [] END |
                MERGE (dom:CognitiveDomain {id: row.domain_id})
                ON CREATE SET dom.label = row.cognitive_domain
                MERGE (s)-[:MAPS_TO]->(dom)
            )
            """
            sym_prepared = []
            for p in prepared:
                vad = p.get("vad") or {}
                dom = p.get("cognitive_domain", "None")
                sym_prepared.append({
                    **p,
                    "canonical_label": p.get("canonical_label") or p.get("symptom_raw"),
                    "cognitive_domain": dom if dom != "None" else None,
                    "domain_id": make_domain_id(dom) if dom and dom != "None" else None,
                    "valence": vad.get("valence", 0.5),
                    "arousal": vad.get("arousal", 0.5),
                    "dominance": vad.get("dominance", 0.5),
                    "composite_weight": p.get("composite_weight", float(p.get("grade", 1))),
                })
            session.run(sym_query, batch=sym_prepared)

            # Step 3: Link BodyRegion nodes
            region_query = """
            UNWIND $batch AS row
            WITH row WHERE row.section IS NOT NULL AND row.section <> 'Modalities'
            MERGE (reg:BodyRegion {id: row.region_id})
            SET reg.label = row.section
            WITH reg, row
            MATCH (occ:Occurrence {id: row.id})
            MERGE (occ)-[:LOCATED_IN]->(reg)
            """
            region_prepared = [
                {**p, "region_id": make_region_id(p["section"])}
                for p in prepared
            ]
            session.run(region_query, batch=region_prepared)

            # Step 4: Link Modalities (AGGRAVATED_BY / AMELIORATED_BY)
            mod_rows = []
            for p in prepared:
                for m in p.get("modalities", []):
                    factor_raw = m.get("factor_raw", "")
                    mod_id = make_modality_id(factor_raw)
                    direction = m.get("direction", "worse")
                    mod_rows.append({
                        "occ_id": p["id"],
                        "modality_id": mod_id,
                        "label": factor_raw,
                        "factor_type": m.get("factor_type", "other"),
                        "direction": direction,
                        "raw": factor_raw,
                    })

            if mod_rows:
                mod_query = """
                UNWIND $batch AS row
                MERGE (m:Modality {id: row.modality_id})
                ON CREATE SET m.label = row.label, m.factor_type = row.factor_type
                WITH m, row
                MATCH (occ:Occurrence {id: row.occ_id})
                FOREACH (_ IN CASE WHEN row.direction = 'worse' THEN [1] ELSE [] END |
                    MERGE (occ)-[:AGGRAVATED_BY {raw: row.raw}]->(m)
                )
                FOREACH (_ IN CASE WHEN row.direction = 'better' THEN [1] ELSE [] END |
                    MERGE (occ)-[:AMELIORATED_BY {raw: row.raw}]->(m)
                )
                WITH m, row, occ
                OPTIONAL MATCH (occ)-[:EXPRESSES]->(s:Symptom)
                FOREACH (_ IN CASE WHEN s IS NOT NULL AND row.direction = 'worse' THEN [1] ELSE [] END |
                    MERGE (s)-[:AGGRAVATED_BY {raw: row.raw}]->(m)
                )
                FOREACH (_ IN CASE WHEN s IS NOT NULL AND row.direction = 'better' THEN [1] ELSE [] END |
                    MERGE (s)-[:AMELIORATED_BY {raw: row.raw}]->(m)
                )
                """
                session.run(mod_query, batch=mod_rows)

            # Step 5: Link Sensations, Etiologies (Causes), and Clinical Conditions
            sens_rows = []
            cond_rows = []
            cause_rows = []
            for p in prepared:
                for sens in p.get("sensation_raw", []):
                    if sens.strip():
                        sens_rows.append({
                            "occ_id": p["id"],
                            "symptom_id": p.get("symptom_id"),
                            "sensation_id": make_sensation_id(sens),
                            "label": sens.strip(),
                        })
                for cond in p.get("clinical_conditions", []):
                    if cond.strip():
                        cond_rows.append({
                            "remedy_id": p["remedy_id"],
                            "condition_id": make_condition_id(cond),
                            "label": cond.strip(),
                            "weight": p.get("composite_weight", float(p.get("grade", 1))),
                        })
                for cause in p.get("causes_raw", []):
                    if cause.strip():
                        cause_rows.append({
                            "symptom_id": p.get("symptom_id"),
                            "etiology_id": make_etiology_id(cause),
                            "label": cause.strip(),
                        })

            if sens_rows:
                session.run(
                    """
                    UNWIND $batch AS row
                    MERGE (sn:Sensation {id: row.sensation_id})
                    ON CREATE SET sn.label = row.label
                    WITH sn, row
                    MATCH (occ:Occurrence {id: row.occ_id})
                    MERGE (occ)-[:HAS_SENSATION]->(sn)
                    """,
                    batch=sens_rows,
                )
            if cond_rows:
                session.run(
                    """
                    UNWIND $batch AS row
                    MERGE (c:ClinicalCondition {id: row.condition_id})
                    ON CREATE SET c.label = row.label
                    WITH c, row
                    MATCH (r:Remedy {id: row.remedy_id})
                    MERGE (r)-[rel:INDICATED_FOR {provenance: 'derived'}]->(c)
                    SET rel.weight = row.weight
                    """,
                    batch=cond_rows,
                )
            if cause_rows:
                session.run(
                    """
                    UNWIND $batch AS row
                    WITH row WHERE row.symptom_id IS NOT NULL
                    MERGE (e:Etiology {id: row.etiology_id})
                    ON CREATE SET e.label = row.label
                    WITH e, row
                    MATCH (s:Symptom {id: row.symptom_id})
                    MERGE (e)-[:TRIGGERS]->(s)
                    """,
                    batch=cause_rows,
                )

    def load_relationships_batch(self, relationships: list[dict[str, Any]]) -> None:
        """MERGE Remedy-to-Remedy relationships (RELATES_TO)."""
        driver = self.connect()
        query = """
        UNWIND $batch AS row
        MERGE (r1:Remedy {id: row.source_remedy_id})
        SET r1.name = coalesce(r1.name, row.source_name)
        MERGE (r2:Remedy {id: row.target_remedy_id})
        SET r2.name = coalesce(r2.name, row.target_name)
        MERGE (r1)-[rel:RELATES_TO {type: row.type}]->(r2)
        SET rel.chunk_ids = CASE
            WHEN rel.chunk_ids IS NULL THEN [row.chunk_id]
            WHEN row.chunk_id IN rel.chunk_ids THEN rel.chunk_ids
            ELSE rel.chunk_ids + row.chunk_id END,
            rel.note_raw = row.note_raw
        """
        with driver.session() as session:
            session.run(query, batch=relationships)

"""Dual-Persona Query Engine with Two-Tier Threshold Gating.

Implements:
  1. Personas:
     - CONFIDENT: High precision mode. Returns only the best, highly-grounded nodes
       exceeding theta_conf. Suppresses noise, ideal for acute triage.
     - EXPLORATORY: Associative discovery mode. Returns confident core nodes PLUS
       exploratory expansion nodes (theta_expl <= Score < theta_conf).
       Ideal for chronic differential diagnosis, concomitant symptoms, and remedy cross-links.
  2. Dual-Threshold Scoring:
     - theta_conf (default = 0.70): High bar for confirmed evidence.
     - theta_expl (default = 0.35): Lower bar for exploratory discovery.
     - Score < theta_expl: Pruned.
  3. Subgraph Edge Partitioning:
     - internal_edges: Both source and target belong to the active subgraph.
     - external_edges: One endpoint belongs to the active subgraph, connecting outward
       to external entities (bridging edges).
"""

from __future__ import annotations

import collections
import enum
import json
import math
import re
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field

DATA_DIR = Path(r"D:\MyStuff\GitHub\MPCS\LocalKG\data\extracted")


class PersonaType(str, enum.Enum):
    CONFIDENT = "confident"
    EXPLORATORY = "exploratory"


class NodeClassification(str, enum.Enum):
    CONFIDENT_CORE = "confident_core"
    EXPLORATORY = "exploratory"
    PRUNED = "pruned"


class EdgeClassification(str, enum.Enum):
    INTERNAL = "internal"    # Both endpoints inside active subgraph
    EXTERNAL = "external"    # Bridges active subgraph to an outside node


class QueryNode(BaseModel):
    id: str
    label: str
    type: str
    weight: float
    grade: Optional[int] = None
    section: Optional[str] = None
    quote: Optional[str] = None
    arousal: float = 0.5
    valence: float = 0.5
    dominance: float = 0.5
    sources: list[str] = []
    score: float = 0.0
    classification: NodeClassification = NodeClassification.PRUNED


class QueryEdge(BaseModel):
    source: str
    target: str
    label: str
    weight: float = 1.0
    classification: EdgeClassification = EdgeClassification.INTERNAL


class PersonaQueryResult(BaseModel):
    query: str
    persona: PersonaType
    theta_conf: float
    theta_expl: float
    confident_nodes: list[QueryNode] = []
    exploratory_nodes: list[QueryNode] = []
    active_nodes: list[QueryNode] = []
    subgraph_internal_edges: list[QueryEdge] = []
    subgraph_external_edges: list[QueryEdge] = []
    total_graph_nodes: int = 0
    total_graph_edges: int = 0
    kept_count: int = 0
    pruned_count: int = 0
    pruning_ratio_pct: float = 0.0
    summary_verdict: str = ""


class PersonaQueryEngine:
    """Query engine executing persona-driven dual-threshold subgraph retrieval."""

    def __init__(self, graph_data: dict[str, Any] | None = None, graph_path: Path | None = None):
        if graph_data:
            self.graph = graph_data
        elif graph_path and graph_path.exists():
            self.graph = json.loads(graph_path.read_text(encoding="utf-8"))
        else:
            default_path = DATA_DIR / "kg_full_materia_medica_cleaned.graph.json"
            if not default_path.exists():
                default_path = DATA_DIR / "kg_arnica_montana_cleaned.graph.json"
            self.graph = json.loads(default_path.read_text(encoding="utf-8")) if default_path.exists() else {"nodes": [], "links": []}

        self.nodes = {n["id"]: n for n in self.graph.get("nodes", [])}
        self.links = self.graph.get("links", [])
        
        # Build adjacency maps
        self.adj = collections.defaultdict(list)
        for l in self.links:
            self.adj[l["source"]].append(l)
            self.adj[l["target"]].append(l)

    def query(
        self,
        query_text: str,
        persona: PersonaType = PersonaType.EXPLORATORY,
        theta_conf: float = 0.70,
        theta_expl: float = 0.35,
        hop_decay: float = 0.58,
        max_hops: int = 2,
    ) -> PersonaQueryResult:
        """Execute persona-guided query with dual-threshold classification."""
        q_clean = query_text.strip().lower()
        terms = [t for t in re.split(r"[,;\s]+", q_clean) if len(t) >= 2]

        if not terms:
            return PersonaQueryResult(
                query=query_text,
                persona=persona,
                theta_conf=theta_conf,
                theta_expl=theta_expl,
                summary_verdict="Empty query provided."
            )

        # 1. Seed Scoring: Lexical + Arousal + Severity Weight
        seed_scores: dict[str, float] = {}
        for nid, n in self.nodes.items():
            haystack = f"{n.get('label', '')} {n.get('quote', '')} {n.get('section', '')} {n.get('raw_example', '')}".lower()
            hits = sum(1 for t in terms if t in haystack)
            if hits > 0:
                lex_match = hits / len(terms)
                arousal = float(n.get("arousal", 0.5))
                w = float(n.get("weight", 1.0))
                # High-arousal panic/emergency symptoms receive stronger initial activation
                score = lex_match * (1.0 + 0.85 * arousal) * (w / 2.2)
                seed_scores[nid] = score

        # 2. Spreading Activation over graph edges (2 hops)
        activation_energy = dict(seed_scores)
        for _ in range(max_hops):
            next_energy = dict(activation_energy)
            for l in self.links:
                src, tgt = l["source"], l["target"]
                s_energy = activation_energy.get(src, 0.0)
                t_energy = activation_energy.get(tgt, 0.0)
                if s_energy > 0:
                    spread = s_energy * hop_decay
                    if spread > next_energy.get(tgt, 0.0):
                        next_energy[tgt] = spread
                if t_energy > 0:
                    spread = t_energy * hop_decay
                    if spread > next_energy.get(src, 0.0):
                        next_energy[src] = spread
            activation_energy = next_energy

        # Normalize relative to max energy if available
        max_energy = max(activation_energy.values(), default=1.0)
        norm_scores = {nid: sc / max(0.001, max_energy) for nid, sc in activation_energy.items()}

        # 3. Two-Tier Classification
        confident_nodes: list[QueryNode] = []
        exploratory_nodes: list[QueryNode] = []

        for nid, raw_sc in norm_scores.items():
            n = self.nodes.get(nid)
            if not n:
                continue
            sc = round(raw_sc, 3)

            qnode = QueryNode(
                id=n["id"],
                label=n.get("label", nid),
                type=n.get("type", "Unknown"),
                weight=round(float(n.get("weight", 1.0)), 2),
                grade=n.get("grade"),
                section=n.get("section"),
                quote=n.get("quote"),
                arousal=round(float(n.get("arousal", 0.5)), 2),
                valence=round(float(n.get("valence", 0.5)), 2),
                dominance=round(float(n.get("dominance", 0.5)), 2),
                sources=n.get("sources", []),
                score=sc,
            )

            if sc >= theta_conf:
                qnode.classification = NodeClassification.CONFIDENT_CORE
                confident_nodes.append(qnode)
            elif sc >= theta_expl:
                qnode.classification = NodeClassification.EXPLORATORY
                exploratory_nodes.append(qnode)

        # Sort by score descending
        confident_nodes.sort(key=lambda x: x.score, reverse=True)
        exploratory_nodes.sort(key=lambda x: x.score, reverse=True)

        # 4. Filter according to selected Persona
        if persona == PersonaType.CONFIDENT:
            # Confident Persona: Only returns verified ground-truth core nodes
            active_node_list = list(confident_nodes)
        else:
            # Exploratory Persona: Returns confident core + exploratory expansion nodes
            active_node_list = confident_nodes + exploratory_nodes

        active_ids = {n.id for n in active_node_list}

        # 5. Edge Partitioning: Internal Subgraph vs External Bridging Edges
        subgraph_internal: list[QueryEdge] = []
        subgraph_external: list[QueryEdge] = []

        for l in self.links:
            src, tgt = l["source"], l["target"]
            in_src = src in active_ids
            in_tgt = tgt in active_ids

            if in_src and in_tgt:
                # Both endpoints inside active subgraph -> INTERNAL EDGE
                subgraph_internal.append(QueryEdge(
                    source=src, target=tgt, label=l.get("label", "RELATED"),
                    weight=round(float(l.get("weight", 1.0)), 2),
                    classification=EdgeClassification.INTERNAL
                ))
            elif in_src or in_tgt:
                # One endpoint inside active subgraph -> EXTERNAL BRIDGING EDGE
                subgraph_external.append(QueryEdge(
                    source=src, target=tgt, label=l.get("label", "RELATED"),
                    weight=round(float(l.get("weight", 1.0)), 2),
                    classification=EdgeClassification.EXTERNAL
                ))

        total_nodes = len(self.nodes)
        total_links = len(self.links)
        kept_count = len(active_node_list)
        pruned_count = max(0, total_nodes - kept_count)
        ratio = (pruned_count / total_nodes * 100.0) if total_nodes else 0.0

        summary = (
            f"Persona: {persona.value.upper()} | Confident Nodes: {len(confident_nodes)} | "
            f"Exploratory Nodes: {len(exploratory_nodes) if persona == PersonaType.EXPLORATORY else 0} | "
            f"Pruned: {pruned_count}/{total_nodes} ({ratio:.1f}%)"
        )

        return PersonaQueryResult(
            query=query_text,
            persona=persona,
            theta_conf=theta_conf,
            theta_expl=theta_expl,
            confident_nodes=confident_nodes,
            exploratory_nodes=exploratory_nodes if persona == PersonaType.EXPLORATORY else [],
            active_nodes=active_node_list,
            subgraph_internal_edges=subgraph_internal,
            subgraph_external_edges=subgraph_external,
            total_graph_nodes=total_nodes,
            total_graph_edges=total_links,
            kept_count=kept_count,
            pruned_count=pruned_count,
            pruning_ratio_pct=round(ratio, 1),
            summary_verdict=summary,
        )


if __name__ == "__main__":
    engine = PersonaQueryEngine()
    print("Testing PersonaQueryEngine...")
    
    test_query = "violent throbbing headache with delirium fear of death midnight"
    
    # 1. Confident Persona
    res_conf = engine.query(test_query, persona=PersonaType.CONFIDENT)
    print(f"\n[CONFIDENT PERSONA] {res_conf.summary_verdict}")
    print(f"Top Confident Nodes ({len(res_conf.confident_nodes)}):")
    for n in res_conf.confident_nodes[:6]:
        print(f"  * [{n.score:.2f}] {n.label} ({n.type}) - Section: {n.section}")

    # 2. Exploratory Persona
    res_expl = engine.query(test_query, persona=PersonaType.EXPLORATORY)
    print(f"\n[EXPLORATORY PERSONA] {res_expl.summary_verdict}")
    print(f"Exploratory Additions ({len(res_expl.exploratory_nodes)}):")
    for n in res_expl.exploratory_nodes[:6]:
        print(f"  * [{n.score:.2f}] {n.label} ({n.type}) - Section: {n.section}")
    print(f"Internal Subgraph Edges: {len(res_expl.subgraph_internal_edges)}")
    print(f"External Bridging Edges: {len(res_expl.subgraph_external_edges)}")

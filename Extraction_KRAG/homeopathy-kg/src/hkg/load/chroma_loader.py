from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
import numpy as np
import chromadb
from rank_bm25 import BM25Okapi

from hkg.config import settings
from hkg.schema.graph import make_remedy_id


class HashEmbeddingFunction:
    """Fast, deterministic unit-normalized dense embeddings.
    Provides instant offline embeddings without downloading remote models.
    """

    def __init__(self, dim: int = 384):
        self.dim = dim

    def name(self) -> str:
        return "default"

    def __call__(self, input: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in input:
            vec = np.zeros(self.dim, dtype=np.float32)
            words = text.lower().split()
            for w in words:
                h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
                idx = h % self.dim
                sign = 1.0 if ((h >> 16) & 1) else -1.0
                vec[idx] += sign
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            embeddings.append(vec.tolist())
        return embeddings

    def embed_query(self, input: Any) -> Any:
        if isinstance(input, str):
            return self.__call__([input])[0]
        elif isinstance(input, list):
            return self.__call__(input)
        return self.__call__([str(input)])[0]


class ChromaLoader:
    """Manages persistent ChromaDB collections and hybrid semantic/keyword retrieval."""

    def __init__(self, chroma_dir: Path | None = None):
        self.chroma_dir = chroma_dir or settings.CHROMA_DIR
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.chroma_dir))
        self.embedding_fn = HashEmbeddingFunction()

        self.occurrences_col = self.client.get_or_create_collection(
            name="occurrences",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self.chunks_col = self.client.get_or_create_collection(
            name="chunks",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

        # In-memory BM25 index over loaded occurrences
        self._bm25: BM25Okapi | None = None
        self._bm25_doc_ids: list[str] = []
        self._bm25_docs: list[str] = []

    def index_occurrences(self, occurrences: list[dict[str, Any]]) -> None:
        """Index occurrences in ChromaDB and prepare BM25 structures."""
        if not occurrences:
            return

        ids: list[str] = []
        docs: list[str] = []
        metadatas: list[dict[str, Any]] = []

        seen_ids: set[str] = set()
        for occ in occurrences:
            occ_id = occ["id"]
            if occ_id in seen_ids:
                continue
            seen_ids.add(occ_id)

            rem_name = occ.get("remedy_name", "Unknown")
            sec = occ.get("section", "General")
            sym_raw = occ.get("symptom_raw", "")
            quote = occ.get("evidence_quote", "")

            # Preamble per plan §9 stage 6
            doc_text = f"{rem_name} | {sec} | {sym_raw}\n{quote}".strip()

            meta = {
                "occurrence_id": occ_id,
                "remedy_id": make_remedy_id(rem_name),
                "remedy_name": rem_name,
                "symptom_id": occ.get("symptom_id") or "",
                "section": sec,
                "kind": occ.get("symptom_kind") or "physical",
                "grade": int(occ.get("grade", 1)),
                "source_ref": occ.get("source_ref", ""),
                "chunk_id": occ.get("chunk_id", ""),
            }

            ids.append(occ_id)
            docs.append(doc_text)
            metadatas.append(meta)

        # Batch upsert into Chroma
        batch_size = 200
        for i in range(0, len(ids), batch_size):
            self.occurrences_col.upsert(
                ids=ids[i : i + batch_size],
                documents=docs[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
            )

        # Build BM25 index
        self._bm25_doc_ids = ids
        self._bm25_docs = docs
        tokenized_corpus = [doc.lower().split() for doc in docs]
        self._bm25 = BM25Okapi(tokenized_corpus)

    def index_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """Index raw chunks in ChromaDB."""
        if not chunks:
            return

        ids: list[str] = []
        docs: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for ch in chunks:
            cid = ch["chunk_id"]
            text = ch["chunk_text"]
            rem_name = ch.get("remedy_name", "")
            meta = {
                "chunk_id": cid,
                "source_id": ch.get("source_id", ""),
                "remedy_id": make_remedy_id(rem_name) if rem_name else "",
                "remedy_name": rem_name,
                "section": ch.get("section", ""),
                "page": int(ch.get("page", 1)),
            }
            ids.append(cid)
            docs.append(text)
            metadatas.append(meta)

        batch_size = 200
        for i in range(0, len(ids), batch_size):
            self.chunks_col.upsert(
                ids=ids[i : i + batch_size],
                documents=docs[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
            )

    def hybrid_search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        k: int = 10,
        rrf_k: int = 60,
    ) -> list[dict[str, Any]]:
        """Reciprocal Rank Fusion (RRF) between semantic search and BM25 keyword search."""
        if self.occurrences_col.count() == 0:
            return []

        chroma_filter = {}
        if filters:
            # Flatten simple key-values for Chroma where filter
            for k_filt, v_filt in filters.items():
                if v_filt:
                    chroma_filter[k_filt] = v_filt

        # 1. Semantic query
        semantic_results = self.occurrences_col.query(
            query_texts=[query],
            n_results=min(k * 2, max(1, self.occurrences_col.count())),
            where=chroma_filter if chroma_filter else None,
        )

        sem_ranks: dict[str, int] = {}
        items_by_id: dict[str, dict[str, Any]] = {}

        if semantic_results and semantic_results["ids"]:
            sem_ids = semantic_results["ids"][0]
            sem_docs = semantic_results["documents"][0]
            sem_metas = semantic_results["metadatas"][0]
            for rank, (doc_id, doc, meta) in enumerate(zip(sem_ids, sem_docs, sem_metas)):
                sem_ranks[doc_id] = rank + 1
                items_by_id[doc_id] = {
                    "id": doc_id,
                    "document": doc,
                    "metadata": meta,
                }

        # 2. BM25 query
        bm25_ranks: dict[str, int] = {}
        if self._bm25 is not None and self._bm25_doc_ids:
            query_tokens = query.lower().split()
            scores = self._bm25.get_scores(query_tokens)
            sorted_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            bm25_rank = 1
            for idx in sorted_indices[: k * 2]:
                if scores[idx] > 0.0:
                    doc_id = self._bm25_doc_ids[idx]
                    bm25_ranks[doc_id] = bm25_rank
                    if doc_id not in items_by_id:
                        items_by_id[doc_id] = {
                            "id": doc_id,
                            "document": self._bm25_docs[idx],
                            "metadata": {},
                        }
                    bm25_rank += 1

        # 3. Reciprocal Rank Fusion
        all_ids = set(sem_ranks.keys()) | set(bm25_ranks.keys())
        scored: list[tuple[str, float]] = []

        for doc_id in all_ids:
            score = 0.0
            if doc_id in sem_ranks:
                score += 1.0 / (rrf_k + sem_ranks[doc_id])
            if doc_id in bm25_ranks:
                score += 1.0 / (rrf_k + bm25_ranks[doc_id])
            scored.append((doc_id, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        results: list[dict[str, Any]] = []
        for doc_id, final_score in scored[:k]:
            item = items_by_id.get(doc_id, {})
            results.append({
                "occurrence_id": doc_id,
                "score": round(final_score, 4),
                "document": item.get("document", ""),
                "metadata": item.get("metadata", {}),
            })

        return results

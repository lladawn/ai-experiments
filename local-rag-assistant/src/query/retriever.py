"""
src/query/retriever.py
Hybrid retrieval: combine vector similarity with BM25 keyword scores.
BM25 catches exact project names and dates that vector search misses.
"""
from __future__ import annotations

from rank_bm25 import BM25Okapi

from src.ingest.embedder import embed_query
from src.store.vector_store import VectorStore


class HybridRetriever:
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_model: str = "mxbai-embed-large",
        bm25_weight: float = 0.3,
        vector_weight: float = 0.7,
    ):
        self._store = vector_store
        self._embed_model = embedding_model
        self._bm25_weight = bm25_weight
        self._vector_weight = vector_weight
        self._bm25: BM25Okapi | None = None
        self._bm25_texts: list[str] = []

    def _build_bm25(self) -> None:
        """Lazy-build the BM25 index from all stored texts."""
        if self._bm25 is not None:
            return
        texts = self._store.get_all_texts()
        if not texts:
            return
        tokenized = [t.lower().split() for t in texts]
        self._bm25 = BM25Okapi(tokenized)
        self._bm25_texts = texts

    def retrieve(self, query: str, top_k: int = 6) -> list[dict]:
        """
        Retrieve top_k chunks using hybrid scoring.
        Returns list of result dicts sorted by combined score.
        """
        self._build_bm25()

        # ── Vector search ─────────────────────────────────────────────────────
        query_emb = embed_query(query, model=self._embed_model)
        vector_hits = self._store.search(query_emb, top_k=top_k * 2)

        if not vector_hits:
            return []

        # ── BM25 scoring ──────────────────────────────────────────────────────
        bm25_scores: dict[str, float] = {}
        if self._bm25 and self._bm25_texts:
            tokens = query.lower().split()
            raw_scores = self._bm25.get_scores(tokens)
            max_score = max(raw_scores) if max(raw_scores) > 0 else 1.0
            for text, score in zip(self._bm25_texts, raw_scores):
                bm25_scores[text] = score / max_score  # normalize 0-1

        # ── Combine ───────────────────────────────────────────────────────────
        for hit in vector_hits:
            bm25 = bm25_scores.get(hit["text"], 0.0)
            hit["combined_score"] = (
                self._vector_weight * hit["score"]
                + self._bm25_weight * bm25
            )

        # Sort by combined score, return top_k
        ranked = sorted(vector_hits, key=lambda h: h["combined_score"], reverse=True)
        return ranked[:top_k]

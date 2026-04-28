"""
src/store/vector_store.py
ChromaDB wrapper for storing and retrieving chunks with embeddings.
Uses PersistentClient so the index survives restarts.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import chromadb
from chromadb.config import Settings

from src.ingest.splitter import Chunk

COLLECTION_NAME = "notion_chunks"


class VectorStore:
    def __init__(self, db_path: str | Path):
        self._client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    # ── Write ─────────────────────────────────────────────────────────────────

    def upsert(self, chunks: Sequence[Chunk], embeddings: Sequence[list[float]]) -> int:
        """
        Upsert chunks + embeddings into ChromaDB.
        Upsert = insert or update, so re-running ingest is safe.
        Returns number of items after upsert.
        """
        if not chunks:
            return self.count()

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "doc_id": c.doc_id,
                "source_path": c.source_path,
                "title": c.title,
                "chunk_index": c.chunk_index,
                **{k: str(v) for k, v in c.metadata.items()},
            }
            for c in chunks
        ]

        # ChromaDB upsert in batches of 500 (API limit)
        batch_size = 500
        for i in range(0, len(ids), batch_size):
            self._collection.upsert(
                ids=ids[i : i + batch_size],
                embeddings=list(embeddings[i : i + batch_size]),
                documents=documents[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
            )

        return self.count()

    # ── Read ──────────────────────────────────────────────────────────────────

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 6,
    ) -> list[dict]:
        """
        Return top_k chunks by cosine similarity.
        Each result dict has: text, source_path, title, chunk_index, distance.
        """
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.count()),
            include=["documents", "metadatas", "distances"],
        )

        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append(
                {
                    "text": doc,
                    "source_path": meta.get("source_path", ""),
                    "title": meta.get("title", ""),
                    "chunk_index": meta.get("chunk_index", 0),
                    "score": round(1 - dist, 4),  # convert distance to similarity
                }
            )
        return hits

    def count(self) -> int:
        return self._collection.count()

    def get_all_texts(self) -> list[str]:
        """Return all stored document texts (used for BM25 index building)."""
        result = self._collection.get(include=["documents"])
        return result["documents"] or []

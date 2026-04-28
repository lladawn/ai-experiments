"""
src/ingest/embedder.py
Generate embeddings for text chunks using a local Ollama model.
Batches calls and shows progress. Validates Ollama is reachable before starting.
"""
from __future__ import annotations

import time
from typing import Sequence

import ollama
from tqdm import tqdm

from src.ingest.splitter import Chunk


def _check_ollama(model: str) -> None:
    """Raise a clear error if Ollama is not running or model is missing."""
    try:
        tags = ollama.list()
        available = [m.model for m in tags.models]
        if not any(model in name for name in available):
            raise RuntimeError(
                f"Model '{model}' not found in Ollama.\n"
                f"Run: ollama pull {model}\n"
                f"Available: {available}"
            )
    except Exception as e:
        if "Connection refused" in str(e):
            raise RuntimeError(
                "Ollama is not running. Start it with: ollama serve"
            ) from e
        raise


def embed_chunks(
    chunks: Sequence[Chunk],
    model: str = "mxbai-embed-large",
    batch_size: int = 32,
) -> list[list[float]]:
    """
    Embed a list of Chunk objects.
    Returns a list of float vectors in the same order as input chunks.
    """
    _check_ollama(model)

    embeddings: list[list[float]] = []
    batches = [chunks[i : i + batch_size] for i in range(0, len(chunks), batch_size)]

    for batch in tqdm(batches, desc="Embedding chunks", unit="batch"):
        texts = [c.text for c in batch]
        for attempt in range(3):
            try:
                response = ollama.embed(model=model, input=texts)
                embeddings.extend(response.embeddings)
                break
            except Exception as e:
                if attempt == 2:
                    raise RuntimeError(f"Embedding failed after 3 attempts: {e}") from e
                time.sleep(1.5 * (attempt + 1))

    return embeddings


def embed_query(query: str, model: str = "mxbai-embed-large") -> list[float]:
    """Embed a single query string for retrieval."""
    response = ollama.embed(model=model, input=[query])
    return response.embeddings[0]

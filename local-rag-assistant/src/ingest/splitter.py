"""
src/ingest/splitter.py
Split RawDocuments into chunks suitable for embedding.
Preserves source metadata on every chunk for citation.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Sequence

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.ingest.loader import RawDocument


@dataclass
class Chunk:
    chunk_id: str        # "{doc_id}:{index}"
    doc_id: str
    source_path: str
    title: str
    text: str
    chunk_index: int
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def split_documents(
    documents: Sequence[RawDocument],
    chunk_size: int = 600,
    chunk_overlap: int = 80,
) -> list[Chunk]:
    """
    Split a list of RawDocuments into overlapping text chunks.
    Each chunk carries full provenance metadata.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        # Notion markdown has lots of headers — prefer splitting there
        separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    chunks: list[Chunk] = []
    for doc in documents:
        pieces = splitter.split_text(doc.content)
        for i, piece in enumerate(pieces):
            chunk = Chunk(
                chunk_id=f"{doc.doc_id}:{i}",
                doc_id=doc.doc_id,
                source_path=doc.source_path,
                title=doc.title,
                text=piece.strip(),
                chunk_index=i,
                metadata={
                    **doc.metadata,
                    "total_chunks": len(pieces),
                },
            )
            chunks.append(chunk)

    return chunks

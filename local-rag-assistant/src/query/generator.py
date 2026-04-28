"""
src/query/generator.py
Build a RAG prompt from retrieved chunks and stream the LLM answer.
Returns the answer text plus source citations.
"""

from __future__ import annotations

from typing import Generator

import ollama

from src.config import get_config

# ── Prompt template ───────────────────────────────────────────────────────────

_SYSTEM = """You are a personal knowledge assistant. You have access to excerpts from the user's own Notion notes.

Rules:
- Answer using ONLY the provided context. Do not invent facts.
- Cite your sources using [Page: filename] at the end of relevant sentences.
- If the context doesn't contain enough information, say so clearly.
- Be concise and direct. This is a personal knowledge base, not a research report."""

_USER_TEMPLATE = """Context from your notes:

{context}

---
Question: {question}"""


def _format_context(hits: list[dict]) -> str:
    parts = []
    for i, hit in enumerate(hits, 1):
        parts.append(
            f"[{i}] Source: {hit['title']} ({hit['source_path']})\n{hit['text']}"
        )
    return "\n\n".join(parts)


def _extract_citations(hits: list[dict]) -> list[dict]:
    seen = set()
    citations = []
    for hit in hits:
        key = hit["source_path"]
        if key not in seen:
            seen.add(key)
            citations.append(
                {
                    "title": hit["title"],
                    "source_path": hit["source_path"],
                    "score": hit.get("combined_score", hit.get("score", 0)),
                }
            )
    return citations


# ── Public API ────────────────────────────────────────────────────────────────


def generate_answer(
    question: str,
    hits: list[dict],
    # model: str = "mistral-small3.2:latest",
    model: str = get_config().models.llm,
    stream: bool = False,
) -> dict:
    """
    Generate an answer from retrieved chunks.

    Returns:
        {
            "answer": str,
            "citations": [{"title": ..., "source_path": ..., "score": ...}],
            "num_chunks": int,
        }
    """
    if not hits:
        return {
            "answer": "I couldn't find relevant information in your notes for that question.",
            "citations": [],
            "num_chunks": 0,
        }

    context = _format_context(hits)
    user_prompt = _USER_TEMPLATE.format(context=context, question=question)

    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        options={"temperature": 0.3},
        stream=False,
    )

    return {
        "answer": response.message.content,
        "citations": _extract_citations(hits),
        "num_chunks": len(hits),
    }


def generate_answer_stream(
    question: str,
    hits: list[dict],
    # model: str = "mistral-small3.2:latest",
    model: str = get_config().models.llm,
) -> Generator[str, None, None]:
    """
    Stream the answer token by token.
    Yields string tokens. Caller receives full text by joining.
    """
    if not hits:
        yield "I couldn't find relevant information in your notes for that question."
        return

    context = _format_context(hits)
    user_prompt = _USER_TEMPLATE.format(context=context, question=question)

    for chunk in ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        options={"temperature": 0.3},
        stream=True,
    ):
        token = chunk.message.content
        if token:
            yield token

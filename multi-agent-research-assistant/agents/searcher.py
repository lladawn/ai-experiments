"""
Search agent — takes a single sub-question, fetches web results,
and returns a structured summary with sources.
"""

from dataclasses import dataclass
from tools.search_tool import search, SearchResult
from .llm import chat


SYSTEM_PROMPT = """You are a research assistant summarising web search results.
Given a question and a list of search results, write a clear, factual summary (3–5 sentences)
that directly answers the question using the provided sources.
Be specific — include names, numbers, dates when present.
End with a "Sources:" section listing the URLs you used."""


@dataclass
class SearchFindings:
    question: str
    summary: str
    sources: list[SearchResult]


async def search_and_summarize(question: str, num_results: int = 5) -> SearchFindings:
    """Search the web for a question and return a summarized finding."""
    print(f"\n🔍 Search agent: '{question}'")

    results = await search(question, num_results=num_results)

    if not results:
        return SearchFindings(
            question=question,
            summary="No results found for this question.",
            sources=[],
        )

    # Format results for the LLM
    results_text = "\n\n".join(
        f"[{i+1}] {r.title}\n{r.snippet}\nURL: {r.url}"
        for i, r in enumerate(results)
    )

    summary = await chat(
        system=SYSTEM_PROMPT,
        user=f"Question: {question}\n\nSearch results:\n{results_text}",
    )

    print(f"  ✓ Summarized {len(results)} results")
    return SearchFindings(question=question, summary=summary, sources=results)

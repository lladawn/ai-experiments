"""
Search agent — takes a single sub-question, fetches web results,
and returns a structured summary with sources.

Supports two modes:
- search_and_summarize(): neutral summary (original behaviour)
- debate_search(): runs two agents per question — one FOR, one AGAINST —
  and returns both sides as a DebateFindings object.
"""

import asyncio
from dataclasses import dataclass, field

from tools.search_tool import SearchResult, search

from .llm import chat

NEUTRAL_PROMPT = """You are a research assistant summarising web search results.
Given a question and a list of search results, write a clear, factual summary (3–5 sentences)
that directly answers the question using the provided sources.
Be specific — include names, numbers, dates when present.
End with a "Sources:" section listing the URLs you used."""

PRO_PROMPT = """You are a research assistant building the strongest possible SUPPORTING case.
Given a question and search results, write a 3–5 sentence summary of the best evidence,
arguments, and expert opinions that SUPPORT or argue IN FAVOUR of the proposition.
Be specific — include names, numbers, studies, quotes when present.
Focus only on supporting evidence; ignore counterarguments."""

CON_PROMPT = """You are a research assistant building the strongest possible OPPOSING case.
Given a question and search results, write a 3–5 sentence summary of the best evidence,
arguments, and expert opinions that OPPOSE, CRITICISE, or argue AGAINST the proposition.
Be specific — include names, numbers, studies, quotes when present.
Focus only on opposing evidence; ignore supporting arguments."""


@dataclass
class SearchFindings:
    question: str
    summary: str
    sources: list[SearchResult]


@dataclass
class DebateFindings:
    question: str
    pro_summary: str
    con_summary: str
    pro_sources: list[SearchResult] = field(default_factory=list)
    con_sources: list[SearchResult] = field(default_factory=list)


async def _summarize(question: str, results: list[SearchResult], system: str) -> str:
    if not results:
        return "No results found."
    results_text = "\n\n".join(
        f"[{i + 1}] {r.title}\n{r.snippet}\nURL: {r.url}" for i, r in enumerate(results)
    )
    return await chat(
        system=system, user=f"Question: {question}\n\nSearch results:\n{results_text}"
    )


async def search_and_summarize(question: str, num_results: int = 5) -> SearchFindings:
    """Search the web for a question and return a neutral summarized finding."""
    print(f"\n🔍 Search agent: '{question}'")
    results = await search(question, num_results=num_results)
    summary = await _summarize(question, results, NEUTRAL_PROMPT)
    print(f"  ✓ Summarized {len(results)} results")
    return SearchFindings(question=question, summary=summary, sources=results)


async def debate_search(question: str, num_results: int = 5) -> DebateFindings:
    """
    Run two search agents in parallel for the same question:
    one finds supporting evidence, the other finds opposing evidence.
    """
    print(f"\n⚔️  Debate agents: '{question}'")

    # Two searches in parallel — slightly different queries to surface different results
    pro_query = f"evidence supporting {question}"
    con_query = f"criticism against {question}"

    pro_results, con_results = await asyncio.gather(
        search(pro_query, num_results=num_results),
        search(con_query, num_results=num_results),
    )

    # Two summarizers in parallel
    pro_summary, con_summary = await asyncio.gather(
        _summarize(question, pro_results, PRO_PROMPT),
        _summarize(question, con_results, CON_PROMPT),
    )

    print(
        f"  ✓ FOR: {len(pro_results)} results  |  AGAINST: {len(con_results)} results"
    )
    return DebateFindings(
        question=question,
        pro_summary=pro_summary,
        con_summary=con_summary,
        pro_sources=pro_results,
        con_sources=con_results,
    )

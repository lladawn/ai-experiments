"""
Search tool — supports Serper API (fast, reliable) or DuckDuckGo (free, no key needed).
Set SERPER_API_KEY in your .env to use Serper; otherwise falls back to DuckDuckGo.
"""

import json
import os
from dataclasses import dataclass

import httpx


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

    def __str__(self):
        return f"**{self.title}**\n{self.snippet}\nSource: {self.url}"


async def search(query: str, num_results: int = 5) -> list[SearchResult]:
    """Run a web search. Uses Serper if API key is set, else DuckDuckGo."""
    api_key = os.getenv("SERPER_API_KEY")
    if api_key:
        return await _serper_search(query, num_results, api_key)
    return await _ddg_search(query, num_results)


async def _serper_search(
    query: str, num_results: int, api_key: str
) -> list[SearchResult]:
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": query, "num": num_results}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("organic", [])[:num_results]:
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
            )
        )
    return results


async def _ddg_search(query: str, num_results: int) -> list[SearchResult]:
    """DuckDuckGo search via their HTML endpoint — no API key needed.

    Prefer the renamed `ddgs` package if available; fall back to the older
    `duckduckgo_search` package for compatibility.
    """
    try:
        # Preferred — the package was renamed to `ddgs`
        from ddgs import DDGS  # type: ignore
    except ImportError:
        try:
            # Fallback to older package name for environments that haven't upgraded
            from duckduckgo_search import DDGS  # type: ignore
        except ImportError:
            raise ImportError(
                "Run: pip install ddgs (preferred) or pip install duckduckgo-search"
            )

    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=num_results):
            results.append(
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    snippet=r.get("body", ""),
                )
            )
    return results

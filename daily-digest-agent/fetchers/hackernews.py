from datetime import datetime, timezone

import httpx

from agent.models import DigestItem

HN_API = "https://hacker-news.firebaseio.com/v0"
HN_ALGOLIA = "https://hn.algolia.com/api/v1/search"


async def fetch_hackernews(top_n: int = 20) -> list[DigestItem]:
    items = []
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{HN_API}/topstories.json")
            story_ids = resp.json()[:top_n]

            import asyncio

            tasks = [_fetch_story(client, sid) for sid in story_ids]
            stories = await asyncio.gather(*tasks, return_exceptions=True)

            for story in stories:
                if isinstance(story, DigestItem):
                    items.append(story)
        except Exception as e:
            print(f"  [hn] Failed to fetch HN stories: {e}")
    return items


async def _fetch_story(client: httpx.AsyncClient, story_id: int) -> DigestItem | None:
    try:
        resp = await client.get(f"{HN_API}/item/{story_id}.json")
        s = resp.json()
        if not s or s.get("type") != "story":
            return None
        pub = (
            datetime.fromtimestamp(s.get("time", 0), tz=timezone.utc)
            if s.get("time")
            else None
        )
        return DigestItem(
            title=s.get("title", "").strip(),
            url=s.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
            source="Hacker News",
            summary=f"Points: {s.get('score', 0)} | Comments: {s.get('descendants', 0)}",
            published_at=pub,
            score=s.get("score", 0),
        )
    except Exception:
        return None

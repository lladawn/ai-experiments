from datetime import datetime, timezone

import httpx

from agent.models import DigestItem

HEADERS = {"User-Agent": "daily-digest-agent/1.0"}


async def fetch_reddit(subreddits: list[dict]) -> list[DigestItem]:
    items = []
    async with httpx.AsyncClient(
        timeout=10, headers=HEADERS, follow_redirects=True
    ) as client:
        for sub_cfg in subreddits:
            name = sub_cfg["name"].lstrip("r/")
            limit = sub_cfg.get("limit", 10)
            try:
                url = f"https://www.reddit.com/r/{name}/hot.json?limit={limit}"
                resp = await client.get(url)
                data = resp.json()
                posts = data.get("data", {}).get("children", [])
                for post in posts:
                    p = post.get("data", {})
                    if p.get("stickied") or p.get("is_video"):
                        continue
                    pub = datetime.fromtimestamp(
                        p.get("created_utc", 0), tz=timezone.utc
                    )
                    items.append(
                        DigestItem(
                            title=p.get("title", "").strip(),
                            url=f"https://reddit.com{p.get('permalink', '')}",
                            source=f"r/{name}",
                            summary=p.get("selftext", "")[:300].strip()
                            or f"↑{p.get('score', 0)} | {p.get('num_comments', 0)} comments",
                            published_at=pub,
                            score=p.get("score", 0),
                        )
                    )
            except Exception as e:
                print(f"  [reddit] Failed to fetch r/{name}: {e}")
    return items

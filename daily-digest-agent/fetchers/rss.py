from datetime import datetime, timezone
from typing import Optional

import feedparser
import httpx

from agent.models import DigestItem


async def fetch_rss_feeds(feeds: list[dict]) -> list[DigestItem]:
    items = []
    async with httpx.AsyncClient(timeout=10) as client:
        for feed_cfg in feeds:
            try:
                resp = await client.get(feed_cfg["url"])
                parsed = feedparser.parse(resp.text)
                for entry in parsed.entries[:10]:
                    pub = _parse_date(entry)
                    items.append(
                        DigestItem(
                            title=entry.get("title", "").strip(),
                            url=entry.get("link", ""),
                            source=feed_cfg["name"],
                            summary=_extract_summary(entry),
                            published_at=pub,
                        )
                    )
            except Exception as e:
                print(f"  [rss] Failed to fetch {feed_cfg['name']}: {e}")
    return items


def _extract_summary(entry) -> str:
    text = entry.get("summary", "") or entry.get("description", "")
    # strip basic HTML tags
    import re

    text = re.sub(r"<[^>]+>", " ", text)
    return text[:500].strip()


def _parse_date(entry) -> Optional[datetime]:
    import time

    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if t:
        return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
    return None

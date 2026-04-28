import json
import os
from datetime import datetime, timezone, timedelta
from .models import DigestItem


def load_seen_urls(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_seen_urls(path: str, seen: dict, max_days: int = 30):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=max_days)).isoformat()
    pruned = {url: ts for url, ts in seen.items() if ts > cutoff}
    with open(path, "w") as f:
        json.dump(pruned, f, indent=2)


def dedup(items: list[DigestItem], seen: dict) -> tuple[list[DigestItem], dict]:
    fresh = []
    now = datetime.now(tz=timezone.utc).isoformat()
    for item in items:
        if item.url and item.url not in seen:
            fresh.append(item)
            seen[item.url] = now
    return fresh, seen


def basic_score(item: DigestItem, interests: list[str]) -> float:
    """
    Fast keyword pre-score before LLM scoring.
    Items that clearly match interests bubble up; others are not dropped yet
    (the LLM may still find them relevant).
    """
    text = (item.title + " " + item.summary).lower()
    hits = sum(1 for kw in interests if kw.lower() in text)
    return min(hits * 2.0, 8.0)  # caps at 8; LLM can push to 10

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class DigestItem:
    title: str
    url: str
    source: str
    summary: str = ""
    published_at: Optional[datetime] = None
    score: int = 0  # upvotes / HN points (raw)
    relevance_score: float = 0.0  # LLM-assigned 1–10
    ai_summary: str = ""  # LLM-generated one-liner
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "summary": self.summary,
            "published_at": self.published_at.isoformat()
            if self.published_at
            else None,
            "score": self.score,
            "relevance_score": self.relevance_score,
            "ai_summary": self.ai_summary,
            "tags": self.tags,
        }

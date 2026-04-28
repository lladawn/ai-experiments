"""
src/extract/schema.py
Pydantic schema for a structured event extracted from a Notion page.
Validated before any DB write — malformed LLM rows are silently dropped.
"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, field_validator


class Event(BaseModel):
    date: Optional[str] = None          # YYYY-MM-DD or YYYY-MM
    project: Optional[str] = None
    topic: Optional[str] = None
    action: str                          # required — what happened
    insight: Optional[str] = None
    source_page: str                     # required — which file this came from

    @field_validator("date", mode="before")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip()
        # Accept YYYY-MM-DD or YYYY-MM
        if re.match(r"^\d{4}-\d{2}(-\d{2})?$", v):
            return v
        return None  # drop unparseable dates rather than crashing

    @field_validator("action", "source_page", mode="before")
    @classmethod
    def must_be_nonempty(cls, v: str) -> str:
        v = str(v).strip()
        if not v:
            raise ValueError("Required field cannot be empty")
        return v

    @field_validator("project", "topic", "insight", mode="before")
    @classmethod
    def clean_optional_str(cls, v: Optional[str]) -> Optional[str]:
        if v is None or str(v).lower() in {"null", "none", "n/a", ""}:
            return None
        return str(v).strip()[:200]  # cap length

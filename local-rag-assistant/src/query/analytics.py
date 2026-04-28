"""
src/query/analytics.py
Generate natural-language summaries of monthly activity using DuckDB + LLM.
"""

from __future__ import annotations

import json
from pathlib import Path

import ollama
import pandas as pd

from src.config import get_config
from src.store.event_store import Analytics

_SUMMARY_PROMPT = """You are summarizing someone's personal work and learning activity.

Here is a JSON summary of their activity data:

{data}

Write a concise, friendly summary (3-5 sentences) covering:
- Which projects they spent the most time on
- Notable topics or areas of learning
- Any visible patterns or trends

Be specific — mention actual project names and topics from the data. Do not make up anything not in the data."""


def summarize_period(
    analytics: Analytics,
    # model: str = "mistral-small3.2:latest",
    model: str = get_config().models.llm,
    year: int | None = None,
) -> str:
    """
    Generate a natural-language summary of activity.
    If year is given, summarize just that year. Otherwise, summarize all time.
    """
    if year:
        df = analytics.year_summary(year)
        top = analytics.top_projects(limit=5)
        label = str(year)
    else:
        df = analytics.monthly_activity()
        top = analytics.top_projects(limit=5)
        label = "all time"

    if df.empty:
        return "No activity data found. Run the ingest + extraction pipeline first."

    summary_data = {
        "period": label,
        "monthly_breakdown": df.head(24).to_dict(orient="records"),
        "top_projects": top.to_dict(orient="records"),
    }

    response = ollama.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": _SUMMARY_PROMPT.format(
                    data=json.dumps(summary_data, default=str)
                ),
            }
        ],
        options={"temperature": 0.4},
    )
    return response.message.content

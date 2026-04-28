#!/usr/bin/env python3
"""
scripts/run_analytics.py
Print analytics summaries to the terminal without starting the UI.

Run from project root:
    python scripts/run_analytics.py [--year 2024]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config
from src.query.analytics import summarize_period
from src.store.event_store import Analytics, EventStore


def main(year: int | None = None) -> None:
    cfg = get_config()
    event_store = EventStore(cfg.paths.sqlite_db)
    analytics = Analytics(cfg.paths.sqlite_db)

    total = event_store.count()
    print(f"Total events in database: {total:,}\n")

    if total == 0:
        print("No events found. Run: python scripts/run_ingest.py")
        return

    # Top projects
    print("── Top Projects ─────────────────────────────────────────")
    top_df = analytics.top_projects(limit=10)
    print(top_df.to_string(index=False))

    # Monthly breakdown
    if year:
        print(f"\n── {year} Monthly Breakdown ──────────────────────────────────")
        df = analytics.year_summary(year)
        print(df.to_string(index=False))
    else:
        print("\n── Monthly Activity (last 12 months) ────────────────────────")
        df = analytics.monthly_activity()
        print(df.tail(12).to_string(index=False))

    # AI summary
    print("\n── AI Summary ───────────────────────────────────────────────")
    print("Generating summary (this may take a moment)...")
    summary = summarize_period(analytics, model=cfg.models.llm, year=year)
    print(summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=None, help="Summarize a specific year")
    args = parser.parse_args()
    main(year=args.year)

#!/usr/bin/env python3
"""
daily-digest-agent
------------------
Run:  python -m daily_digest_agent
Or:   python main.py
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

from fetchers.rss import fetch_rss_feeds
from fetchers.hackernews import fetch_hackernews
from fetchers.reddit import fetch_reddit
from agent.filter import dedup, load_seen_urls, save_seen_urls, basic_score
from agent.summarizer import score_and_summarize, generate_digest_intro
from outputs.markdown import render_markdown


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


async def run(config_path: str = "config.yaml"):
    cfg = load_config(config_path)
    profile = cfg["profile"]
    interests = profile["interests"]
    llm_cfg = cfg["llm"]
    out_cfg = cfg["output"]
    mem_cfg = cfg["memory"]

    print(f"\n🗞  Daily Digest Agent — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # ── 1. Fetch all sources in parallel ────────────────
    print("\n[1/4] Fetching sources...")
    tasks = []
    sources = cfg["sources"]

    if sources.get("rss", {}).get("enabled"):
        tasks.append(fetch_rss_feeds(sources["rss"]["feeds"]))
    if sources.get("hackernews", {}).get("enabled"):
        tasks.append(fetch_hackernews(sources["hackernews"].get("top_n", 20)))
    if sources.get("reddit", {}).get("enabled"):
        tasks.append(fetch_reddit(sources["reddit"]["subreddits"]))

    results = await asyncio.gather(*tasks)
    all_items = [item for batch in results for item in batch]
    print(f"   Fetched {len(all_items)} raw items")

    # ── 2. Dedup ─────────────────────────────────────────
    print("\n[2/4] Deduplicating...")
    seen = load_seen_urls(mem_cfg["seen_urls_file"])
    fresh_items, seen = dedup(all_items, seen)
    save_seen_urls(mem_cfg["seen_urls_file"], seen, mem_cfg.get("max_history_days", 30))
    print(f"   {len(fresh_items)} new items (dropped {len(all_items) - len(fresh_items)} seen)")

    # Pre-score with keywords to sort batch order (higher = process first)
    for item in fresh_items:
        item.relevance_score = basic_score(item, interests)
    fresh_items.sort(key=lambda x: x.relevance_score, reverse=True)

    # ── 3. LLM scoring + summarization ──────────────────
    print(f"\n[3/4] Scoring with LLM ({llm_cfg['provider']} / {llm_cfg['model']})...")
    scored = await score_and_summarize(
        fresh_items,
        interests,
        provider=llm_cfg["provider"],
        model=llm_cfg["model"],
        max_items=llm_cfg.get("max_items_to_summarize", 15),
    )

    min_score = profile.get("min_relevance_score", 6)
    top = [i for i in scored if i.relevance_score >= min_score]
    print(f"   {len(top)} items above threshold (≥{min_score})")

    intro = await generate_digest_intro(top, interests, llm_cfg["provider"], llm_cfg["model"])

    # ── 4. Output ────────────────────────────────────────
    print("\n[4/4] Rendering output...")
    digest = render_markdown(scored, intro, min_score, profile["name"])

    if out_cfg["delivery"].get("terminal"):
        print("\n" + "=" * 50)
        print(digest)

    if out_cfg["delivery"].get("save_file"):
        file_path = out_cfg["delivery"]["file_path"].replace(
            "{date}", datetime.now().strftime("%Y-%m-%d")
        )
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            f.write(digest)
        print(f"\n✓ Saved to {file_path}")

    print("\nDone.\n")


if __name__ == "__main__":
    config = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    asyncio.run(run(config))

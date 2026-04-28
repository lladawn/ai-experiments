#!/usr/bin/env python3
"""
query.py — Ask questions against your LLM wiki.

Usage:
    python scripts/query.py "What are the main themes in my research?"
    python scripts/query.py "Compare X and Y" --save
    python scripts/query.py "What do I know about transformers?" --format marp

Options:
    --save          Save the answer as a wiki page (query-result type)
    --format        Output format: text (default), marp (slides), table

Requirements:
    pip install anthropic
    export ANTHROPIC_API_KEY=your_key
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import anthropic

WIKI_ROOT = Path(__file__).parent.parent
WIKI_DIR = WIKI_ROOT / "wiki"
AGENTS_MD = WIKI_ROOT / "AGENTS.md"
TODAY = date.today().isoformat()

QUERY_PROMPT = """
You are the maintainer of a personal LLM wiki. Answer a question using only the knowledge in the wiki.

## Your instructions (AGENTS.md)
{agents_md}

## Wiki index
{index_md}

## Relevant wiki pages
{relevant_pages}

## Question
{question}

## Output format requested
{output_format}

---

Respond with a JSON object (no markdown fences):

{{
  "answer": "your full answer in markdown, with [[wiki page]] citations",
  "relevant_pages": ["list", "of", "page", "titles", "you", "used"],
  "confidence": "high | medium | low",
  "gaps": "what's missing from the wiki to answer this more fully",
  "save_as_title": "suggested page title if this answer is worth saving (or null)"
}}

Rules:
- Cite wiki pages using [[Title]] inline.
- If the wiki doesn't have enough information, say so clearly.
- Don't make up facts not in the wiki.
- For 'marp' format, write the answer as a Marp slide deck (--- separators, # headings per slide).
- For 'table' format, use a markdown table where appropriate.
"""


def find_relevant_pages(question: str, index_md: str) -> str:
    """Simple keyword-based page finder. Reads all pages and returns content."""
    # In a real system you'd embed + cosine search. For week-1, keywords work fine.
    question_words = set(re.sub(r"[^\w\s]", "", question.lower()).split())
    
    scores = {}
    for md_file in sorted(WIKI_DIR.glob("**/*.md")):
        if md_file.name in ("index.md", "log.md"):
            continue
        content = md_file.read_text(encoding="utf-8").lower()
        score = sum(1 for w in question_words if w in content and len(w) > 3)
        if score > 0:
            scores[md_file] = score

    # Take top 8 pages
    top_pages = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:8]
    
    if not top_pages:
        return "(no relevant pages found — wiki may be empty)"

    result = []
    for fpath, score in top_pages:
        rel = fpath.relative_to(WIKI_ROOT)
        content = fpath.read_text(encoding="utf-8")
        result.append(f"### {rel} (relevance: {score})\n{content}")
    
    return "\n\n---\n\n".join(result)


def query(question: str, model: str, output_format: str, save: bool):
    agents_md = AGENTS_MD.read_text(encoding="utf-8")
    index_md_path = WIKI_DIR / "index.md"
    index_md = index_md_path.read_text(encoding="utf-8") if index_md_path.exists() else "(empty)"
    relevant_pages = find_relevant_pages(question, index_md)

    prompt = QUERY_PROMPT.format(
        agents_md=agents_md,
        index_md=index_md,
        relevant_pages=relevant_pages,
        question=question,
        output_format=output_format,
    )

    print(f"\n🔍 Query: {question}")
    print(f"   Model: {model}\n")

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse response: {e}")
        print(raw[:500])
        sys.exit(1)

    print("=" * 60)
    print(result["answer"])
    print("=" * 60)
    print(f"\n📊 Confidence: {result.get('confidence', '?')}")
    if result.get("gaps"):
        print(f"⚠️  Gaps: {result['gaps']}")

    if save or (result.get("save_as_title") and _ask_save(result["save_as_title"])):
        _save_query_result(question, result, output_format)


def _ask_save(suggested_title: str) -> bool:
    try:
        ans = input(f"\n💾 Save as wiki page '{suggested_title}'? [y/N] ").strip().lower()
        return ans == "y"
    except (KeyboardInterrupt, EOFError):
        return False


def _save_query_result(question: str, result: dict, output_format: str):
    safe_name = re.sub(r"[^\w\s-]", "", question.lower())[:50].strip().replace(" ", "-")
    fname = f"wiki/queries/{TODAY}-{safe_name}.md"
    fpath = WIKI_ROOT / fname
    fpath.parent.mkdir(parents=True, exist_ok=True)

    title = result.get("save_as_title") or f"Query: {question[:60]}"
    sources_used = ", ".join(result.get("relevant_pages", []))

    content = f"""---
title: "{title}"
type: query-result
tags: [query]
sources: [{sources_used}]
updated: {TODAY}
---

Query: {question}

## Answer

{result["answer"]}

## Metadata
- Confidence: {result.get("confidence", "?")}
- Pages used: {sources_used}
- Gaps: {result.get("gaps", "none noted")}
"""

    fpath.write_text(content, encoding="utf-8")
    print(f"\n✅ Saved to {fname}")

    # Append to log
    log_path = WIKI_DIR / "log.md"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n## [{TODAY}] query | {title}\n")
        f.write(f"Question: {question}\nSaved as: {fname}\n")


def main():
    parser = argparse.ArgumentParser(description="Query your LLM wiki")
    parser.add_argument("question", help="Your question")
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Claude model")
    parser.add_argument("--format", default="text", choices=["text", "marp", "table"])
    parser.add_argument("--save", action="store_true", help="Auto-save as wiki page")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Set ANTHROPIC_API_KEY environment variable first.")
        sys.exit(1)

    query(args.question, args.model, args.format, args.save)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
ingest.py — Add a new source to your LLM wiki.

Usage:
    python scripts/ingest.py path/to/source.md
    python scripts/ingest.py path/to/source.md --model claude-opus-4-6
    python scripts/ingest.py path/to/source.md --dry-run

What it does:
    1. Reads the source file
    2. Reads your current wiki (AGENTS.md + index.md + existing pages)
    3. Sends everything to Claude with instructions to update the wiki
    4. Writes all new/updated wiki files to disk
    5. Appends to log.md

Requirements:
    pip install anthropic
    export ANTHROPIC_API_KEY=your_key
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import anthropic

WIKI_ROOT = Path(__file__).parent.parent
SOURCES_DIR = WIKI_ROOT / "sources"
WIKI_DIR = WIKI_ROOT / "wiki"
AGENTS_MD = WIKI_ROOT / "AGENTS.md"

TODAY = date.today().isoformat()

INGEST_PROMPT = """
You are the maintainer of a personal LLM wiki. Your job is to ingest a new source document and update the wiki accordingly.

## Your instructions (AGENTS.md)
{agents_md}

## Current wiki state

### index.md
{index_md}

### Existing wiki pages
{existing_pages}

## New source to ingest
Filename: {source_filename}

{source_content}

---

## Your task

Ingest this source into the wiki. Follow the INGEST operation from AGENTS.md exactly.

Respond with a JSON object in this exact format (no other text, no markdown fences):

{{
  "discussion": "3-5 bullet points summarizing key takeaways from this source",
  "files": [
    {{
      "path": "wiki/sources/article-title.md",
      "content": "full markdown content of this file"
    }},
    {{
      "path": "wiki/some-concept.md",
      "content": "full markdown content"
    }},
    {{
      "path": "wiki/index.md",
      "content": "complete updated index.md content"
    }},
    {{
      "path": "wiki/log.md",
      "content": "complete updated log.md content with new entry appended"
    }}
  ]
}}

Rules:
- Include ALL files that need to be created or updated, including index.md and log.md.
- For existing pages, write the COMPLETE updated content (not just the diff).
- Use [[Double bracket]] syntax for all internal wiki links.
- Today's date is {today}.
- Be thorough — a single source might update 5-15 pages.
"""


def load_existing_wiki_pages():
    """Load all current wiki pages into a string summary."""
    pages = []
    for md_file in sorted(WIKI_DIR.glob("**/*.md")):
        rel = md_file.relative_to(WIKI_ROOT)
        content = md_file.read_text(encoding="utf-8")
        # Truncate very long pages to save tokens
        if len(content) > 2000:
            content = content[:2000] + "\n\n... [truncated for context]"
        pages.append(f"### {rel}\n{content}")
    return "\n\n---\n\n".join(pages) if pages else "(no wiki pages yet)"


def ingest(source_path: Path, model: str, dry_run: bool):
    source_content = source_path.read_text(encoding="utf-8")
    agents_md = AGENTS_MD.read_text(encoding="utf-8")
    index_md_path = WIKI_DIR / "index.md"
    index_md = index_md_path.read_text(encoding="utf-8") if index_md_path.exists() else "(empty)"
    existing_pages = load_existing_wiki_pages()

    prompt = INGEST_PROMPT.format(
        agents_md=agents_md,
        index_md=index_md,
        existing_pages=existing_pages,
        source_filename=source_path.name,
        source_content=source_content,
        today=TODAY,
    )

    print(f"\n📥 Ingesting: {source_path.name}")
    print(f"   Model: {model}")
    print(f"   Source length: {len(source_content):,} chars\n")

    client = anthropic.Anthropic()

    print("🤖 Sending to Claude...\n")
    response = client.messages.create(
        model=model,
        max_tokens=8096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip accidental markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse JSON response: {e}")
        print("Raw response:\n", raw[:500])
        sys.exit(1)

    # Print discussion
    print("💡 Key takeaways:")
    print(result.get("discussion", "(none)"))
    print()

    files = result.get("files", [])
    print(f"📝 Wiki updates ({len(files)} files):")

    for f in files:
        fpath = WIKI_ROOT / f["path"]
        print(f"   {'[DRY RUN] ' if dry_run else ''}→ {f['path']}")
        if not dry_run:
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(f["content"], encoding="utf-8")

    # Copy source to sources/ if not already there
    dest = SOURCES_DIR / source_path.name
    if not dest.exists() and not dry_run:
        import shutil
        shutil.copy2(source_path, dest)
        print(f"\n   → Copied source to sources/{source_path.name}")

    print(f"\n✅ Done! {'(dry run — no files written)' if dry_run else 'Wiki updated.'}")
    print(f"\nTip: Open the wiki/ folder in Obsidian to browse the results.")


def main():
    parser = argparse.ArgumentParser(description="Ingest a source into your LLM wiki")
    parser.add_argument("source", help="Path to source file (markdown or text)")
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Claude model to use")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"❌ File not found: {source_path}")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Set ANTHROPIC_API_KEY environment variable first.")
        sys.exit(1)

    ingest(source_path, args.model, args.dry_run)


if __name__ == "__main__":
    main()

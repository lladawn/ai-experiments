#!/usr/bin/env python3
"""
lint.py — Health-check your LLM wiki.

Usage:
    python scripts/lint.py
    python scripts/lint.py --fix    (let Claude suggest repairs)

Checks for:
  - Orphan pages (no inbound links)
  - Broken [[wiki links]] (link targets that don't exist)
  - Pages missing required frontmatter fields
  - Concepts mentioned in text but lacking their own page
  - Stale/contradictory claims (requires LLM)
  - Suggested new sources to find

Requirements:
    pip install anthropic
    export ANTHROPIC_API_KEY=your_key  (only needed with --fix)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import anthropic

WIKI_ROOT = Path(__file__).parent.parent
WIKI_DIR = WIKI_ROOT / "wiki"
AGENTS_MD = WIKI_ROOT / "AGENTS.md"

REQUIRED_FRONTMATTER = ["title", "type", "updated"]

LINT_PROMPT = """
You are health-checking a personal LLM wiki. Review all pages below and identify issues.

## AGENTS.md
{agents_md}

## All wiki pages
{all_pages}

---

Respond with JSON (no fences):

{{
  "contradictions": [
    {{"pages": ["Page A", "Page B"], "issue": "Page A says X, Page B says Y"}}
  ],
  "stale_claims": [
    {{"page": "Page Title", "claim": "the claim that may be stale", "reason": "why"}}
  ],
  "missing_pages": [
    {{"concept": "term frequently mentioned", "mentioned_in": ["Page A", "Page B"]}}
  ],
  "suggested_sources": [
    "Source or topic worth investigating to fill gaps"
  ],
  "suggested_questions": [
    "An interesting question your wiki could now answer"
  ],
  "health_score": 0-100,
  "summary": "2-3 sentence overall health assessment"
}}
"""


def get_all_page_titles() -> dict:
    """Returns {normalized_title: Path} for all wiki pages."""
    titles = {}
    for md_file in WIKI_DIR.glob("**/*.md"):
        if md_file.name in ("log.md",):
            continue
        # Try to get title from frontmatter, fall back to filename
        content = md_file.read_text(encoding="utf-8")
        m = re.search(r"^title:\s*[\"']?(.+?)[\"']?\s*$", content, re.MULTILINE)
        title = m.group(1).strip() if m else md_file.stem.replace("-", " ").title()
        titles[title.lower()] = md_file
    return titles


def extract_wiki_links(content: str) -> list:
    return re.findall(r"\[\[([^\]]+)\]\]", content)


def check_frontmatter(content: str, path: Path) -> list:
    issues = []
    if not content.startswith("---"):
        issues.append(f"  ⚠  Missing frontmatter")
        return issues
    end = content.find("---", 3)
    if end == -1:
        issues.append(f"  ⚠  Unclosed frontmatter")
        return issues
    fm = content[3:end]
    for field in REQUIRED_FRONTMATTER:
        if f"{field}:" not in fm:
            issues.append(f"  ⚠  Missing frontmatter field: {field}")
    return issues


def run_local_checks():
    """Fast checks that don't need an LLM."""
    all_titles = get_all_page_titles()
    
    inbound_links = {t: [] for t in all_titles}
    broken_links = []
    frontmatter_issues = []

    for md_file in sorted(WIKI_DIR.glob("**/*.md")):
        if md_file.name == "log.md":
            continue
        rel = str(md_file.relative_to(WIKI_ROOT))
        content = md_file.read_text(encoding="utf-8")
        
        # Check frontmatter (skip index and log)
        if md_file.name not in ("index.md", "log.md", "overview.md"):
            issues = check_frontmatter(content, md_file)
            if issues:
                frontmatter_issues.append((rel, issues))

        # Check links
        for link in extract_wiki_links(content):
            target = link.lower()
            if target in inbound_links:
                inbound_links[target].append(rel)
            else:
                broken_links.append((rel, link))

    orphans = [
        (title, str(path.relative_to(WIKI_ROOT)))
        for title, path in all_titles.items()
        if len(inbound_links.get(title, [])) == 0
        and path.name not in ("index.md", "log.md", "overview.md")
    ]

    return {
        "orphans": orphans,
        "broken_links": broken_links,
        "frontmatter_issues": frontmatter_issues,
        "page_count": len(all_titles),
        "link_count": sum(len(v) for v in inbound_links.values()),
    }


def run_llm_checks(model: str):
    """Deeper checks using Claude — contradictions, suggestions, etc."""
    agents_md = AGENTS_MD.read_text(encoding="utf-8")

    pages = []
    for md_file in sorted(WIKI_DIR.glob("**/*.md")):
        if md_file.name == "log.md":
            continue
        rel = md_file.relative_to(WIKI_ROOT)
        content = md_file.read_text(encoding="utf-8")
        if len(content) > 1500:
            content = content[:1500] + "\n... [truncated]"
        pages.append(f"### {rel}\n{content}")
    all_pages = "\n\n---\n\n".join(pages)

    prompt = LINT_PROMPT.format(agents_md=agents_md, all_pages=all_pages)

    client = anthropic.Anthropic()
    print("\n🤖 Running LLM health check...")
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description="Health-check your LLM wiki")
    parser.add_argument("--fix", action="store_true", help="Run LLM deep check for contradictions/suggestions")
    parser.add_argument("--model", default="claude-sonnet-4-6")
    args = parser.parse_args()

    print("\n🔍 Running local checks...")
    local = run_local_checks()

    print(f"\n📊 Wiki stats: {local['page_count']} pages, {local['link_count']} links\n")

    if local["orphans"]:
        print(f"🔴 Orphan pages ({len(local['orphans'])} — no inbound links):")
        for title, path in local["orphans"]:
            print(f"   {path}")

    if local["broken_links"]:
        print(f"\n🔴 Broken links ({len(local['broken_links'])}):")
        for source, link in local["broken_links"]:
            print(f"   [[{link}]] in {source}")

    if local["frontmatter_issues"]:
        print(f"\n🟡 Frontmatter issues ({len(local['frontmatter_issues'])} files):")
        for path, issues in local["frontmatter_issues"]:
            print(f"   {path}:")
            for issue in issues:
                print(f"  {issue}")

    if not any([local["orphans"], local["broken_links"], local["frontmatter_issues"]]):
        print("✅ No local issues found!")

    if args.fix:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("❌ Set ANTHROPIC_API_KEY for --fix mode.")
            sys.exit(1)
        llm = run_llm_checks(args.model)

        print(f"\n🏥 Health score: {llm.get('health_score', '?')}/100")
        print(f"   {llm.get('summary', '')}")

        if llm.get("contradictions"):
            print(f"\n⚠️  Contradictions ({len(llm['contradictions'])}):")
            for c in llm["contradictions"]:
                print(f"   {c['pages']}: {c['issue']}")

        if llm.get("missing_pages"):
            print(f"\n📄 Concepts needing their own page:")
            for m in llm["missing_pages"]:
                print(f"   [[{m['concept']}]] — mentioned in: {', '.join(m['mentioned_in'])}")

        if llm.get("suggested_sources"):
            print(f"\n📚 Suggested sources to add:")
            for s in llm["suggested_sources"]:
                print(f"   • {s}")

        if llm.get("suggested_questions"):
            print(f"\n💭 Interesting questions your wiki could answer:")
            for q in llm["suggested_questions"]:
                print(f"   • {q}")


if __name__ == "__main__":
    main()

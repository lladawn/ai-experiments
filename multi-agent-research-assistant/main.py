"""
Research Agent — main orchestrator.

Usage:
  python main.py "The impact of large language models on software engineering"
  python main.py "Quantum computing current state" --output report.md
"""

import argparse
import asyncio
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agents import plan, search_and_summarize, write_report


async def run_research(topic: str) -> str:
    """Full pipeline: plan → search (parallel) → write."""
    start = time.time()
    print(f"\n{'=' * 60}")
    print(f"  Research Agent")
    print(f"  Topic: {topic}")
    print(f"{'=' * 60}")

    # Step 1: Planner breaks topic into sub-questions
    sub_questions = await plan(topic)

    # Step 2: Search agents run in parallel — one per sub-question
    print(f"\n📡 Running {len(sub_questions)} search agents in parallel...")
    findings = await asyncio.gather(*[search_and_summarize(q) for q in sub_questions])

    # Step 3: Writer synthesises everything into a report
    report = await write_report(topic, list(findings))

    elapsed = time.time() - start
    print(f"\n✅ Done in {elapsed:.1f}s")
    return report


def main():
    parser = argparse.ArgumentParser(description="Multi-agent research assistant")
    parser.add_argument("topic", help="Research topic")
    parser.add_argument("--output", "-o", help="Save report to file (e.g. report.md)")
    args = parser.parse_args()

    report = asyncio.run(run_research(args.topic))

    print(f"\n{'=' * 60}")
    print(report)
    print(f"{'=' * 60}\n")

    # Ensure outputs directory exists and save a copy of the report there
    out_dir = Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = args.topic[:40].strip().replace(" ", "_").replace("/", "_")
    out_path = out_dir / f"{safe_name}.md"
    out_path.write_text(report)
    print(f"💾 Report saved to {out_path}")

    if args.output:
        Path(args.output).write_text(report)
        print(f"💾 Report saved to {args.output}")


if __name__ == "__main__":
    main()

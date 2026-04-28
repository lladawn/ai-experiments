"""
Research Agent — main orchestrator.

Usage:
  python main.py "The impact of large language models on software engineering"
  python main.py "Is remote work good for productivity?" --debate
  python main.py "Quantum computing current state" --output report.md
"""

import argparse
import asyncio
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agents import (
    debate_search,
    plan,
    search_and_summarize,
    write_debate_report,
    write_report,
)


async def run_research(topic: str, debate: bool = False) -> str:
    """Full pipeline: plan → search (parallel) → write."""
    start = time.time()
    mode = "DEBATE MODE ⚔️ " if debate else "RESEARCH MODE"
    print(f"\n{'=' * 60}")
    print(f"  Research Agent — {mode}")
    print(f"  Topic: {topic}")
    print(f"{'=' * 60}")

    # Step 1: Planner breaks topic into sub-questions
    sub_questions = await plan(topic)

    if debate:
        # Step 2b: Two agents per question — FOR and AGAINST — all in parallel
        print(
            f"\n⚔️  Running {len(sub_questions) * 2} debate agents in parallel ({len(sub_questions)} questions × 2 sides)..."
        )
        findings = await asyncio.gather(*[debate_search(q) for q in sub_questions])
        report = await write_debate_report(topic, list(findings))
    else:
        # Step 2a: One neutral search agent per question
        print(f"\n📡 Running {len(sub_questions)} search agents in parallel...")
        findings = await asyncio.gather(
            *[search_and_summarize(q) for q in sub_questions]
        )
        report = await write_report(topic, list(findings))

    elapsed = time.time() - start
    print(f"\n✅ Done in {elapsed:.1f}s")
    return report


def main():
    parser = argparse.ArgumentParser(description="Multi-agent research assistant")
    parser.add_argument("topic", help="Research topic")
    parser.add_argument(
        "--debate",
        action="store_true",
        help="Run in debate mode: FOR vs AGAINST per question",
    )
    parser.add_argument("--output", "-o", help="Save report to file (e.g. report.md)")
    args = parser.parse_args()

    report = asyncio.run(run_research(args.topic, debate=args.debate))

    print(f"\n{'=' * 60}")
    print(report)
    print(f"{'=' * 60}\n")

    if args.output:
        Path(args.output).write_text(report)
        print(f"💾 Report saved to {args.output}")


if __name__ == "__main__":
    main()

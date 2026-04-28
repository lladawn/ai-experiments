"""
Writer agent — takes all search findings and synthesises them into
a well-structured markdown report with inline citations.
"""

from .searcher import SearchFindings
from .llm import chat


SYSTEM_PROMPT = """You are an expert research writer.
Given a topic and a set of research findings (each with a question, summary, and sources),
write a comprehensive, well-structured report in markdown.

Structure:
# [Topic]

## Executive Summary
2–3 sentence overview.

## [Section per finding — use a meaningful heading, not the raw question]
Detailed prose synthesising the finding. Cite sources inline as [1], [2], etc.

## Conclusion
Key takeaways and open questions.

## References
Numbered list of all source URLs.

Rules:
- Write flowing prose, not bullet points
- Cite sources inline throughout the sections
- Be specific: include numbers, names, dates when present
- Keep the tone neutral and informative
- References section must number all URLs from all findings"""


async def write_report(topic: str, findings: list[SearchFindings]) -> str:
    """Synthesise all findings into a final markdown report."""
    print(f"\n✍️  Writer: Synthesising {len(findings)} findings into report...")

    # Build the input for the writer
    findings_text = ""
    ref_counter = 1
    for f in findings:
        findings_text += f"\n### Question: {f.question}\n"
        findings_text += f"Summary:\n{f.summary}\n"
        findings_text += "Sources:\n"
        for src in f.sources:
            findings_text += f"  [{ref_counter}] {src.title} — {src.url}\n"
            ref_counter += 1

    report = await chat(
        system=SYSTEM_PROMPT,
        user=f"Topic: {topic}\n\nFindings:\n{findings_text}",
        max_tokens=2000,
    )

    print("  ✓ Report complete")
    return report

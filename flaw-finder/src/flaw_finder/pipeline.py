from __future__ import annotations

from .agents import PersonaReviewer, default_reviewers
from .models import Finding, InputArtifact, Severity, Synthesis


SEVERITY_ORDER = {
    Severity.HIGH: 0,
    Severity.MEDIUM: 1,
    Severity.LOW: 2,
}


def run_review(
    artifact: InputArtifact,
    reviewers: list[PersonaReviewer] | None = None,
) -> Synthesis:
    active_reviewers = reviewers or default_reviewers()
    reviews = [reviewer.review(artifact) for reviewer in active_reviewers]
    findings = [finding for review in reviews for finding in review.findings]
    ranked = sorted(findings, key=lambda finding: (SEVERITY_ORDER[finding.severity], finding.persona))

    summary = _summarize(artifact, findings)
    top_fixes = _top_fixes(ranked)
    return Synthesis(summary=summary, top_fixes=top_fixes, reviews=reviews)


def render_markdown(synthesis: Synthesis) -> str:
    lines = ["# Flaw Finder Report", "", synthesis.summary, "", "## Top fixes"]
    if synthesis.top_fixes:
        lines.extend(f"{index}. {fix}" for index, fix in enumerate(synthesis.top_fixes, start=1))
    else:
        lines.append("No obvious flaws found by the current local rules.")

    for review in synthesis.reviews:
        lines.extend(["", f"## {review.persona}", "", review.stance])
        if not review.findings:
            lines.append("")
            lines.append("No findings from this persona.")
            continue

        for finding in sorted(review.findings, key=lambda item: SEVERITY_ORDER[item.severity]):
            lines.extend(
                [
                    "",
                    f"### {finding.severity.value.title()}: {finding.issue}",
                    f"- Evidence: {finding.evidence}",
                    f"- Fix: {finding.fix}",
                ]
            )

    return "\n".join(lines) + "\n"


def _summarize(artifact: InputArtifact, findings: list[Finding]) -> str:
    high_count = sum(1 for finding in findings if finding.severity == Severity.HIGH)
    if not findings:
        return f"`{artifact.title}` survived the current local red-team checks."
    return (
        f"`{artifact.title}` has {len(findings)} flagged issue(s), including "
        f"{high_count} high-severity item(s). Treat this as an experiment-grade first pass, "
        "not a substitute for expert review."
    )


def _top_fixes(findings: list[Finding], limit: int = 5) -> list[str]:
    seen: set[str] = set()
    fixes: list[str] = []
    for finding in findings:
        if finding.fix in seen:
            continue
        fixes.append(finding.fix)
        seen.add(finding.fix)
        if len(fixes) == limit:
            break
    return fixes


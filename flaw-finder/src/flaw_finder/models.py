from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class InputArtifact:
    title: str
    body: str
    source: str = "inline"


@dataclass(frozen=True)
class Finding:
    persona: str
    severity: Severity
    issue: str
    evidence: str
    fix: str


@dataclass(frozen=True)
class Review:
    persona: str
    stance: str
    findings: list[Finding] = field(default_factory=list)


@dataclass(frozen=True)
class Synthesis:
    summary: str
    top_fixes: list[str]
    reviews: list[Review]


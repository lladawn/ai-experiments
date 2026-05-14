from __future__ import annotations

import re
from collections.abc import Callable

from .models import Finding, InputArtifact, Review, Severity


ReviewerRule = Callable[[InputArtifact], Finding | None]


def _contains_any(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _missing_any(text: str, terms: list[str]) -> bool:
    return not _contains_any(text, terms)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


class PersonaReviewer:
    def __init__(self, persona: str, stance: str, rules: list[ReviewerRule]) -> None:
        self.persona = persona
        self.stance = stance
        self.rules = rules

    def review(self, artifact: InputArtifact) -> Review:
        findings = [finding for rule in self.rules if (finding := rule(artifact))]
        return Review(persona=self.persona, stance=self.stance, findings=findings)


def skeptical_investor() -> PersonaReviewer:
    return PersonaReviewer(
        persona="Skeptical investor",
        stance="Looks for market, differentiation, traction, and business-model holes.",
        rules=[
            _investor_missing_customer,
            _investor_missing_business_model,
            _investor_missing_traction,
            _investor_vague_superlatives,
        ],
    )


def hostile_lawyer() -> PersonaReviewer:
    return PersonaReviewer(
        persona="Hostile lawyer",
        stance="Looks for unsupported claims, regulatory exposure, and liability traps.",
        rules=[
            _lawyer_unsupported_guarantees,
            _lawyer_missing_privacy,
            _lawyer_medical_financial_or_legal,
            _lawyer_broad_competitor_claims,
        ],
    )


def confused_end_user() -> PersonaReviewer:
    return PersonaReviewer(
        persona="Confused end-user",
        stance="Looks for confusing language, unclear next steps, and missing workflow context.",
        rules=[
            _user_missing_next_step,
            _user_jargon_density,
            _user_missing_time_to_value,
            _user_too_short_to_understand,
        ],
    )


def default_reviewers() -> list[PersonaReviewer]:
    return [skeptical_investor(), hostile_lawyer(), confused_end_user()]


def _investor_missing_customer(artifact: InputArtifact) -> Finding | None:
    if _missing_any(artifact.body, ["customer", "user", "buyer", "founder", "team", "sales"]):
        return Finding(
            persona="Skeptical investor",
            severity=Severity.HIGH,
            issue="The target customer is not concrete enough.",
            evidence="The artifact does not clearly name who buys or repeatedly uses this.",
            fix="Name the first painful segment, their current workaround, and why they switch now.",
        )
    return None


def _investor_missing_business_model(artifact: InputArtifact) -> Finding | None:
    if _missing_any(artifact.body, ["price", "pricing", "revenue", "subscription", "seat", "plan"]):
        return Finding(
            persona="Skeptical investor",
            severity=Severity.MEDIUM,
            issue="The business model is absent or too implicit.",
            evidence="There is no obvious pricing, revenue motion, or willingness-to-pay signal.",
            fix="Add a simple initial pricing hypothesis and the budget this replaces or unlocks.",
        )
    return None


def _investor_missing_traction(artifact: InputArtifact) -> Finding | None:
    if _missing_any(artifact.body, ["pilot", "waitlist", "usage", "retention", "customer", "revenue", "%"]):
        return Finding(
            persona="Skeptical investor",
            severity=Severity.MEDIUM,
            issue="There is no proof that anyone wants this yet.",
            evidence="The pitch has no traction, usage, pilot, waitlist, or conversion signal.",
            fix="Include the smallest real demand proof: interviews, prototype sessions, pilots, or paid LOIs.",
        )
    return None


def _investor_vague_superlatives(artifact: InputArtifact) -> Finding | None:
    if _contains_any(artifact.body, ["revolutionary", "game-changing", "world-class", "best-in-class"]):
        return Finding(
            persona="Skeptical investor",
            severity=Severity.LOW,
            issue="The pitch leans on superlatives instead of evidence.",
            evidence="Terms like revolutionary or best-in-class invite skepticism unless backed by proof.",
            fix="Replace broad adjectives with a measurable before-and-after claim.",
        )
    return None


def _lawyer_unsupported_guarantees(artifact: InputArtifact) -> Finding | None:
    if _contains_any(artifact.body, ["guarantee", "never", "always", "eliminate", "risk-free"]):
        return Finding(
            persona="Hostile lawyer",
            severity=Severity.HIGH,
            issue="Absolute claims create avoidable liability.",
            evidence="Guarantees and words like never, always, eliminate, or risk-free are easy to attack.",
            fix="Qualify the claim, state conditions, and distinguish assistance from guaranteed outcomes.",
        )
    return None


def _lawyer_missing_privacy(artifact: InputArtifact) -> Finding | None:
    if _contains_any(artifact.body, ["upload", "deck", "email", "proposal", "website", "app"]) and _missing_any(
        artifact.body, ["privacy", "confidential", "retention", "delete", "security", "encrypted"]
    ):
        return Finding(
            persona="Hostile lawyer",
            severity=Severity.HIGH,
            issue="Sensitive input handling is not addressed.",
            evidence="Users may upload confidential decks, emails, proposals, or app links.",
            fix="State data retention, deletion, access controls, and whether user content trains models.",
        )
    return None


def _lawyer_medical_financial_or_legal(artifact: InputArtifact) -> Finding | None:
    if _contains_any(artifact.body, ["lawyer", "legal", "investor", "financial", "medical", "health"]):
        return Finding(
            persona="Hostile lawyer",
            severity=Severity.MEDIUM,
            issue="The product may be mistaken for professional advice.",
            evidence="The artifact invokes legal, investor, financial, medical, or health contexts.",
            fix="Clarify that outputs are issue-spotting aids, not legal, financial, or medical advice.",
        )
    return None


def _lawyer_broad_competitor_claims(artifact: InputArtifact) -> Finding | None:
    broad_claim_pattern = re.compile(
        r"\b(only|first)\s+(platform|product|company|tool|solution|app)\b|"
        r"\b(better than|unlike every)\b",
        re.IGNORECASE,
    )
    if broad_claim_pattern.search(artifact.body):
        return Finding(
            persona="Hostile lawyer",
            severity=Severity.LOW,
            issue="Competitive claims need substantiation.",
            evidence="First, only, and better-than claims can trigger substantiation questions.",
            fix="Use narrower comparisons and keep dated evidence for any defensible claim.",
        )
    return None


def _user_missing_next_step(artifact: InputArtifact) -> Finding | None:
    if _missing_any(artifact.body, ["upload", "paste", "try", "start", "send", "drop in", "link"]):
        return Finding(
            persona="Confused end-user",
            severity=Severity.HIGH,
            issue="The user does not know what to do first.",
            evidence="There is no clear action such as uploading, pasting, linking, or starting a review.",
            fix="Make the first action unmistakable and describe what the user receives after doing it.",
        )
    return None


def _user_jargon_density(artifact: InputArtifact) -> Finding | None:
    jargon = ["agent", "synthesis", "persona", "red team", "workflow", "pipeline", "adversarial"]
    hits = sum(1 for term in jargon if term in artifact.body.lower())
    if hits >= 4:
        return Finding(
            persona="Confused end-user",
            severity=Severity.MEDIUM,
            issue="The copy may be too insider-coded for a normal buyer.",
            evidence="It uses several AI/product terms before explaining the plain outcome.",
            fix="Lead with the result in everyday language, then explain the agent mechanics later.",
        )
    return None


def _user_missing_time_to_value(artifact: InputArtifact) -> Finding | None:
    if _missing_any(artifact.body, ["minute", "second", "today", "instant", "fast", "quick"]):
        return Finding(
            persona="Confused end-user",
            severity=Severity.LOW,
            issue="The user cannot tell how quickly they get value.",
            evidence="The artifact does not set expectations for turnaround time or effort.",
            fix="Add a concrete promise such as 'get the top fixes in under 2 minutes.'",
        )
    return None


def _user_too_short_to_understand(artifact: InputArtifact) -> Finding | None:
    if _word_count(artifact.body) < 35:
        return Finding(
            persona="Confused end-user",
            severity=Severity.MEDIUM,
            issue="The description is too short to answer basic buyer questions.",
            evidence="The artifact has fewer than 35 words.",
            fix="Add who it is for, what they submit, what reviewers check, and what output they receive.",
        )
    return None

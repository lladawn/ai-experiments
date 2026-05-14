from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    findings: tuple[str, ...] = ()


class Verifier:
    def verify(self, answer: str, required_terms: tuple[str, ...] = ()) -> VerificationResult:
        missing = tuple(term for term in required_terms if term.lower() not in answer.lower())
        if missing:
            return VerificationResult(False, tuple(f"Missing required term: {term}" for term in missing))
        if not answer.strip():
            return VerificationResult(False, ("Answer is empty.",))
        return VerificationResult(True, ("Verification passed.",))

from __future__ import annotations

from dataclasses import dataclass

from mac_agent_runtime.context import ContextPacket


@dataclass(frozen=True)
class EnforcementResult:
    passed: bool
    violations: tuple[str, ...] = ()


class Enforcer:
    def check_context(self, packet: ContextPacket) -> EnforcementResult:
        violations: list[str] = []
        if not packet.task.strip():
            violations.append("Task must not be empty.")
        if len(set(packet.allowed_tools)) != len(packet.allowed_tools):
            violations.append("Allowed tools must not contain duplicates.")
        return EnforcementResult(not violations, tuple(violations))

    def check_answer(self, answer: str, blocked_terms: tuple[str, ...] = ()) -> EnforcementResult:
        violations = tuple(
            f"Answer contains blocked term: {term}"
            for term in blocked_terms
            if term.lower() in answer.lower()
        )
        return EnforcementResult(not violations, violations)

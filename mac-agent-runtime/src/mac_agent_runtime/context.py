from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class ContextSection:
    name: str
    content: str
    visibility: str = "agent"


@dataclass(frozen=True)
class ContextPacket:
    task: str
    system_rules: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    evidence: tuple[ContextSection, ...] = ()
    scratchpad: tuple[ContextSection, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def render_for_model(self) -> str:
        parts = ["# Task", self.task]

        if self.system_rules:
            parts.extend(["", "# Rules", *[f"- {rule}" for rule in self.system_rules]])

        if self.constraints:
            parts.extend(["", "# Constraints", *[f"- {item}" for item in self.constraints]])

        visible_evidence = [section for section in self.evidence if section.visibility != "hidden"]
        if visible_evidence:
            parts.append("")
            parts.append("# Evidence")
            for section in visible_evidence:
                parts.append(f"## {section.name}")
                parts.append(section.content)

        visible_notes = [section for section in self.scratchpad if section.visibility == "agent"]
        if visible_notes:
            parts.append("")
            parts.append("# Working Notes")
            for section in visible_notes:
                parts.append(f"## {section.name}")
                parts.append(section.content)

        if self.allowed_tools:
            parts.extend(["", "# Allowed Tools", ", ".join(self.allowed_tools)])

        return "\n".join(parts)

    def isolate_for_subagent(
        self,
        subtask: str,
        allowed_tools: tuple[str, ...],
        evidence_names: set[str] | None = None,
    ) -> "ContextPacket":
        selected_evidence = self.evidence
        if evidence_names is not None:
            selected_evidence = tuple(section for section in self.evidence if section.name in evidence_names)

        return ContextPacket(
            task=subtask,
            system_rules=self.system_rules,
            constraints=self.constraints + ("Do not assume parent-only context exists.",),
            evidence=tuple(section for section in selected_evidence if section.visibility != "hidden"),
            scratchpad=(),
            allowed_tools=allowed_tools,
            metadata={**self.metadata, "isolated_from": self.task},
        )

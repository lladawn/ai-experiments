from __future__ import annotations

from dataclasses import dataclass, replace

from mac_agent_runtime.context import ContextPacket, ContextSection
from mac_agent_runtime.enforcement import Enforcer
from mac_agent_runtime.model import Model
from mac_agent_runtime.tools import ToolRegistry
from mac_agent_runtime.verification import VerificationResult, Verifier


@dataclass(frozen=True)
class AgentResult:
    answer: str
    tool_outputs: tuple[ContextSection, ...]
    verification: VerificationResult


class AgentHarness:
    def __init__(
        self,
        model: Model,
        tools: ToolRegistry,
        verifier: Verifier | None = None,
        enforcer: Enforcer | None = None,
    ) -> None:
        self.model = model
        self.tools = tools
        self.verifier = verifier or Verifier()
        self.enforcer = enforcer or Enforcer()

    def run(
        self,
        packet: ContextPacket,
        required_terms: tuple[str, ...] = (),
        blocked_terms: tuple[str, ...] = (),
        approved_writes: tuple[str, ...] = (),
        max_steps: int = 4,
    ) -> AgentResult:
        context_check = self.enforcer.check_context(packet)
        if not context_check.passed:
            raise ValueError("; ".join(context_check.violations))

        tool_outputs: list[ContextSection] = []
        answer = ""
        current_packet = packet

        for step in range(max_steps):
            prompt = self._render_prompt(current_packet)
            response = self.model.complete(prompt)
            answer = response.answer

            if not response.tool_calls:
                break

            step_outputs: list[ContextSection] = []
            for tool_name, args in response.tool_calls:
                output = self.tools.run(tool_name, args, packet.allowed_tools, approved_writes)
                section = ContextSection(name=f"tool:{tool_name}", content=output)
                tool_outputs.append(section)
                step_outputs.append(section)

            current_packet = replace(
                current_packet,
                scratchpad=current_packet.scratchpad
                + (ContextSection(name=f"model step {step + 1}", content=answer),)
                + tuple(step_outputs),
            )

        if tool_outputs:
            answer = f"{answer}\n\nTool evidence:\n" + "\n".join(
                f"- {section.name}: {section.content}" for section in tool_outputs[-8:]
            )

        answer_check = self.enforcer.check_answer(answer, blocked_terms)
        if not answer_check.passed:
            raise ValueError("; ".join(answer_check.violations))

        verification = self.verifier.verify(answer, required_terms)
        return AgentResult(answer=answer, tool_outputs=tuple(tool_outputs), verification=verification)

    def _render_prompt(self, packet: ContextPacket) -> str:
        prompt = packet.render_for_model()
        tool_descriptions = self.tools.descriptions_for(packet.allowed_tools)
        if tool_descriptions:
            prompt += "\n\n# Tool Descriptions\n" + "\n".join(f"- {item}" for item in tool_descriptions)
        return prompt

    def delegate(
        self,
        parent_packet: ContextPacket,
        subtask: str,
        allowed_tools: tuple[str, ...] = (),
        evidence_names: set[str] | None = None,
    ) -> AgentResult:
        subagent_packet = parent_packet.isolate_for_subagent(
            subtask=subtask,
            allowed_tools=allowed_tools,
            evidence_names=evidence_names,
        )
        return self.run(subagent_packet)

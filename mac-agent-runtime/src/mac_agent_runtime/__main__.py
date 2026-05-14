from __future__ import annotations

import argparse

from mac_agent_runtime.context import ContextPacket, ContextSection
from mac_agent_runtime.harness import AgentHarness
from mac_agent_runtime.model import StubModel
from mac_agent_runtime.tools import Tool, ToolRegistry


def build_harness() -> AgentHarness:
    tools = ToolRegistry()
    tools.register(
        Tool(
            name="echo_context",
            description="Echoes a tiny marker proving the tool boundary was used.",
            handler=lambda args: f"echo_context({args.get('note', '')})",
        )
    )
    return AgentHarness(model=StubModel(), tools=tools)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the context engineering harness demo.")
    parser.add_argument("task", nargs="?", default="Explain the harness shape.")
    args = parser.parse_args()

    packet = ContextPacket(
        task=args.task,
        system_rules=("Use only explicitly allowed tools.", "Surface verification status."),
        constraints=("Keep the answer compact.",),
        evidence=(ContextSection("project", "This project explores context engineering."),),
        allowed_tools=("echo_context",),
    )

    result = build_harness().run(packet, required_terms=("context",))
    print(result.answer)
    print(f"\nVerified: {result.verification.passed}")
    for finding in result.verification.findings:
        print(f"- {finding}")


if __name__ == "__main__":
    main()

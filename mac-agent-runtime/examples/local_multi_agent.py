from __future__ import annotations

import argparse

from mac_agent_runtime.context import ContextPacket, ContextSection
from mac_agent_runtime.harness import AgentHarness
from mac_agent_runtime.model import OllamaModel, StubModel
from mac_agent_runtime.multi_agent import AgentSpec, MultiAgentHarness
from mac_agent_runtime.tools import ToolRegistry


def build_model(name: str, use_stub: bool) -> OllamaModel | StubModel:
    if use_stub:
        return StubModel()
    return OllamaModel(model=name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run multiple isolated agents with one local model.")
    parser.add_argument("task", help="Work for the agents to do.")
    parser.add_argument("--model", default="llama3.2", help="Ollama model name.")
    parser.add_argument("--stub", action="store_true", help="Use deterministic stub model instead of Ollama.")
    args = parser.parse_args()

    parent_packet = ContextPacket(
        task=args.task,
        system_rules=(
            "Use only the context provided in your packet.",
            "Be direct and explicit about uncertainty.",
        ),
        constraints=("Keep each response compact.",),
        evidence=(
            ContextSection(
                name="user request",
                content=args.task,
            ),
        ),
        allowed_tools=(),
    )

    harness = AgentHarness(
        model=build_model(args.model, args.stub),
        tools=ToolRegistry(),
    )
    multi_agent = MultiAgentHarness(harness)

    result = multi_agent.run(
        parent_packet=parent_packet,
        workers=(
            AgentSpec(
                name="planner",
                task=f"Break this work into a concise implementation plan: {args.task}",
                evidence_names={"user request"},
            ),
            AgentSpec(
                name="risk-reviewer",
                task=f"Identify risks, missing information, and verification checks for: {args.task}",
                evidence_names={"user request"},
            ),
            AgentSpec(
                name="executor",
                task=f"Propose the concrete first version of the work product for: {args.task}",
                evidence_names={"user request"},
            ),
        ),
        synthesizer_task=(
            "Combine the planner, risk-reviewer, and executor outputs into one practical answer. "
            "Include a short plan, key risks, and the recommended next action."
        ),
    )

    for name, worker_result in result.worker_results.items():
        print(f"\n## {name}\n{worker_result.answer}")

    print(f"\n## final\n{result.final_result.answer}")


if __name__ == "__main__":
    main()

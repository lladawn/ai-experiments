from __future__ import annotations

import argparse
import json
from pathlib import Path

from mac_agent_runtime.approval import ApprovalQueue
from mac_agent_runtime.context import ContextPacket, ContextSection
from mac_agent_runtime.harness import AgentHarness
from mac_agent_runtime.laptop_tools import register_laptop_tools
from mac_agent_runtime.model import JsonToolOllamaModel, OllamaModel
from mac_agent_runtime.multi_agent import AgentSpec, MultiAgentHarness
from mac_agent_runtime.overlay_state import OverlayState
from mac_agent_runtime.tools import ToolRegistry


DEFAULT_TOOLS = ("open_app", "list_dir", "read_text_file", "find_files", "propose_laptop_action")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local laptop operator harness.")
    parser.add_argument("task", help="Task to give the local model and agents.")
    parser.add_argument("--model", default="gemma4", help="Ollama model name to use as the shared brain.")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument(
        "--approval-log",
        default="~/.mac-agent-runtime/pending_actions.jsonl",
        help="JSONL log for proposed laptop mutations.",
    )
    args = parser.parse_args()

    report = run_operator_task(
        task=args.task,
        model_name=args.model,
        max_workers=args.max_workers,
        approval_log=Path(args.approval_log).expanduser(),
    )
    print(report)


def run_operator_task(
    task: str,
    model_name: str = "gemma4",
    max_workers: int = 4,
    approval_log: Path | None = None,
    overlay_state: OverlayState | None = None,
    run_id: str | None = None,
) -> str:
    approval_queue = ApprovalQueue(approval_log or Path("~/.mac-agent-runtime/pending_actions.jsonl").expanduser())
    tools = ToolRegistry()
    register_laptop_tools(tools, approval_queue)

    planner_model = OllamaModel(model=model_name)
    tool_model = JsonToolOllamaModel(model=model_name)
    harness = AgentHarness(model=tool_model, tools=tools)

    parent_packet = ContextPacket(
        task=task,
        system_rules=(
            "You are a local laptop operator controlled by the user.",
            "You may directly open or focus apps with open_app.",
            "Read-only tools may inspect files and app data needed for the task.",
            "Never create, update, delete, move, send, click, type, submit, or edit app data directly.",
            "For every mutation or non-open app-control step, use propose_laptop_action with a concrete command and risk.",
            "Do not request or expose secrets, private keys, tokens, passwords, or keychain data.",
            "When uncertain, inspect narrowly and explain the gap.",
        ),
        constraints=(
            "Prefer narrow searches over broad scans.",
            "Keep a concise trace of evidence.",
            "Final output must include proposed actions that require approval.",
        ),
        evidence=(ContextSection(name="user task", content=task),),
        allowed_tools=DEFAULT_TOOLS,
        metadata={"model": model_name},
    )

    if overlay_state and run_id:
        overlay_state.set_run_status(run_id, "planning")

    workers = plan_workers(planner_model, parent_packet, max_workers)
    for worker in workers:
        _emit_agent(overlay_state, run_id, worker.name, worker.task, "queued")

    result = MultiAgentHarness(
        harness,
        max_workers=max_workers,
        on_agent_event=lambda name, agent_task, status, summary="": _emit_agent(
            overlay_state,
            run_id,
            name,
            agent_task,
            status,
            summary,
        ),
    ).run(
        parent_packet=parent_packet,
        workers=workers,
        synthesizer_task=(
            "Synthesize the worker findings into a clear operator report. "
            "List what was read, what was found, what remains uncertain, and every proposed action awaiting approval."
        ),
    )

    lines: list[str] = ["# Worker Results"]
    for name, worker_result in result.worker_results.items():
        lines.append(f"\n## {name}\n{worker_result.answer}")

    lines.append(f"\n# Final\n{result.final_result.answer}")

    pending = approval_queue.list_pending()
    if pending:
        lines.append(f"\n# Pending Approval Actions ({len(pending)})")
        for action in pending[-10:]:
            lines.append(f"- {action.id}: {action.summary} | risk: {action.risk}")
            lines.append(f"  command: {action.command}")

    report = "\n".join(lines)
    if overlay_state and run_id:
        overlay_state.set_final(run_id, result.final_result.answer)
    return report


def _emit_agent(
    overlay_state: OverlayState | None,
    run_id: str | None,
    name: str,
    task: str,
    status: str,
    summary: str = "",
) -> None:
    if overlay_state and run_id:
        overlay_state.set_agent(run_id, name, task, status, summary)


def plan_workers(
    model: OllamaModel,
    parent_packet: ContextPacket,
    max_workers: int,
) -> tuple[AgentSpec, ...]:
    prompt = (
        "Decide how to split this laptop task into isolated agents. "
        "Return JSON only with shape "
        '{"agents": [{"name": "short-name", "task": "specific task"}]}. '
        f"Use 1 to {max_workers} agents. Task: {parent_packet.task}"
    )
    response = model.complete(prompt)
    parsed = _parse_json(response.answer)
    agents = parsed.get("agents", []) if parsed else []

    specs: list[AgentSpec] = []
    for index, item in enumerate(agents[:max_workers]):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", f"agent-{index + 1}")).strip() or f"agent-{index + 1}"
        task = str(item.get("task", "")).strip()
        if task:
            specs.append(
                AgentSpec(
                    name=name,
                    task=task,
                    allowed_tools=DEFAULT_TOOLS,
                    evidence_names={"user task"},
                )
            )

    if specs:
        return tuple(specs)

    return (
        AgentSpec(
            name="operator",
            task=parent_packet.task,
            allowed_tools=DEFAULT_TOOLS,
            evidence_names={"user task"},
        ),
    )


def _parse_json(text: str) -> dict[str, object] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


if __name__ == "__main__":
    main()

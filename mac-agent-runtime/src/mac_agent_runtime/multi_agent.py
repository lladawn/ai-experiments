from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from mac_agent_runtime.context import ContextPacket, ContextSection
from mac_agent_runtime.harness import AgentHarness, AgentResult


@dataclass(frozen=True)
class AgentSpec:
    name: str
    task: str
    allowed_tools: tuple[str, ...] = ()
    evidence_names: set[str] | None = None
    required_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class MultiAgentResult:
    worker_results: dict[str, AgentResult]
    final_result: AgentResult


class MultiAgentHarness:
    def __init__(
        self,
        harness: AgentHarness,
        max_workers: int = 4,
        on_agent_event: Callable[[str, str, str, str], None] | None = None,
    ) -> None:
        self.harness = harness
        self.max_workers = max_workers
        self.on_agent_event = on_agent_event

    def run(
        self,
        parent_packet: ContextPacket,
        workers: tuple[AgentSpec, ...],
        synthesizer_task: str,
        synthesizer_required_terms: tuple[str, ...] = (),
    ) -> MultiAgentResult:
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(workers) or 1)) as executor:
            futures = {
                executor.submit(
                    self._run_worker,
                    parent_packet,
                    worker,
                ): worker.name
                for worker in workers
            }
            worker_results = {name: future.result() for future, name in futures.items()}

        synthesis_evidence = tuple(
            ContextSection(name=f"worker:{name}", content=result.answer)
            for name, result in worker_results.items()
        )
        self._emit("synthesizer", synthesizer_task, "running")
        synthesis_packet = ContextPacket(
            task=synthesizer_task,
            system_rules=parent_packet.system_rules,
            constraints=parent_packet.constraints
            + ("Synthesize only from worker evidence.", "Call out disagreements or gaps."),
            evidence=synthesis_evidence,
            allowed_tools=(),
            metadata={**parent_packet.metadata, "phase": "synthesis"},
        )
        final_result = self.harness.run(
            synthesis_packet,
            required_terms=synthesizer_required_terms,
        )
        self._emit("synthesizer", synthesizer_task, "done", final_result.answer)
        return MultiAgentResult(worker_results=worker_results, final_result=final_result)

    def _run_worker(self, parent_packet: ContextPacket, worker: AgentSpec) -> AgentResult:
        self._emit(worker.name, worker.task, "running")
        subagent_packet = parent_packet.isolate_for_subagent(
            subtask=worker.task,
            allowed_tools=worker.allowed_tools,
            evidence_names=worker.evidence_names,
        )
        try:
            result = self.harness.run(subagent_packet, required_terms=worker.required_terms)
        except Exception as error:
            self._emit(worker.name, worker.task, "error", str(error))
            raise
        self._emit(worker.name, worker.task, "done", result.answer)
        return result

    def _emit(self, name: str, task: str, status: str, summary: str = "") -> None:
        if self.on_agent_event:
            self.on_agent_event(name, task, status, summary)

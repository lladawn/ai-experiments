from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Lock


@dataclass
class AgentView:
    name: str
    task: str
    status: str = "queued"
    summary: str = ""
    updated_at: float = field(default_factory=time.time)


@dataclass
class RunView:
    id: str
    task: str
    status: str
    agents: dict[str, AgentView] = field(default_factory=dict)
    final: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class OverlayState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._runs: dict[str, RunView] = {}
        self._load()

    def start_run(self, task: str) -> str:
        run_id = str(uuid.uuid4())[:8]
        with self._lock:
            self._runs[run_id] = RunView(id=run_id, task=task, status="planning")
            self._save()
        return run_id

    def set_run_status(self, run_id: str, status: str, error: str = "") -> None:
        with self._lock:
            run = self._runs[run_id]
            run.status = status
            run.error = error
            run.updated_at = time.time()
            self._save()

    def set_final(self, run_id: str, final: str) -> None:
        with self._lock:
            run = self._runs[run_id]
            run.final = final[:4000]
            run.status = "done"
            run.updated_at = time.time()
            self._save()

    def set_agent(self, run_id: str, name: str, task: str, status: str, summary: str = "") -> None:
        with self._lock:
            run = self._runs[run_id]
            run.agents[name] = AgentView(
                name=name,
                task=task,
                status=status,
                summary=summary[:1200],
            )
            run.updated_at = time.time()
            self._save()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return self._snapshot_unlocked()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        for item in data.get("runs", []):
            agents = {
                agent["name"]: AgentView(**agent)
                for agent in item.get("agents", [])
                if isinstance(agent, dict) and "name" in agent
            }
            run = RunView(
                id=item["id"],
                task=item["task"],
                status=item["status"],
                agents=agents,
                final=item.get("final", ""),
                error=item.get("error", ""),
                created_at=item.get("created_at", time.time()),
                updated_at=item.get("updated_at", time.time()),
            )
            self._runs[run.id] = run

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._snapshot_unlocked(), indent=2), encoding="utf-8")

    def _snapshot_unlocked(self) -> dict[str, object]:
        runs = sorted(self._runs.values(), key=lambda item: item.updated_at, reverse=True)[:8]
        return {
            "updated_at": time.time(),
            "runs": [
                {
                    **asdict(run),
                    "agents": [asdict(agent) for agent in run.agents.values()],
                }
                for run in runs
            ],
        }

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProposedAction:
    id: str
    kind: str
    summary: str
    command: str
    risk: str
    created_at: float


class ApprovalQueue:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def propose(self, kind: str, summary: str, command: str, risk: str) -> ProposedAction:
        action = ProposedAction(
            id=str(uuid.uuid4()),
            kind=kind,
            summary=summary,
            command=command,
            risk=risk,
            created_at=time.time(),
        )
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(asdict(action), sort_keys=True) + "\n")
        return action

    def list_pending(self) -> tuple[ProposedAction, ...]:
        if not self.path.exists():
            return ()
        actions: list[ProposedAction] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                actions.append(ProposedAction(**json.loads(line)))
        return tuple(actions)

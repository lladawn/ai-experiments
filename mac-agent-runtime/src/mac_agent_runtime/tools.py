from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


ToolHandler = Callable[[dict[str, str]], str]


class ToolMode(str, Enum):
    READ = "read"
    CONTROL = "control"
    PROPOSE = "propose"
    WRITE = "write"


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    handler: ToolHandler
    mode: ToolMode = ToolMode.READ


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def run(
        self,
        name: str,
        args: dict[str, str],
        allowed_tools: tuple[str, ...],
        approved_writes: tuple[str, ...] = (),
    ) -> str:
        if name not in allowed_tools:
            raise PermissionError(f"Tool is not allowed in this context: {name}")
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        tool = self._tools[name]
        if tool.mode == ToolMode.WRITE and name not in approved_writes:
            raise PermissionError(f"Write tool requires explicit approval: {name}")
        return tool.handler(args)

    def descriptions_for(self, allowed_tools: tuple[str, ...]) -> list[str]:
        return [
            f"{name} [{self._tools[name].mode.value}]: {self._tools[name].description}"
            for name in allowed_tools
            if name in self._tools
        ]

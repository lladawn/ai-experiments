from __future__ import annotations

import os
import subprocess
from pathlib import Path

from mac_agent_runtime.approval import ApprovalQueue
from mac_agent_runtime.tools import Tool, ToolMode, ToolRegistry


DEFAULT_DENY_PARTS = {
    ".ssh",
    ".gnupg",
    "Keychains",
    "passwords",
    "secrets",
    ".aws",
    ".config/gcloud",
}


def is_denied(path: Path, deny_parts: set[str] = DEFAULT_DENY_PARTS) -> bool:
    path_text = str(path.expanduser())
    return any(part in path_text for part in deny_parts)


def register_laptop_tools(registry: ToolRegistry, approval_queue: ApprovalQueue) -> None:
    registry.register(
        Tool(
            name="open_app",
            description="Open or focus a macOS application. Args: app_name. Control-only, no data mutation.",
            mode=ToolMode.CONTROL,
            handler=lambda args: open_app(args.get("app_name", "")),
        )
    )
    registry.register(
        Tool(
            name="list_dir",
            description="List files in a directory. Args: path. Read-only.",
            mode=ToolMode.READ,
            handler=lambda args: list_dir(args.get("path", "~")),
        )
    )
    registry.register(
        Tool(
            name="read_text_file",
            description="Read a UTF-8-ish text file with size limits. Args: path, max_chars. Read-only.",
            mode=ToolMode.READ,
            handler=lambda args: read_text_file(args.get("path", ""), int(args.get("max_chars", "12000"))),
        )
    )
    registry.register(
        Tool(
            name="find_files",
            description="Find files by case-insensitive filename fragment. Args: root, name_contains, limit. Read-only.",
            mode=ToolMode.READ,
            handler=lambda args: find_files(
                root=args.get("root", "~"),
                name_contains=args.get("name_contains", ""),
                limit=int(args.get("limit", "80")),
            ),
        )
    )
    registry.register(
        Tool(
            name="propose_laptop_action",
            description=(
                "Record a proposed create/update/delete/control action for human approval. "
                "Args: kind, summary, command, risk."
            ),
            mode=ToolMode.PROPOSE,
            handler=lambda args: propose_laptop_action(args, approval_queue),
        )
    )


def list_dir(path: str) -> str:
    resolved = Path(path).expanduser()
    if is_denied(resolved):
        return f"Denied by local safety policy: {resolved}"
    if not resolved.exists():
        return f"Path does not exist: {resolved}"
    if not resolved.is_dir():
        return f"Path is not a directory: {resolved}"

    rows = []
    for entry in sorted(resolved.iterdir(), key=lambda item: item.name.lower())[:250]:
        kind = "dir" if entry.is_dir() else "file"
        rows.append(f"{kind}\t{entry.name}")
    return "\n".join(rows)


def read_text_file(path: str, max_chars: int = 12000) -> str:
    resolved = Path(path).expanduser()
    if is_denied(resolved):
        return f"Denied by local safety policy: {resolved}"
    if not resolved.exists() or not resolved.is_file():
        return f"File does not exist: {resolved}"
    if resolved.stat().st_size > max(max_chars * 4, 1_000_000):
        return f"File too large for direct read: {resolved}"

    return resolved.read_text(encoding="utf-8", errors="replace")[:max_chars]


def find_files(root: str, name_contains: str, limit: int = 80) -> str:
    resolved = Path(root).expanduser()
    if is_denied(resolved):
        return f"Denied by local safety policy: {resolved}"
    if not resolved.exists() or not resolved.is_dir():
        return f"Search root is not a directory: {resolved}"

    needle = name_contains.lower()
    matches: list[str] = []
    for current_root, dirs, files in os.walk(resolved):
        current_path = Path(current_root)
        dirs[:] = [item for item in dirs if not is_denied(current_path / item)]
        for filename in files:
            candidate = current_path / filename
            if is_denied(candidate):
                continue
            if needle in filename.lower():
                matches.append(str(candidate))
                if len(matches) >= limit:
                    return "\n".join(matches)
    return "\n".join(matches) if matches else "No matches."


def open_app(app_name: str) -> str:
    cleaned = app_name.strip()
    if not cleaned:
        return "Missing app_name."
    if "/" in cleaned or "\0" in cleaned:
        return "App name must be a plain application name, not a path."

    completed = subprocess.run(
        ["open", "-a", cleaned],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        return f"Could not open app {cleaned}: {details}"
    return f"Opened or focused app: {cleaned}"


def propose_laptop_action(args: dict[str, str], approval_queue: ApprovalQueue) -> str:
    action = approval_queue.propose(
        kind=args.get("kind", "unknown"),
        summary=args.get("summary", ""),
        command=args.get("command", ""),
        risk=args.get("risk", "unspecified"),
    )
    return f"Proposed action {action.id}: {action.summary}"

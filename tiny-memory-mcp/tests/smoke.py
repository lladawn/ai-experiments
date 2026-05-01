#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server.py"


def request(proc: subprocess.Popen[str], method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    request.counter += 1
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request.counter, "method": method}
    if params is not None:
        payload["params"] = params

    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise AssertionError("server exited without responding")
    response = json.loads(line)
    if "error" in response:
        raise AssertionError(response["error"])
    return response["result"]


request.counter = 0


def notify(proc: subprocess.Popen[str], method: str) -> None:
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
    proc.stdin.flush()


def tool(proc: subprocess.Popen[str], name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = request(proc, "tools/call", {"name": name, "arguments": arguments})
    text = result["content"][0]["text"]
    return json.loads(text)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env["TINY_MEMORY_DB"] = str(Path(tmp) / "memory.sqlite3")
        proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        assert proc.stdin is not None
        assert proc.stdout is not None

        try:
            init = request(
                proc,
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "smoke-test", "version": "0.1.0"},
                },
            )
            assert init["serverInfo"]["name"] == "tiny-memory"
            notify(proc, "notifications/initialized")

            tools = request(proc, "tools/list")
            tool_names = {item["name"] for item in tools["tools"]}
            assert {"remember", "recall", "list_memories", "forget"} <= tool_names

            stored = tool(
                proc,
                "remember",
                {"key": "favorite-protocol", "value": "MCP", "tags": ["ai", "protocol"]},
            )
            assert stored["stored"]["key"] == "favorite-protocol"

            recalled = tool(proc, "recall", {"query": "protocol"})
            assert recalled["memories"][0]["value"] == "MCP"

            listed = tool(proc, "list_memories", {"limit": 5})
            assert len(listed["memories"]) == 1

            forgotten = tool(proc, "forget", {"key": "favorite-protocol"})
            assert forgotten["deleted"] is True

            recalled_again = tool(proc, "recall", {"query": "protocol"})
            assert recalled_again["memories"] == []
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    print("smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

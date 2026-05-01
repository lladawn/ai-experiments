#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HTTP_SERVER = ROOT / "http_server.py"
URL = "http://127.0.0.1:8765/mcp"


def post(payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Method": payload["method"],
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read())


def wait_until_ready() -> None:
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            post({"jsonrpc": "2.0", "id": 0, "method": "ping"})
            return
        except (ConnectionError, urllib.error.URLError):
            time.sleep(0.1)
    raise AssertionError("HTTP MCP server did not start")


def call_tool(counter: int, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = post(
        {
            "jsonrpc": "2.0",
            "id": counter,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    if "error" in response:
        raise AssertionError(response["error"])
    return json.loads(response["result"]["content"][0]["text"])


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env["HOST"] = "127.0.0.1"
        env["PORT"] = "8765"
        env["TINY_MEMORY_DB"] = str(Path(tmp) / "memory.sqlite3")
        proc = subprocess.Popen(
            [sys.executable, str(HTTP_SERVER)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        try:
            wait_until_ready()
            init = post(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "http-smoke", "version": "0.1.0"},
                    },
                }
            )
            assert init["result"]["serverInfo"]["name"] == "tiny-memory"

            tools = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            tool_names = {tool["name"] for tool in tools["result"]["tools"]}
            assert {"search", "fetch", "remember", "recall", "list_memories", "forget"} <= tool_names

            call_tool(3, "remember", {"key": "remote-test", "value": "HTTP MCP works", "tags": ["remote"]})
            search = call_tool(4, "search", {"query": "remote"})
            assert search["results"][0]["id"] == "remote-test"
            fetched = call_tool(5, "fetch", {"id": "remote-test"})
            assert fetched["value"] == "HTTP MCP works"
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    print("http smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

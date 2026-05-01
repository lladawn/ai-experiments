#!/usr/bin/env python3
"""Streamable HTTP wrapper for Tiny Memory MCP."""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from server import DEFAULT_DB, MemoryStore, TinyMemoryMcp, error_response

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
MCP_PATH = os.environ.get("MCP_PATH", "/mcp")
TOKEN = os.environ.get("MCP_BEARER_TOKEN", "")
DEFAULT_ALLOWED_ORIGINS = {
    "https://chatgpt.com",
    "https://chat.openai.com",
    "http://localhost",
    "http://127.0.0.1",
}


def allowed_origins() -> set[str]:
    raw = os.environ.get("MCP_ALLOWED_ORIGINS", "")
    if not raw.strip():
        return DEFAULT_ALLOWED_ORIGINS
    return {origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()}


class McpHttpHandler(BaseHTTPRequestHandler):
    server_version = "TinyMemoryMCP/0.1"

    @property
    def mcp(self) -> TinyMemoryMcp:
        return self.server.mcp  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        if self.path != MCP_PATH:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not self._authorized() or not self._origin_allowed():
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(b": tiny-memory-mcp ready\n\n")

    def do_POST(self) -> None:
        if self.path != MCP_PATH:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not self._authorized() or not self._origin_allowed():
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            self._write_json(error_response(None, -32700, f"Parse error: {exc}"), HTTPStatus.BAD_REQUEST)
            return

        if isinstance(payload, list):
            responses = [self.mcp.handle(item) for item in payload if isinstance(item, dict)]
            responses = [response for response in responses if response is not None]
            if responses:
                self._write_json(responses)
            else:
                self.send_response(HTTPStatus.ACCEPTED)
                self.end_headers()
            return

        if not isinstance(payload, dict):
            self._write_json(error_response(None, -32600, "Invalid request"), HTTPStatus.BAD_REQUEST)
            return

        response = self.mcp.handle(payload)
        if response is None:
            self.send_response(HTTPStatus.ACCEPTED)
            self.end_headers()
            return
        self._write_json(response)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _authorized(self) -> bool:
        if not TOKEN:
            return True
        expected = f"Bearer {TOKEN}"
        if self.headers.get("Authorization") == expected:
            return True
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", "Bearer")
        self.end_headers()
        return False

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        normalized = origin.rstrip("/")
        if normalized in allowed_origins():
            return True
        self._write_json(error_response(None, -32000, "Origin not allowed"), HTTPStatus.FORBIDDEN)
        return False

    def _write_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> int:
    db_path = Path(os.environ.get("TINY_MEMORY_DB", DEFAULT_DB))
    httpd = ThreadingHTTPServer((HOST, PORT), McpHttpHandler)
    httpd.mcp = TinyMemoryMcp(MemoryStore(db_path))  # type: ignore[attr-defined]
    print(f"Tiny Memory MCP HTTP server listening on http://{HOST}:{PORT}{MCP_PATH}", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

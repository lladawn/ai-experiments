#!/usr/bin/env python3
"""Tiny Memory MCP server.

This is a small dependency-free MCP server that implements enough of the MCP
stdio protocol for local hosts to discover and call memory tools.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "2025-06-18"
DEFAULT_DB = Path(__file__).with_name("memory.sqlite3")


@dataclass
class Memory:
    key: str
    value: str
    tags: list[str]
    created_at: str
    updated_at: str


class MemoryStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.lock:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self.conn.commit()

    def remember(self, key: str, value: str, tags: list[str] | None = None) -> Memory:
        clean_key = key.strip()
        clean_value = value.strip()
        clean_tags = sorted({tag.strip() for tag in tags or [] if tag.strip()})
        if not clean_key:
            raise ValueError("key must not be empty")
        if not clean_value:
            raise ValueError("value must not be empty")

        with self.lock:
            self.conn.execute(
                """
                INSERT INTO memories (key, value, tags)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    tags = excluded.tags,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (clean_key, clean_value, json.dumps(clean_tags)),
            )
            self.conn.commit()
        return self.get(clean_key)

    def get(self, key: str) -> Memory:
        with self.lock:
            row = self.conn.execute(
                "SELECT key, value, tags, created_at, updated_at FROM memories WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            raise KeyError(key)
        return row_to_memory(row)

    def recall(self, query: str, limit: int = 10) -> list[Memory]:
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("query must not be empty")
        bounded_limit = max(1, min(limit, 50))
        pattern = f"%{clean_query}%"
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT key, value, tags, created_at, updated_at
                FROM memories
                WHERE key LIKE ? OR value LIKE ? OR tags LIKE ?
                ORDER BY updated_at DESC, key ASC
                LIMIT ?
                """,
                (pattern, pattern, pattern, bounded_limit),
            ).fetchall()
        return [row_to_memory(row) for row in rows]

    def list_memories(self, limit: int = 20) -> list[Memory]:
        bounded_limit = max(1, min(limit, 100))
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT key, value, tags, created_at, updated_at
                FROM memories
                ORDER BY updated_at DESC, key ASC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        return [row_to_memory(row) for row in rows]

    def forget(self, key: str) -> bool:
        with self.lock:
            cursor = self.conn.execute("DELETE FROM memories WHERE key = ?", (key.strip(),))
            self.conn.commit()
        return cursor.rowcount > 0


def row_to_memory(row: sqlite3.Row) -> Memory:
    return Memory(
        key=row["key"],
        value=row["value"],
        tags=json.loads(row["tags"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def memory_to_dict(memory: Memory) -> dict[str, Any]:
    return {
        "key": memory.key,
        "value": memory.value,
        "tags": memory.tags,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
    }


def content(payload: Any) -> list[dict[str, str]]:
    return [{"type": "text", "text": json.dumps(payload, indent=2)}]


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "search",
            "description": "Search memories for ChatGPT connector compatibility.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search text."}
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "fetch",
            "description": "Fetch one memory by id for ChatGPT connector compatibility.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Memory key returned by search."}
                },
                "required": ["id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "remember",
            "description": "Store or update a durable memory by key.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Stable memory key."},
                    "value": {"type": "string", "description": "Memory text to store."},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for grouping and search.",
                    },
                },
                "required": ["key", "value"],
                "additionalProperties": False,
            },
        },
        {
            "name": "recall",
            "description": "Search memories by key, value, or tag.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search text."},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 10,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "list_memories",
            "description": "List recently updated memories.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 20,
                    }
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "forget",
            "description": "Delete a memory by key.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Memory key to delete."}
                },
                "required": ["key"],
                "additionalProperties": False,
            },
        },
    ]


class TinyMemoryMcp:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if "method" not in message:
            return None

        method = message["method"]
        request_id = message.get("id")
        is_notification = "id" not in message
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "tiny-memory", "version": "0.1.0"},
                }
            elif method == "notifications/initialized":
                return None
            elif method == "tools/list":
                result = {"tools": tool_definitions()}
            elif method == "tools/call":
                result = self.call_tool(message.get("params", {}))
            elif method == "ping":
                result = {}
            else:
                if is_notification:
                    return None
                return error_response(request_id, -32601, f"Method not found: {method}")
            if is_notification:
                return None
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:
            if is_notification:
                return None
            return error_response(request_id, -32000, str(exc))

    def call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        args = params.get("arguments") or {}

        if name == "search":
            memories = self.store.recall(str(args.get("query", "")), 10)
            results = [
                {
                    "id": memory.key,
                    "title": memory.key,
                    "url": f"memory://{memory.key}",
                    "text": memory.value,
                }
                for memory in memories
            ]
            return {"content": content({"results": results})}

        if name == "fetch":
            memory = self.store.get(str(args.get("id", "")))
            return {"content": content(memory_to_dict(memory))}

        if name == "remember":
            memory = self.store.remember(
                str(args.get("key", "")),
                str(args.get("value", "")),
                args.get("tags") or [],
            )
            return {"content": content({"stored": memory_to_dict(memory)})}

        if name == "recall":
            memories = self.store.recall(
                str(args.get("query", "")),
                int(args.get("limit", 10)),
            )
            return {"content": content({"memories": [memory_to_dict(m) for m in memories]})}

        if name == "list_memories":
            memories = self.store.list_memories(int(args.get("limit", 20)))
            return {"content": content({"memories": [memory_to_dict(m) for m in memories]})}

        if name == "forget":
            deleted = self.store.forget(str(args.get("key", "")))
            return {"content": content({"deleted": deleted})}

        raise ValueError(f"Unknown tool: {name}")


def error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def main() -> int:
    db_path = Path(os.environ.get("TINY_MEMORY_DB", DEFAULT_DB))
    server = TinyMemoryMcp(MemoryStore(db_path))

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            response = server.handle(message)
        except json.JSONDecodeError as exc:
            response = error_response(None, -32700, f"Parse error: {exc}")

        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

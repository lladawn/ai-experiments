# Tiny Memory MCP Architecture

This document explains how Tiny Memory MCP works, why it is structured this way,
and what concepts are useful to learn from the project.

## Project Goal

Tiny Memory MCP is a small Model Context Protocol server that gives an AI client
durable local memory.

It can:

- Store a memory with a stable key.
- Search memories by key, value, or tag.
- List recent memories.
- Delete a memory.
- Expose ChatGPT-compatible `search` and `fetch` tools.
- Run locally over stdio.
- Run remotely over HTTP, Docker, and ngrok.

The project intentionally uses only Python standard library modules. That keeps
the code easy to inspect and makes the protocol mechanics visible.

## File Layout

```text
tiny-memory-mcp/
  server.py             Core MCP server and SQLite memory store
  http_server.py        Streamable HTTP wrapper around the core MCP server
  Dockerfile            Container image for remote HTTP usage
  docker-compose.yml    Local container runtime configuration
  tests/
    smoke.py            Stdio MCP smoke test
    http_smoke.py       HTTP MCP smoke test
  README.md             Quick start and setup commands
  docs/
    ARCHITECTURE.md     This document
```

## Technical Architecture

At a high level, the project has four layers:

```text
MCP client
  |
  | JSON-RPC over stdio or HTTP
  v
Transport layer
  |
  v
TinyMemoryMcp request router
  |
  v
MemoryStore
  |
  v
SQLite database
```

The core design choice is to keep the MCP logic independent from the transport.
`server.py` knows how to handle MCP JSON-RPC messages. `http_server.py` only
turns HTTP requests into those same messages.

## MCP Concepts Used

### Host

The host is the application the user talks to, such as ChatGPT Desktop, Claude
Desktop, Cursor, or another MCP-compatible app.

The host manages the model, chat UI, permissions, and connection setup.

### Client

The MCP client usually lives inside the host. It connects to one MCP server,
asks what capabilities are available, and calls tools when the model decides
they are useful.

In this project, the tests act as tiny MCP clients.

### Server

The MCP server is the thing we built. It exposes capabilities to the host.

Tiny Memory MCP exposes only tools:

- `search`
- `fetch`
- `remember`
- `recall`
- `list_memories`
- `forget`

It does not yet expose MCP resources or prompts.

### Tools

Tools are functions the model can call through the MCP host.

Each tool has:

- a `name`
- a human-readable `description`
- an `inputSchema`
- a result returned as MCP content

In `server.py`, tool definitions live in `tool_definitions()`, and execution
lives in `TinyMemoryMcp.call_tool()`.

### JSON-RPC

MCP messages are JSON-RPC-style messages. A normal request has:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list"
}
```

The server responds with:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {}
}
```

Notifications are messages without an `id`. The server should not respond to
notifications. `server.py` handles this with the `is_notification` check.

## Code Architecture

### `Memory`

`Memory` is a dataclass representing one stored memory:

- `key`
- `value`
- `tags`
- `created_at`
- `updated_at`

It gives the rest of the code a predictable Python object instead of passing
SQLite rows around everywhere.

### `MemoryStore`

`MemoryStore` owns the SQLite database and implements the persistence logic.

Responsibilities:

- create the `memories` table
- validate keys and values
- insert or update records
- search records
- list records
- delete records

SQLite is a good fit because it is free, local, durable, and part of the Python
standard library.

The database schema is intentionally simple:

```sql
CREATE TABLE IF NOT EXISTS memories (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  tags TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
```

Tags are stored as JSON text. This keeps the database small and avoids extra
join tables for a beginner project.

### Thread Safety

The HTTP server uses `ThreadingHTTPServer`, which can handle requests on
different threads.

SQLite connections are thread-bound by default, so the project uses:

```python
sqlite3.connect(self.db_path, check_same_thread=False)
```

It also wraps database operations in a `threading.Lock`.

That combination keeps the shared SQLite connection simple and safe enough for
this small server.

### `TinyMemoryMcp`

`TinyMemoryMcp` is the protocol router.

It handles methods like:

- `initialize`
- `notifications/initialized`
- `tools/list`
- `tools/call`
- `ping`

Its job is to translate MCP requests into calls on `MemoryStore`.

For example:

```text
tools/call remember
  -> TinyMemoryMcp.call_tool()
  -> MemoryStore.remember()
  -> SQLite INSERT ... ON CONFLICT DO UPDATE
```

### `content()`

MCP tool calls return content blocks. This project returns JSON encoded as a
text content block:

```json
[
  {
    "type": "text",
    "text": "{ ... }"
  }
]
```

This is simple and readable. A future version could return richer structured
content if the target host supports it.

## Transport Architecture

The project supports two transport styles.

### Stdio

`server.py` reads newline-delimited JSON messages from `stdin` and writes JSON
responses to `stdout`.

This is useful when an MCP host launches the server as a local process.

```text
Host
  -> starts `python3 server.py`
  -> sends JSON-RPC lines to stdin
  <- reads JSON-RPC lines from stdout
```

### HTTP

`http_server.py` wraps the same MCP logic in an HTTP endpoint.

Default endpoint:

```text
http://127.0.0.1:8000/mcp
```

With Docker and ngrok:

```text
ChatGPT
  -> https://your-ngrok-domain.ngrok-free.app/mcp
  -> ngrok tunnel
  -> Docker container on localhost:8000
  -> http_server.py
  -> TinyMemoryMcp
  -> SQLite
```

The HTTP wrapper handles:

- `GET /mcp` with a basic event-stream response
- `POST /mcp` with JSON-RPC request handling
- optional bearer token auth via `MCP_BEARER_TOKEN`
- basic origin checking via `MCP_ALLOWED_ORIGINS`

## Docker Architecture

The Docker image runs the HTTP server:

```text
python:3.14-slim
  -> /app/server.py
  -> /app/http_server.py
  -> /data/memory.sqlite3
```

The Compose file maps:

- host port `8000` to container port `8000`
- Docker volume `tiny-memory-data` to `/data`

That means the database survives container restarts.

## Request Flows

### Initialization

```text
Client -> initialize
Server -> protocolVersion, capabilities, serverInfo
Client -> notifications/initialized
```

The server declares:

```json
{
  "capabilities": {
    "tools": {}
  }
}
```

This tells the client that the server supports tool discovery and tool calls.

### Tool Discovery

```text
Client -> tools/list
Server -> list of tool definitions
```

The model can use this list to understand which actions are available.

### Remember

```text
Client -> tools/call remember
Server -> validate input
Server -> upsert memory in SQLite
Server -> return stored memory
```

The SQL uses `ON CONFLICT(key) DO UPDATE`, so calling `remember` with an existing
key updates the memory instead of creating a duplicate.

### Recall

```text
Client -> tools/call recall
Server -> SQL LIKE search across key, value, tags
Server -> return matching memories
```

This is simple substring search, not embeddings or semantic search.

### Search And Fetch

`search` and `fetch` exist for ChatGPT connector-style compatibility.

`search` returns a list of results:

```json
{
  "results": [
    {
      "id": "remote-test",
      "title": "remote-test",
      "url": "memory://remote-test",
      "text": "HTTP MCP works"
    }
  ]
}
```

`fetch` retrieves one memory by id.

## Configuration

Useful environment variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `TINY_MEMORY_DB` | SQLite database path | `memory.sqlite3` next to `server.py` |
| `HOST` | HTTP bind host | `127.0.0.1` |
| `PORT` | HTTP port | `8000` |
| `MCP_PATH` | HTTP MCP endpoint path | `/mcp` |
| `MCP_BEARER_TOKEN` | Optional bearer auth token | empty |
| `MCP_ALLOWED_ORIGINS` | Comma-separated allowed origins | ChatGPT and localhost origins |

## Tests

The tests are smoke tests rather than a full unit test suite.

`tests/smoke.py`:

- starts `server.py` as a subprocess
- sends stdio JSON-RPC messages
- verifies tool discovery and memory operations

`tests/http_smoke.py`:

- starts `http_server.py` as a subprocess
- sends HTTP JSON-RPC messages
- verifies initialization, tool discovery, `remember`, `search`, and `fetch`

Run both:

```bash
python3 tests/smoke.py
python3 tests/http_smoke.py
```

## Why This Design

### Why dependency-free Python?

It makes the project easy to run, inspect, and publish. There is no package
manager setup and no framework magic hiding the protocol.

### Why SQLite?

SQLite is durable, local, portable, and free. For a tiny memory server, it is a
better starting point than a hosted database.

### Why support both stdio and HTTP?

Different MCP hosts support different transports.

Stdio is great for local desktop tools. HTTP is needed when a host needs to call
the server through a remote URL, such as an ngrok tunnel.

### Why add `search` and `fetch`?

Some connector-style MCP clients expect a search/fetch pattern:

- `search` finds candidate records
- `fetch` retrieves one exact record

The project keeps those alongside the more memory-specific tools.

## Things To Learn From This Project

- How MCP separates hosts, clients, and servers.
- How MCP tools are described with JSON Schema.
- How JSON-RPC request, response, and notification messages work.
- How stdio transport differs from HTTP transport.
- How to persist local tool state with SQLite.
- How to Dockerize a small Python service.
- How ngrok exposes a local service as a public HTTPS URL.
- How smoke tests can validate protocol behavior without a full MCP host.

## Suggested Improvements

Good next additions:

- Add real MCP resources, such as `memory://all` and `memory://{key}`.
- Add a `prompts/list` and `prompts/get` implementation for reusable memory workflows.
- Add OAuth or stronger auth for public remote use.
- Add pagination for large memory lists.
- Add full-text search with SQLite FTS5.
- Add semantic search with local embeddings.
- Add import/export commands for Markdown or JSON.
- Add unit tests for `MemoryStore`.
- Add GitHub Actions for smoke tests.
- Add a small CLI for managing memories without an MCP host.
- Add structured logging for production debugging.

## Security Notes

Be careful when exposing an MCP server publicly.

This project can store and return personal data. If you expose it through ngrok
or any public URL, consider setting `MCP_BEARER_TOKEN` and keeping the tunnel
private.

Also avoid committing the SQLite database. The project `.gitignore` excludes
`memory.sqlite3` and other local database files.

## Mental Model

Think of this project as two parts:

```text
Protocol brain: TinyMemoryMcp
Storage heart: MemoryStore
```

Everything else is delivery:

```text
stdio delivery: server.py main loop
HTTP delivery: http_server.py
container delivery: Dockerfile + docker-compose.yml
public delivery: ngrok
```

That separation is the most important architectural idea in the project.

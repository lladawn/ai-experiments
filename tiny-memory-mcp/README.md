# Tiny Memory MCP

A small, dependency-free MCP server written in Python. It stores durable memories in
a local SQLite database and exposes them as MCP tools over stdio or Streamable HTTP.

## Tools

- `search`: search memories in ChatGPT connector format
- `fetch`: fetch one memory by key in ChatGPT connector format
- `remember`: store or update a memory by key
- `recall`: search memories by key, value, or tag
- `list_memories`: list recent memories
- `forget`: delete a memory by key

## Run Locally With Stdio

```bash
python3 server.py
```

The server speaks MCP over stdio, so it is meant to be launched by an MCP host.

## Configure In An MCP Host

Use the absolute path to this folder on your machine:

```json
{
  "mcpServers": {
    "tiny-memory": {
      "command": "python3",
      "args": [
        "/Users/dawn/Code/ai-experiments/tiny-memory-mcp/server.py"
      ],
      "env": {
        "TINY_MEMORY_DB": "/Users/dawn/Code/ai-experiments/tiny-memory-mcp/memory.sqlite3"
      }
    }
  }
}
```

## Manual Smoke Test

```bash
python3 tests/smoke.py
```

This starts the server as a subprocess, initializes an MCP session, stores a
memory, searches for it, lists memories, deletes it, and verifies it is gone.

## Run Locally With Streamable HTTP

```bash
HOST=127.0.0.1 PORT=8000 python3 http_server.py
```

The MCP endpoint is:

```text
http://127.0.0.1:8000/mcp
```

HTTP smoke test:

```bash
python3 tests/http_smoke.py
```

## Docker

Build and run:

```bash
docker build -t tiny-memory-mcp .
docker run --rm -p 8000:8000 -v tiny-memory-data:/data tiny-memory-mcp
```

Or with Compose:

```bash
docker compose up --build
```

## Expose With Ngrok

Once the Docker container is running on port 8000:

```bash
ngrok http 8000
```

Use the HTTPS forwarding URL with `/mcp` appended:

```text
https://YOUR-NGROK-DOMAIN.ngrok-free.app/mcp
```

In ChatGPT custom MCP settings, choose Streamable HTTP and use that URL.

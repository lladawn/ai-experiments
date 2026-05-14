from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from mac_agent_runtime.operator import run_operator_task
from mac_agent_runtime.overlay_state import OverlayState


DEFAULT_STATE_PATH = Path("~/.mac-agent-runtime/overlay_state.json").expanduser()
DEFAULT_APPROVAL_LOG = Path("~/.mac-agent-runtime/pending_actions.jsonl").expanduser()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local operator overlay daemon.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", default="gemma4")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--state-path", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--approval-log", default=str(DEFAULT_APPROVAL_LOG))
    args = parser.parse_args()

    state = OverlayState(Path(args.state_path).expanduser())
    handler = build_handler(
        state=state,
        model_name=args.model,
        max_workers=args.max_workers,
        approval_log=Path(args.approval_log).expanduser(),
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Overlay daemon running at http://{args.host}:{args.port}")
    server.serve_forever()


def build_handler(
    state: OverlayState,
    model_name: str,
    max_workers: int,
    approval_log: Path,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/" or self.path.startswith("/?"):
                self._send_html(OVERLAY_HTML)
                return
            if self.path.startswith("/state"):
                self._send_json(state.snapshot())
                return
            self.send_error(404)

        def do_POST(self) -> None:
            if self.path != "/task":
                self.send_error(404)
                return

            task = self._read_task()
            if not task:
                self.send_error(400, "Missing task")
                return

            run_id = state.start_run(task)
            thread = threading.Thread(
                target=self._run_task,
                args=(run_id, task),
                daemon=True,
            )
            thread.start()
            self._send_json({"ok": True, "run_id": run_id})

        def log_message(self, format: str, *args: object) -> None:
            return

        def _run_task(self, run_id: str, task: str) -> None:
            try:
                run_operator_task(
                    task=task,
                    model_name=model_name,
                    max_workers=max_workers,
                    approval_log=approval_log,
                    overlay_state=state,
                    run_id=run_id,
                )
            except Exception as error:
                state.set_run_status(run_id, "error", str(error))

        def _read_task(self) -> str:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            content_type = self.headers.get("Content-Type", "")
            if "application/json" in content_type:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    return ""
                return str(data.get("task", "")).strip()
            parsed = parse_qs(raw)
            return parsed.get("task", [""])[0].strip()

        def _send_json(self, value: dict[str, object]) -> None:
            body = json.dumps(value).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


OVERLAY_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mac Agent</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: transparent;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 14px;
      color: #f5f7fb;
      background: transparent;
      overflow: hidden;
    }
    .panel {
      width: min(460px, calc(100vw - 28px));
      max-height: calc(100vh - 28px);
      overflow: hidden;
      border: 1px solid rgba(255,255,255,.18);
      background: rgba(16, 22, 31, .82);
      backdrop-filter: blur(18px);
      box-shadow: 0 18px 60px rgba(0,0,0,.32);
      border-radius: 8px;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid rgba(255,255,255,.12);
    }
    h1 {
      margin: 0;
      font-size: 13px;
      font-weight: 650;
      letter-spacing: 0;
    }
    .pulse {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #4ade80;
      box-shadow: 0 0 18px #4ade80;
    }
    main {
      padding: 10px;
      display: grid;
      gap: 10px;
      max-height: calc(100vh - 82px);
      overflow: auto;
    }
    .empty {
      padding: 18px 14px;
      color: #aab4c3;
      font-size: 13px;
      line-height: 1.4;
    }
    .run {
      border: 1px solid rgba(255,255,255,.12);
      border-radius: 8px;
      padding: 10px;
      background: rgba(255,255,255,.045);
    }
    .run-top {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: start;
      margin-bottom: 8px;
    }
    .task {
      font-size: 13px;
      line-height: 1.35;
      font-weight: 600;
    }
    .status {
      flex: 0 0 auto;
      font-size: 11px;
      color: #10161f;
      background: #93c5fd;
      padding: 2px 7px;
      border-radius: 999px;
      text-transform: uppercase;
      letter-spacing: .04em;
    }
    .status.done { background: #86efac; }
    .status.error { background: #fca5a5; }
    .agent {
      display: grid;
      grid-template-columns: 84px 1fr;
      gap: 8px;
      padding: 8px 0;
      border-top: 1px solid rgba(255,255,255,.08);
    }
    .agent-name {
      font-size: 12px;
      color: #cbd5e1;
      overflow-wrap: anywhere;
    }
    .agent-body {
      min-width: 0;
      font-size: 12px;
      line-height: 1.35;
      color: #e5e7eb;
    }
    .agent-task, .agent-summary {
      overflow: hidden;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
    }
    .agent-summary {
      margin-top: 4px;
      color: #aab4c3;
      -webkit-line-clamp: 3;
    }
    .agent-state {
      margin-top: 5px;
      color: #93c5fd;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .04em;
    }
  </style>
</head>
<body>
  <section class="panel">
    <header>
      <h1>Mac Agent</h1>
      <div class="pulse"></div>
    </header>
    <main id="runs"><div class="empty">Waiting for dictation. Press E twice, then say a task.</div></main>
  </section>
  <script>
    const runsEl = document.getElementById("runs");
    function esc(value) {
      return String(value || "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }
    function render(data) {
      const runs = data.runs || [];
      if (!runs.length) {
        runsEl.innerHTML = '<div class="empty">Waiting for dictation. Press E twice, then say a task.</div>';
        return;
      }
      runsEl.innerHTML = runs.map(run => `
        <article class="run">
          <div class="run-top">
            <div class="task">${esc(run.task)}</div>
            <div class="status ${esc(run.status)}">${esc(run.status)}</div>
          </div>
          ${(run.agents || []).map(agent => `
            <div class="agent">
              <div class="agent-name">${esc(agent.name)}</div>
              <div class="agent-body">
                <div class="agent-task">${esc(agent.task)}</div>
                <div class="agent-state">${esc(agent.status)}</div>
                <div class="agent-summary">${esc(agent.summary)}</div>
              </div>
            </div>
          `).join("")}
          ${run.error ? `<div class="agent-summary">${esc(run.error)}</div>` : ""}
        </article>
      `).join("");
    }
    async function tick() {
      try {
        const res = await fetch("/state", { cache: "no-store" });
        render(await res.json());
      } catch (error) {
        runsEl.innerHTML = '<div class="empty">Overlay daemon unavailable.</div>';
      }
    }
    tick();
    setInterval(tick, 900);
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()

# Mac Agent App Architecture

## Components

```text
MacAgentApp
  AppKit menu bar app
  Overlay WKWebView
  Double-E global hotkey through a read-only CG event tap
  Native speech recognizer
  Agent daemon launcher

mac-agent-runtime
  Local HTTP daemon
  Context packet harness
  Multi-agent planner/executor
  Tool registry and security modes
  Approval queue
  Overlay state store

Ollama
  Local model host
  Default model: gemma4
```

## Runtime Flow

1. User double-presses `E`.
2. App records a short speech command.
3. App submits the transcript to `POST /task`.
4. Python daemon creates a run in overlay state.
5. Planner decides whether to split into agents.
6. Agents run with isolated context and allowed tools.
7. Overlay polls `/state` through WKWebView.
8. Mutations are proposed to the approval queue, not executed.

## Security Position

- The Mac app can open the overlay and capture voice only after macOS grants
  permissions.
- The double-`E` shortcut requires Accessibility permission because it uses a
  global keyboard event tap.
- The Python tool layer classifies tools as `read`, `control`, `propose`, or
  `write`.
- `open_app` is direct control because it does not mutate user data.
- Typing, clicking, bookmark edits, file writes, sends, and deletes require an
  approval proposal.
- Secret-bearing paths remain denied by default.

## Senior-Engineer Next Steps

1. Replace hard-coded repo path with a bundled helper lookup.
2. Add a permissions onboarding window.
3. Add a model picker and Ollama health panel.
4. Add approval review UI in the menu bar app.
5. Replace polling with Server-Sent Events once the daemon state model settles.
6. Add a signed helper tool for approved mutations only.

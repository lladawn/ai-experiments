# Voice Shortcut Setup

This setup shows a small background overlay and makes a quick double press of
`E` start dictation, then pass the spoken task into the local operator harness.

## 1. Start Ollama

```bash
ollama pull gemma4
ollama serve
```

## 2. Create a macOS Shortcut

Create a Shortcut named:

```text
Mac Agent Voice
```

Actions:

1. Dictate Text
2. Run Shell Script

Shell script:

```bash
/Users/dawn/Code/ai-experiments/mac-agent-runtime/scripts/run-voice-task.sh "$SHORTCUT_INPUT"
```

For the first smoke test, say:

```text
Open Notion
```

## 3. Add Double-E Hotkey With Hammerspoon

Start the overlay daemon in a terminal:

```bash
/Users/dawn/Code/ai-experiments/mac-agent-runtime/scripts/start-overlay-daemon.sh
```

Install Hammerspoon, grant Accessibility permission, then copy:

```text
/Users/dawn/Code/ai-experiments/mac-agent-runtime/scripts/hammerspoon-double-e.lua
```

into:

```text
~/.hammerspoon/init.lua
```

Reload Hammerspoon config. Press `E` twice quickly to trigger the Shortcut.
The overlay will poll `http://127.0.0.1:8765/state` and show each run, worker
agent, status, and short summary.

## Safety Behavior

- `open_app` may directly open/focus apps such as Notion.
- Read tools may inspect local files needed for a task.
- Create, update, delete, typing, submitting, bookmark edits, and browser data
  changes must be proposed with `propose_laptop_action`.
- Proposed mutations are logged at
  `~/.mac-agent-runtime/pending_actions.jsonl`.

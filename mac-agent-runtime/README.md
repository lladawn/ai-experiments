# Mac Agent Runtime

A local desktop-agent runtime for experimenting with context as a first-class
execution object. The goal is to make every agent step explicit:

- what context the model receives
- which tools it is allowed to call
- which claims or actions must be verified
- which rules are enforced before and after a step
- what information is isolated from delegated subagents

This is intentionally framework-light. The first version uses a deterministic
stub model so the harness can be tested without API keys.

## Core Idea

The harness treats an agent run as a sequence of controlled packets:

```text
User task
  -> ContextPacket
  -> Policy enforcement
  -> Model step
  -> Tool execution
  -> Verification
  -> Final answer or isolated subagent task
```

## Quickstart

```bash
cd mac-agent-runtime
PYTHONPATH=src python3 -m mac_agent_runtime "Summarize the project shape"
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Local Multi-Agent Run

The multi-agent example uses one local Ollama model for every worker. Each
worker receives an isolated context packet, then a synthesizer agent receives
only the worker outputs.

```bash
ollama pull llama3.2
PYTHONPATH=src python3 examples/local_multi_agent.py \
  "Design a safer context packet format for coding agents"
```

For a no-model smoke test:

```bash
PYTHONPATH=src python3 examples/local_multi_agent.py \
  "Design a safer context packet format for coding agents" \
  --stub
```

## Desktop Agent Mode

Desktop agent mode uses one local Ollama model, defaulting to `gemma4`, as the brain
for all agents. The model may split a task into worker agents. Every worker gets
isolated context and the same security contract:

- read-only tools may inspect files and app data
- create/update/delete/app-control actions must be proposed
- proposed actions are written to `~/.mac-agent-runtime/pending_actions.jsonl`
- no mutation is executed by the harness without a separate approval executor

```bash
ollama pull gemma4
ollama serve
PYTHONPATH=src python3 -m mac_agent_runtime.operator \
  "Find job-related research from the past month and propose how to bookmark it"
```

For a keyboard shortcut or voice flow on macOS, create a Shortcut that dictates
text and passes it to:

```bash
/Users/dawn/Code/ai-experiments/mac-agent-runtime/scripts/run-voice-task.sh "DICTATED TASK"
```

For double-press `E` voice activation, see
[`notes/voice-shortcut.md`](notes/voice-shortcut.md). The included Hammerspoon
snippet runs a macOS Shortcut named `Mac Agent Voice`.

Start the background overlay daemon first:

```bash
/Users/dawn/Code/ai-experiments/mac-agent-runtime/scripts/start-overlay-daemon.sh
```

The Dia bookmark example should initially produce proposed actions only. Once
the read path to Dia's browser data is confirmed, the next layer can add a
separate approval executor for the exact bookmark edits.

## Project Structure

```text
mac-agent-runtime/
  src/mac_agent_runtime/
    __main__.py       # CLI demo
    harness.py        # Agent runtime orchestration
    multi_agent.py    # Parallel worker agents plus synthesis
    context.py        # Context packets and isolation
    tools.py          # Tool registry and permissions
    laptop_tools.py   # Read-only laptop tools and mutation proposal tool
    approval.py       # Pending approval queue
    verification.py   # Verification results and policies
    enforcement.py    # Runtime guardrails
    model.py          # Model interface and deterministic stub
  examples/
    basic_agent.py
  tests/
    test_harness.py
  notes/
    design.md
```

## Harness Principles

1. Context is structured, not a loose prompt string.
2. Tools are capabilities with input schemas, not ambient powers.
3. Verification is a required phase, not a nice-to-have.
4. Enforcement happens before model calls and after tool calls.
5. Subagents receive deliberately narrowed context, never the whole parent
   scratchpad by default.

## Next Experiments

- Add a real LLM adapter.
- Teach local models to emit structured tool calls.
- Add typed tool input validation.
- Track token budgets per context section.
- Persist run traces as JSONL.
- Add verifier agents that can only inspect evidence, not hidden reasoning.
- Add context compression strategies and compare outcomes.

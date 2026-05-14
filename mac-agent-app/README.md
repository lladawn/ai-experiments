# Mac Agent App

A native macOS shell for `mac-agent-runtime`.

This is the productized replacement for the prototype stack of Hammerspoon plus
macOS Shortcuts. It owns:

- menu bar lifecycle
- always-on-top overlay
- double-press `E` hotkey
- native speech recognition
- background daemon launch
- task submission to the local agent runtime

The Python runtime in `../mac-agent-runtime` still owns:

- model calls through Ollama
- agent planning and subagent execution
- tool security policy
- approval queue
- overlay state endpoint

## Run From Source

Start Ollama:

```bash
ollama serve
```

Run the app shell:

```bash
cd /Users/dawn/Code/ai-experiments/mac-agent-app
swift run MacAgentApp
```

The app appears as a menu bar item named `Mac Agent`. It starts the local overlay
daemon automatically, shows the overlay, and listens for a quick double press of
`E`.

For microphone and speech permission prompts, prefer running the dev app bundle:

```bash
cd /Users/dawn/Code/ai-experiments/mac-agent-app
scripts/build-dev-app.sh
open "dist/Mac Agent.app"
```

If double-`E` does not work, open the menu bar item and choose
`Open Accessibility Settings`, then enable `Mac Agent`. You may need to
quit and reopen the app after toggling the permission.

When dictation starts, the overlay shows a native `Listening...` banner. After
recognition, it shows `Heard: ...` before sending the task to the local daemon.

For the first smoke test:

```text
Open Notion
```

## Permissions

macOS will require:

- Microphone permission for speech input
- Speech Recognition permission for transcription
- Accessibility permission for the global double-`E` event tap

The app does not need blanket disk access for the overlay itself. The Python
runtime may ask for file access depending on which tools are enabled and which
folders a user authorizes in the future.

## Distribution Plan

This Swift Package is the fast development shell. To distribute to users:

1. Keep the native app shell as the product entrypoint.
2. Move to an Xcode project when we need signing, hardened runtime, and
   notarization.
3. Bundle or install the Python agent runtime as a helper.
4. Add onboarding screens for permissions and model selection.
5. Sign and notarize a `.dmg`.

Shortcuts and Hammerspoon should remain prototype-only integrations.

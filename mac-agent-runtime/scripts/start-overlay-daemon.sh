#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHONPATH=src python3 -m mac_agent_runtime.overlay_server --model "${MAC_AGENT_MODEL:-gemma4}"

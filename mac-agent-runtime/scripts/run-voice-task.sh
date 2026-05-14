#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
TASK="${*:-}"

if [[ -z "$TASK" ]]; then
  echo "Missing task" >&2
  exit 1
fi

if /usr/bin/curl -fsS \
  -X POST \
  --data-urlencode "task=$TASK" \
  http://127.0.0.1:8765/task >/dev/null; then
  exit 0
fi

PYTHONPATH=src python3 -m mac_agent_runtime.operator "$TASK"

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_FILE="${1:-$ROOT/.host_bridge.pid}"
if [ ! -f "$PID_FILE" ]; then
  printf 'No host bridge pid file at %s\n' "$PID_FILE"
  exit 0
fi
PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  printf 'Stopping host bridge (pid %s)\n' "$PID"
  kill "$PID"
  wait "$PID" 2>/dev/null || true
else
  printf 'Host bridge pid %s not running\n' "$PID"
fi
rm -f "$PID_FILE"

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE=".env"
PORT="${FRONTEND_ENHANCEMENT_BRIDGE_PORT:-5600}"
MODE="foreground"
PID_FILE="$ROOT/.host_bridge.pid"
LOG_FILE="$ROOT/.host_bridge.log"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --background)
      MODE="background"
      shift
      ;;
    --pid-file)
      PID_FILE="$2"
      shift 2
      ;;
    --log-file)
      LOG_FILE="$2"
      shift 2
      ;;
    *)
      ENV_FILE="$1"
      shift
      ;;
  esac
done

cd "$ROOT"
if [ ! -f "$ENV_FILE" ]; then
  printf 'Host bridge env file %s not found\n' "$ENV_FILE" >&2
  exit 1
fi

CMD=(uv run uvicorn apps.host_bridge.app:app --env-file "$ENV_FILE" --host 0.0.0.0 --port "$PORT")

if [ "$MODE" = "background" ]; then
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    printf 'Host bridge already running (pid file: %s)\n' "$PID_FILE"
    exit 0
  fi
  printf 'Starting host bridge in background (log: %s, pid: %s)\n' "$LOG_FILE" "$PID_FILE"
  "${CMD[@]}" > "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  disown || true
else
  exec "${CMD[@]}"
fi

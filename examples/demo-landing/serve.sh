#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-3000}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
printf 'Serving demo landing on http://0.0.0.0:%s (Ctrl+C to exit)\n' "$PORT"
python -m http.server "$PORT" --bind 0.0.0.0

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARGS=("$@")
if [ "${#ARGS[@]}" -eq 0 ]; then
  ARGS=(--remove-orphans)
fi
cd "$ROOT"
printf 'Stopping Docker Compose stack (%s)\n' "${ARGS[*]}"
docker compose down "${ARGS[@]}"

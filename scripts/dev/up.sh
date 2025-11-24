#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARGS=("$@")
if [ "${#ARGS[@]}" -eq 0 ]; then
  ARGS=(--detach)
fi
cd "$ROOT"
printf 'Starting Docker Compose stack (%s)\n' "${ARGS[*]}"
docker compose up "${ARGS[@]}"

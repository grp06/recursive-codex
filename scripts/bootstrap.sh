#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"

if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"

python -m pip install --upgrade pip uv
uv pip install --editable "${ROOT}[dev]"

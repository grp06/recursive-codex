#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: scripts/release.sh <version>"
  exit 1
fi

version="$1"
tag="v$version"

if git rev-parse "$tag" >/dev/null 2>&1; then
  echo "tag $tag already exists"
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "working tree must be clean"
  exit 1
fi

make lint
make test
make e2e

VERSION="$version" python - <<'PY'
import os
from pathlib import Path
version = os.environ["VERSION"]
path = Path("pyproject.toml")
text = path.read_text()
target = 'version = "'
start = text.index(target) + len(target)
end = text.index('"', start)
path.write_text(text[:start] + version + text[end:])
PY

git add pyproject.toml CHANGELOG.md
git commit -m "chore: release v$version"
git tag "$tag"
git push origin HEAD
git push origin "$tag"

if [ "${PUBLISH_IMAGES:-0}" = "1" ]; then
  docker compose build
  docker compose push
fi

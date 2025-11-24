# Release Guide

Follow this checklist whenever you ship a tagged version or public demo build. Automate steps later via Milestone 4 release tooling.

## Branch hygiene

1. Ensure `main` is green: `git checkout main && git pull`.
2. Rebase your release branch on top of `main` and resolve merge conflicts locally.

## Versioning

1. Choose a semantic version (e.g., `v0.2.0` after Milestone 4 lands).
2. Update `pyproject.toml` with the new version string.
3. Update `README.md` and `docs/getting-started.md` if commands or prerequisites changed.

## Validation

1. Run `make lint`, `make test`, and `make e2e`.
2. Execute `uv run enhancement_cli pipeline run --demo --iterations 2` when you need multi-pass validation; omit `--iterations` to capture the legacy single-run payload for downstream automation.
3. Capture docker compose logs that prove the services started cleanly.

## Tagging and publishing

1. Commit the version bump (`git commit -am "chore: release v0.x.y"`).
2. Tag the commit (`git tag v0.x.y`) and push (`git push --tags`).
3. Publish container images if applicable: `docker compose build` followed by `docker compose push` once registries are configured.
4. Draft GitHub release notes summarizing highlights, setup steps, and known issues. Attach the pipeline artifacts if they help new adopters reproduce the run.

## Post-release tasks

- Update open issues or ExecPlan milestones with the released version.
- Announce the release in community channels linked from the README badges.
- Monitor `run_logs/codex_runs/` and user feedback for regressions, recording lessons in `docs/troubleshooting.md`.

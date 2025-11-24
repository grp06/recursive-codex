# Contributing Guide

Thank you for improving the toolkit. Please read this entire document plus `CODE_OF_CONDUCT.md` before opening a pull request.

## Workflow

1. Open an issue or discussion describing the proposed change.
2. Create a topic branch named `feature/<short-description>` or `fix/<short-description>`.
3. Run `make bootstrap` once per machine, then `make dev` so Docker Compose stays aligned with docs.
4. Add or update docs as part of every change. If you touch scripts, verify `docs/getting-started.md` still matches reality.
5. Run `make lint`, `make test`, and `make e2e` (if applicable) before requesting review.
6. Reference the relevant ExecPlan milestone in your pull request description so reviewers know the context.

## Coding standards

- Fail fast on invalid input and raise actionable errors instead of silently ignoring problems.
- Never add inline comments; favor descriptive names and pure functions so the code explains itself.
- Avoid fallbacks unless you have concrete evidence they are needed. Understand every API response by logging it rather than guessing.
- Keep functions small and single-purpose. Duplicate logic twice before extracting abstractions.
- Use `enhancement_core.logging.configure(service_name)` in every entrypoint so logs remain structured.
- Add lightweight logging whenever you cross an error boundary or mutate external state, but avoid noisy loops.

## Tests and validation

- Mirror the production layout under `tests/` and rely on pytest fixtures for network or Codex stubs.
- FastAPI routes must be covered by TestClient-based tests once Milestone 4 lands; for now provide manual repro steps in pull requests.
- If you introduce new CLI flags or environment variables, add them to `.env.example`, `docs/getting-started.md`, and `docs/troubleshooting.md`.

## Documentation expectations

Every feature change must update at least one doc. When in doubt, prefer:

- `README.md` for high-level positioning
- `docs/architecture.md` for data flow changes
- `docs/troubleshooting.md` for operational gotchas
- `docs/release.md` for artifacts or tagging tweaks

Treat docs as part of the feature, not an afterthought.

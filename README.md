# Frontend Enhancement Toolkit

[![CI](https://img.shields.io/badge/ci-manual-lightgrey)](../../actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Community](https://img.shields.io/badge/community-discussions-blue)](../../discussions)

Recursive Codex is an open-source toolkit that captures full-page screenshots, asks the OpenAI Responses API for actionable UI feedback, and applies those edits to your frontend repo through the Codex CLI.

## Highlights

- **Single CLI:** `uv run enhancement_cli ...` validates environments, runs the screenshot → feedback → Codex pipeline, and stores artifacts.
- **Containerized services:** Screenshot, feedback, and router services live under `apps/` and communicate over HTTP via Docker Compose.
- **Host bridge:** Codex commands run on the host to keep repo access simple while logging every run under `run_logs/codex_runs/`.
- **Schema-driven Config UI:** Edit `.env` and CLI defaults from a zero-dependency FastAPI app served at `http://localhost:8110` with restart guidance for every control.
- **Docs-first onboarding:** Comprehensive guides live in `docs/` so newcomers can set up everything in minutes.

## Quick start

1. **Bootstrap dependencies**
   ```bash
   make bootstrap
   ```
2. **Configure the environment**
   ```bash
   cp .env.example .env
   ```
   Only set the required fields (`OPENAI_API_KEY`, `TARGET_REPO_PATH`); remove optional lines if you want to rely on the baked-in defaults shown in `.env.example`.
   Set `TARGET_REPO_PATH` to the absolute path of `examples/demo-landing` if you are just exploring the pipeline.
3. **Open the Config UI**
   ```bash
   docker compose up config_ui -d
   ```
   Visit `http://localhost:8110` to inspect `.env` and CLI overrides. Edits save atomically and the toast reminds you which containers to restart. See `docs/config-ui/README.md` for feature details.
4. **Start the services (Docker + host bridge)**
   ```bash
   make dev
   ```
   `make dev` builds the containers (screenshot, feedback, router) and backgrounds the host bridge. Logs for the bridge stream to `.host_bridge.log`.
5. **Run the demo landing page** (optional but recommended)
   ```bash
   cd examples/demo-landing
   ./serve.sh 3000
   ```
6. **Validate and run the pipeline**
   ```bash
   uv run enhancement_cli doctor --env-file .env
   uv run enhancement_cli pipeline run --demo --env-file .env
   ```
   Add `--iterations 3` when you want back-to-back Codex passes; omitting the flag keeps the legacy single-run payload for scripts that parse stdout.
   Use `--model gpt-4.1-mini` to override the Codex execution parameters for a single pipeline run.
7. **Stop services**
   ```bash
   make stop
   ```

See `docs/getting-started.md` for the full walkthrough plus artifact details.

## Core commands

| Command | Purpose |
| --- | --- |
| `make bootstrap` | Install Python deps and Playwright browsers via `scripts/bootstrap.sh`. |
| `make dev` | Start Docker Compose plus the host bridge (background) with `scripts/dev/up.sh` and `scripts/host_bridge/start.sh`. |
| `make host-bridge` | Manually run the host bridge in the foreground for debugging. |
| `make stop` | Stop the host bridge and Docker containers via `scripts/host_bridge/stop.sh` + `scripts/dev/down.sh`. |
| `make lint` | Run Ruff checks (requires `[project.optional-dependencies.dev]`). |
| `make test` | Run pytest suites as they are added. |
| `make e2e` | Run the orchestrated pipeline in demo mode. |
| `uv run enhancement_cli doctor` | Verify service health and Codex CLI prerequisites. |
| `uv run enhancement_cli pipeline sample-feedback` | Send canned feedback directly to the router for fast Codex verification. |
| `uv run enhancement_cli pipeline run --iterations 3` | Capture fresh screenshots and apply Codex changes three times in succession. |
| `uv run enhancement_cli pipeline run --model gpt-4.1-mini` | Override the Codex model for a run. |

## Documentation

- `docs/getting-started.md` – step-by-step onboarding and demo instructions
- `docs/architecture.md` – diagrams plus data flow explanations
- `docs/contributing.md` – workflow, coding standards, and testing expectations
- `docs/troubleshooting.md` – fixes for common Docker, Codex, and OpenAI issues
- `docs/release.md` – versioning and tagging checklist
- `docs/config-ui/README.md` – Config UI workflow, schema reference, troubleshooting, and smoke checklist

Additional governance files:

- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `LICENSE`
- `.github/ISSUE_TEMPLATE/*.md`

## Project layout

```
apps/                     FastAPI + Typer entrypoints for every runtime component
packages/enhancement_core Shared configuration, logging, Playwright, Codex, orchestration modules
docs/                     Getting started, architecture, troubleshooting, contributing, release
docker-compose.yml        Docker services for screenshot, feedback, router
scripts/                  Bootstrap + dev helpers used by Makefile targets
examples/demo-landing/    Static landing page for demos and smoke tests
```

## Need help?

- Open an issue using the templates in `.github/ISSUE_TEMPLATE/`
- Start a discussion via the community badge link
- Review `docs/troubleshooting.md` before filing bugs

# Getting Started

New contributors should be able to go from clone to a successful pipeline run in minutes. Follow these steps exactly on macOS, Linux, or WSL.

## Prerequisites

- Docker Desktop 4.30+ or any Docker Engine with Compose V2 enabled
- Python 3.10+ plus [uv](https://github.com/astral-sh/uv) or `pip`
- Codex CLI installed and authenticated (`codex --version` should work)
- An OpenAI API key with access to the Responses API

## 1. Clone and bootstrap

```bash
git clone https://github.com/<your-org>/recursive-codex.git
cd recursive-codex
make bootstrap
```
`make bootstrap` installs the project in editable mode, Playwright dependencies, and any dev extras defined in `pyproject.toml`.

## 2. Configure the environment

Copy the sample file, then fill only the required values. Delete optional lines if you want the services to fall back to the defaults shown in `.env.example`.

```bash
cp .env.example .env
```
Set `TARGET_REPO_PATH` to the absolute path of `examples/demo-landing` if you plan to demo against the bundled site before touching your production frontend.
The host bridge runs directly on your machine and mounts that path along with `FRONTEND_ENHANCEMENT_CODEX_LOG_DIR` and `FRONTEND_ENHANCEMENT_CODEX_BIN`, so **all three values must be absolute host paths that already exist** before you start the bridge.
Keep `.env` at the repo root so both Docker Compose and the CLI can load it automatically.

## 3. Edit settings from the Config UI

Launch the browser-based Config UI in a separate terminal so you can update `.env` and CLI overrides without hand-editing files:

```bash
docker compose up config_ui -d
```

Visit [http://localhost:8110](http://localhost:8110) to view the primary controls plus grouped secondary sections. Every save call validates the payload, writes `.env` atomically, and shows which containers must be restarted. Use the **Download .env** button before sweeping changes and the **Upload .env** button to restore previous snapshots.

## 4. Start the services

Use the wrapper script so you get consistent logging and error handling.

```bash
make dev
```
This runs `scripts/dev/up.sh` for the Dockerized services and then backgrounds the host bridge via `scripts/host_bridge/start.sh --background`. Bridge logs live in `.host_bridge.log`, and the PID is stored at `.host_bridge.pid` for clean shutdowns.

## 5. Launch the demo landing page

The quickest way to exercise the pipeline is to host the provided static site at port 3000.

```bash
cd examples/demo-landing
./serve.sh 3000
```
The page lives at `http://localhost:3000` and is referenced by default in `.env.example`. You can swap in any other frontend later.

## 6. Run the pipeline

Open a new terminal in the repo root and point the CLI at your `.env` file (or rely on defaults). Remember that Typer treats global options like `--env-file` before the subcommand name.

```bash
uv run enhancement_cli --env-file .env doctor
uv run enhancement_cli --env-file .env pipeline run --demo
```
`doctor` verifies service health plus Codex prerequisites. `pipeline run` triggers screenshot capture, routes the screenshot through the feedback model, and executes the resulting Codex instructions inside `TARGET_REPO_PATH`.
Append `--iterations 3` to the pipeline command when you want Codex to analyze three consecutive screenshots; this is different from `PIPELINE_MAX_ATTEMPTS`, which only retries a single iteration after transient service failures.
Set `--model gpt-4.1-mini` when you need to override the Codex binary for a given run without touching the host bridge environment.

Artifacts flow to predictable locations:

- Codex CLI logs: `run_logs/codex_runs/<timestamp>-<run_id>`
- Pipeline artifacts (stitched screenshot, metadata, feedback JSON): `run_logs/pipeline_runs/<timestamp>`

Inspect these folders after every run to understand what changed.

## 7. Tear everything down

When finished, stop Docker containers and optional demo services.

```bash
make stop
```
`make stop` kills the backgrounded host bridge (using `.host_bridge.pid`) before tearing down Docker. Stop the demo landing page with `Ctrl+C` in its terminal, and use `scripts/dev/down.sh --volumes` if you need a full reset.

Need to debug the bridge manually? Run `make host-bridge` in a separate terminal to foreground it, or tail `.host_bridge.log` for streaming output.

## Next steps

- Read `docs/architecture.md` to understand data flow and extension points.
- Review `docs/contributing.md` before opening a pull request.
- Keep `docs/troubleshooting.md` handy while iterating on local setups.

# Troubleshooting

Keep this guide nearby while onboarding or demoing the toolkit. Each entry lists symptoms plus a fix.

## Docker compose build fails on Playwright images

**Symptoms:** `docker compose build` hangs or errors while downloading Chromium.

**Fix:** Run `docker pull mcr.microsoft.com/playwright/python:v1.45.0-focal` manually, then retry `make dev`. If you are on Apple Silicon, ensure Docker Desktop uses `Use Rosetta for x86/amd64 emulation` so the Playwright image can execute.

## Containers cannot reach the host landing page

**Symptoms:** Screenshot service logs show `net::ERR_CONNECTION_REFUSED` when hitting `http://host.docker.internal:3000`.

**Fix:** Confirm the demo landing page (or your own app) is running on the host. If you are on Linux and `host.docker.internal` is unavailable, set `FRONTEND_SCREENSHOT_URL=http://172.17.0.1:3000` in `.env`.

## Codex CLI fails with `command not found`

**Symptoms:** `enhancement_cli doctor` reports it cannot resolve `codex`.

**Fix:** Install the Codex CLI per the official instructions, then update `.env` with `FRONTEND_ENHANCEMENT_CODEX_BIN=/path/to/codex`. Re-run `doctor` to verify.

## Feedback service returns authentication errors

**Symptoms:** Router responses contain `401 Unauthorized` from the OpenAI API.

**Fix:** Double-check `OPENAI_API_KEY` inside `.env` and confirm the key has Responses API access. Restart the stack after updating `.env` so containers pick up the new value.

## Pipeline run hangs at router stage

**Symptoms:** `pipeline run` prints `waiting for router response` for more than a minute.

**Fix:** Confirm the host bridge that `make dev` starts is still alive (`tail .host_bridge.log` or `curl http://localhost:5600/health`). If it stopped, rerun `make dev` or start it manually with `make host-bridge`. Inspect router logs (`docker compose logs router_service`) for concurrency limit errors. Lower `ROUTER_MAX_CONCURRENCY` inside `.env` if your machine throttles HTTP fan-out, or increase `FRONTEND_ENHANCEMENT_HOST_TIMEOUT` so the host bridge has more time to finish Codex edits (the same value now also caps how long the Codex CLI is allowed to run).

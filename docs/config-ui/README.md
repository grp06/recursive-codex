# Config UI Overview

The Config UI exposes every Codex environment variable and CLI default in a single view at [http://localhost:8110](http://localhost:8110). Launch it with:

```bash
docker compose up config_ui -d
```

It reads and writes the same `.env` and `config/pipeline_overrides.json` files consumed by Docker Compose and `enhancement_cli`. All primary controls stay visible in a two-column layout, while secondary controls live inside collapsible sections grouped by subsystem (screenshot, feedback, router, pipeline, endpoints).

![Config UI screenshot](./config-ui-overview.png)

## Features

- Automatic schema-driven field rendering from `config/frontend_config_schema.json` with validation hints and restart instructions per control.
- Save button with optimistic locking: every update includes the current `.env` and override digests, so the API rejects stale writes.
- Per-field reset, default badges, and service restart callouts (screenshot service, feedback service, router, host bridge, CLI) so operators know which containers to bounce.
- `.env` backup buttons: download the current file or upload a replacement, with validation before the atomically rewritten file is persisted.
- Sensitive field handling that only reveals whether a value exists; new values stay in-memory until saved and never log.

## Usage tips

1. Start `docker compose up config_ui` (or keep it running alongside the other services via `make dev`).
2. Visit `http://localhost:8110`, make edits, and press **Save Changes**. The toast lists every service that must be restarted.
3. Run `git status` (or `git diff .env config/pipeline_overrides.json`) to review changes before committing.
4. Use the search box when hunting for secondary controls—matching cards stay visible and the accordion section auto-expands.
5. Download `.env` before major edits so you can restore previous settings in one click if needed.

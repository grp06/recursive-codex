# Config Schema Reference

The UI schema lives at `config/frontend_config_schema.json` and drives both the FastAPI responses and the frontend renderer. Each field entry includes:

- `key`: Environment variable or CLI override identifier
- `target`: `env` or `cli`
- `group`: Section identifier (primary, pipeline_flags, screenshot, feedback, router_host, pipeline, endpoints)
- `control`: Rendering hint (`text`, `textarea`, `number`, `select`, `radio`, `toggle`, `password`, `path`)
- `services`: Containers or processes that must be restarted after changes (`screenshot_service`, `feedback_service`, `router_service`, `host_bridge`, `orchestrator_cli`)
- `validation`: Optional constraints (`min`, `max`, `step`, `minLength`, `maxLength`)
- `options`: Select/radio choices with `value`/`label`
- `default_source`: Indicates whether a field pulls defaults from `.env.example` or from the schema itself (for CLI overrides)

## Groups

| Group ID | Description | Sample fields |
| --- | --- | --- |
| `primary` | Always-visible, high-sensitivity controls | `OPENAI_API_KEY`, `UI_FEEDBACK_PROMPT`, `TARGET_REPO_PATH`, `iterations`, `model_reasoning_effort` |
| `pipeline_flags` | CLI-only overrides surfaced as toggles or text inputs | `demo`, `artifacts_dir` |
| `screenshot` | Playwright capture settings | `FRONTEND_SCREENSHOT_URL`, `FRONTEND_SCREENSHOT_VIEWPORT_WIDTH`, `FRONTEND_SCREENSHOT_OUTPUT_DIR` |
| `feedback` | OpenAI feedback worker settings | `UI_FEEDBACK_MODEL_NAME`, `UI_FEEDBACK_MAX_OUTPUT_TOKENS`, `UI_FEEDBACK_HTTP_TIMEOUT` |
| `router_host` | Router + host bridge integration | `FRONTEND_ENHANCEMENT_BRIDGE_URL`, `FRONTEND_ENHANCEMENT_CODEX_LOG_DIR`, `ROUTER_MAX_CONCURRENCY` |
| `pipeline` | Retry cadence and artifact paths | `PIPELINE_REQUEST_TIMEOUT`, `PIPELINE_RETRY_BACKOFF`, `PIPELINE_SAMPLE_FEEDBACK`, `PIPELINE_ARTIFACT_ROOT` |
| `endpoints` | Internal service URLs consumed by the CLI | `FRONTEND_SCREENSHOTS_URL`, `UI_FEEDBACK_SERVICE_URL` |

Every new environment variable or CLI override should be added to the schema with appropriate metadata. The FastAPI layer validates incoming form data against this schema (types, required flags, restart instructions) before writing to `.env` or `config/pipeline_overrides.json`.

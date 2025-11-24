# Config UI Smoke Checklist

Run this quick loop before shipping UI changes or demoing the tool.

1. `docker compose up config_ui --build -d` and wait for the FastAPI logs to show `Application startup complete`.
2. Load `http://localhost:8110` and confirm primary controls render with default values from `.env.example` when `.env` lacks an entry.
3. Change each primary input, click **Save Changes**, and verify the toast lists the correct restart targets. Confirm `git diff -- .env config/pipeline_overrides.json` reflects the edits.
4. Use **Download .env**, then immediately use **Upload .env** with that file. Verify the API accepts the upload and UI reloads with no validation errors.
5. Trigger a validation error by pointing `TARGET_REPO_PATH` to a missing directory. Ensure the inline field error surfaces and the API returns HTTP 400.
6. Set `iterations` and `model_reasoning_effort` in the UI, then run `uv run enhancement_cli pipeline run` without flags—the CLI should pick up the overrides automatically.
7. Refresh the page to confirm dirty state clears and secret indicators still reflect stored values (only the placeholder preview, never the raw key).

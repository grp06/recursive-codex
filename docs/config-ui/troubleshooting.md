# Config UI Troubleshooting

| Symptom | Resolution |
| --- | --- |
| **Save failed due to version mismatch** | Another process modified `.env` or `config/pipeline_overrides.json` after you loaded the UI. Refresh the page to grab the latest digests, review the git diff, and retry the save. |
| **Fields show blank values even though `.env` has entries** | The schema only displays keys listed in `config/frontend_config_schema.json`. Add the missing key to the schema file (including labels, validation, restart targets), restart the Config UI container, and reload the page. |
| **Upload .env rejected** | The API validates uploads with the same Pydantic models as the pipeline. Ensure required fields (`OPENAI_API_KEY`, `TARGET_REPO_PATH`, etc.) exist and point to real paths/URLs before uploading. |
| **Cannot write `.env` inside Docker** | The Config UI container needs write access to the repo root. Confirm `docker-compose.yml` mounts both `./.env` and `./config` as bind volumes. If permissions block the write, run `chmod` on the host file or edit as the host user outside Docker. |
| **Browser still shows stale values after editing files manually** | The UI caches the latest snapshot client-side. Hit the refresh icon or reload the page to trigger a new `GET /api/config` request. |
| **OpenAI key leak concerns** | The UI never displays existing secret values—only a placeholder string with the hashed preview. To rotate the key, paste the new value, click Save, and restart the feedback service. |

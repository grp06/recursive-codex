# Demo Landing Page

This static landing page gives newcomers a safe target for the screenshot → feedback → Codex pipeline. Serve it locally, point `FRONTEND_SCREENSHOT_URL` to `http://localhost:3000`, and watch Codex edits land in this directory instead of your production frontend.

## Run locally

```bash
./serve.sh 3000
```
The script defaults to port 3000 and listens on `0.0.0.0` so Docker containers can reach it via `host.docker.internal`.

Update the copy or layout to experiment with different feedback responses.

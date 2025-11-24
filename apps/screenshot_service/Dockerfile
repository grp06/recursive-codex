# syntax=docker/dockerfile:1.9
ARG PLAYWRIGHT_IMAGE=mcr.microsoft.com/playwright/python:v1.55.0-jammy

FROM ${PLAYWRIGHT_IMAGE} AS runtime

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY --from=root pyproject.toml /app/
COPY --from=root README.md /app/
COPY --from=packages / /app/packages
COPY . /app/apps/screenshot_service

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[screenshot-service]" \
    && playwright install --with-deps chromium

ENV PYTHONPATH=/app
ENV FRONTEND_SCREENSHOT_OUTPUT_DIR=/screenshots

CMD ["uvicorn", "apps.screenshot_service.app:app", "--host", "0.0.0.0", "--port", "8000"]

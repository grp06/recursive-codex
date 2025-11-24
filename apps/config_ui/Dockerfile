# syntax=docker/dockerfile:1.9
ARG PYTHON_IMAGE=python:3.11-slim

FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY --from=root pyproject.toml /app/
COPY --from=root README.md /app/
COPY --from=root .env.example /app/.env.example
COPY --from=root config /app/config
COPY --from=packages / /app/packages
COPY . /app/apps/config_ui

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[config-ui]"

ENV PYTHONPATH=/app

CMD ["uvicorn", "apps.config_ui.app:app", "--host", "0.0.0.0", "--port", "8000"]

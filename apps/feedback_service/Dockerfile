# syntax=docker/dockerfile:1.9
ARG PYTHON_IMAGE=python:3.11-slim

FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY --from=root pyproject.toml /app/
COPY --from=root README.md /app/
COPY --from=root config/ui_feedback_schema.json /app/config/ui_feedback_schema.json
COPY --from=packages / /app/packages
COPY . /app/apps/feedback_service

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[feedback-service]"

ENV PYTHONPATH=/app

CMD ["uvicorn", "apps.feedback_service.app:app", "--host", "0.0.0.0", "--port", "8000"]

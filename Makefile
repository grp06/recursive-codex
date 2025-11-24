.PHONY: bootstrap dev stop host-bridge lint test e2e

HOST_BRIDGE_ENV ?= .env

bootstrap:
	bash scripts/bootstrap.sh

dev:
	bash scripts/dev/up.sh
	bash scripts/host_bridge/start.sh --env-file "$(HOST_BRIDGE_ENV)"

stop:
	bash scripts/host_bridge/stop.sh
	bash scripts/dev/down.sh

host-bridge:
	bash scripts/host_bridge/start.sh --env-file "$(HOST_BRIDGE_ENV)"

lint:
	uv run --extra dev ruff format --check
	uv run --extra dev ruff check
	uv run --extra dev mypy packages apps

test:
	uv run --extra dev pytest

e2e:
	uv run --extra dev pytest -m e2e

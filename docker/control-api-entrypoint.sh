#!/bin/sh
set -eu

exec python -m uvicorn server.control_api.app:app --host "${CONTROL_API_HOST:-0.0.0.0}" --port "${CONTROL_API_PORT:-8000}"

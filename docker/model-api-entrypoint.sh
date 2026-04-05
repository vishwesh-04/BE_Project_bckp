#!/bin/sh
set -e

exec python -m uvicorn server.model_api.app:app --host "${MODEL_API_HOST:-0.0.0.0}" --port "${MODEL_API_PORT:-8000}"

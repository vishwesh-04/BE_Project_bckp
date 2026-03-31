#!/bin/sh
set -eu

exec python -m uvicorn server.inference_api.app:app --host "${INFERENCE_API_HOST:-0.0.0.0}" --port "${INFERENCE_API_PORT:-8001}"

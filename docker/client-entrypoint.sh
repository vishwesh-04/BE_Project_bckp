#!/bin/sh
set -eu

if [ -z "${CLIENT_ID:-}" ]; then
  echo "CLIENT_ID is required"
  exit 1
fi

FLOWER_SUPERNODE_BIN=${FLOWER_SUPERNODE_BIN:-flower-supernode}
APP_DIR=${APP_DIR:-/app}
CLIENT_APP=${CLIENT_APP:-client.client_app:app}
CLIENT_SERVER_ADDRESS=${CLIENT_SERVER_ADDRESS:-127.0.0.1:45678}
CLIENT_PERSONALIZE=${CLIENT_PERSONALIZE:-false}
CLIENT_CONTROL_PORT=${CLIENT_CONTROL_PORT:-8000}

# Start the Sidecar API in the background
uvicorn client.control_api.app:app --host 0.0.0.0 --port "${CLIENT_CONTROL_PORT}" &

exec "${FLOWER_SUPERNODE_BIN}" \
  --insecure \
  --dir "${APP_DIR}" \
  --superlink "${CLIENT_SERVER_ADDRESS}" \
  --node-config "client_id=\"${CLIENT_ID}\",client_personalize=\"${CLIENT_PERSONALIZE}\"" \
  "${CLIENT_APP}"

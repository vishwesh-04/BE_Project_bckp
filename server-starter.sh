#!/bin/sh
set -eu
. "/home/vishwesh/Documents/BE Project 2026/.venv/bin/activate"

# Updated to use the exact binaries from your environment
FLOWER_SERVER_APP_BIN=${FLOWER_SERVER_APP_BIN:-flwr-serverapp}
FLOWER_SUPERLINK_BIN=${FLOWER_SUPERLINK_BIN:-flower-superlink}
APP_DIR=${APP_DIR:-"/home/vishwesh/Documents/BE Project 2026/BE_Project/My-refractored"}
SERVER_APP=${SERVER_APP:-server.server_app:app}
SERVER_ADDRESS=${SERVER_ADDRESS:-0.0.0.0:45678}
SERVER_CONTROL_ADDRESS=${SERVER_CONTROL_ADDRESS:-127.0.0.1:9091}
SUPERLINK_STARTUP_DELAY=${SUPERLINK_STARTUP_DELAY:-2}

# Start the SuperLink (the central orchestrator that handles connections)
"${FLOWER_SUPERLINK_BIN}" \
  --insecure \
  --fleet-api-address "${SERVER_ADDRESS}" \
  --control-api-address "${SERVER_CONTROL_ADDRESS}" &
SUPERLINK_PID=$!

cleanup() {
  kill "${SUPERLINK_PID}" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

sleep "${SUPERLINK_STARTUP_DELAY}"

# Start the ServerApp (contains your custom strategy and orchestration logic)
exec "${FLOWER_SERVER_APP_BIN}" \
  --insecure \
  --dir "${APP_DIR}" \
  --superlink "${SERVER_CONTROL_ADDRESS}" \
  "${SERVER_APP}"
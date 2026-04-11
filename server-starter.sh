#!/bin/sh
set -eu
. "/home/vishwesh/Documents/BE Project 2026/.venv/bin/activate"
FLOWER_SERVER_APP_BIN=${FLOWER_SERVER_APP_BIN:-flower-server-app}
FLOWER_SUPERLINK_BIN=${FLOWER_SUPERLINK_BIN:-flower-superlink}
APP_DIR=${APP_DIR:-"/home/vishwesh/Documents/BE Project 2026/BE_Project/My-refractored"}
SERVER_APP=${SERVER_APP:-server.server_app:app}
SERVER_ADDRESS=${SERVER_ADDRESS:-0.0.0.0:45678}
SERVER_DRIVER_ADDRESS=${SERVER_DRIVER_ADDRESS:-127.0.0.1:9091}
SUPERLINK_STARTUP_DELAY=${SUPERLINK_STARTUP_DELAY:-2}

"${FLOWER_SUPERLINK_BIN}" \
  --insecure \
  --fleet-api-address "${SERVER_ADDRESS}" \
  --driver-api-address "${SERVER_DRIVER_ADDRESS}" &
SUPERLINK_PID=$!

cleanup() {
  kill "${SUPERLINK_PID}" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

sleep "${SUPERLINK_STARTUP_DELAY}"

exec "${FLOWER_SERVER_APP_BIN}" \
  --insecure \
  --dir "${APP_DIR}" \
  --superlink "${SERVER_DRIVER_ADDRESS}" \
  "${SERVER_APP}"

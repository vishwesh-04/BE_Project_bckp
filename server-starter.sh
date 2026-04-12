#!/bin/sh
# server-starter.sh — Launch the Flower server infrastructure (SuperLink + SuperExec).
#
# Usage:
#   ./server-starter.sh                                          # use defaults from .env
#   ./server-starter.sh --fleet-api-address 0.0.0.0:45678
#   ./server-starter.sh --appio-address 127.0.0.1:9091
#   ./server-starter.sh --startup-delay 3
#   ./server-starter.sh --log-level DEBUG
#   ./server-starter.sh --help                                   # show all options
#
# All flags are passed through to `python -m server`.
# Unset values fall back to the .env file / environment variables.

set -eu

# ── Activate the project venv ──────────────────────────────────────────────
VENV_ACTIVATE=${VENV_ACTIVATE:-"/home/vishwesh/Documents/BE Project 2026/.venv/bin/activate"}
if [ -f "${VENV_ACTIVATE}" ]; then
  # shellcheck disable=SC1090
  . "${VENV_ACTIVATE}"
fi

# ── Change to project root ─────────────────────────────────────────────────
APP_DIR=${APP_DIR:-"$(cd "$(dirname "$0")" && pwd)"}
cd "${APP_DIR}"

echo "[SERVER-STARTER] Working directory: ${APP_DIR}"
echo "[SERVER-STARTER] Python: $(python --version 2>&1)"
echo "[SERVER-STARTER] Launching server..."
echo ""

# Pass all CLI arguments through to python -m server
exec python -m server "$@"
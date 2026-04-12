#!/bin/sh
# client-starter.sh — Launch this node as a standalone Flower SuperNode.
#
# Usage:
#   ./client-starter.sh                            # use defaults from .env
#   ./client-starter.sh --client-id 1
#   ./client-starter.sh --superlink 127.0.0.1:45678 --client-id 2
#   ./client-starter.sh --epochs 5 --batch-size 64 --lr 0.0005
#   ./client-starter.sh --help                     # show all options
#
# All flags are passed through to `python -m client`.
# Unset values fall back to the .env file / environment variables.

set -eu

# ── Activate the project venv ──────────────────────────────────────────────
VENV_ACTIVATE=${VENV_ACTIVATE:-"/home/vishwesh/Documents/BE Project 2026/.venv/bin/activate"}
if [ -f "${VENV_ACTIVATE}" ]; then
  # shellcheck disable=SC1090
  . "${VENV_ACTIVATE}"
fi

# ── Change to project root so relative .env / data paths resolve correctly ─
APP_DIR=${APP_DIR:-"$(cd "$(dirname "$0")" && pwd)"}
cd "${APP_DIR}"

echo "[CLIENT-STARTER] Working directory: ${APP_DIR}"
echo "[CLIENT-STARTER] Python: $(python --version 2>&1)"
echo "[CLIENT-STARTER] Launching supernode..."
echo ""

# Pass all CLI arguments through to python -m client
exec python -m client "$@"

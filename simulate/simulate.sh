#!/usr/bin/env bash
# simulate/simulate.sh — Launch a full FL simulation: server + N clients.
#
# Usage:
#   ./simulate/simulate.sh                        # 10 clients, defaults
#   ./simulate/simulate.sh --num-clients 5
#   ./simulate/simulate.sh --num-clients 10 --rounds 4 --epochs 3
#   ./simulate/simulate.sh --num-clients 10 --skip-partition   # reuse existing data
#
# What this script does:
#   1. Activates the venv
#   2. Partitions data into N client splits (unless --skip-partition)
#   3. Sets simulation environment variables
#   4. Starts the Flower server (SuperLink + SuperExec) in background
#   5. Submits a run with `flwr run . local-insecure`
#   6. Starts N SuperNode clients in background (each with unique client-id)
#   7. Waits for server to finish; cleans up all processes on Ctrl+C

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
NUM_CLIENTS="${NUM_CLIENTS:-10}"
ROUNDS="${ROUNDS:-4}"
LOCAL_EPOCHS="${LOCAL_EPOCHS:-3}"
BATCH_SIZE="${BATCH_SIZE:-32}"
LR="${LR:-0.001}"
SKIP_PARTITION="${SKIP_PARTITION:-false}"
DATA_PREFIX="${DATA_PREFIX:-sim_client}"
SUPERLINK_STARTUP_DELAY="${SUPERLINK_STARTUP_DELAY:-3}"
RUN_SUBMIT_DELAY="${RUN_SUBMIT_DELAY:-5}"
CLIENT_START_DELAY="${CLIENT_START_DELAY:-0.5}"

FLEET_API_ADDRESS="${FLEET_API_ADDRESS:-0.0.0.0:45678}"
SUPERLINK_CONNECT_ADDRESS="${SUPERLINK_CONNECT_ADDRESS:-127.0.0.1:45678}"
APPIO_ADDRESS="${APPIO_ADDRESS:-127.0.0.1:9091}"

# ── Parse CLI overrides ────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --num-clients)    NUM_CLIENTS="$2";    shift 2 ;;
    --rounds)         ROUNDS="$2";         shift 2 ;;
    --epochs)         LOCAL_EPOCHS="$2";   shift 2 ;;
    --batch-size)     BATCH_SIZE="$2";     shift 2 ;;
    --lr)             LR="$2";             shift 2 ;;
    --skip-partition) SKIP_PARTITION=true; shift ;;
    --help|-h)
      echo "Usage: $0 [--num-clients N] [--rounds R] [--epochs E] [--batch-size B] [--lr F] [--skip-partition]"
      exit 0 ;;
    *) echo "[SIM] Unknown option: $1"; exit 1 ;;
  esac
done

# ── Resolve paths ──────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_ACTIVATE="${VENV_ACTIVATE:-/home/vishwesh/Documents/BE Project 2026/.venv/bin/activate}"
DATA_DIR="${APP_DIR}/data"

# ── Activate venv ──────────────────────────────────────────────────────────────
if [[ -f "${VENV_ACTIVATE}" ]]; then
  # shellcheck disable=SC1090
  source "${VENV_ACTIVATE}"
fi
cd "${APP_DIR}"
mkdir -p "${APP_DIR}/logs"

echo "╔══════════════════════════════════════════════════════════════════════╗"
printf "║  MedLink FL Simulation — %2s clients, %s rounds                      ║\n" "${NUM_CLIENTS}" "${ROUNDS}"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "[SIM] App dir      : ${APP_DIR}"
echo "[SIM] Clients      : ${NUM_CLIENTS}"
echo "[SIM] Rounds       : ${ROUNDS}"
echo "[SIM] Local epochs : ${LOCAL_EPOCHS}"
echo "[SIM] Batch size   : ${BATCH_SIZE}"
echo "[SIM] Learning rate: ${LR}"
echo ""

# ── Step 1: Partition data ─────────────────────────────────────────────────────
if [[ "${SKIP_PARTITION}" == "false" ]]; then
  echo "[SIM] Partitioning data into ${NUM_CLIENTS} client splits..."
  python simulate/partition_data.py \
    --num-clients "${NUM_CLIENTS}" \
    --data-dir "${DATA_DIR}" \
    --prefix "${DATA_PREFIX}"
  echo ""
fi

# ── Step 2: Export simulation environment vars directly ───────────────────────
# We export directly instead of sourcing a file to avoid path-with-spaces issues.
echo "[SIM] Configuring simulation environment..."
export NUM_CLIENTS MIN_CLIENTS="${NUM_CLIENTS}"
export TRAINING_SESSION_ROUNDS="${ROUNDS}"
export LOCAL_EPOCHS BATCH_SIZE LEARNING_RATE="${LR}"
export SERVER_ADDRESS="${FLEET_API_ADDRESS}"
export CLIENT_SERVER_ADDRESS="${SUPERLINK_CONNECT_ADDRESS}"
export SERVER_APPIO_ADDRESS="${APPIO_ADDRESS}"
export QUORUM_WAIT_TIMEOUT=15
export SESSION_COOLDOWN_SECONDS=30
export SECAGG_ENABLED=false

for ((i=1; i<=NUM_CLIENTS; i++)); do
  export "CLIENT_${i}_TRAINING_SET=${DATA_DIR}/${DATA_PREFIX}_${i}_train.csv"
  export "CLIENT_${i}_TESTING_SET=${DATA_DIR}/${DATA_PREFIX}_${i}_test.csv"
done
echo "[SIM] Environment ready."
echo ""

# ── PID tracking for cleanup ───────────────────────────────────────────────────
SERVER_PID=""
CLIENT_PIDS=()

cleanup() {
  echo ""
  echo "[SIM] ── Cleaning up processes ─────────────────────────────────────────"
  for pid in "${CLIENT_PIDS[@]:-}"; do
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  done
  [[ -n "${SERVER_PID}" ]] && kill "${SERVER_PID}" 2>/dev/null || true
  echo "[SIM] Done."
}
trap cleanup INT TERM EXIT

# ── Step 3: Start server in background ───────────────────────────────────────
echo "[SIM] Starting FL server..."
python -m server \
  --fleet-api-address "${FLEET_API_ADDRESS}" \
  --appio-address "${APPIO_ADDRESS}" \
  --startup-delay "${SUPERLINK_STARTUP_DELAY}" \
  --log-level INFO \
  > "${APP_DIR}/logs/sim_server.log" 2>&1 &
SERVER_PID=$!
echo "[SIM] Server started (pid=${SERVER_PID}). Log: logs/sim_server.log"
echo "[SIM] Waiting ${SUPERLINK_STARTUP_DELAY}s for SuperLink + SuperExec to bind..."
sleep "${SUPERLINK_STARTUP_DELAY}"

# ── Step 4: Submit run via flwr run ──────────────────────────────────────────
echo "[SIM] Waiting ${RUN_SUBMIT_DELAY}s more before submitting run..."
sleep "${RUN_SUBMIT_DELAY}"
echo "[SIM] Submitting training run: 'flwr run . local-insecure'"
flwr run . local-insecure \
  --run-config "num_rounds=${ROUNDS} local_epochs=${LOCAL_EPOCHS} batch_size=${BATCH_SIZE} learning_rate=${LR}" \
  2>&1 | tee "${APP_DIR}/logs/sim_flwr_run.log"
echo ""

# ── Step 5: Start N clients in background ────────────────────────────────────
echo "[SIM] Starting ${NUM_CLIENTS} SuperNode clients..."
for ((i=1; i<=NUM_CLIENTS; i++)); do
  CLIENT_LOG="${APP_DIR}/logs/sim_client_${i}.log"
  python -m client \
    --superlink "${SUPERLINK_CONNECT_ADDRESS}" \
    --client-id "${i}" \
    --epochs "${LOCAL_EPOCHS}" \
    --batch-size "${BATCH_SIZE}" \
    --lr "${LR}" \
    --log-level INFO \
    > "${CLIENT_LOG}" 2>&1 &
  pid=$!
  CLIENT_PIDS+=("${pid}")
  echo "[SIM]   Client ${i:>2} started (pid=${pid}). Log: logs/sim_client_${i}.log"
  sleep "${CLIENT_START_DELAY}"
done

echo ""
echo "[SIM] ── All ${NUM_CLIENTS} clients launched ─────────────────────────────────────────"
echo "[SIM] Press Ctrl+C to stop. Tailing server log below:"
echo "──────────────────────────────────────────────────────────────────────────"
echo ""

# ── Step 6: Tail server log and wait ──────────────────────────────────────────
tail -f "${APP_DIR}/logs/sim_server.log" &
TAIL_PID=$!

wait "${SERVER_PID}" || true
kill "${TAIL_PID}" 2>/dev/null || true

echo ""
echo "[SIM] ── Server finished ──────────────────────────────────────────────────"
echo "[SIM] Individual client logs are in: logs/sim_client_N.log"
echo "[SIM] Simulation complete."

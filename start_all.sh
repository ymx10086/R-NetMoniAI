#!/usr/bin/env bash
set -euo pipefail

# One-command launcher for NetMoniAI backend + frontend.
# Usage:
#   ./start_all.sh
# Optional env vars:
#   ENV_NAME=netmoniai BACKEND_PORT=8000 FRONTEND_PORT=3000 NETMON_INTERFACE=wlp9s0 ./start_all.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="${ENV_NAME:-netmoniai}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
HEALTH_TIMEOUT_SECS="${HEALTH_TIMEOUT_SECS:-60}"

RUNTIME_DIR="${ROOT_DIR}/.runtime"
BACKEND_LOG="${RUNTIME_DIR}/backend.log"
FRONTEND_LOG="${RUNTIME_DIR}/frontend.log"
BACKEND_PID_FILE="${RUNTIME_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUNTIME_DIR}/frontend.pid"
BACKEND_PID=""
FRONTEND_PID=""

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERROR] Required command not found: $1"
    exit 1
  fi
}

check_port_available() {
  local port="$1"
  local role="$2"
  local pid
  pid="$(lsof -t -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
  if [[ -n "${pid}" ]]; then
    echo "[ERROR] ${role} port ${port} is already in use by PID ${pid}."
    ps -p "${pid}" -o pid,command || true
    echo "[HINT] Stop existing process or use a different port:"
    echo "       BACKEND_PORT=<port> FRONTEND_PORT=<port> ./start_all.sh"
    exit 1
  fi
}

cleanup_pid_file() {
  local pid_file="$1"
  if [[ -f "${pid_file}" ]]; then
    local pid
    pid="$(cat "${pid_file}" 2>/dev/null || true)"
    if [[ -z "${pid}" ]] || ! kill -0 "${pid}" >/dev/null 2>&1; then
      rm -f "${pid_file}"
    fi
  fi
}

wait_for_http() {
  local url="$1"
  local name="$2"
  local timeout="$3"
  local elapsed=0

  until curl -fsS "$url" >/dev/null 2>&1; do
    sleep 1
    elapsed=$((elapsed + 1))
    if [[ "$elapsed" -ge "$timeout" ]]; then
      echo "[ERROR] ${name} health check timed out: ${url}"
      return 1
    fi
  done

  echo "[OK] ${name} is ready: ${url}"
}

cleanup() {
  echo
  echo "[INFO] Stopping NetMoniAI services..."

  if [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" >/dev/null 2>&1; then
    kill "${FRONTEND_PID}" >/dev/null 2>&1 || true
  fi

  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" >/dev/null 2>&1; then
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
  fi

  rm -f "${BACKEND_PID_FILE}" "${FRONTEND_PID_FILE}"
}

trap cleanup EXIT INT TERM

require_cmd conda
require_cmd npm
require_cmd curl
require_cmd lsof

mkdir -p "${RUNTIME_DIR}"
cleanup_pid_file "${BACKEND_PID_FILE}"
cleanup_pid_file "${FRONTEND_PID_FILE}"

if [[ ! -f "${ROOT_DIR}/backend/app.py" || ! -f "${ROOT_DIR}/frontend/package.json" ]]; then
  echo "[ERROR] Please run this script from the NetMoniAI repository root."
  exit 1
fi

check_port_available "${BACKEND_PORT}" "Backend"
check_port_available "${FRONTEND_PORT}" "Frontend"

echo "[INFO] Starting backend on port ${BACKEND_PORT} (conda env: ${ENV_NAME})..."
if [[ -n "${NETMON_INTERFACE:-}" ]]; then
  (
    cd "${ROOT_DIR}"
    NETMON_INTERFACE="${NETMON_INTERFACE}" APP_PORT="${BACKEND_PORT}" BACKEND_PORT="${BACKEND_PORT}" PYTHONUNBUFFERED=1 conda run --no-capture-output -n "${ENV_NAME}" python backend/app.py
  ) >"${BACKEND_LOG}" 2>&1 &
else
  (
    cd "${ROOT_DIR}"
    APP_PORT="${BACKEND_PORT}" BACKEND_PORT="${BACKEND_PORT}" PYTHONUNBUFFERED=1 conda run --no-capture-output -n "${ENV_NAME}" python backend/app.py
  ) >"${BACKEND_LOG}" 2>&1 &
fi
BACKEND_PID=$!
echo "${BACKEND_PID}" > "${BACKEND_PID_FILE}"

wait_for_http "http://127.0.0.1:${BACKEND_PORT}/gcstatuses" "Backend" "${HEALTH_TIMEOUT_SECS}"

echo "[INFO] Starting frontend on port ${FRONTEND_PORT}..."
(
  cd "${ROOT_DIR}/frontend"
  PORT="${FRONTEND_PORT}" \
  BROWSER=none \
  REACT_APP_API_URL="http://127.0.0.1:${BACKEND_PORT}" \
  REACT_APP_WS_URL="ws://127.0.0.1:${BACKEND_PORT}/ws" \
  npm start
) >"${FRONTEND_LOG}" 2>&1 &
FRONTEND_PID=$!
echo "${FRONTEND_PID}" > "${FRONTEND_PID_FILE}"

wait_for_http "http://127.0.0.1:${FRONTEND_PORT}" "Frontend" "${HEALTH_TIMEOUT_SECS}"

echo ""
echo "[READY] NetMoniAI is running"
echo "- Frontend: http://127.0.0.1:${FRONTEND_PORT}"
echo "- Backend : http://127.0.0.1:${BACKEND_PORT}"
echo "- WS      : ws://127.0.0.1:${BACKEND_PORT}/ws"
echo ""
echo "[LOGS]"
echo "- Backend log : ${BACKEND_LOG}"
echo "- Frontend log: ${FRONTEND_LOG}"
echo ""
echo "Press Ctrl+C to stop both services."

while true; do
  if ! kill -0 "${BACKEND_PID}" >/dev/null 2>&1; then
    echo "[ERROR] Backend process exited. Check: ${BACKEND_LOG}"
    exit 1
  fi

  if ! kill -0 "${FRONTEND_PID}" >/dev/null 2>&1; then
    echo "[ERROR] Frontend process exited. Check: ${FRONTEND_LOG}"
    exit 1
  fi

  sleep 2
done


# ENV_NAME=netmoniai BACKEND_PORT=8000 FRONTEND_PORT=3000 NETMON_INTERFACE=wlp9s0 ./start_all.sh

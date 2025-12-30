#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON:-python3.13}"
PY_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv-debug-py${PY_VERSION}}"

if [[ ! -d "${VENV_DIR}" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "${ROOT_DIR}/requirements.txt"

HOST="${SHARP_GUI_HOST:-127.0.0.1}"
PORT="${SHARP_GUI_PORT:-7860}"

if [[ "${SHARP_GUI_NO_BROWSER:-0}" != "1" ]]; then
  (sleep 1 && open "http://${HOST}:${PORT}") >/dev/null 2>&1 &
fi

export PYTHONUNBUFFERED=1
echo "Starting SHARP Studio GUI with debug logs on http://${HOST}:${PORT}"
sharp gui --host "${HOST}" --port "${PORT}" -v

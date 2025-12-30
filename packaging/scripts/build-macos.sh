#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
PY_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv-packaging-py${PY_VERSION}}"

if [[ ! -d "${VENV_DIR}" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "${ROOT_DIR}/requirements.txt" pyinstaller

cd "${ROOT_DIR}"
pyinstaller --clean --noconfirm "${ROOT_DIR}/packaging/pyinstaller/sharp-studio.spec"

APP_PATH="${ROOT_DIR}/dist/SHARP Studio.app"
DMG_PATH="${ROOT_DIR}/dist/SHARP-Studio-unsigned.dmg"

if [[ -d "${APP_PATH}" ]]; then
  hdiutil create -volname "SHARP Studio" -srcfolder "${APP_PATH}" -ov -format UDZO "${DMG_PATH}"
  echo "Created ${DMG_PATH}"
else
  echo "Expected app not found at ${APP_PATH}"
  exit 1
fi

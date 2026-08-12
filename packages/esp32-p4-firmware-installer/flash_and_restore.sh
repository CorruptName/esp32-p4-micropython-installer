#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"

if ! "$PYTHON" -c "import esptool, serial" >/dev/null 2>&1; then
    echo "Installing required Python packages..."
    "$PYTHON" -m pip install -r requirements.txt
fi

exec "$PYTHON" enable_espnow.py "$@"

#!/usr/bin/env sh
# Compatibility launcher for the full ESP32-P4 MicroPython provisioning flow.

set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

echo "The C6-only backup/restore flow is no longer supported by this project."
echo "Starting the full ESP32-P4 MicroPython installer instead."
echo

exec "$SCRIPT_DIR/packages/esp32-p4-firmware-installer/install_firmware.sh" "$@"
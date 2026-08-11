#!/usr/bin/env bash
# Install the matched ESP32-C6 ESP-NOW firmware through the ESP32-P4 OTA host.

set -euo pipefail

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m'
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PORT="${1:-}"
readonly BACKUP_FILE="$SCRIPT_DIR/p4-flash-backup.bin"

if [[ -z "$PORT" ]]; then
    printf "%bError: serial port not specified%b\n" "$RED" "$NC"
    echo "Usage: $0 /dev/ttyACM0"
    exit 1
fi

if ! command -v python >/dev/null 2>&1; then
    printf "%bError: python was not found.%b\n" "$RED" "$NC"
    exit 1
fi

if ! python -m esptool version >/dev/null 2>&1; then
    printf "%bError: the Python esptool module was not found.%b\n" "$RED" "$NC"
    echo "Install ESP-IDF or run: python -m pip install esptool"
    exit 1
fi

cd "$SCRIPT_DIR"
printf "%b=== ESP32-P4/C6 ESP-NOW Enabler ===%b\n" "$GREEN" "$NC"
echo "Port: $PORT"
echo "ESP-Hosted: custom 2.7.0 (dd95bdf3316fc8c6110b387855033a26c0aa2447)"
echo

echo "Verifying coordinated release artifacts..."
python update_firmware.py

has_backup=false
printf "\n%bBack up the first 8 MiB of P4 flash before continuing? [Y/n] %b" "$YELLOW" "$NC"
read -r response
if [[ ! "$response" =~ ^([nN]|[nN][oO])$ ]]; then
    echo "Place the P4 in download mode now."
    read -r -p "Press Enter when the board is ready... "
    python -m esptool --chip esp32p4 -p "$PORT" -b 460800 \
        --before default_reset --after hard_reset \
        read_flash 0x0 0x800000 "$BACKUP_FILE"
    printf "%bBackup saved to %s%b\n" "$GREEN" "$BACKUP_FILE" "$NC"
    has_backup=true
fi

echo
echo "Place the P4 in download mode for the OTA installer."
read -r -p "Press Enter when the board is ready... "

python -m esptool --chip esp32p4 -p "$PORT" -b 460800 \
    --before default_reset --after hard_reset write_flash \
    0x2000 binaries/bootloader.bin \
    0x8000 binaries/partition-table.bin \
    0xd000 binaries/ota_data_initial.bin \
    0x10000 modified_ota_host/host_performs_slave_ota.bin \
    0x410000 binaries/storage.bin

printf "\n%bOTA installer written.%b\n" "$GREEN" "$NC"
echo "Reset the board and monitor its serial output until it reports that the"
echo "slave OTA completed and the C6 rebooted."

if [[ "$has_backup" == true ]]; then
    echo
    printf "%bRestore the original P4 flash only after C6 OTA completes.%b\n" "$YELLOW" "$NC"
    read -r -p "Restore $BACKUP_FILE now? [y/N] " response
    if [[ "$response" =~ ^([yY]|[yY][eE][sS])$ ]]; then
        echo "Place the P4 in download mode again."
        read -r -p "Press Enter when the board is ready... "
        python -m esptool --chip esp32p4 -p "$PORT" -b 460800 \
            --before default_reset --after hard_reset \
            write_flash 0x0 "$BACKUP_FILE"
        printf "%bOriginal P4 flash restored.%b\n" "$GREEN" "$NC"
    else
        echo "Restore later with:"
        echo "python -m esptool --chip esp32p4 -p '$PORT' -b 460800 write_flash 0x0 '$BACKUP_FILE'"
    fi
fi
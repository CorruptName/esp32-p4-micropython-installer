#!/usr/bin/env python3
"""Select and flash ESP32-P4 MicroPython firmware with optional ESP-NOW."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


PACKAGE_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = PACKAGE_DIR / "firmware-manifest.json"
with MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
    MANIFEST = json.load(manifest_file)

ARTIFACTS = MANIFEST["artifacts"]
INSTALLER_IMAGES = (
    ("0x2000", "firmware/installer/bootloader.bin"),
    ("0x8000", "firmware/installer/partition-table.bin"),
    ("0xd000", "firmware/installer/ota_data_initial.bin"),
    ("0x10000", "firmware/installer/host_performs_slave_ota.bin"),
    ("0x410000", "firmware/installer/storage.bin"),
)
DEVICES = MANIFEST["boards"]
REQUIRED_MARKERS = {
    "C6_ELF_IDENTITY_VERIFIED",
    "C6_ESPNOW_VERIFIED",
    "C6 ESP-NOW installation completed successfully",
}
FAILURE_MARKERS = {
    "C6 ESP-NOW verification failed",
    "C6 ELF identity mismatch",
    "C6 OTA activation did not produce a working ESP-NOW service",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_artifacts() -> None:
    print("Verifying bundled firmware...")
    for name, metadata in ARTIFACTS.items():
        path = PACKAGE_DIR / name
        if not path.is_file():
            raise RuntimeError(f"Missing bundled firmware: {name}")
        if path.stat().st_size != metadata["size"]:
            raise RuntimeError(f"Size mismatch for {name}")
        actual_hash = sha256(path)
        if actual_hash != metadata["sha256"]:
            raise RuntimeError(
                f"SHA-256 mismatch for {name}\n"
                f"  expected: {metadata['sha256']}\n"
                f"  actual:   {actual_hash}"
            )
        print(f"  OK  {name}")


def choose_device(requested: str | None) -> str:
    if requested:
        return requested
    print("Select the target device:")
    keys = list(DEVICES)
    for index, key in enumerate(keys, start=1):
        print(f"  {index}. {DEVICES[key]['label']}")
    while True:
        response = input("Device number: ").strip()
        if response.isdigit() and 1 <= int(response) <= len(keys):
            return keys[int(response) - 1]
        print("Enter one of the listed numbers.")


def choose_port(requested: str | None) -> str:
    if requested:
        return requested
    try:
        from serial.tools import list_ports
    except ImportError as error:
        raise RuntimeError(
            "pyserial is required. Install it with: python -m pip install pyserial"
        ) from error

    while True:
        ports = sorted(list_ports.comports(), key=lambda item: item.device)
        if not ports:
            input("No serial ports found. Connect the board and press Enter to rescan...")
            continue
        print("Select the board's serial port:")
        for index, item in enumerate(ports, start=1):
            print(f"  {index}. {item.device} - {item.description}")
        response = input("Port number, or R to rescan: ").strip()
        if response.lower() == "r":
            continue
        if response.isdigit() and 1 <= int(response) <= len(ports):
            return ports[int(response) - 1].device
        print("Enter one of the listed numbers or R.")


def choose_espnow(requested: str | None) -> bool:
    if requested:
        return requested == "yes"
    while True:
        response = input("Enable ESP-NOW support? [y/N]: ").strip().lower()
        if response in ("", "n", "no"):
            return False
        if response in ("y", "yes"):
            return True
        print("Enter Y or N.")


def esptool_command(port: str, images: tuple[tuple[str, str], ...]) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "esptool",
        "--chip",
        "esp32p4",
        "-p",
        port,
        "-b",
        "460800",
        "--before",
        "no-reset",
        "--after",
        "no-reset",
        "write-flash",
    ]
    for offset, name in images:
        command.extend((offset, str(PACKAGE_DIR / name)))
    return command


def esptool_erase_command(port: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "esptool",
        "--chip",
        "esp32p4",
        "-p",
        port,
        "--before",
        "no-reset",
        "--after",
        "no-reset",
        "erase-flash",
    ]


def wait_for_download_mode(port: str, message: str) -> str:
    try:
        from serial.tools import list_ports
    except ImportError as error:
        raise RuntimeError(
            "pyserial is required. Install it with: python -m pip install pyserial"
        ) from error

    original_ports = {item.device for item in list_ports.comports()}
    print()
    print(message)
    print("Waiting for a new download-mode serial port; no keyboard input is required...")
    last_devices: tuple[str, ...] = ()
    while True:
        available = {item.device for item in list_ports.comports()}
        new_ports = sorted(available - original_ports)
        reused_port = [port] if port in available else []
        candidates = tuple(dict.fromkeys(new_ports + reused_port))
        if candidates != last_devices:
            print("Checking download-mode ports: " + ", ".join(candidates))
            last_devices = candidates

        for candidate in candidates:
            probe_command = [
                sys.executable,
                "-m",
                "esptool",
                "--chip",
                "esp32p4",
                "-p",
                candidate,
                "--before",
                "no-reset",
                "--after",
                "no-reset",
                "--connect-attempts",
                "1",
                "chip-id",
            ]
            result = subprocess.run(
                probe_command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if result.returncode == 0:
                print(f"P4 bootloader detected on {candidate}.")
                return candidate
        time.sleep(0.5)


def run_flash(command: list[str], dry_run: bool) -> None:
    print("Command:", subprocess.list2cmdline(command))
    if dry_run:
        return
    subprocess.run(command, check=True)


def monitor_verification(port: str, timeout: float, prompt_for_reset: bool = False) -> None:
    try:
        import serial
    except ImportError as error:
        raise RuntimeError(
            "pyserial is required. Install it with: python -m pip install pyserial"
        ) from error

    print()
    print(f"Opening {port} before reset so no boot output is missed...")
    deadline = time.monotonic() + timeout
    found: set[str] = set()
    connection = None
    reset_requested = not prompt_for_reset
    try:
        while time.monotonic() < deadline:
            if connection is None:
                try:
                    connection = serial.Serial(port, 115200, timeout=0.25)
                    print(f"Connected to {port}.")
                    if not reset_requested:
                        print("Press the physical reset button now.")
                        reset_requested = True
                        deadline = time.monotonic() + timeout
                        print(
                            f"Monitoring {port} for C6 verification "
                            f"(timeout: {timeout:.0f}s)..."
                        )
                except serial.SerialException:
                    time.sleep(0.5)
                    continue

            try:
                raw_line = connection.readline()
            except serial.SerialException:
                print(f"{port} re-enumerated; waiting to reconnect...")
                try:
                    connection.close()
                except serial.SerialException:
                    pass
                connection = None
                time.sleep(0.5)
                continue
            if not raw_line:
                continue
            line = raw_line.decode("utf-8", "replace").rstrip()
            print(line)
            for marker in REQUIRED_MARKERS:
                if marker in line:
                    found.add(marker)
            if any(marker in line for marker in FAILURE_MARKERS):
                raise RuntimeError("The temporary installer reported a verification failure.")
            if found == REQUIRED_MARKERS:
                print("All C6 identity and ESP-NOW verification markers received.")
                return
    finally:
        if connection is not None:
            try:
                connection.close()
            except serial.SerialException:
                pass

    missing = REQUIRED_MARKERS - found
    raise RuntimeError("Verification timed out; missing: " + ", ".join(sorted(missing)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Flash ESP32-P4 MicroPython firmware with optional ESP-NOW support."
    )
    parser.add_argument(
        "port",
        nargs="?",
        help="P4 serial port; omit it to select from detected ports",
    )
    parser.add_argument(
        "--device",
        choices=DEVICES,
        help="Target device; omit it to use the device menu",
    )
    parser.add_argument(
        "--espnow",
        choices=("yes", "no"),
        help="Whether to install ESP-NOW support; omit it to be prompted",
    )
    parser.add_argument(
        "--restore-only",
        action="store_true",
        help="Skip C6 installation and restore the bundled P4 MicroPython image",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Monitor an already-flashed installer, then restore P4 MicroPython",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify files and print flash commands without accessing hardware",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="C6 verification timeout in seconds (default: 120)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.restore_only and args.verify_only:
            raise RuntimeError("--restore-only and --verify-only cannot be combined.")

        device_key = choose_device(args.device)
        port = args.port or ("<selected-port>" if args.dry_run else choose_port(None))
        enable_espnow = choose_espnow(args.espnow)
        if args.verify_only and not enable_espnow:
            raise RuntimeError("--verify-only requires --espnow yes.")
        firmware_mode = "espnow" if enable_espnow else "standard"
        p4_image = DEVICES[device_key][firmware_mode]

        print()
        print(f"Device:   {DEVICES[device_key]['label']}")
        print(f"Port:     {port}")
        print(f"ESP-NOW:  {'enabled' if enable_espnow else 'disabled'}")
        print(f"Firmware: {p4_image}")
        print()
        verify_artifacts()

        if args.verify_only:
            if not args.dry_run:
                print("The temporary installer must already be flashed.")
                monitor_verification(port, args.timeout, prompt_for_reset=True)
        elif enable_espnow and not args.restore_only:
            installer_port = port
            if not args.dry_run:
                installer_port = wait_for_download_mode(
                    port,
                    "Stage 1/2: flash the temporary P4-to-C6 installer."
                )
            installer_command = esptool_command(installer_port, INSTALLER_IMAGES)
            run_flash(installer_command, args.dry_run)
            if not args.dry_run:
                print(
                    "The installer flash is verified and the P4 remains in download mode."
                )
                monitor_verification(port, args.timeout, prompt_for_reset=True)

        restore_port = port
        if not args.dry_run:
            stage = "Stage 2/2" if enable_espnow else "Firmware flash"
            restore_port = wait_for_download_mode(
                port,
                f"{stage}: flash the selected P4 MicroPython firmware.\n"
                "Put the P4 back in download mode now."
            )
        print("Erasing the complete P4 flash before provisioning firmware...")
        run_flash(esptool_erase_command(restore_port), args.dry_run)
        restore_command = esptool_command(restore_port, (("0x0", p4_image),))
        run_flash(restore_command, args.dry_run)

        if not args.dry_run:
            print()
            print("The MicroPython flash is verified.")
            print("Disconnect all board power, then reconnect the Serial UART USB port.")

        if args.dry_run:
            print("Dry run completed successfully; no hardware was accessed.")
        elif enable_espnow:
            print("ESP-NOW installation and P4 MicroPython flash completed successfully.")
        else:
            print("P4 MicroPython flash completed successfully.")
        return 0
    except (RuntimeError, subprocess.CalledProcessError, KeyboardInterrupt) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
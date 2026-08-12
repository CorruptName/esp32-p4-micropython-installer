#!/usr/bin/env python3
"""Verify the coordinated P4/C6 ESP-NOW release artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys


PACKAGE_ROOT = Path(__file__).resolve().parent
ESP_HOSTED_COMMIT = "dd95bdf3316fc8c6110b387855033a26c0aa2447"
ARTIFACTS = {
    "slave_firmware/network_adapter.bin": "6d1f4850000c418767c1d79313db044402804e13465908ccbadd9bb97e1a5642",
    "binaries/storage.bin": "b2d36ded17aeff5c36fc2d472761f4e0f3e91d7fa7734094ba5d4f864a4e0cea",
    "binaries/bootloader.bin": "6634b61e3f8243ccfa2951d5a148eb927c7adad111a4b98a0de490823179d4da",
    "binaries/partition-table.bin": "83f9e26a243bbbb4942757d42a0bf61742cfbb810ae46ca46de8a00ee56b2003",
    "binaries/ota_data_initial.bin": "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f",
    "modified_ota_host/host_performs_slave_ota.bin": "8f7a07357e365f57aefacdba111ef106179d9f8b8b2c5a5f8b45e62f31140feb",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    print(f"ESP-Hosted source: {ESP_HOSTED_COMMIT}")
    valid = True

    for relative_path, expected_hash in ARTIFACTS.items():
        path = PACKAGE_ROOT / relative_path
        if not path.is_file():
            print(f"MISSING  {relative_path}")
            valid = False
            continue

        actual_hash = sha256(path)
        if actual_hash == expected_hash:
            print(f"OK       {relative_path}")
        else:
            print(f"INVALID  {relative_path}")
            print(f"  expected: {expected_hash}")
            print(f"  actual:   {actual_hash}")
            valid = False

    if not valid:
        print("Package verification failed. Do not flash these files.")
        return 1

    print("All release artifacts match the coordinated ESP-NOW package.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
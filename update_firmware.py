#!/usr/bin/env python3
"""Verify the coordinated P4/C6 ESP-NOW release artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


PACKAGE_ROOT = Path(__file__).resolve().parent
PACKAGE_DIR = PACKAGE_ROOT / "packages" / "esp32-p4-firmware-installer"
MANIFEST_PATH = PACKAGE_DIR / "firmware-manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    with MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)

    print(f"ESP-Hosted source: {manifest['sources']['esp_hosted']['commit']}")
    valid = True

    for source_path, package_path in manifest["provenance_copies"].items():
        source = PACKAGE_ROOT / source_path
        packaged = PACKAGE_DIR / package_path
        if not source.is_file() or not packaged.is_file():
            print(f"MISSING  {source_path} or {package_path}")
            valid = False
            continue

        expected_hash = manifest["artifacts"][package_path]["sha256"]
        source_hash = sha256(source)
        packaged_hash = sha256(packaged)
        if source_hash == packaged_hash == expected_hash:
            print(f"OK       {source_path}")
        else:
            print(f"INVALID  {source_path}")
            print(f"  expected: {expected_hash}")
            print(f"  source:   {source_hash}")
            print(f"  packaged: {packaged_hash}")
            valid = False

    if not valid:
        print("Package verification failed. Do not flash these files.")
        return 1

    print("All release artifacts match the coordinated ESP-NOW package.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
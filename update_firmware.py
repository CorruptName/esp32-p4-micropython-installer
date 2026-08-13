#!/usr/bin/env python3
"""Verify the coordinated P4/C6 ESP-NOW release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


PACKAGE_ROOT = Path(__file__).resolve().parent
PACKAGE_DIR = PACKAGE_ROOT / "packages" / "esp32-p4-firmware-installer"
MANIFEST_PATH = PACKAGE_DIR / "firmware-manifest.json"
WAVESHARE_ESPNOW_PACKAGE_PATH = (
    "firmware/p4/waveshare-esp32-p4-4.3-espnow.bin"
)
WAVESHARE_ESPNOW_BUILD_PATH = (
    "build_artifacts/waveshare-esp32-p4-4.3-espnow.bin"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(repository: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def sync_lvgl_firmware(manifest: dict, repository: Path) -> None:
    repository = repository.resolve()
    source = repository / WAVESHARE_ESPNOW_BUILD_PATH
    packaged = PACKAGE_DIR / WAVESHARE_ESPNOW_PACKAGE_PATH

    if not source.is_file():
        raise FileNotFoundError(
            f"Missing lvgl_micropython build artifact: {source}"
        )

    checksum_path = source.with_suffix(source.suffix + ".sha256")
    source_hash = sha256(source)
    if checksum_path.is_file():
        recorded_hash = checksum_path.read_text(encoding="utf-8").split()[0]
        if recorded_hash != source_hash:
            raise RuntimeError(
                f"Build checksum mismatch: expected {recorded_hash}, got {source_hash}"
            )

    packaged.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, packaged)

    manifest["sources"]["lvgl_micropython"]["commit"] = git_commit(repository)
    manifest["artifacts"][WAVESHARE_ESPNOW_PACKAGE_PATH] = {
        "size": packaged.stat().st_size,
        "sha256": source_hash,
    }

    print(f"SYNCED   {source}")
    print(f"  target: {packaged}")
    print(f"  sha256: {source_hash}")
    print(
        "  source: "
        f"{manifest['sources']['lvgl_micropython']['commit']}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize and verify coordinated firmware artifacts."
    )
    parser.add_argument(
        "--sync-lvgl",
        type=Path,
        metavar="REPOSITORY",
        help=(
            "copy the latest Waveshare ESP-NOW build from an "
            "lvgl_micropython checkout and update its manifest metadata"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    with MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)

    if args.sync_lvgl is not None:
        try:
            sync_lvgl_firmware(manifest, args.sync_lvgl)
        except (FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as error:
            print(f"Unable to synchronize lvgl_micropython firmware: {error}")
            return 1

        MANIFEST_PATH.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"ESP-Hosted source: {manifest['sources']['esp_hosted']['commit']}")
    valid = True

    for package_path, metadata in manifest["artifacts"].items():
        packaged = PACKAGE_DIR / package_path
        if not packaged.is_file():
            print(f"MISSING  {package_path}")
            valid = False
            continue

        packaged_size = packaged.stat().st_size
        packaged_hash = sha256(packaged)
        if (
            packaged_size == metadata["size"]
            and packaged_hash == metadata["sha256"]
        ):
            print(f"OK       {package_path}")
        else:
            print(f"INVALID  {package_path}")
            print(f"  expected size:   {metadata['size']}")
            print(f"  packaged size:   {packaged_size}")
            print(f"  expected sha256: {metadata['sha256']}")
            print(f"  packaged sha256: {packaged_hash}")
            valid = False

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
#!/usr/bin/env python3
"""Verify the coordinated P4/C6 ESP-NOW release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request


PACKAGE_ROOT = Path(__file__).resolve().parent
PACKAGE_DIR = PACKAGE_ROOT / "packages" / "esp32-p4-firmware-installer"
MANIFEST_PATH = PACKAGE_DIR / "firmware-manifest.json"
PRODUCER_REPOSITORY = "CorruptName/lvgl_micropython"
PRODUCER_RELEASE_INDEX = "firmware-release.json"
P4_PACKAGE_PATHS = {
    "firmware/p4/esp32-p4.bin",
    "firmware/p4/esp32-p4-espnow.bin",
    "firmware/p4/waveshare-esp32-p4-4.3.bin",
    "firmware/p4/waveshare-esp32-p4-4.3-espnow.bin",
}
REQUIRED_FLASH_LAYOUT = {
    "flash_size_mb": 32,
    "app_offset": "0x10000",
    "app_size": "0x500000",
    "vfs_offset": "0x510000",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def github_request(url: str) -> urllib.request.Request:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "esp32-p4-micropython-installer",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def download(url: str, destination: Path) -> None:
    with urllib.request.urlopen(github_request(url)) as response:
        destination.write_bytes(response.read())


def load_release(tag: str) -> dict:
    if tag == "latest":
        url = (
            f"https://api.github.com/repos/{PRODUCER_REPOSITORY}/releases"
            "?per_page=100"
        )
        with urllib.request.urlopen(github_request(url)) as response:
            releases = json.load(response)
        for release in releases:
            if (
                release["tag_name"].startswith("firmware-v")
                and not release["draft"]
                and not release["prerelease"]
            ):
                return release
        raise RuntimeError("No published firmware-v* producer release found")

    endpoint = "tags/" + urllib.parse.quote(tag, safe="")
    url = f"https://api.github.com/repos/{PRODUCER_REPOSITORY}/releases/{endpoint}"
    with urllib.request.urlopen(github_request(url)) as response:
        return json.load(response)


def sync_producer_release(manifest: dict, requested_tag: str) -> None:
    release = load_release(requested_tag)
    tag = release["tag_name"]
    assets = {asset["name"]: asset for asset in release["assets"]}
    if PRODUCER_RELEASE_INDEX not in assets:
        raise RuntimeError(
            f"Release {tag} has no {PRODUCER_RELEASE_INDEX} asset"
        )

    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        index_path = temporary_path / PRODUCER_RELEASE_INDEX
        download(assets[PRODUCER_RELEASE_INDEX]["browser_download_url"], index_path)
        index = json.loads(index_path.read_text(encoding="utf-8"))

        if index.get("schema_version") != 1:
            raise RuntimeError("Unsupported producer firmware index schema")

        producer = index["producer"]
        compatibility = index["radio_compatibility"]
        if index.get("flash_layout") != REQUIRED_FLASH_LAYOUT:
            raise RuntimeError("Producer release has an unsupported flash layout")
        if (
            producer["esp_hosted_commit"]
            != manifest["sources"]["esp_hosted"]["commit"]
        ):
            raise RuntimeError("ESP-Hosted producer/installer commit mismatch")
        if compatibility["c6_elf_sha256"] != manifest["c6"]["elf_sha256"]:
            raise RuntimeError("P4 producer release does not match bundled C6 firmware")

        staged = []
        package_paths = set()
        for artifact in index["artifacts"].values():
            package_path = artifact["package_path"]
            package_paths.add(package_path)
            filename = artifact["filename"]
            if filename not in assets:
                raise RuntimeError(f"Release {tag} is missing {filename}")

            source = temporary_path / filename
            download(assets[filename]["browser_download_url"], source)
            actual_hash = sha256(source)
            actual_size = source.stat().st_size
            if actual_hash != artifact["sha256"] or actual_size != artifact["size"]:
                raise RuntimeError(f"Producer artifact verification failed: {filename}")
            staged.append((source, package_path, artifact))

        if package_paths != P4_PACKAGE_PATHS:
            missing = sorted(P4_PACKAGE_PATHS - package_paths)
            extra = sorted(package_paths - P4_PACKAGE_PATHS)
            raise RuntimeError(
                f"Producer release is not a complete P4 set; missing={missing}, extra={extra}"
            )

        for source, package_path, artifact in staged:
            destination = PACKAGE_DIR / package_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            manifest["artifacts"][package_path] = {
                "size": artifact["size"],
                "sha256": artifact["sha256"],
            }
            print(f"SYNCED   {tag}/{artifact['filename']}")

        manifest["sources"]["lvgl_micropython"]["commit"] = producer["commit"]
        manifest["sources"]["micropython"]["commit"] = producer[
            "micropython_commit"
        ]
        manifest["sources"]["lvgl"] = {
            "repository": "https://github.com/lvgl/lvgl",
            "commit": producer["lvgl_commit"],
        }
        manifest["toolchain"]["esp_idf"]["commit"] = producer[
            "esp_idf_commit"
        ]
        manifest["release"]["firmware_source"] = {
            "repository": f"https://github.com/{PRODUCER_REPOSITORY}",
            "tag": tag,
            "commit": producer["commit"],
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize and verify coordinated firmware artifacts."
    )
    parser.add_argument(
        "--sync-release",
        metavar="TAG",
        help=(
            "import and pin all four P4 images from an immutable "
            "lvgl_micropython firmware release; use 'latest' to resolve the "
            "newest release before pinning its exact tag and commit"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    with MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)

    if args.sync_release is not None:
        try:
            sync_producer_release(manifest, args.sync_release)
        except (KeyError, RuntimeError, urllib.error.URLError) as error:
            print(f"Unable to synchronize producer firmware release: {error}")
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
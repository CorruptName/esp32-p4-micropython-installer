#!/usr/bin/env python3
"""Verify firmware artifacts and build a deterministic installer archive."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "packages" / "esp32-p4-firmware-installer"
MANIFEST_PATH = PACKAGE_ROOT / "firmware-manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict:
    with MANIFEST_PATH.open(encoding="utf-8") as source:
        return json.load(source)


def verify_artifacts(manifest: dict) -> None:
    for relative_path, metadata in manifest["artifacts"].items():
        path = PACKAGE_ROOT / relative_path
        if not path.is_file():
            raise RuntimeError(f"Missing artifact: {relative_path}")
        if path.stat().st_size != metadata["size"]:
            raise RuntimeError(f"Size mismatch: {relative_path}")
        actual_hash = sha256(path)
        if actual_hash != metadata["sha256"]:
            raise RuntimeError(f"SHA-256 mismatch: {relative_path}")
        print(f"OK  {relative_path}")


def package_files() -> list[Path]:
    return sorted(
        path
        for path in PACKAGE_ROOT.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    )


def build_archive(manifest: dict) -> tuple[Path, Path]:
    release = manifest["release"]
    archive_path = PACKAGE_ROOT.parent / release["archive_name"]
    checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    archive_path.unlink(missing_ok=True)

    with zipfile.ZipFile(
        archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in package_files():
            relative_path = path.relative_to(PACKAGE_ROOT).as_posix()
            archive_name = f"{release['package_directory']}/{relative_path}"
            info = zipfile.ZipInfo(archive_name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((0o755 if path.suffix == ".sh" else 0o644) & 0xFFFF) << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compresslevel=9)

    archive_hash = sha256(archive_path)
    checksum_path.write_text(
        f"{archive_hash}  {archive_path.name}\n", encoding="ascii", newline="\n"
    )
    print(f"Built {archive_path} ({archive_path.stat().st_size} bytes)")
    print(f"SHA-256 {archive_hash}")
    return archive_path, checksum_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify-only", action="store_true", help="Verify inputs without building"
    )
    args = parser.parse_args()

    manifest = load_manifest()
    verify_artifacts(manifest)
    if not args.verify_only:
        build_archive(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

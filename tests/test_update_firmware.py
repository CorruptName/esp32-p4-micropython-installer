from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import update_firmware


class ProducerReleaseImportTests(unittest.TestCase):
    def test_complete_release_is_verified_and_imported(self):
        manifest = json.loads(update_firmware.MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest = copy.deepcopy(manifest)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets_dir = root / "assets"
            package_dir = root / "package"
            assets_dir.mkdir()
            package_dir.mkdir()

            artifacts = {}
            release_assets = []
            for index, package_path in enumerate(sorted(update_firmware.P4_PACKAGE_PATHS)):
                filename = Path(package_path).name
                data = bytes([index + 1]) * (128 + index)
                path = assets_dir / filename
                path.write_bytes(data)
                artifacts[f"artifact-{index}"] = {
                    "filename": filename,
                    "package_path": package_path,
                    "device": "waveshare" if "waveshare" in filename else "dev",
                    "espnow": "espnow" in filename,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
                release_assets.append(
                    {"name": filename, "browser_download_url": str(path)}
                )

            producer = {
                "repository": "https://github.com/CorruptName/lvgl_micropython",
                "commit": "1" * 40,
                "git_ref": "firmware-v-test",
                "micropython_commit": "2" * 40,
                "lvgl_commit": "3" * 40,
                "esp_idf_commit": manifest["toolchain"]["esp_idf"]["commit"],
                "esp_hosted_commit": manifest["sources"]["esp_hosted"]["commit"],
            }
            release_index = {
                "schema_version": 1,
                "producer": producer,
                "radio_compatibility": {
                    "esp_hosted_protocol": "2.7.0",
                    "c6_elf_sha256": manifest["c6"]["elf_sha256"],
                },
                "artifacts": artifacts,
            }
            index_path = assets_dir / update_firmware.PRODUCER_RELEASE_INDEX
            index_path.write_text(json.dumps(release_index), encoding="utf-8")
            release_assets.append(
                {
                    "name": update_firmware.PRODUCER_RELEASE_INDEX,
                    "browser_download_url": str(index_path),
                }
            )
            release = {"tag_name": "firmware-v-test", "assets": release_assets}

            def copy_download(source: str, destination: Path) -> None:
                shutil.copy2(source, destination)

            with (
                mock.patch.object(update_firmware, "PACKAGE_DIR", package_dir),
                mock.patch.object(update_firmware, "load_release", return_value=release),
                mock.patch.object(update_firmware, "download", side_effect=copy_download),
            ):
                update_firmware.sync_producer_release(manifest, "firmware-v-test")

            self.assertEqual(
                manifest["release"]["firmware_source"]["tag"],
                "firmware-v-test",
            )
            self.assertEqual(
                manifest["sources"]["lvgl_micropython"]["commit"],
                producer["commit"],
            )
            for artifact in artifacts.values():
                destination = package_dir / artifact["package_path"]
                self.assertTrue(destination.is_file())
                self.assertEqual(update_firmware.sha256(destination), artifact["sha256"])


if __name__ == "__main__":
    unittest.main()

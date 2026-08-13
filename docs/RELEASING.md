# Firmware and Installer Release Process

The installer treats the four ESP32-P4 images as one atomic compatibility set.
It never downloads firmware while flashing a board.

## Producer Contract

The `CorruptName/lvgl_micropython` repository publishes committed
`firmware-v*` releases containing:

| Artifact ID | Filename | Device | ESP-NOW |
| --- | --- | --- | --- |
| `dev-standard` | `esp32-p4.bin` | Generic ESP32-P4 | No |
| `dev-espnow` | `esp32-p4-espnow.bin` | Generic ESP32-P4 | Yes |
| `waveshare-standard` | `waveshare-esp32-p4-4.3.bin` | Waveshare 4.3-inch | No |
| `waveshare-espnow` | `waveshare-esp32-p4-4.3-espnow.bin` | Waveshare 4.3-inch | Yes |

Each release also contains individual `.sha256` files, `SHA256SUMS`, and
`firmware-release.json`. The index records the producer, MicroPython, LVGL,
ESP-IDF, and ESP-Hosted commits and the required C6 ELF identity.

All four images use a fixed 5 MiB application partition at `0x10000`; FAT VFS
therefore begins at `0x510000`. Both Waveshare variants use the validated
PPA-disabled, VSYNC-safe display profile.

## Candidate and Hardware Gate

1. Run the producer's `Build installer firmware` workflow manually on the
   candidate commit.
2. Download the exact CI artifact and record its commit and four SHA-256 values.
3. Test that exact artifact:
   - Generic standard: erase/flash, boot, REPL, and VFS mount.
   - Generic ESP-NOW: standard checks plus Wi-Fi and ESP-NOW with matched C6.
   - Waveshare standard: clean display redraws, touch, audio, SD, RTC, and VFS.
   - Waveshare ESP-NOW: all Waveshare checks plus C6 identity and ESP-NOW.
4. Record board revisions, tester, result, producer commit, and all four hashes.
5. Only after the candidate passes, create immutable `firmware-vX.Y.Z` on the
   same producer commit. Never move or recreate the tag.

## Import Into The Installer

Import an explicit producer release:

```bash
python update_firmware.py --sync-release firmware-vX.Y.Z
```

`--sync-release latest` is only a convenience for resolving the newest stable
`firmware-v*` release. The resolved immutable tag and commit are written into
`firmware-manifest.json`.

The import is all-or-nothing. Before replacing files it verifies:

- All four required package paths are present.
- Every image size and SHA-256 matches `firmware-release.json`.
- The ESP-Hosted commit matches the installer.
- The producer's required C6 ELF identity matches the bundled C6 image.
- The producer declares 32 MiB flash, app offset `0x10000`, app size
   `0x500000`, and VFS offset `0x510000`.

The `Import producer firmware release` workflow performs this import and opens
a reviewable pull request. It does not merge or publish automatically.

## Installer Acceptance and Release

From the import pull request:

- [ ] Producer tag and commit match `firmware-manifest.json`.
- [ ] All four P4 SHA-256 values are recorded.
- [ ] Generic standard boot/REPL/VFS passed.
- [ ] Generic ESP-NOW Wi-Fi/ESP-NOW passed.
- [ ] Waveshare standard display/touch/audio/SD/RTC passed.
- [ ] Waveshare ESP-NOW board and radio validation passed.
- [ ] App size `0x500000` and VFS offset `0x510000` are confirmed.
- [ ] All four selections were exercised from the generated installer ZIP.
- [ ] Board revisions, tester, and results are recorded.

After approval, merge the import PR and create installer tag `vX.Y.Z` from that
exact merge commit. The installer release workflow verifies all bundled files,
runs dry-runs for all four choices, creates a deterministic ZIP, and publishes
only the pinned offline package.

## Offline Meaning

Firmware payloads and hashes are bundled; flashing never downloads firmware.
A completely disconnected computer must already have the pinned Python
`esptool` and `pyserial` dependencies installed, or use a separately prepared
offline wheel bundle. Launchers may contact PyPI on first run when dependencies
are absent.

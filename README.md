# ESP32-P4/C6 ESP-NOW Enabler

This repository installs the ESP32-C6 half of the ESP-NOW proxy used by the
matching ESP32-P4 host firmware. The P4 and C6 communicate over ESP-Hosted's
SDIO peer-data channel, while applications use the standard ESP-IDF or
MicroPython ESP-NOW API on the P4.

## Compatibility

This package is a coordinated firmware pair. Use it only with P4 firmware built
from these revisions:

- ESP-Hosted fork: `CorruptName/esp-hosted-mcu`, commit
  `dd95bdf3316fc8c6110b387855033a26c0aa2447`
- MicroPython fork: `CorruptName/micropython`, commit
  `43eedf776127d47235550afb8e8c0010061c0a3c`
- ESP-IDF: `v5.5.1`
- ESP-Hosted protocol baseline: `2.7.0`, plus the custom ESP-NOW proxy

The package targets ESP32-P4 boards whose ESP32-C6 radio is connected over
4-bit SDIO. It was prepared for the Waveshare
ESP32-P4-WIFI6-Touch-LCD-4.3. Other P4/C6 boards may use different flash or
SDIO settings and should not be assumed compatible without validation.

## Included Images

| Path | Purpose | Flash offset |
| --- | --- | ---: |
| `binaries/bootloader.bin` | Temporary P4 OTA bootloader | `0x2000` |
| `binaries/partition-table.bin` | Temporary P4 OTA partition table | `0x8000` |
| `binaries/ota_data_initial.bin` | Temporary P4 OTA state | `0xd000` |
| `modified_ota_host/host_performs_slave_ota.bin` | Temporary P4 OTA application | `0x10000` |
| `binaries/storage.bin` | LittleFS image containing the C6 payload | `0x410000` |
| `slave_firmware/network_adapter.bin` | Standalone matched C6 payload | not flashed directly to the P4 |

The OTA application intentionally forces the C6 update. This handles factory
C6 firmware that cannot answer the newer ESP-Hosted version query.

The packaged C6 image enables full application-descriptor reporting. Its ELF
SHA-256 is `85544ac1fa10fee3b652525141b2c51d3aecac89e56e8d88a4dded594b56eef4`.
The temporary P4 application persists a verification marker before activation,
reconnects after both processors reboot, requires that exact running ELF
identity, and performs an ESP-NOW init/deinit round trip. OTA completion alone
is not treated as installation success.

## Verify The Package

Run the verifier before placing the board in download mode:

```bash
python update_firmware.py
```

It checks the SHA-256 digest of every binary. Do not mix images from another
ESP-Hosted release or replace only `network_adapter.bin`: the host RPC protocol
and C6 implementation must remain matched.

## Install

The standalone package in `packages/esp32-p4-firmware-installer` contains
prebuilt generic ESP32-P4 Dev and Waveshare 4.3-inch images. Its shared Python
runner supports Windows and Linux, lists available serial ports, asks which
device to flash and whether to enable ESP-NOW, and does not require a 32 MiB
backup. ESP-NOW installations verify the C6 automatically before writing the
selected P4 image.

The standalone package is intended for initial provisioning. It erases the
complete P4 flash before writing the selected merged image, deleting any
existing P4 applications, files, and settings. Esptool detects the installed
flash capacity, so no board-specific filesystem erase range is required.

The distributable archive is `packages/esp32-p4-firmware-installer.zip`
(7,635,850 bytes, SHA-256
`39b5c20bbe4b74c3088796cf5a688d5f4dbf38c39e34ddb198d42bfae241ea7c`).

Prerequisites:

- Python with the `esptool` module installed
- A data-capable USB connection to the ESP32-P4 USB serial/JTAG port
- The P4 serial port name

On Linux, macOS, or WSL with the serial device passed through:

```bash
chmod +x flash_c6_firmware.sh
./flash_c6_firmware.sh /dev/ttyACM0
```

The script backs up the complete 32 MiB P4 flash before installing the
temporary OTA application. After the C6 update completes, the P4 restarts and
performs a second verification phase. Restore the original P4 firmware only
after the serial log reports both `C6_ELF_IDENTITY_VERIFIED` and
`C6_ESPNOW_VERIFIED`. Keep the backup until the normal P4 firmware boots
successfully.

The board must be placed in its download/boot mode before each P4 flash or
restore operation. The script never flashes the C6 directly; the temporary P4
application transfers `network_adapter.bin` to the C6 over SDIO.

## Expected OTA Log

The temporary application should report messages equivalent to:

```text
ESP-Hosted initialized successfully
Forcing slave OTA update
Using LittleFS OTA method
OTA completed successfully
Slave will reboot with new firmware
ESP-Hosted initialized successfully
Verifying the activated C6 firmware
C6_ELF_IDENTITY_VERIFIED
C6_ESPNOW_VERIFIED
C6 ESP-NOW installation completed successfully
```

If identity or ESP-NOW verification fails, the verification marker remains set
and the temporary P4 application will retry verification on its next boot. Do
not restore the P4 backup or report installation success from the earlier
`OTA completed successfully` message alone.

After restoring and booting the matched MicroPython build, verify the standard
API rather than relying only on a version string:

```python
import espnow
import network

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
radio = espnow.ESPNow()
radio.active(True)
print("ESP-NOW initialized")
```

## Rebuilding

The binaries were built from the ESP-Hosted fork and commit listed above using
ESP-IDF `v5.5.1`:

1. Build `slave/` for `esp32c6` with `slave/sdkconfig.espnow` enabling
   `CONFIG_ESP_HOSTED_ENABLE_PEER_DATA_TRANSFER`,
   `CONFIG_ESP_HOSTED_ENABLE_ESPNOW`, and
   `CONFIG_ESP_HOSTED_ALLOW_FULL_APP_DESC`. Use DIO at 80 MHz for the embedded
   C6 flash.
2. Copy the resulting `network_adapter.bin` into the LittleFS OTA example.
3. Select `CONFIG_OTA_METHOD_LITTLEFS=y`, use 512-byte OTA chunks with a 10 ms
   delay after each write RPC, set the P4-to-C6 SDIO clock to 10 MHz, and force
   the OTA in the example host.
4. Set `EXPECTED_C6_ELF_SHA256` in `modified_ota_host/main_modified.c` to the
   ELF SHA-256 reported by `esptool image-info network_adapter.bin`.
5. Build `examples/host_performs_slave_ota` for `esp32p4`.
6. Keep the P4 OTA images and C6 payload from that same source revision.

The temporary host build uses the local ESP-Hosted fork as an extra component
directory and `esp_wifi_remote` 0.15.2. Its OTA response parser propagates the
actual `OTAEnd` and `OTAActivate` error codes instead of collapsing them into a
generic parse failure.

The upstream example's LittleFS cleanup hook may remove `temp_littlefs` before
the image target consumes it. If that occurs, remove the component `POST_BUILD`
cleanup command for the packaging build, then clean up the directory manually.

## Recovery

If OTA fails, do not erase the board. Re-enter P4 download mode and restore the
backup made by the script:

```bash
python -m esptool --chip esp32p4 -p /dev/ttyACM0 -b 460800 \
  --before default_reset --after hard_reset write_flash 0x0 p4-flash-backup.bin
```

The custom C6 firmware is not an official Espressif release. Restoring P4 flash
does not roll back the C6; a known-good C6 image must be transferred through a
compatible ESP-Hosted OTA host to perform that rollback.

## License

The code is based on ESP-Hosted and retains its Apache-2.0 licensing. Binary
provenance is recorded above and can be checked with `update_firmware.py`.
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

## Verify The Package

Run the verifier before placing the board in download mode:

```bash
python update_firmware.py
```

It checks the SHA-256 digest of every binary. Do not mix images from another
ESP-Hosted release or replace only `network_adapter.bin`: the host RPC protocol
and C6 implementation must remain matched.

## Install

Prerequisites:

- Python with the `esptool` module installed
- A data-capable USB connection to the ESP32-P4 USB serial/JTAG port
- The P4 serial port name

On Linux, macOS, or WSL with the serial device passed through:

```bash
chmod +x flash_c6_firmware.sh
./flash_c6_firmware.sh /dev/ttyACM0
```

The script can back up the first 8 MiB of P4 flash before installing the
temporary OTA application. After the C6 update completes and the P4 restarts,
run the script's restore step to return the original P4 firmware and partition
contents. Keep the backup until the normal P4 firmware boots successfully.

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
```

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

1. Build `slave/` for `esp32c6` with `slave/sdkconfig.espnow` enabled.
2. Copy the resulting `network_adapter.bin` into the LittleFS OTA example.
3. Select `CONFIG_OTA_METHOD_LITTLEFS=y` and force the OTA in the example host.
4. Build `examples/host_performs_slave_ota` for `esp32p4`.
5. Keep the P4 OTA images and C6 payload from that same source revision.

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
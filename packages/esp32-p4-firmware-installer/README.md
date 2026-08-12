# ESP32-P4 MicroPython Firmware Installer

This folder is a self-contained firmware package for these targets:

- ESP32-P4 Dev
- Waveshare ESP32-P4-WIFI6-Touch-LCD-4.3

The installer asks which device to flash, lists the available serial ports,
and asks whether ESP-NOW support should be enabled. Without ESP-NOW it writes
the selected P4 MicroPython image directly. With ESP-NOW it temporarily boots
a P4 installer, updates the onboard ESP32-C6, verifies the exact C6 firmware
and ESP-NOW RPC, then writes the matching P4 MicroPython image.

This is a provisioning utility for a board that does not yet have the selected
MicroPython firmware. Before the final P4 image is written, the complete P4
flash is erased. Existing applications, files, settings, and partition data on
the P4 are intentionally deleted. Esptool detects the installed flash capacity,
so this step does not depend on a board-specific filesystem offset.

## Included Firmware

- Temporary P4 bootloader, partition table, OTA state, and installer app
- LittleFS image containing the matched ESP32-C6 firmware
- Generic and Waveshare P4 MicroPython images, each with and without ESP-NOW
- Validated ESP32-C6 ESP-NOW firmware
- SHA-256 values embedded in `enable_espnow.py`; every image is checked before
  the first write

The package was hardware-validated with ESP-IDF 5.5.1 and the custom
ESP-Hosted 2.7.0 fork at commit
`dd95bdf3316fc8c6110b387855033a26c0aa2447`.

## Windows

Requirements:

- Python 3 available as `python`
- Connect the board's **Serial UART** USB port. Do not use the **USB 2.0** port
  for installation, verification, or the MicroPython REPL.
- Internet access on the first run if `esptool` and `pyserial` are not already
  installed

Run:

```powershell
.\flash_and_restore.bat
```

The optional command-line form skips menus when automating or recovering:

```powershell
python enable_espnow.py COM10 --device waveshare --espnow yes
```

## Linux

Run:

```bash
chmod +x flash_and_restore.sh
./flash_and_restore.sh
```

If serial access is denied, add your user to the distribution's serial-port
group (commonly `dialout`), then sign out and back in. Do not run the installer
as root unless your system specifically requires it.

## Installation Flow

An ESP-NOW installation has four physical steps:

1. Put the P4 in download mode. The script watches for newly appeared COM ports,
  probes them for the P4 bootloader, and writes the temporary installer. If
  Windows reuses the supplied COM port, that port is checked too. No keyboard
  input is required.
2. Wait for the script to open the serial monitor and print `Press the physical
  reset button now.` Then press reset immediately; no typed confirmation is
  needed. It monitors the log for up to 120 seconds.
3. Only after all C6 checks pass, put the P4 in download mode again. The serial
  monitor is closed first, then the same new-port detection finds the bootloader
  before restoring the bundled MicroPython firmware.
4. Disconnect all power from the board, wait a few seconds, then reconnect the
  Serial UART USB port. A complete power cycle ensures the P4, C6, USB, and
  SDIO state are initialized cleanly before using MicroPython.

Physical resets are intentional. Automatic RTS reset is not reliable when the
P4 USB device re-enumerates on Windows, even though the flash write succeeded.
The serial monitor automatically reconnects when the installer reboots the P4
between the C6 OTA phase and the verification phase.

The first stage is accepted only after all three messages appear:

```text
C6_ELF_IDENTITY_VERIFIED
C6_ESPNOW_VERIFIED
C6 ESP-NOW installation completed successfully
```

No backup is performed. The full-chip erase before the final P4 write is
intentional and ensures that temporary installer data cannot corrupt the new
MicroPython filesystem. All P4 images are prebuilt and pinned to the device
option shown in the menu.

## Recovery

If the process stops after the temporary installer is written, put the P4 back
in normal boot mode and resume verification without rewriting it:

```powershell
python enable_espnow.py COM10 --device waveshare --espnow yes --verify-only
```

After successful verification, the resume command continues to the normal P4
restore gate. To skip C6 verification and restore only the bundled MicroPython
image, put the P4 in download mode and run:

```powershell
python enable_espnow.py COM10 --device waveshare --espnow yes --restore-only
```

The restore path verifies every bundled image, erases the complete P4 flash,
and then writes the selected P4 image. It does not change the C6 firmware.

Use `--dry-run` to verify all files and print both esptool commands without
opening the serial port:

```powershell
python enable_espnow.py TESTPORT --device waveshare --espnow yes --dry-run
```

Use `python enable_espnow.py --help` for all command-line options.
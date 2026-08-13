# Waveshare ESP32-P4 4.3-inch examples

These examples target the Waveshare ESP32-P4-WIFI6-Touch-LCD-4.3. Install a
named immutable installer release and select the Waveshare target. Display,
touch, audio, SD, and RTC examples work with either Waveshare choice;
`espnow_scanner.py` and `wizmote_listener.py` require the ESP-NOW choice and
the matching C6 firmware installed by this package.

The installer root README contains provisioning instructions. Direct producer
flashing should use an explicit `firmware-v*` release with `SHA256SUMS`
verification, never an unversioned loose binary.

Install `mpremote` on the computer connected to the board:

```powershell
python -m pip install mpremote
```

## LVGL touch button

`lvgl_button.py` creates a centered LVGL button. Each touch updates its label
and prints the number of presses. Run it from the repository root:

```powershell
python -m mpremote connect COM10 run examples/waveshare_esp32_p4_4_3/lvgl_button.py
```

From the MicroPython REPL, the same script can be pasted or saved to the board
and imported. The board's generated `display` module initializes the ST7701
display, GT911 touch controller, and LVGL task handler.

## Onboard speaker tone

`audio_tone.py` plays a 440 Hz sine wave for one second at volume 100:

```powershell
python -m mpremote connect COM10 run examples/waveshare_esp32_p4_4_3/audio_tone.py
```

To choose a different tone from the MicroPython REPL, import the function and
pass frequency in hertz, duration in milliseconds, and volume from 0 to 100:

```python
from audio_tone import play_tone
play_tone(frequency=880, duration_ms=500, volume=75)
```

Running the script plays the default tone. Importing it only provides the
`play_tone()` function.

The audio example uses the board's supported format: 16 kHz, signed 16-bit
stereo PCM with a 384x master clock. It disables the ES8311 codec and speaker
amplifier even if playback raises an exception.

## ESP-NOW device scanner

`espnow_scanner.py` discovers cooperating ESP-NOW peers and lists them on
screen. ESP-NOW has no native "scan" call, so the example uses channel 6 to
broadcast a beacon once a second and listens for matching beacons, tracking
each peer's MAC address and RSSI:

```powershell
python -m mpremote connect COM10 run examples/waveshare_esp32_p4_4_3/espnow_scanner.py
```

Run the headless companion on a second MicroPython ESP32 with ESP-NOW support:

```powershell
python -m mpremote connect COM7 run examples/waveshare_esp32_p4_4_3/espnow_beacon.py
```

Nearby phones, access points, and ESP32 boards not transmitting this beacon
cannot be discovered. Both boards require firmware with `MICROPY_PY_ESPNOW`
enabled, and neither board may be connected to an access point on a channel
other than 6 while discovery is running.

## WiZmote listener

`wizmote_listener.py` listens for a Philips WiZ remote. It scans Wi-Fi
channels 1 through 11 until a valid WiZmote ESP-NOW packet is received, then
locks to that channel and displays the remote MAC, RSSI, button, and payload:

```powershell
python -m mpremote connect COM10 run examples/waveshare_esp32_p4_4_3/wizmote_listener.py
```

Press the remote repeatedly while the listener is scanning. Supported button
codes are ON, OFF, Moon, brightness up/down, and presets 1 through 4.

## microSD card

`sdcard_test.py` enables the board's SDMMC I/O supply on LDO channel 4 and
uses the 4-bit slot 0 interface. It reports card and filesystem capacity,
lists the root directory, and performs a small write/read/delete test:

```powershell
python -m mpremote connect COM10 run examples/waveshare_esp32_p4_4_3/sdcard_test.py
```

The test never formats the card. It unmounts the filesystem and disables the
SD I/O supply before exiting, including after an error.

## Internal RTC

`rtc_test.py` reads the ESP32-P4 internal RTC twice and verifies that it
advances. It does not change the current date or time:

```powershell
python -m mpremote connect COM10 run examples/waveshare_esp32_p4_4_3/rtc_test.py
```

The board's vendor BSP lists only the ES8311 codec and GT911 touch controller
on I2C and does not define a separate external RTC. The board schematic connects
the RTC battery header directly to the ESP32-P4 `VBAT` pin, so it backs up the
P4's internal RTC and low-power domain in hardware.

Only connect a compatible rechargeable RTC battery with the correct polarity.
Waveshare explicitly states that this header does not support non-rechargeable
RTC batteries.

To test battery retention, install the rechargeable RTC battery, set
`machine.RTC()` to a known time, then completely remove USB and main-battery
power for at least one minute. Restore main power and run `rtc_test.py`; the
reported time should include the interval spent without main power. A reset-only
test is insufficient because the RTC normally survives resets without the
backup battery.

## Requirements

- Waveshare ESP32-P4 4.3" display with LVGL support
- ESP-NOW firmware only for `espnow_scanner.py` and `wizmote_listener.py`
- A second ESP-NOW device running the companion beacon only for discovery

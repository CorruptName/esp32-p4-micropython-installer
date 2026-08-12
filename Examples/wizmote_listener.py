"""Discover and decode WiZ remote ESP-NOW button packets."""

import time
import display
import lvgl as lv
import network
import espnow

CHANNELS = tuple(range(1, 12))
CHANNEL_HOP_MS = 200
BUTTON_NAMES = {
    1: "ON",
    2: "OFF",
    3: "MOON",
    8: "BRIGHTNESS DOWN",
    9: "BRIGHTNESS UP",
    16: "PRESET 1",
    17: "PRESET 2",
    18: "PRESET 3",
    19: "PRESET 4",
}

sta = None
e = None
running = False
channel_index = 0
locked_channel = None
last_hop_ms = 0
last_sequence = {}


def format_mac(mac):
    return ":".join("%02x" % byte for byte in mac)


def format_payload(message):
    return " ".join("%02X" % byte for byte in message)


def is_wizmote_packet(message):
    return len(message) >= 7 and message[0] in (0x81, 0x91)


def set_channel(channel):
    global channel_index, last_hop_ms

    sta.config(channel=channel)
    channel_index = CHANNELS.index(channel)
    last_hop_ms = time.ticks_ms()
    channel_label.set_text("Channel %d" % channel)


def init_espnow():
    global sta, e

    sta = network.WLAN(network.WLAN.IF_STA)
    sta.active(True)
    sta.disconnect()

    e = espnow.ESPNow()
    e.active(True)
    set_channel(CHANNELS[0])


def show_packet(mac, message):
    global locked_channel

    button_code = message[6]
    button_name = BUTTON_NAMES.get(button_code, "UNKNOWN %d" % button_code)
    sequence = bytes(message[1:5])
    if last_sequence.get(mac) == sequence:
        return
    last_sequence[mac] = sequence

    locked_channel = sta.config("channel")
    rssi = e.peers_table.get(mac, [None])[0]
    status_label.set_text("WiZmote found - locked to channel %d" % locked_channel)
    button_label.set_text(button_name)
    details_label.set_text(
        "%s\nRSSI: %s dBm\nCode: %d\n%s"
        % (format_mac(mac), rssi, button_code, format_payload(message))
    )
    print(
        "WiZmote:",
        format_mac(mac),
        "channel", locked_channel,
        "button", button_name,
        "payload", format_payload(message),
    )


def poll_timer_cb(timer):
    global channel_index

    if not running:
        return

    while True:
        mac, message = e.recv(0)
        if mac is None:
            break
        if is_wizmote_packet(message):
            show_packet(mac, message)

    if locked_channel is None and time.ticks_diff(time.ticks_ms(), last_hop_ms) >= CHANNEL_HOP_MS:
        channel_index = (channel_index + 1) % len(CHANNELS)
        set_channel(CHANNELS[channel_index])


def start_listening(event):
    global running, locked_channel

    try:
        if e is None:
            init_espnow()
        locked_channel = None
        set_channel(CHANNELS[0])
    except Exception as ex:
        status_label.set_text("ESP-NOW init failed")
        details_label.set_text(str(ex))
        print("ESP-NOW init failed:", ex)
        return

    running = True
    control_label.set_text("Pause")
    status_label.set_text("Scanning channels 1-11 - press the remote")


def stop_listening(event):
    global running

    running = False
    control_label.set_text("Scan Again")
    status_label.set_text("Paused")


def toggle_listening(event):
    if running:
        stop_listening(event)
    else:
        start_listening(event)


screen = lv.screen_active()
screen.set_style_bg_color(lv.color_hex(0x18212B), 0)

heading = lv.label(screen)
heading.set_text("WiZmote Listener")
heading.align(lv.ALIGN.CENTER, 0, -120)
heading.set_style_text_font(lv.font_montserrat_16, 0)

status_label = lv.label(screen)
status_label.set_width(400)
status_label.set_long_mode(lv.label.LONG_MODE.WRAP)
status_label.set_text("Starting...")
status_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
status_label.align(lv.ALIGN.CENTER, 0, -80)

channel_label = lv.label(screen)
channel_label.set_text("Channel 1")
channel_label.align(lv.ALIGN.CENTER, 0, -45)

button_label = lv.label(screen)
button_label.set_text("Waiting for a button press")
button_label.set_style_text_font(lv.font_montserrat_16, 0)
button_label.align(lv.ALIGN.CENTER, 0, 0)

details_label = lv.label(screen)
details_label.set_width(420)
details_label.set_long_mode(lv.label.LONG_MODE.WRAP)
details_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
details_label.set_text("Press buttons repeatedly while channels are scanned.")
details_label.align(lv.ALIGN.CENTER, 0, 65)

control = lv.button(screen)
control.set_size(180, 50)
control.align(lv.ALIGN.CENTER, 0, 145)
control.add_event_cb(toggle_listening, lv.EVENT.CLICKED, None)

control_label = lv.label(control)
control_label.set_text("Pause")
control_label.center()

poll_timer = lv.timer_create(poll_timer_cb, 50, None)
start_listening(None)

print("WiZmote listener ready; scanning channels 1-11")
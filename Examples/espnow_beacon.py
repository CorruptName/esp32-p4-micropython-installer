"""Headless companion beacon for the Waveshare ESP-NOW peer scanner."""

import time
import network
import espnow

BROADCAST = b"\xff\xff\xff\xff\xff\xff"
BEACON = b"ESPNOW-HELLO"
CHANNEL = 6

sta = network.WLAN(network.WLAN.IF_STA)
sta.active(True)
sta.disconnect()
sta.config(channel=CHANNEL)

e = espnow.ESPNow()
e.active(True)
e.add_peer(BROADCAST, channel=CHANNEL)

print("ESP-NOW beacon active on channel", CHANNEL)
print("MAC:", ":".join("%02x" % byte for byte in sta.config("mac")))

while True:
    e.send(BROADCAST, BEACON, False)
    deadline = time.ticks_add(time.ticks_ms(), 1000)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        mac, message = e.recv(100)
        if mac is not None and message == BEACON:
            print("Peer:", ":".join("%02x" % byte for byte in mac))
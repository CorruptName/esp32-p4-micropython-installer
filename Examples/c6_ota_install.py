"""Experimental C6 app-only OTA helpers.

Transfer and validation work, but activation has not yet reproduced the
ESP-NOW behavior of a complete C6 flash. Keep a known-good full image available.
"""

import binascii
import hashlib
import os

import c6_ota


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as image:
        while True:
            chunk = image.read(4096)
            if not chunk:
                break
            digest.update(chunk)
    return binascii.hexlify(digest.digest()).decode()


def copy_file(source_path, destination_path):
    total = 0
    with open(source_path, "rb") as source:
        with open(destination_path, "wb") as destination:
            while True:
                chunk = source.read(4096)
                if not chunk:
                    break
                destination.write(chunk)
                total += len(chunk)
    return total


def install(path, expected_sha256, activate=False):
    expected_sha256 = expected_sha256.lower()
    actual_sha256 = file_sha256(path)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            "C6 image SHA-256 mismatch: expected {}, got {}".format(
                expected_sha256, actual_sha256
            )
        )

    with open(path, "rb") as image:
        if image.read(1) != b"\xe9":
            raise ValueError("file is not an ESP application image")
        image.seek(0)

        c6_ota.begin()
        total = 0
        while True:
            chunk = image.read(c6_ota.MAX_CHUNK_SIZE)
            if not chunk:
                break
            total += c6_ota.write(chunk)
            print("Transferred {} bytes".format(total))

    c6_ota.end()
    print("C6 application image validated ({} bytes)".format(total))

    if activate:
        print("Activating C6 application image")
        c6_ota.activate()
    else:
        print("Run c6_ota.activate() to boot the new C6 image")


def stage_from_sd(
    sd_path,
    expected_sha256,
    staging_path="/c6_ota_staging.bin",
):
    import machine

    expected_sha256 = expected_sha256.lower()
    sdcard = machine.SDCard(slot=0, width=4, freq=40_000_000, ldo_chan=4)
    mounted = False
    try:
        os.mount(sdcard, "/sd")
        mounted = True

        actual_sha256 = file_sha256(sd_path)
        if actual_sha256 != expected_sha256:
            raise ValueError(
                "SD image SHA-256 mismatch: expected {}, got {}".format(
                    expected_sha256, actual_sha256
                )
            )

        total = copy_file(sd_path, staging_path)
        print("Staged {} bytes in internal storage".format(total))
    finally:
        if mounted:
            os.umount("/sd")
        sdcard.deinit()

    staged_sha256 = file_sha256(staging_path)
    if staged_sha256 != expected_sha256:
        raise ValueError(
            "staged image SHA-256 mismatch: expected {}, got {}".format(
                expected_sha256, staged_sha256
            )
        )
    print("Staged image SHA-256 verified")
    print("Reboot before calling install_staged()")
    return staging_path


def install_staged(
    expected_sha256,
    staging_path="/c6_ota_staging.bin",
    activate=False,
):
    import network
    import time

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    time.sleep_ms(500)
    if not wlan.active():
        raise RuntimeError("ESP-Hosted did not initialize")

    install(staging_path, expected_sha256, activate=activate)

    try:
        os.remove(staging_path)
    except OSError:
        pass


if __name__ == "__main__":
    raise RuntimeError("import install() and provide the expected SHA-256 explicitly")

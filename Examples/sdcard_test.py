import machine
import os


MOUNT_POINT = "/sd"
TEST_PATH = MOUNT_POINT + "/.lvgl_micropython_sd_test.tmp"
TEST_DATA = b"Waveshare ESP32-P4 SD card test\n"


def format_bytes(value):
    units = ("B", "KiB", "MiB", "GiB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return "{:.1f} {}".format(size, unit)
        size /= 1024


def test_sdcard():
    sdcard = None
    mounted = False

    try:
        sdcard = machine.SDCard(
            slot=0,
            width=4,
            freq=40_000_000,
            ldo_chan=4,
        )
        capacity, block_size = sdcard.info()
        print("Card capacity:", format_bytes(capacity))
        print("Block size:", block_size, "bytes")

        os.mount(sdcard, MOUNT_POINT)
        mounted = True

        filesystem = os.statvfs(MOUNT_POINT)
        total = filesystem[0] * filesystem[2]
        free = filesystem[0] * filesystem[3]
        print("Filesystem total:", format_bytes(total))
        print("Filesystem free:", format_bytes(free))
        print("Root entries:", os.listdir(MOUNT_POINT))

        try:
            os.stat(TEST_PATH)
        except OSError:
            pass
        else:
            raise RuntimeError("test file already exists; refusing to overwrite it")

        try:
            with open(TEST_PATH, "wb") as test_file:
                test_file.write(TEST_DATA)
            with open(TEST_PATH, "rb") as test_file:
                result = test_file.read()
            if result != TEST_DATA:
                raise RuntimeError("SD card read-back did not match the written data")
        finally:
            try:
                os.remove(TEST_PATH)
            except OSError:
                pass

        print("SD card read/write test: PASS")
    finally:
        if mounted:
            os.umount(MOUNT_POINT)
        if sdcard is not None:
            sdcard.deinit()


if __name__ == "__main__":
    test_sdcard()
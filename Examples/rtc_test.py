import machine
import time


def format_datetime(value):
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        value[0], value[1], value[2], value[4], value[5], value[6]
    )


def test_rtc():
    rtc = machine.RTC()
    first = rtc.datetime()
    print("RTC initial:", format_datetime(first))

    time.sleep_ms(2200)
    second = rtc.datetime()
    print("RTC later:  ", format_datetime(second))

    first_seconds = first[4] * 3600 + first[5] * 60 + first[6]
    second_seconds = second[4] * 3600 + second[5] * 60 + second[6]
    elapsed = (second_seconds - first_seconds) % (24 * 3600)
    if not 1 <= elapsed <= 4:
        raise RuntimeError("RTC did not advance by the expected amount")

    print("Internal RTC advancement test: PASS ({} seconds)".format(elapsed))
    print("The RTC battery header backs up the ESP32-P4 internal RTC.")
    print("This test does not verify retention through a main-power loss.")


if __name__ == "__main__":
    test_rtc()
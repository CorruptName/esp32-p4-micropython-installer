from array import array
from math import pi, sin
from machine import I2S, Pin

import display
from es8311 import ES8311


def play_tone(frequency=440, duration_ms=1000, volume=100):
    sample_rate = 16000
    frames = 512
    pcm = array("h", (0 for _ in range(frames * 2)))

    audio = I2S(
        0,
        sck=Pin(12),
        ws=Pin(10),
        sd=Pin(9),
        mck=Pin(13),
        mck_multiplier=384,
        mode=I2S.TX,
        bits=16,
        format=I2S.STEREO,
        rate=sample_rate,
        ibuf=frames * 8,
    )
    codec = ES8311(display.audio_device, pa_pin=53)
    codec.set_volume(volume)

    try:
        codec.enable()
        frame_index = 0
        frames_remaining = sample_rate * duration_ms // 1000

        while frames_remaining:
            frame_count = min(frames, frames_remaining)
            for index in range(frame_count):
                sample = int(
                    28000
                    * sin(2 * pi * frequency * frame_index / sample_rate)
                )
                pcm[index * 2] = sample
                pcm[index * 2 + 1] = sample
                frame_index += 1

            audio.write(memoryview(pcm)[:frame_count * 2])
            frames_remaining -= frame_count
    finally:
        codec.disable()
        audio.deinit()


if __name__ == "__main__":
    play_tone()

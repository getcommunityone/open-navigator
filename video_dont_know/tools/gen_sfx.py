#!/usr/bin/env python3
"""Synthesize the game-show sound cues used by the video.

Pure standard-library additive/noise synthesis -> 16-bit mono PCM WAV files in
public/audio/. Re-run with:  python3 tools/gen_sfx.py
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

SR = 44100
OUT = Path(__file__).resolve().parent.parent / "public" / "audio"


def env(n: int, attack: float, release: float) -> list[float]:
    """Simple attack/exponential-release amplitude envelope, length n samples."""
    a = max(1, int(attack * SR))
    out = []
    for i in range(n):
        if i < a:
            amp = i / a
        else:
            amp = math.exp(-(i - a) / (release * SR))
        out.append(amp)
    return out


def sine(freq: float, n: int, phase: float = 0.0) -> list[float]:
    return [math.sin(2 * math.pi * freq * i / SR + phase) for i in range(n)]


def mix(*tracks: list[float]) -> list[float]:
    n = max(len(t) for t in tracks)
    out = [0.0] * n
    for t in tracks:
        for i, v in enumerate(t):
            out[i] += v
    return out


def normalize(samples: list[float], peak: float = 0.89) -> list[float]:
    m = max((abs(s) for s in samples), default=1.0) or 1.0
    return [s / m * peak for s in samples]


def write(name: str, samples: list[float]) -> None:
    samples = normalize(samples)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.wav"
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples
        )
        w.writeframes(frames)
    print(f"  wrote {path.relative_to(OUT.parent.parent)}  ({len(samples)/SR:.2f}s)")


def stinger() -> list[float]:
    """Bright major-chord stab for the title slam."""
    n = int(0.7 * SR)
    e = env(n, 0.004, 0.22)
    chord = mix(sine(523.25, n), sine(659.25, n), sine(783.99, n), sine(1046.5, n))
    noise = [(random.uniform(-1, 1)) * math.exp(-i / (0.02 * SR)) for i in range(n)]
    return [(chord[i] * 0.25 + noise[i] * 0.5) * e[i] for i in range(n)]


def whoosh() -> list[float]:
    """Filtered-noise sweep for transitions / slides."""
    n = int(0.45 * SR)
    out = []
    prev = 0.0
    for i in range(n):
        t = i / n
        raw = random.uniform(-1, 1)
        # rising low-pass cutoff -> brighter toward the end = "swoosh"
        a = 0.02 + 0.4 * t
        prev = prev + a * (raw - prev)
        amp = math.sin(math.pi * t)  # fade in/out
        out.append(prev * amp)
    return out


def pop() -> list[float]:
    """Short upward blip for chips/cards appearing."""
    n = int(0.12 * SR)
    e = env(n, 0.002, 0.045)
    out = []
    for i in range(n):
        f = 620 + 900 * (i / n)
        out.append(math.sin(2 * math.pi * f * i / SR) * e[i])
    return out


def ding() -> list[float]:
    """Pleasant bell for the correct answer."""
    n = int(0.8 * SR)
    e = env(n, 0.003, 0.32)
    bell = mix(sine(1318.5, n), [0.6 * v for v in sine(1976.0, n)],
               [0.3 * v for v in sine(2637.0, n)])
    return [bell[i] * e[i] for i in range(n)]


def boom() -> list[float]:
    """Low impact for reveals / the scoreboard drop."""
    n = int(0.8 * SR)
    e = env(n, 0.002, 0.28)
    out = []
    for i in range(n):
        f = 90 - 45 * (i / n)  # pitch drop
        thump = math.sin(2 * math.pi * f * i / SR)
        click = random.uniform(-1, 1) * math.exp(-i / (0.01 * SR))
        out.append((thump * 0.9 + click * 0.4) * e[i])
    return out


def clash() -> list[float]:
    """Dissonant detuned stab for the VS badge."""
    n = int(0.5 * SR)
    e = env(n, 0.003, 0.16)
    # square-ish via odd harmonics, two detuned voices a tritone apart
    def square(f):
        s = [0.0] * n
        for h in (1, 3, 5, 7):
            for i, v in enumerate(sine(f * h, n)):
                s[i] += v / h
        return s
    a = square(220.0)
    b = square(311.1)  # tritone
    return [(a[i] + b[i]) * e[i] for i in range(n)]


def applause() -> list[float]:
    """Crowd-ish filtered noise bursts for the outro."""
    n = int(1.6 * SR)
    out = []
    prev = 0.0
    for i in range(n):
        t = i / n
        raw = random.uniform(-1, 1)
        prev = prev + 0.25 * (raw - prev)  # low-pass -> softer
        # overlapping claps as amplitude flutter
        flutter = 0.6 + 0.4 * abs(math.sin(2 * math.pi * 11 * t) *
                                  math.sin(2 * math.pi * 7.3 * t))
        amp = min(1.0, t * 6) * math.exp(-max(0.0, t - 0.6) * 3)
        out.append(prev * flutter * amp)
    return out


def tick() -> list[float]:
    """Tiny timer click."""
    n = int(0.05 * SR)
    e = env(n, 0.001, 0.012)
    return [random.uniform(-1, 1) * e[i] for i in range(n)]


def main() -> None:
    random.seed(8)  # deterministic output
    print("Generating SFX ->", OUT)
    write("stinger", stinger())
    write("whoosh", whoosh())
    write("pop", pop())
    write("ding", ding())
    write("boom", boom())
    write("vs", clash())
    write("applause", applause())
    write("tick", tick())
    print("done.")


if __name__ == "__main__":
    main()

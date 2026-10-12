#!/usr/bin/env python3
"""Synthesize the soundtrack: a low cryostat drone plus hits locked to the
scene's timeline (superposition shimmer, barrier whoosh, entanglement pings,
observer alarm, collapse chord). Pure numpy, deterministic, 28 s stereo WAV."""
import argparse
import wave
from pathlib import Path

import numpy as np

SR, T = 44100, 28.0
PHASES = [3, 8, 10, 15, 23.5]          # phase boundaries (see index.html → PH)
BARRIER_T = 12.0                       # octopus crosses V0
ENTANGLE_FLIPS = [15 + k * 1.25 for k in range(5)]
OBSERVER = (20.0, 23.5)
COLLAPSE = 23.5


def build() -> np.ndarray:
    t = np.arange(int(SR * T)) / SR
    rng = np.random.default_rng(7)
    sig = sum(np.sin(2 * np.pi * f * t + p) * a for f, a, p in
              [(49, .2, 0), (73.4, .1, 1), (98, .07, 2), (146.8, .04, .4)])
    sig *= 0.8 + 0.2 * np.sin(2 * np.pi * 0.1 * t)
    sig += np.convolve(rng.standard_normal(t.size), np.ones(300) / 300, "same") * 0.7

    def window(a, b, fade):
        return np.clip((t - a) / fade, 0, 1) * np.clip((b - t) / fade, 0, 1)

    def ping(t0, f, amp, decay):
        m = t >= t0
        x = t[m] - t0
        sig[m] += amp * np.exp(-x * decay) * np.sin(2 * np.pi * f * x)

    shimmer = sum(np.sin(2 * np.pi * f * t * (1 + 0.003 * np.sin(3 * t + i))) * 0.025
                  for i, f in enumerate([880, 1108, 1318, 1760]))
    sig += shimmer * window(3, 10, 0.8)
    for i in range(16):                                   # copies popping in
        ping(3 + i * 0.28, 700 + i * 60, 0.06, 12)
    for p in PHASES:                                      # phase hits
        ping(p, 110, 0.4, 4)
        ping(p, 220, 0.15, 6)
    sig += (np.convolve(rng.standard_normal(t.size), np.ones(40) / 40, "same")
            * np.exp(-((t - BARRIER_T) / 0.5) ** 2) * 0.9)
    for k, ft in enumerate(ENTANGLE_FLIPS):
        ping(ft, 523.25 if k % 2 else 659.25, 0.12, 5)
    alarm = np.sign(np.sin(2 * np.pi * 2.5 * t)) * 0.5 + 0.5
    sig += np.sin(2 * np.pi * 440 * t) * 0.06 * alarm * window(*OBSERVER, 0.1)
    for f in [261.6, 329.6, 392, 523.3, 659.3]:
        ping(COLLAPSE, f, 0.12, 0.8)

    sig *= np.minimum(1, (T - t) / 1.0)
    sig = sig / np.max(np.abs(sig)) * 0.6
    return np.stack([sig, np.roll(sig, 250)], axis=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "media" / "soundtrack.wav"))
    out = Path(ap.parse_args().out)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = (build() * 32767).astype(np.int16)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print(f"Wrote {out}")

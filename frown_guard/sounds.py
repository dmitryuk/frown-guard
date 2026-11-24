"""
Alert sound playback.

Sound ids: "chime" (the built-in synthesized zen chime) or the name of a macOS
system alert sound (e.g. "Glass"), found in /System/Library/Sounds. On macOS
playback uses NSSound (asynchronous, no extra audio library); elsewhere only the
chime is offered and it is played through sounddevice as before.
"""
import io
import os
import sys
import wave
from typing import Dict, List, Optional

import numpy as np

CHIME = "chime"
SYSTEM_SOUNDS_DIR = "/System/Library/Sounds"
SAMPLE_RATE = 44100
# Peak amplitude of the chime at 100% volume (the original fixed level was 0.15,
# which now corresponds to the 50% default).
CHIME_PEAK = 0.3


def available_sounds() -> List[str]:
    """Sound ids to offer: the built-in chime first, then macOS system sounds."""
    sounds = [CHIME]
    if sys.platform == "darwin" and os.path.isdir(SYSTEM_SOUNDS_DIR):
        names = sorted(
            os.path.splitext(f)[0]
            for f in os.listdir(SYSTEM_SOUNDS_DIR)
            if f.lower().endswith((".aiff", ".aif", ".wav", ".caf"))
        )
        sounds.extend(names)
    return sounds


def _system_sound_path(name: str) -> Optional[str]:
    for ext in (".aiff", ".aif", ".wav", ".caf"):
        path = os.path.join(SYSTEM_SOUNDS_DIR, name + ext)
        if os.path.isfile(path):
            return path
    return None


def synth_chime() -> np.ndarray:
    """Gentle E5 bell with overtones and exponential decay, peak-normalized to 1.0."""
    duration = 1.0
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    f0 = 659.25
    wave_ = (
        np.sin(2 * np.pi * f0 * t)
        + 0.5 * np.sin(2 * np.pi * (2 * f0) * t)
        + 0.25 * np.sin(2 * np.pi * (3 * f0) * t)
        + 0.15 * np.sin(2 * np.pi * (4.2 * f0) * t)
    ) * np.exp(-4.5 * t)
    return wave_ / np.max(np.abs(wave_))


def _chime_wav_bytes() -> bytes:
    pcm = (synth_chime() * CHIME_PEAK * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


class AlertPlayer:
    """Plays alert sounds by id at a volume of 0.0-1.0. Call from the Tk thread."""

    def __init__(self) -> None:
        self._cache: Dict[str, object] = {}  # NSSound objects must stay referenced while playing
        self._mac = False
        if sys.platform == "darwin":
            try:
                from AppKit import NSSound  # noqa: F401
                self._mac = True
            except Exception:
                self._mac = False

    def play(self, sound_id: str, volume: float) -> None:
        volume = max(0.0, min(1.0, volume))
        try:
            if self._mac:
                self._play_mac(sound_id, volume)
            else:
                self._play_portable(volume)
        except Exception as e:
            # Fall back silently if no audio device/backend is available
            print(f"Could not play alert sound '{sound_id}': {e}")

    def _play_mac(self, sound_id: str, volume: float) -> None:
        from AppKit import NSSound
        from Foundation import NSData

        sound = self._cache.get(sound_id)
        if sound is None:
            if sound_id == CHIME:
                data = _chime_wav_bytes()
                sound = NSSound.alloc().initWithData_(NSData.dataWithBytes_length_(data, len(data)))
            else:
                path = _system_sound_path(sound_id)
                if path is None:
                    return self._play_mac(CHIME, volume)
                sound = NSSound.alloc().initWithContentsOfFile_byReference_(path, True)
            if sound is None:
                return
            self._cache[sound_id] = sound
        if sound.isPlaying():
            sound.stop()
        sound.setVolume_(volume)
        sound.play()

    def _play_portable(self, volume: float) -> None:
        import sounddevice as sd

        sd.play(synth_chime() * CHIME_PEAK * volume, SAMPLE_RATE)

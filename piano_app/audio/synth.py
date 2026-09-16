from __future__ import annotations

import math
import threading

import numpy as np
from PySide6 import QtCore, QtMultimedia


class _AudioStream(QtCore.QIODevice):
    def __init__(self, synth, parent=None):
        super().__init__(parent)
        self.synth = synth

    def readData(self, max_size: int) -> bytes:
        if not self.isOpen() or max_size < 2:
            return b""
        return self.synth.render(max_size // 2)

    def writeData(self, data: bytes) -> int:
        return -1

    def bytesAvailable(self) -> int:
        return 16384 + super().bytesAvailable()


class SoftwareSynth(QtCore.QObject):
    """Low-latency polyphonic software synth backed by one continuous stream."""

    SAMPLE_RATE = 44100
    MAX_VOICES = 32
    TABLE_SIZE = 2048

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._programs = [0] * 16
        self._voices: dict[tuple[int, int], dict] = {}
        self._waveforms = [np.asarray(waveform, dtype=np.float32) for waveform in self._build_waveforms()]
        self.enabled = True
        self._closed = False
        self._stream = _AudioStream(self, self)
        self._stream.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)
        audio_format = QtMultimedia.QAudioFormat()
        audio_format.setSampleRate(self.SAMPLE_RATE)
        audio_format.setChannelCount(1)
        audio_format.setSampleFormat(QtMultimedia.QAudioFormat.SampleFormat.Int16)
        self._sink = QtMultimedia.QAudioSink(audio_format, self)
        self._sink.setBufferSize(8192)
        self._sink.setVolume(0.55)
        self._sink.start(self._stream)

    def handle_message(self, message):
        if message.type == "program_change":
            with self._lock:
                self._programs[message.channel] = message.program
        elif message.type == "note_on" and message.velocity > 0:
            self.note_on(message.channel, message.note, message.velocity)
        elif message.type == "note_off" or (message.type == "note_on" and message.velocity == 0):
            self.note_off(message.channel, message.note)
        elif message.type == "control_change" and message.control == 123:
            self.stop_all()

    def note_on(self, channel: int, note: int, velocity: int):
        with self._lock:
            key = (channel, note)
            self._voices.pop(key, None)
            if len(self._voices) >= self.MAX_VOICES:
                oldest = next(iter(self._voices))
                self._voices.pop(oldest)
            self._voices[key] = {
                "phase": 0.0,
                "frequency": 440.0 * (2.0 ** ((note - 69) / 12.0)),
                "step": (440.0 * (2.0 ** ((note - 69) / 12.0))) * self.TABLE_SIZE / self.SAMPLE_RATE,
                "level": min(1.0, velocity / 127.0),
                "age": 0,
                "release": False,
                "program": self._programs[channel],
            }

    @classmethod
    def _build_waveforms(cls):
        waveforms = []
        harmonic_sets = (
            (1.00, 0.42, 0.20, 0.11, 0.06, 0.03),
            (1.00, 0.28, 0.34, 0.16, 0.08, 0.035),
            (1.00, 0.18, 0.10, 0.24, 0.10, 0.04),
        )
        for harmonics in harmonic_sets:
            values = []
            for index in range(cls.TABLE_SIZE):
                phase = 2.0 * math.pi * index / cls.TABLE_SIZE
                sample = sum(weight * math.sin(phase * (harmonic + 1)) for harmonic, weight in enumerate(harmonics))
                values.append(sample)
            waveforms.append(values)
        return waveforms

    def note_off(self, channel: int, note: int):
        with self._lock:
            voice = self._voices.get((channel, note))
            if voice is not None:
                voice["release"] = True

    def stop_all(self):
        with self._lock:
            for voice in self._voices.values():
                voice["release"] = True

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        if not enabled:
            with self._lock:
                self._voices.clear()

    def render(self, sample_count: int) -> bytes:
        if not self.enabled:
            return b"\x00\x00" * sample_count
        if sample_count <= 0:
            return b""

        with self._lock:
            voices = list(self._voices.items())
            if not voices:
                return b"\x00\x00" * sample_count

            sample_indices = np.arange(sample_count, dtype=np.float32)
            mixed = np.zeros(sample_count, dtype=np.float32)
            mix_gain = 0.08 / math.sqrt(len(voices))
            expired = set()
            for key, voice in voices:
                age = voice["age"]
                if voice["release"] and "release_age" not in voice:
                    voice["release_age"] = age

                elapsed = age + sample_indices
                attack = np.minimum(1.0, elapsed / (self.SAMPLE_RATE * 0.006))
                decay_seconds = max(
                    0.45,
                    min(2.2, 1.45 * (440.0 / voice["frequency"]) ** 0.18),
                )
                envelope = attack * np.exp(-elapsed / (self.SAMPLE_RATE * decay_seconds))
                if voice["release"]:
                    envelope *= np.maximum(
                        0.0,
                        1.0 - (elapsed - voice["release_age"]) / (self.SAMPLE_RATE * 0.22),
                    )

                phase_indices = (
                    voice["phase"] + voice["step"] * sample_indices
                ).astype(np.int32) & (self.TABLE_SIZE - 1)
                program = voice["program"]
                family = 0 if program < 8 else 1 if program < 24 else 2
                mixed += self._waveforms[family][phase_indices] * voice["level"] * envelope * mix_gain

                voice["phase"] = (voice["phase"] + voice["step"] * sample_count) % self.TABLE_SIZE
                voice["age"] = age + sample_count
                if voice["release"] and voice["age"] - voice["release_age"] >= self.SAMPLE_RATE * 0.08:
                    expired.add(key)

            for key in expired:
                self._voices.pop(key, None)

        output = np.clip(mixed, -0.92, 0.92)
        return (output * 32767).astype("<i2").tobytes()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.stop_all()
        self._sink.stop()
        self._stream.close()
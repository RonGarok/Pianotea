from __future__ import annotations

import os
from pathlib import Path

from PySide6 import QtCore


class FluidSynthEngine(QtCore.QObject):
    """SoundFont playback through the native FluidSynth audio driver."""

    def __init__(self, soundfont: Path, parent=None):
        super().__init__(parent)
        try:
            import fluidsynth
        except ImportError as exc:
            raise RuntimeError("pyfluidsynth is not installed") from exc

        self._fluidsynth = fluidsynth
        self._synth = fluidsynth.Synth(samplerate=44100, gain=0.7)
        self._driver = self._synth.start(driver="dsound")
        self._soundfont_id = self._synth.sfload(str(soundfont))
        for channel in range(16):
            self._synth.program_select(channel, self._soundfont_id, 0, 0)
        self._enabled = True
        self._closed = False

    @staticmethod
    def find_soundfont() -> Path | None:
        configured = os.environ.get("PIANOTEA_SOUNDFONT")
        candidates = []
        if configured:
            candidates.append(Path(configured))
        project_root = Path(__file__).resolve().parents[2]
        candidates.extend((project_root / "assets").glob("*.sf2"))
        candidates.extend((project_root / "soundfonts").glob("*.sf2"))
        return next((path for path in candidates if path.is_file()), None)

    def handle_message(self, message):
        if not self._enabled or self._closed:
            return
        message_type = message.type
        if message_type == "program_change":
            self._synth.program_select(message.channel, self._soundfont_id, 0, message.program)
        elif message_type == "note_on" and message.velocity > 0:
            self._synth.noteon(message.channel, message.note, message.velocity)
        elif message_type == "note_off" or (message_type == "note_on" and message.velocity == 0):
            self._synth.noteoff(message.channel, message.note)
        elif message_type == "control_change":
            self._synth.cc(message.channel, message.control, message.value)

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        if not enabled:
            self.stop_all()

    def stop_all(self):
        if self._closed:
            return
        for channel in range(16):
            self._synth.cc(channel, 123, 0)
            self._synth.cc(channel, 120, 0)

    def close(self):
        if self._closed:
            return
        self.stop_all()
        self._closed = True
        if hasattr(self._synth, "stop"):
            self._synth.stop()
        if hasattr(self._synth, "delete"):
            self._synth.delete()


def create_audio_engine(parent=None):
    soundfont = FluidSynthEngine.find_soundfont()
    if soundfont is None:
        raise RuntimeError(
            "No SoundFont found. Set PIANOTEA_SOUNDFONT to a .sf2 file or put one in assets/."
        )
    return FluidSynthEngine(soundfont, parent)

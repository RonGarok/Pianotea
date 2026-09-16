from __future__ import annotations

import logging
from typing import List, Optional

try:
    import rtmidi
except ImportError:  # pragma: no cover
    rtmidi = None


logger = logging.getLogger(__name__)


class MidiDeviceManager:
    def __init__(self):
        self._rtmidi_in = None
        self._rtmidi_out = None
        self._input_names: List[str] = []
        self._output_names: List[str] = []
        self._input_callback = None

    def detect_input_ports(self) -> List[str]:
        if rtmidi is None:
            logger.warning("python-rtmidi is not installed or failed to import. MIDI input ports will not be detected.")
            return []
        try:
            midi_in = rtmidi.MidiIn()
            self._input_names = [port for port in midi_in.get_ports()]
            del midi_in
            return list(self._input_names)
        except Exception as exc:  # pragma: no cover
            logger.warning("Unable to enumerate MIDI inputs: %s", exc)
            return []

    def detect_output_ports(self) -> List[str]:
        if rtmidi is None:
            logger.warning("python-rtmidi is not installed or failed to import. MIDI output ports will not be detected.")
            return []
        try:
            midi_out = rtmidi.MidiOut()
            self._output_names = [port for port in midi_out.get_ports()]
            del midi_out
            return list(self._output_names)
        except Exception as exc:  # pragma: no cover
            logger.warning("Unable to enumerate MIDI outputs: %s", exc)
            return []

    def open_input(self, port_name: str, callback=None) -> bool:
        if rtmidi is None:
            raise RuntimeError("python-rtmidi is not installed or could not be loaded. Install it with: python -m pip install python-rtmidi")

        try:
            if self._rtmidi_in is not None:
                self.close_input()
            self._rtmidi_in = rtmidi.MidiIn()
            ports = self._rtmidi_in.get_ports()
            for index, name in enumerate(ports):
                if name == port_name:
                    self._rtmidi_in.open_port(index)
                    self._input_callback = callback
                    if callback is not None:
                        self._rtmidi_in.set_callback(callback)
                    return True
            raise ValueError(f"MIDI input port not found: {port_name}")
        except Exception as exc:
            logger.exception("Failed to open MIDI input %s", port_name)
            raise RuntimeError(f"Unable to open MIDI input '{port_name}': {exc}") from exc

    def close_input(self):
        if self._rtmidi_in is not None:
            try:
                self._rtmidi_in.close_port()
            except Exception:  # pragma: no cover
                pass
            self._rtmidi_in = None

    def open_output(self, port_name: str) -> bool:
        if rtmidi is None:
            raise RuntimeError("python-rtmidi is not installed. Install it via pip install python-rtmidi")
        try:
            if self._rtmidi_out is not None:
                self.close_output()
            self._rtmidi_out = rtmidi.MidiOut()
            ports = self._rtmidi_out.get_ports()
            for index, name in enumerate(ports):
                if name == port_name:
                    self._rtmidi_out.open_port(index)
                    return True
            raise ValueError(f"MIDI output port not found: {port_name}")
        except Exception as exc:
            logger.exception("Failed to open MIDI output %s", port_name)
            raise RuntimeError(f"Unable to open MIDI output '{port_name}': {exc}") from exc

    def close_output(self):
        if self._rtmidi_out is not None:
            try:
                self._rtmidi_out.close_port()
            except Exception:  # pragma: no cover
                pass
            self._rtmidi_out = None

    def send(self, message) -> bool:
        if self._rtmidi_out is None:
            return False
        try:
            self._rtmidi_out.send_message(message.bytes())
            return True
        except Exception as exc:  # pragma: no cover
            logger.warning("Unable to send MIDI message: %s", exc)
            return False

    def all_notes_off(self):
        if self._rtmidi_out is None:
            return
        for channel in range(16):
            self._rtmidi_out.send_message([0xB0 | channel, 123, 0])

    @property
    def input_ports(self) -> List[str]:
        return list(self._input_names)

    @property
    def output_ports(self) -> List[str]:
        return list(self._output_names)

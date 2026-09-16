from __future__ import annotations

from bisect import bisect_left, bisect_right
import time
from dataclasses import dataclass
from threading import Event, Thread, current_thread
from typing import List, Optional

import mido

from piano_app.midi.parser import NoteEvent


@dataclass
class PlaybackState:
    is_playing: bool = False
    is_paused: bool = False
    current_time: float = 0.0
    total_time: float = 0.0
    playback_speed: float = 1.0


class MidiPlayer:
    def __init__(self, events: List[NoteEvent], total_time: float):
        self.events = list(events)
        self.total_time = total_time
        self.state = PlaybackState(total_time=total_time)
        self._thread: Optional[Thread] = None
        self._stop_event = Event()
        self._pause_event = Event()
        self._start_time = 0.0
        self._started_at = 0.0
        self._last_time = 0.0
        self._callback = None
        self._output_callback = None
        self._audio_callback = None
        self._track_filter: Optional[int] = None
        self._output_events = []
        self._output_times_cache = []
        self._output_index = 0
        self._last_output_time = 0.0
        self._last_ui_callback_time = -1.0
        self._rebuild_output_events()

    def set_callback(self, callback):
        self._callback = callback

    def set_output_callback(self, callback):
        self._output_callback = callback

    def set_audio_callback(self, callback):
        self._audio_callback = callback

    def set_track_filter(self, track: Optional[int]):
        self._silence_output()
        self._track_filter = track
        self._rebuild_output_events()
        self._last_output_time = self.state.current_time
        self._output_index = bisect_right(self._output_times(), self.state.current_time)

    def refresh_events(self):
        self._rebuild_output_events()

    def _rebuild_output_events(self):
        output_events = []
        channel_programs = {}
        for event in self.events:
            if self._track_filter is not None and event.track != self._track_filter:
                continue
            if channel_programs.get(event.channel) != event.program:
                output_events.append((event.start_time, 0, mido.Message(
                    "program_change", channel=event.channel, program=event.program)))
                channel_programs[event.channel] = event.program
            output_events.append((event.start_time, 1, mido.Message(
                "note_on", channel=event.channel, note=event.pitch, velocity=event.velocity)))
            output_events.append((event.start_time + event.duration, 2, mido.Message(
                "note_off", channel=event.channel, note=event.pitch, velocity=0)))
        self._output_events = sorted(output_events, key=lambda item: (item[0], item[1]))
        self._output_times_cache = [event_time for event_time, _, _ in self._output_events]

    def _output_times(self):
        return self._output_times_cache

    def _send_output_until(self, current_time: float):
        if self._output_callback is None and self._audio_callback is None:
            self._last_output_time = current_time
            return

        while self._output_index < len(self._output_events):
            event_time, _, message = self._output_events[self._output_index]
            if event_time > current_time + 1e-9:
                break

            if self._output_callback is not None:
                self._output_callback(message)
            if self._audio_callback is not None:
                self._audio_callback(message)
            self._output_index += 1

        self._last_output_time = current_time

    def _silence_output(self):
        if self._output_callback is not None or self._audio_callback is not None:
            for channel in range(16):
                message = mido.Message("control_change", channel=channel, control=123, value=0)
                if self._output_callback is not None:
                    self._output_callback(message)
                if self._audio_callback is not None:
                    self._audio_callback(message)

    def play(self):
        if self.state.is_playing:
            return
        self.state.is_playing = True
        self.state.is_paused = False
        self._stop_event.clear()
        self._pause_event.clear()
        self._start_time = time.monotonic() - self.state.current_time / self.state.playback_speed
        self._last_time = self.state.current_time
        self._last_output_time = self.state.current_time - 1e-9
        self._output_index = bisect_left(self._output_times(), self.state.current_time)
        self._last_ui_callback_time = -1.0
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def pause(self):
        if not self.state.is_playing:
            return
        self.state.is_paused = True
        self._pause_event.set()
        self._silence_output()

    def resume(self):
        if not self.state.is_playing:
            return
        self.state.is_paused = False
        self._pause_event.clear()
        self._start_time = time.monotonic() - self.state.current_time / self.state.playback_speed
        self._last_output_time = self.state.current_time
        self._output_index = bisect_right(self._output_times(), self.state.current_time)

    def stop(self):
        self.state.is_playing = False
        self.state.is_paused = False
        self.state.current_time = 0.0
        self._stop_event.set()
        self._pause_event.set()
        self._silence_output()
        if self._thread is not None and self._thread is not current_thread():
            self._thread.join(timeout=1.0)
            self._thread = None

    def seek(self, seconds: float):
        self._silence_output()
        self.state.current_time = max(0.0, min(seconds, self.total_time))
        self._last_output_time = self.state.current_time
        self._output_index = bisect_right(self._output_times(), self.state.current_time)
        if self._callback is not None:
            self._callback(self.state.current_time)

    def set_speed(self, multiplier: float):
        self.state.playback_speed = multiplier

    def _run(self):
        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                time.sleep(0.001)
                continue

            self.state.current_time = min(
                self.total_time,
                max(0.0, (time.monotonic() - self._start_time) * self.state.playback_speed),
            )
            self._send_output_until(self.state.current_time)
            if self._callback is not None and (
                self._last_ui_callback_time < 0.0
                or self.state.current_time - self._last_ui_callback_time >= 1.0 / 60.0
                or self.state.current_time >= self.total_time
            ):
                self._callback(self.state.current_time)
                self._last_ui_callback_time = self.state.current_time
            if self.state.current_time >= self.total_time:
                self.state.is_playing = False
                self._stop_event.set()
                break
            time.sleep(0.001)

    def current_time(self):
        return self.state.current_time

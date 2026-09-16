from __future__ import annotations

import json
import logging
from bisect import bisect_left
from pathlib import Path
from typing import Dict, List, Optional

from PySide6 import QtCore, QtWidgets

from piano_app.audio.engine import create_audio_engine
from piano_app.learning.trainer import LearningTrainer
from piano_app.midi.device import MidiDeviceManager
from piano_app.midi.parser import GENERAL_MIDI_INSTRUMENTS, NoteEvent, parse_midi_file, parse_midi_info
from piano_app.midi.player import MidiPlayer
from piano_app.piano.notes import build_keyboard_layout, get_note_name
from piano_app.ui.falling_notes import FallingNote, FallingNotesView
from piano_app.ui.piano_view import PianoView


logger = logging.getLogger(__name__)


class PianoAppWindow(QtWidgets.QMainWindow):
    midi_message_received = QtCore.Signal(object)
    audio_message_received = QtCore.Signal(object)
    player_tick_received = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pianotea MIDI Piano")
        self.resize(1200, 720)

        self.midi_manager = MidiDeviceManager()
        self.software_synth = create_audio_engine(self)
        self.midi_events: List[NoteEvent] = []
        self.midi_info = None
        self.current_file: Optional[Path] = None
        self.player: Optional[MidiPlayer] = None
        self.learning_trainer: Optional[LearningTrainer] = None
        self.input_port_name: str = "Désactivé"
        self.output_port_name: str = "Désactivé"
        self.midi_enabled = False
        self.midi_output_enabled = False
        self.software_audio_enabled = True
        self.selected_track: Optional[int] = None
        self.active_notes: set[int] = set()
        self.last_held_note: Optional[int] = None
        self.keyboard_layout = build_keyboard_layout()
        self.keyboard_by_pitch = {note["midi_note"]: note for note in self.keyboard_layout}

        self._setup_ui()
        self.midi_message_received.connect(self._process_midi_input)
        self.audio_message_received.connect(self._process_audio_message)
        self.player_tick_received.connect(self._update_player_ui)
        self._refresh_midi_ports()

    def _setup_ui(self):
        self.central = QtWidgets.QWidget(self)
        self.setCentralWidget(self.central)

        self.main_layout = QtWidgets.QVBoxLayout(self.central)
        self.main_layout.setContentsMargins(12, 12, 12, 12)

        top_bar = QtWidgets.QHBoxLayout()
        self.file_label = QtWidgets.QLabel("Aucun fichier MIDI")
        top_bar.addWidget(self.file_label)

        self.open_button = QtWidgets.QPushButton("Ouvrir MIDI")
        self.play_button = QtWidgets.QPushButton("Play")
        self.pause_button = QtWidgets.QPushButton("Pause")
        self.stop_button = QtWidgets.QPushButton("Stop")
        top_bar.addWidget(self.open_button)
        top_bar.addWidget(self.play_button)
        top_bar.addWidget(self.pause_button)
        top_bar.addWidget(self.stop_button)

        self.playback_speed_combo = QtWidgets.QComboBox()
        self.playback_speed_combo.addItems(["25 %", "50 %", "75 %", "100 %", "125 %", "150 %"])
        self.playback_speed_combo.setCurrentText("100 %")
        top_bar.addWidget(self.playback_speed_combo)

        self.main_layout.addLayout(top_bar)

        self.timeline = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.timeline.setRange(0, 1000)
        self.main_layout.addWidget(self.timeline)

        self.time_label = QtWidgets.QLabel("00:00 / 00:00")
        self.main_layout.addWidget(self.time_label)

        self.track_combo = QtWidgets.QComboBox()
        self.track_combo.addItem("Toutes les pistes", None)
        self.track_combo.setEnabled(False)
        self.track_combo.currentIndexChanged.connect(self.on_track_changed)
        self.main_layout.addWidget(self.track_combo)

        self.instrument_combo = QtWidgets.QComboBox()
        self.instrument_combo.addItem("Instrument de la piste")
        self.instrument_combo.setEnabled(False)
        self.instrument_combo.currentIndexChanged.connect(self.on_instrument_changed)
        self.main_layout.addWidget(self.instrument_combo)

        self.visualisation = FallingNotesView(self)
        self.visualisation.setMinimumHeight(220)
        self.main_layout.addWidget(self.visualisation)

        self.piano_view = PianoView()
        self.main_layout.addWidget(self.piano_view)

        bottom_bar = QtWidgets.QHBoxLayout()
        self.midi_enable_checkbox = QtWidgets.QCheckBox("Activer MIDI")
        self.midi_enable_checkbox.setChecked(False)
        self.midi_input_label = QtWidgets.QLabel("MIDI Input:")
        self.midi_input_combo = QtWidgets.QComboBox()
        self.midi_input_combo.addItem("Désactivé")
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["Playback", "Learning"])
        self.midi_output_combo = QtWidgets.QComboBox()
        self.midi_output_combo.addItem("Désactivé")
        self.midi_output_label = QtWidgets.QLabel("Son / MIDI Output:")
        self.sound_checkbox = QtWidgets.QCheckBox("Son logiciel")
        self.sound_checkbox.setChecked(True)

        bottom_bar.addWidget(self.midi_enable_checkbox)
        bottom_bar.addWidget(self.sound_checkbox)
        bottom_bar.addWidget(self.midi_input_label)
        bottom_bar.addWidget(self.midi_input_combo)
        bottom_bar.addWidget(self.mode_combo)
        bottom_bar.addWidget(self.midi_output_label)
        bottom_bar.addWidget(self.midi_output_combo)
        self.main_layout.addLayout(bottom_bar)

        self.open_button.clicked.connect(self.open_midi_file)
        self.play_button.clicked.connect(self.play)
        self.pause_button.clicked.connect(self.pause)
        self.stop_button.clicked.connect(self.stop)
        self.timeline.valueChanged.connect(self.on_timeline_changed)
        self.playback_speed_combo.currentIndexChanged.connect(self.on_speed_changed)
        self.midi_input_combo.currentIndexChanged.connect(self.on_input_changed)
        self.midi_output_combo.currentIndexChanged.connect(self.on_output_changed)
        self.sound_checkbox.toggled.connect(self.on_sound_toggled)
        self.midi_enable_checkbox.toggled.connect(self.on_midi_enabled_changed)
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)

    def _refresh_midi_ports(self):
        if not self.midi_enabled:
            self.midi_input_combo.blockSignals(True)
            self.midi_input_combo.clear()
            self.midi_input_combo.addItem("Désactivé")
            self.midi_input_combo.setCurrentText("Désactivé")
            self.midi_input_combo.blockSignals(False)

            self.midi_output_combo.blockSignals(True)
            self.midi_output_combo.clear()
            self.midi_output_combo.addItem("Désactivé")
            self.midi_output_combo.setCurrentText("Désactivé")
            self.midi_output_combo.blockSignals(False)
            self.midi_manager.close_input()
            return

        input_ports = ["Désactivé"] + self.midi_manager.detect_input_ports()
        self.midi_input_combo.blockSignals(True)
        self.midi_input_combo.clear()
        self.midi_input_combo.addItems(input_ports)
        self.midi_input_combo.blockSignals(False)

        output_ports = ["Désactivé"] + self.midi_manager.detect_output_ports()
        self.midi_output_combo.blockSignals(True)
        self.midi_output_combo.clear()
        self.midi_output_combo.addItems(output_ports)
        self.midi_output_combo.blockSignals(False)

    def open_midi_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Ouvrir un fichier MIDI",
            "",
            "MIDI Files (*.mid *.midi)",
        )
        if not file_path:
            return

        self.current_file = Path(file_path)
        self.file_label.setText(self.current_file.name)
        try:
            self.midi_events = parse_midi_file(self.current_file)
            self.event_start_times = [event.start_time for event in self.midi_events]
            info = parse_midi_info(self.current_file)
            self.midi_info = info
            self.track_combo.blockSignals(True)
            self.track_combo.clear()
            self.track_combo.addItem("Toutes les pistes", None)
            for track in info.track_infos:
                if track.note_count:
                    self.track_combo.addItem(
                        f"{track.name} - {track.instrument} ({track.note_count} notes)",
                        track.index,
                    )
            self.track_combo.setEnabled(bool(info.track_infos))
            self.track_combo.blockSignals(False)
            self.player = MidiPlayer(self.midi_events, info.total_time)
            self.player.set_callback(self.on_player_tick)
            self.player.set_output_callback(self._send_midi_message)
            self.player.set_audio_callback(self._handle_audio_message)
            self.learning_trainer = LearningTrainer([event.pitch for event in self.midi_events])
            self.draw_falling_notes()
            self.timeline.setMaximum(int(max(info.total_time, 1.0) * 1000))
            self.time_label.setText(self._format_time(0.0, info.total_time))
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Erreur MIDI", f"Impossible de charger le fichier MIDI : {exc}")

    def on_player_tick(self, value: float):
        self.player_tick_received.emit()

    def _update_player_ui(self):
        if self.player is None:
            return
        value = self.player.current_time()
        self.timeline.blockSignals(True)
        self.timeline.setValue(int(value * 1000))
        self.timeline.blockSignals(False)
        self.time_label.setText(self._format_time(value, self.player.total_time))
        self.draw_falling_notes()

    def on_speed_changed(self, index: int):
        value = self.playback_speed_combo.itemText(index)
        multiplier = float(value.replace(" %", "")) / 100.0
        if self.player is not None:
            self.player.set_speed(multiplier)

    def on_timeline_changed(self, value: int):
        if self.player is not None:
            self.player.seek(value / 1000.0)

    def play(self):
        if self.player is None:
            return
        if self.player.state.is_paused:
            self.player.resume()
        else:
            self.player.play()

    def pause(self):
        if self.player is not None:
            self.player.pause()

    def stop(self):
        if self.player is not None:
            self.player.stop()
            self.timeline.setValue(0)
            self.time_label.setText(self._format_time(0.0, self.player.total_time))

    def on_midi_enabled_changed(self, enabled: bool):
        self.midi_enabled = enabled
        self._refresh_midi_ports()
        if not enabled:
            self.input_port_name = "Désactivé"
            self.output_port_name = "Désactivé"
            self.midi_manager.close_input()
            self.midi_manager.close_output()

    def on_input_changed(self, index: int):
        selected = self.midi_input_combo.itemText(index)
        if selected in {"Désactivé", "Aucun"}:
            self.input_port_name = "Désactivé"
            self.midi_manager.close_input()
            return
        self.input_port_name = selected
        try:
            self.midi_manager.open_input(selected, self.handle_midi_input)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "MIDI Input", f"Impossible d'ouvrir le périphérique MIDI : {exc}")

    def on_mode_changed(self, index: int):
        if self.learning_trainer is None:
            return
        mode = self.mode_combo.itemText(index)
        self.learning_trainer.set_mode(mode.lower())

    def on_track_changed(self, index: int):
        self.selected_track = self.track_combo.itemData(index)
        self._refresh_instrument_combo()
        if self.player is not None:
            self.player.set_track_filter(self.selected_track)
        self.draw_falling_notes()

    def _refresh_instrument_combo(self):
        self.instrument_combo.blockSignals(True)
        self.instrument_combo.clear()
        if self.selected_track is None or self.midi_info is None:
            self.instrument_combo.addItem("Instrument de la piste")
            self.instrument_combo.setEnabled(False)
        else:
            track = next((item for item in self.midi_info.track_infos if item.index == self.selected_track), None)
            if track is None:
                self.instrument_combo.addItem("Instrument de la piste")
                self.instrument_combo.setEnabled(False)
            else:
                for program in range(128):
                    name = GENERAL_MIDI_INSTRUMENTS[program] if program < len(GENERAL_MIDI_INSTRUMENTS) else f"Program {program}"
                    self.instrument_combo.addItem(f"{program:03d} - {name}", program)
                self.instrument_combo.setCurrentIndex(track.program)
                self.instrument_combo.setEnabled(True)
        self.instrument_combo.blockSignals(False)

    def on_instrument_changed(self, index: int):
        if self.selected_track is None or self.midi_info is None:
            return
        program = self.instrument_combo.itemData(index)
        if program is None:
            return
        track = next((item for item in self.midi_info.track_infos if item.index == self.selected_track), None)
        if track is None:
            return
        instrument = GENERAL_MIDI_INSTRUMENTS[program] if program < len(GENERAL_MIDI_INSTRUMENTS) else f"Program {program}"
        track.program = program
        track.instrument = instrument
        for event in self.midi_events:
            if event.track == self.selected_track:
                event.program = program
                event.instrument = instrument
        if self.player is not None:
            self.player.refresh_events()

    def on_output_changed(self, index: int):
        selected = self.midi_output_combo.itemText(index)
        if selected in {"Désactivé", "Aucun"}:
            self.output_port_name = "Désactivé"
            self.midi_manager.close_output()
            return
        try:
            self.midi_manager.open_output(selected)
            self.output_port_name = selected
        except Exception as exc:
            self.output_port_name = "Désactivé"
            QtWidgets.QMessageBox.warning(self, "MIDI Output", f"Impossible d'ouvrir la sortie MIDI : {exc}")

    def on_sound_toggled(self, enabled: bool):
        self.software_audio_enabled = enabled
        self.software_synth.set_enabled(enabled)

    def _handle_audio_message(self, message):
        self.audio_message_received.emit(message)

    def _process_audio_message(self, message):
        self.software_synth.handle_message(message)

    def _send_midi_message(self, message):
        if self.output_port_name != "Désactivé":
            self.midi_manager.send(message)

    def closeEvent(self, event):
        if self.player is not None:
            self.player.stop()
        self.midi_manager.close_input()
        self.midi_manager.close_output()
        self.software_synth.close()
        super().closeEvent(event)

    def handle_midi_input(self, message, data=None):
        self.midi_message_received.emit(message)

    def _process_midi_input(self, message):
        if not hasattr(message, "type"):
            return
        if message.type == "note_on" and message.velocity > 0:
            self.active_notes.add(message.note)
            self.piano_view.set_key_active(message.note, True)
            self.piano_view.set_key_pressed(message.note, True)
        elif message.type in {"note_off", "note_on"} and getattr(message, "velocity", 0) == 0:
            self.active_notes.discard(message.note)
            self.piano_view.set_key_active(message.note, False)
            self.piano_view.set_key_pressed(message.note, False)
        elif message.type == "control_change" and message.control == 64:
            if message.value >= 64:
                self.active_notes = set(self.active_notes)

    def draw_falling_notes(self):
        if self.player is None or not self.midi_events:
            self.visualisation.set_notes([])
            return

        current_time = self.player.current_time()
        view_width = self.visualisation.width() or 800
        notes: List[FallingNote] = []

        keyboard_layout = self.keyboard_layout
        white_count = 52
        white_width = (view_width - 40) / white_count
        first_event = bisect_left(self.event_start_times, current_time)
        visible_seconds = max(2.0, (self.visualisation.height() - 20) / 80.0)
        for event in self.midi_events[first_event:]:
            if event.start_time - current_time > visible_seconds:
                break
            if self.selected_track is not None and event.track != self.selected_track:
                continue
            if current_time < event.start_time:
                distance = event.start_time - current_time
                y = (distance * 80) + 20
                key = self.keyboard_by_pitch.get(event.pitch)
                if key is None:
                    continue
                if key["white"]:
                    x = 20 + key["white_index"] * white_width
                    width = white_width * 0.82
                else:
                    x = 20 + (key["white_index"] + 1) * white_width - white_width * 0.25
                    width = white_width * 0.5
                notes.append(FallingNote(event.pitch, x, y, max(20, event.duration * 80 * 2), False, width))

        self.visualisation.set_notes(notes)

    def _format_time(self, current: float, total: float) -> str:
        def fmt(seconds: float):
            minutes, secs = divmod(int(seconds), 60)
            return f"{minutes:02d}:{secs:02d}"

        return f"{fmt(current)} / {fmt(total)}"

    def closeEvent(self, event):
        self.software_synth.close()
        self.midi_manager.close_input()
        self.midi_manager.close_output()
        super().closeEvent(event)


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    window = PianoAppWindow()
    window.show()
    sys.exit(app.exec())

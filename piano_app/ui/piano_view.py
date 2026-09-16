from __future__ import annotations

from typing import Dict

from PySide6 import QtCore, QtGui, QtWidgets

from piano_app.piano.notes import build_keyboard_layout


class PianoKeyWidget(QtWidgets.QWidget):
    def __init__(self, midi_note: int, white: bool, parent=None):
        super().__init__(parent)
        self.midi_note = midi_note
        self.white = white
        self.active = False
        self._pressed = False
        self.setMinimumHeight(56)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        if self.white:
            color = QtGui.QColor(245, 245, 245)
            outline = QtGui.QColor(140, 140, 140)
        else:
            color = QtGui.QColor(34, 34, 34)
            outline = QtGui.QColor(20, 20, 20)

        if self.active:
            color = QtGui.QColor(105, 167, 255) if self.white else QtGui.QColor(86, 120, 230)

        painter.setPen(QtGui.QPen(outline, 1))
        painter.setBrush(color)
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 2, 2)

        if self._pressed:
            painter.setBrush(QtGui.QColor(255, 201, 78))
            painter.drawRect(rect.adjusted(4, 4, -5, -5))

    def set_active(self, value: bool):
        self.active = value
        self.update()

    def set_pressed(self, value: bool):
        self._pressed = value
        self.update()


class PianoView(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.layout_data = build_keyboard_layout()
        self.white_keys = [note for note in self.layout_data if note["white"]]
        self.black_keys = [note for note in self.layout_data if note["black"]]
        self.key_widgets: Dict[int, PianoKeyWidget] = {}
        self._build_ui()

    def _build_ui(self):
        self.setMinimumHeight(220)
        self.root_layout = QtWidgets.QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        self.keyboard_widget = QtWidgets.QWidget(self)
        self.keyboard_widget.setObjectName("keyboard")
        self.keyboard_widget.setMinimumHeight(170)

        white_notes = [note for note in self.layout_data if note["white"]]
        for note in white_notes:
            key_widget = PianoKeyWidget(note["midi_note"], True, self.keyboard_widget)
            self.key_widgets[note["midi_note"]] = key_widget
            key_widget.lower()

        for note in self.layout_data:
            if note["black"]:
                key_widget = PianoKeyWidget(note["midi_note"], False, self.keyboard_widget)
                self.key_widgets[note["midi_note"]] = key_widget
                key_widget.raise_()

        self.root_layout.addWidget(self.keyboard_widget)
        self.root_layout.addStretch(1)

    def set_key_active(self, midi_note: int, active: bool):
        widget = self.key_widgets.get(midi_note)
        if widget is not None:
            widget.set_active(active)

    def set_key_pressed(self, midi_note: int, active: bool):
        widget = self.key_widgets.get(midi_note)
        if widget is not None:
            widget.set_pressed(active)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        white_notes = [note for note in self.layout_data if note["white"]]
        white_width = self.keyboard_widget.width() / len(white_notes)
        white_height = self.keyboard_widget.height()
        black_width = max(12, white_width * 0.58)
        black_height = white_height * 0.62

        for note in white_notes:
            widget = self.key_widgets[note["midi_note"]]
            widget.setGeometry(round(note["white_index"] * white_width), 0, round(white_width) + 1, white_height)

        for note in self.black_keys:
            widget = self.key_widgets[note["midi_note"]]
            x = (note["white_index"] + 1) * white_width - black_width / 2
            widget.setGeometry(round(x), 0, round(black_width), round(black_height))

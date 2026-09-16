from __future__ import annotations

from dataclasses import dataclass
from typing import List

from PySide6 import QtCore, QtGui, QtWidgets


@dataclass
class FallingNote:
    midi_note: int
    x: float
    y: float
    height: float
    active: bool = False
    width: float = 16.0


class FallingNotesView(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.notes: List[FallingNote] = []
        self._note_color = QtGui.QColor(60, 140, 255)
        self.setMinimumHeight(180)

    def set_notes(self, notes: List[FallingNote]):
        self.notes = notes
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(16, 16, 22))

        hit_y = self.height() - 8
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 201, 78), 2))
        painter.drawLine(0, hit_y, self.width(), hit_y)

        for note in self.notes:
            rect = QtCore.QRectF(
                note.x,
                note.y,
                note.width,
                max(18.0, note.height),
            )
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(255, 201, 78) if note.active else self._note_color)
            painter.drawRoundedRect(rect, 4, 4)

        painter.end()

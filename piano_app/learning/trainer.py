from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass
class LearningState:
    expected_notes: List[int] = field(default_factory=list)
    active_expected: Set[int] = field(default_factory=set)
    current_index: int = 0
    mode: str = "playback"
    pending_mistakes: int = 0
    free_mode: bool = False


class LearningTrainer:
    def __init__(self, midi_notes: List[int]):
        self.notes = list(midi_notes)
        self.state = LearningState(expected_notes=list(midi_notes))

    def set_mode(self, mode: str):
        self.state.mode = mode

    def set_free_mode(self, enabled: bool):
        self.state.free_mode = enabled

    def note_ready(self, time_seconds: float) -> Optional[int]:
        if not self.notes:
            return None
        if self.state.current_index >= len(self.notes):
            return None
        return self.notes[self.state.current_index]

    def accept_note(self, midi_note: int) -> bool:
        current = self.note_ready(0.0)
        if current is None:
            return False
        if midi_note == current:
            self.state.current_index += 1
            return True
        self.state.pending_mistakes += 1
        return self.state.free_mode

    def reset(self):
        self.state.current_index = 0
        self.state.pending_mistakes = 0

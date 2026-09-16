from __future__ import annotations

from typing import Dict, List

MIDI_NOTE_TO_NAME: Dict[int, str] = {}
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

for midi_note in range(21, 109):
    octave = midi_note // 12 - 1
    note_index = midi_note % 12
    note_name = NOTE_NAMES[note_index]
    MIDI_NOTE_TO_NAME[midi_note] = f"{note_name}{octave}"


def get_note_name(midi_note: int) -> str:
    if midi_note < 0 or midi_note > 127:
        raise ValueError(f"MIDI note out of range: {midi_note}")
    return MIDI_NOTE_TO_NAME.get(midi_note, f"Note{midi_note}")


def build_keyboard_layout() -> List[dict]:
    layout: List[dict] = []
    white_keys = [0, 2, 4, 5, 7, 9, 11]
    black_keys = {1: "C#", 3: "D#", 6: "F#", 8: "G#", 10: "A#"}

    for midi_note in range(21, 109):
        name = get_note_name(midi_note)
        is_white = midi_note % 12 in white_keys
        is_black = not is_white
        layout.append({
            "midi_note": midi_note,
            "name": name,
            "white": is_white,
            "black": is_black,
            "x": 0.0,
            "width": 0.0,
        })

    white_index = 0
    for note in layout:
        if note["white"]:
            note["white_index"] = white_index
            white_index += 1
        else:
            note["white_index"] = white_index - 1

    # ensure every note in the real piano range exists, including accidentals
    assert len(layout) == 88
    return layout


def midi_to_name(midi_note: int) -> str:
    return get_note_name(midi_note)

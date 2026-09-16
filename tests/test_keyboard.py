from piano_app.piano.notes import build_keyboard_layout


def test_keyboard_has_88_notes_and_white_black_counts():
    layout = build_keyboard_layout()
    assert len(layout) == 88
    assert sum(1 for key in layout if key["white"]) == 52
    assert sum(1 for key in layout if key["black"]) == 36
    assert layout[0]["midi_note"] == 21
    assert layout[-1]["midi_note"] == 108

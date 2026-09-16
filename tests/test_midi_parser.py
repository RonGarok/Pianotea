from pathlib import Path

import mido

from piano_app.midi.parser import NoteEvent, parse_midi_file
from piano_app.piano.notes import MIDI_NOTE_TO_NAME, get_note_name


def test_note_lookup_for_c4_and_a0():
    assert get_note_name(21) == "A0"
    assert get_note_name(60) == "C4"
    assert get_note_name(108) == "C8"
    assert MIDI_NOTE_TO_NAME[60] == "C4"


def test_parse_midi_file_creates_events(tmp_path):
    midi_path = tmp_path / "test.mid"
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    track.append(mido.Message("note_on", note=60, velocity=64, time=0))
    track.append(mido.Message("note_off", note=60, velocity=64, time=480))
    mid.tracks.append(track)
    mid.save(midi_path)

    events = parse_midi_file(midi_path)
    assert len(events) == 1
    assert isinstance(events[0], NoteEvent)
    assert events[0].pitch == 60
    assert events[0].start_time == 0.0
    assert events[0].duration > 0


def test_parse_midi_file_keeps_same_note_on_separate_tracks(tmp_path):
    midi_path = tmp_path / "multi-track.mid"
    mid = mido.MidiFile()
    first = mido.MidiTrack()
    first.append(mido.MetaMessage("track_name", name="Piano", time=0))
    first.append(mido.Message("program_change", program=0, channel=0, time=0))
    first.append(mido.Message("note_on", note=60, velocity=80, channel=0, time=0))
    first.append(mido.Message("note_off", note=60, velocity=0, channel=0, time=240))
    second = mido.MidiTrack()
    second.append(mido.MetaMessage("track_name", name="Strings", time=0))
    second.append(mido.Message("program_change", program=48, channel=1, time=0))
    second.append(mido.Message("note_on", note=60, velocity=70, channel=1, time=0))
    second.append(mido.Message("note_off", note=60, velocity=0, channel=1, time=480))
    mid.tracks.extend([first, second])
    mid.save(midi_path)

    from piano_app.midi.parser import parse_midi_info

    info = parse_midi_info(midi_path)
    assert len(info.notes) == 2
    assert {event.track for event in info.notes} == {0, 1}
    assert info.track_infos[0].name == "Piano"
    assert info.track_infos[1].instrument == "Program 48"


def test_player_sends_all_events_that_share_the_same_timestamp():
    from piano_app.midi.player import MidiPlayer

    events = [
        NoteEvent(pitch=60, velocity=80, start_time=0.0, duration=0.2, channel=0, track=0, note_name="C4", program=0),
        NoteEvent(pitch=64, velocity=70, start_time=0.0, duration=0.2, channel=0, track=0, note_name="E4", program=0),
    ]
    player = MidiPlayer(events, 0.5)
    sent = []
    player.set_output_callback(sent.append)
    player._last_output_time = -1.0
    player._output_index = 0

    player._send_output_until(0.0)

    assert [message.type for message in sent] == ["program_change", "note_on", "note_on"]

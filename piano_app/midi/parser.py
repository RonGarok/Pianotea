from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import mido


@dataclass
class NoteEvent:
    pitch: int
    velocity: int
    start_time: float
    duration: float
    channel: int
    track: int
    note_name: str
    program: int = 0
    instrument: str = "Piano"


@dataclass
class MidiTrackInfo:
    index: int
    name: str
    channel: int | None
    program: int
    instrument: str
    note_count: int


@dataclass
class MidiFileInfo:
    file_path: str
    title: str
    total_time: float
    tempo: float
    ticks_per_beat: int
    tracks: int
    instruments: List[str]
    track_infos: List[MidiTrackInfo]
    notes: List[NoteEvent]


def _midi_note_to_name(pitch: int) -> str:
    note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = pitch // 12 - 1
    return f"{note_names[pitch % 12]}{octave}"


def _resolve_tempo(msg, current_tempo):
    if msg.type == "set_tempo":
        return msg.tempo / 1_000_000.0
    return current_tempo


def _seconds_from_ticks(ticks: int, tempo: float, ticks_per_beat: int) -> float:
    if tempo <= 0:
        return 0.0
    beats = ticks / ticks_per_beat
    return beats * (60.0 / tempo)


GENERAL_MIDI_INSTRUMENTS = [
    "Piano", "Bright Piano", "Electric Piano", "Honky-tonk Piano", "Electric Piano 1",
    "Electric Piano 2", "Harpsichord", "Clavinet", "Celesta", "Glockenspiel",
    "Music Box", "Vibraphone", "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
    "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ", "Reed Organ",
    "Accordion", "Harmonica", "Tango Accordion", "Acoustic Guitar (nylon)",
    "Acoustic Guitar (steel)", "Electric Guitar (jazz)", "Electric Guitar (clean)",
    "Electric Guitar (muted)", "Overdriven Guitar", "Distortion Guitar", "Guitar Harmonics",
]


def _instrument_name(program: int) -> str:
    return GENERAL_MIDI_INSTRUMENTS[program] if program < len(GENERAL_MIDI_INSTRUMENTS) else f"Program {program}"


def _build_tempo_map(midi: mido.MidiFile) -> list[tuple[int, float]]:
    changes = [(0, 500000.0)]
    if midi.tracks:
        absolute_ticks = 0
        for msg in midi.tracks[0]:
            absolute_ticks += msg.time
            if msg.type == "set_tempo":
                changes.append((absolute_ticks, float(msg.tempo)))
    return sorted(dict(changes).items())


def _ticks_to_seconds(ticks: int, tempo_map: list[tuple[int, float]], ticks_per_beat: int) -> float:
    seconds = 0.0
    previous_tick = 0
    tempo = 500000.0
    for change_tick, change_tempo in tempo_map:
        if change_tick >= ticks:
            break
        segment_ticks = change_tick - previous_tick
        seconds += segment_ticks * (tempo / 1_000_000.0) / ticks_per_beat
        previous_tick = change_tick
        tempo = change_tempo
    seconds += (ticks - previous_tick) * (tempo / 1_000_000.0) / ticks_per_beat
    return seconds


def parse_midi_file(file_path: str | Path) -> List[NoteEvent]:
    midi_path = Path(file_path)
    midi = mido.MidiFile(str(midi_path))
    if not midi.tracks:
        return []

    tempo = 120.0
    ticks_per_beat = midi.ticks_per_beat
    tempo_map = _build_tempo_map(midi)
    tracked_notes: dict[tuple[int, int, int], tuple[int, int, int, int]] = {}
    events: List[NoteEvent] = []

    for track_index, track in enumerate(midi.tracks):
        current_ticks = 0
        programs = [0] * 16
        for msg in track:
            current_ticks += msg.time
            if msg.type == "program_change":
                programs[msg.channel] = msg.program
            if msg.type == "note_on" and msg.velocity > 0:
                tracked_notes[(track_index, msg.channel, msg.note)] = (msg.velocity, current_ticks, programs[msg.channel], msg.channel)
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                key = (track_index, msg.channel, msg.note)
                if key in tracked_notes:
                    velocity, start_ticks, program, channel = tracked_notes.pop(key)
                    start_seconds = _ticks_to_seconds(start_ticks, tempo_map, ticks_per_beat)
                    end_seconds = _ticks_to_seconds(current_ticks, tempo_map, ticks_per_beat)
                    duration = max(0.0, end_seconds - start_seconds)
                    events.append(
                        NoteEvent(
                            pitch=msg.note,
                            velocity=velocity,
                            start_time=start_seconds,
                            duration=duration,
                            channel=msg.channel,
                            track=track_index,
                            note_name=_midi_note_to_name(msg.note),
                            program=program,
                            instrument=_instrument_name(program),
                        )
                    )

    events.sort(key=lambda event: (event.start_time, event.pitch))
    return events


def parse_midi_info(file_path: str | Path) -> MidiFileInfo:
    midi_path = Path(file_path)
    midi = mido.MidiFile(str(midi_path))
    notes = parse_midi_file(midi_path)
    total_time = max((event.start_time + event.duration for event in notes), default=0.0)
    tempo = 120.0
    instruments: List[str] = []
    track_infos: List[MidiTrackInfo] = []

    for track_index, track in enumerate(midi.tracks):
        track_name = f"Piste {track_index + 1}"
        channel = None
        program = 0
        note_count = 0
        for msg in track:
            if msg.type == "set_tempo":
                tempo = msg.tempo / 1_000_000.0
            elif msg.type == "program_change":
                program = msg.program
                channel = msg.channel
            elif msg.type == "track_name":
                track_name = msg.name
            elif msg.type == "note_on" and msg.velocity > 0:
                note_count += 1
        instrument = _instrument_name(program)
        track_infos.append(MidiTrackInfo(track_index, track_name, channel, program, instrument, note_count))
        if note_count:
            instruments.append(f"{track_name} - {instrument}")

    return MidiFileInfo(
        file_path=str(midi_path),
        title=midi_path.stem,
        total_time=total_time,
        tempo=tempo,
        ticks_per_beat=midi.ticks_per_beat,
        tracks=len(midi.tracks),
        instruments=instruments,
        track_infos=track_infos,
        notes=notes,
    )

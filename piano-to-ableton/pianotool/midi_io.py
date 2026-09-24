"""Opslaan en inlezen van MIDI-bestanden (Standard MIDI File, type 1).

Ableton Live leest type-1 .mid-bestanden rechtstreeks in: sleep het bestand in
een MIDI-track of in de Session View en elke track in het bestand wordt een clip.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import mido

PPQ = 480  # ticks per kwartnoot


@dataclass
class Note:
    pitch: int
    start: float  # seconden vanaf begin van de take
    end: float
    velocity: int
    channel: int = 0


@dataclass
class Control:
    """Een controller-event (bv. sustainpedaal CC64) of pitch bend."""

    time: float
    kind: str  # "cc" of "pitchwheel"
    number: int  # CC-nummer (genegeerd bij pitchwheel)
    value: int
    channel: int = 0


@dataclass
class Track:
    name: str
    notes: list[Note] = field(default_factory=list)
    controls: list[Control] = field(default_factory=list)
    program: int | None = None  # General MIDI programma (0 = piano)
    channel: int = 0


@dataclass
class Song:
    bpm: float
    tracks: list[Track]
    time_signature: tuple[int, int] = (4, 4)

    @property
    def duration(self) -> float:
        ends = [n.end for t in self.tracks for n in t.notes]
        ends += [c.time for t in self.tracks for c in t.controls]
        return max(ends, default=0.0)


def seconds_to_ticks(seconds: float, bpm: float) -> int:
    return max(0, round(seconds * bpm / 60.0 * PPQ))


def ticks_to_seconds(ticks: int, bpm: float) -> float:
    return ticks / PPQ * 60.0 / bpm


def _track_to_events(track: Track, bpm: float) -> list[tuple[int, int, mido.Message]]:
    """Zet een track om naar (tick, volgorde, bericht)-tuples.

    De volgorde zorgt dat op dezelfde tick eerst note_offs komen, zodat een
    herhaalde toon niet direct weer wordt afgekapt.
    """
    ch = track.channel
    events: list[tuple[int, int, mido.Message]] = []
    if track.program is not None and ch != 9:
        events.append((0, 0, mido.Message("program_change", program=track.program, channel=ch)))
    for n in track.notes:
        on = seconds_to_ticks(n.start, bpm)
        off = max(on + 1, seconds_to_ticks(n.end, bpm))
        pitch = min(127, max(0, n.pitch))
        vel = min(127, max(1, n.velocity))
        events.append((on, 2, mido.Message("note_on", note=pitch, velocity=vel, channel=ch)))
        events.append((off, 1, mido.Message("note_off", note=pitch, velocity=0, channel=ch)))
    for c in track.controls:
        tick = seconds_to_ticks(c.time, bpm)
        if c.kind == "pitchwheel":
            msg = mido.Message("pitchwheel", pitch=c.value, channel=ch)
        else:
            msg = mido.Message("control_change", control=c.number, value=c.value, channel=ch)
        events.append((tick, 1, msg))
    events.sort(key=lambda e: (e[0], e[1]))
    return events


def save_song(song: Song, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mid = mido.MidiFile(type=1, ticks_per_beat=PPQ)

    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("track_name", name="Tempo", time=0))
    meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(song.bpm), time=0))
    num, den = song.time_signature
    meta.append(mido.MetaMessage("time_signature", numerator=num, denominator=den, time=0))
    meta.append(mido.MetaMessage("end_of_track", time=0))
    mid.tracks.append(meta)

    for track in song.tracks:
        mt = mido.MidiTrack()
        mt.append(mido.MetaMessage("track_name", name=track.name, time=0))
        last = 0
        for tick, _, msg in _track_to_events(track, song.bpm):
            mt.append(msg.copy(time=tick - last))
            last = tick
        mt.append(mido.MetaMessage("end_of_track", time=0))
        mid.tracks.append(mt)

    mid.save(path)
    return path


def load_song(path: str | Path) -> Song:
    """Lees een .mid-bestand in. Tempowisselingen worden correct verrekend."""
    mid = mido.MidiFile(path)
    bpm = 120.0
    tracks: list[Track] = []
    first_tempo_seen = False

    # Tempokaart opbouwen (tempo kan in elke track staan, meestal track 0).
    tempo_changes: list[tuple[int, int]] = []
    for mt in mid.tracks:
        tick = 0
        for msg in mt:
            tick += msg.time
            if msg.type == "set_tempo":
                tempo_changes.append((tick, msg.tempo))
                if not first_tempo_seen:
                    bpm = mido.tempo2bpm(msg.tempo)
                    first_tempo_seen = True
    tempo_changes.sort()

    def tick_to_sec(t: int) -> float:
        sec, prev_tick, tempo = 0.0, 0, 500000
        for change_tick, change_tempo in tempo_changes:
            if change_tick >= t:
                break
            sec += mido.tick2second(change_tick - prev_tick, mid.ticks_per_beat, tempo)
            prev_tick, tempo = change_tick, change_tempo
        return sec + mido.tick2second(t - prev_tick, mid.ticks_per_beat, tempo)

    for i, mt in enumerate(mid.tracks):
        track = Track(name=mt.name or f"Track {i}")
        open_notes: dict[tuple[int, int], list[tuple[float, int]]] = {}
        tick = 0
        channels: set[int] = set()
        for msg in mt:
            tick += msg.time
            if msg.is_meta:
                continue
            t = tick_to_sec(tick)
            if msg.type == "note_on" and msg.velocity > 0:
                open_notes.setdefault((msg.channel, msg.note), []).append((t, msg.velocity))
                channels.add(msg.channel)
            elif msg.type in ("note_off", "note_on"):
                stack = open_notes.get((msg.channel, msg.note))
                if stack:
                    start, vel = stack.pop(0)
                    track.notes.append(Note(msg.note, start, t, vel, msg.channel))
            elif msg.type == "control_change":
                track.controls.append(Control(t, "cc", msg.control, msg.value, msg.channel))
            elif msg.type == "pitchwheel":
                track.controls.append(Control(t, "pitchwheel", 0, msg.pitch, msg.channel))
            elif msg.type == "program_change" and track.program is None:
                track.program = msg.program
        if channels:
            track.channel = min(channels)
        if track.notes or track.controls:
            track.notes.sort(key=lambda n: (n.start, n.pitch))
            tracks.append(track)

    return Song(bpm=bpm, tracks=tracks)

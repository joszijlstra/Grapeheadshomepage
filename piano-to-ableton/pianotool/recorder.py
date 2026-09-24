"""Live opnemen van een MIDI-piano.

De recorder luistert continu. Zodra je de eerste toets aanslaat begint een
nieuwe "take"; als het een tijd stil is (geen toetsen, geen pedaal) wordt de
take automatisch als .mid-bestand opgeslagen. Je hoeft dus niets aan te klikken:
gewoon spelen, even stoppen, en het idee staat klaar voor Ableton.
"""

from __future__ import annotations

import queue
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import mido

from .midi_io import Control, Note, Song, Track, save_song

SUSTAIN_CC = 64
IGNORED_PORT_WORDS = ("through", "thru", "rtmidi", "iac")


def list_inputs() -> list[str]:
    return mido.get_input_names()


def find_piano_port(preferred: str | None = None) -> str | None:
    """Kies automatisch de piano.

    Met ``preferred`` wordt de eerste poort gekozen waarvan de naam die tekst bevat
    (hoofdletterongevoelig). Anders de eerste 'echte' hardwarepoort, dus geen
    virtuele doorvoerpoorten zoals 'Midi Through' of de IAC-driver.
    """
    names = list_inputs()
    if preferred:
        for name in names:
            if preferred.lower() in name.lower():
                return name
        return None
    for name in names:
        if not any(word in name.lower() for word in IGNORED_PORT_WORDS):
            return name
    return None


@dataclass
class TakeBuilder:
    """Bouwt één take op uit binnenkomende MIDI-berichten (zonder hardware testbaar)."""

    t0: float
    notes: list[Note] = field(default_factory=list)
    controls: list[Control] = field(default_factory=list)
    open_notes: dict[tuple[int, int], tuple[float, int]] = field(default_factory=dict)
    pedal_down: bool = False
    last_activity: float = 0.0

    def feed(self, msg: mido.Message, t: float) -> None:
        rel = t - self.t0
        self.last_activity = t
        if msg.type == "note_on" and msg.velocity > 0:
            key = (msg.channel, msg.note)
            if key in self.open_notes:  # dubbele note_on: sluit de vorige af
                self._close(key, rel)
            self.open_notes[key] = (rel, msg.velocity)
        elif msg.type in ("note_off", "note_on"):
            self._close((msg.channel, msg.note), rel)
        elif msg.type == "control_change":
            self.controls.append(Control(rel, "cc", msg.control, msg.value, msg.channel))
            if msg.control == SUSTAIN_CC:
                self.pedal_down = msg.value >= 64
        elif msg.type == "pitchwheel":
            self.controls.append(Control(rel, "pitchwheel", 0, msg.pitch, msg.channel))

    def _close(self, key: tuple[int, int], rel: float) -> None:
        opened = self.open_notes.pop(key, None)
        if opened:
            start, vel = opened
            self.notes.append(Note(key[1], start, max(rel, start + 0.01), vel, key[0]))

    @property
    def idle(self) -> bool:
        return not self.open_notes and not self.pedal_down

    def finish(self, t: float, bpm: float, name: str = "Piano") -> Song:
        rel = t - self.t0
        for key in list(self.open_notes):
            self._close(key, rel)
        if self.pedal_down:  # pedaal netjes loslaten aan het eind
            self.controls.append(Control(rel, "cc", SUSTAIN_CC, 0, 0))
        self.notes.sort(key=lambda n: (n.start, n.pitch))
        return Song(bpm=bpm, tracks=[Track(name=name, notes=self.notes, controls=self.controls, program=0)])


def take_filename(out_dir: Path, when: datetime | None = None) -> Path:
    when = when or datetime.now()
    return out_dir / f"take_{when:%Y%m%d_%H%M%S}.mid"


def record(
    port_name: str,
    out_dir: Path,
    bpm: float = 120.0,
    silence: float = 4.0,
    lead_in: float = 0.0,
    min_notes: int = 3,
    on_saved: Callable[[Path, Song], None] | None = None,
    log: Callable[[str], None] = print,
) -> None:
    """Luister op ``port_name`` en sla elke take op in ``out_dir``. Stop met Ctrl+C.

    ``silence``: seconden stilte waarna een take wordt afgesloten.
    ``lead_in``: stilte (seconden) vóór de eerste noot in het bestand, handig als
    je de clip in Ableton op een maatstreep wilt laten beginnen.
    ``min_notes``: takes met minder noten (bv. per ongeluk een toets geraakt) worden weggegooid.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    inbox: queue.Queue[tuple[mido.Message, float]] = queue.Queue()

    def callback(msg: mido.Message) -> None:
        inbox.put((msg, time.perf_counter()))

    take: TakeBuilder | None = None

    def close_take(now: float) -> None:
        nonlocal take
        if take is None:
            return
        song = take.finish(now, bpm)
        count = len(song.tracks[0].notes)
        take = None
        if count < min_notes:
            log(f"  (take met {count} noot/noten genegeerd)")
            return
        path = save_song(song, take_filename(out_dir))
        log(f"✔ Opgeslagen: {path}  ({count} noten, {song.duration:.1f} s)")
        if on_saved:
            on_saved(path, song)

    with mido.open_input(port_name, callback=callback):
        log(f"🎹 Luistert naar '{port_name}'. Speel maar! (Ctrl+C om te stoppen)")
        log(f"   Een take wordt opgeslagen na {silence:g} s stilte in: {out_dir}")
        try:
            while True:
                try:
                    msg, t = inbox.get(timeout=0.1)
                except queue.Empty:
                    now = time.perf_counter()
                    if take and take.idle and now - take.last_activity >= silence:
                        close_take(take.last_activity)
                    continue
                if msg.type in ("clock", "active_sensing", "start", "stop", "continue"):
                    continue
                if take is None:
                    if not (msg.type == "note_on" and msg.velocity > 0):
                        continue  # take begint pas bij de eerste aangeslagen toets
                    take = TakeBuilder(t0=t - lead_in)
                    log("● Opname gestart…")
                take.feed(msg, t)
        except KeyboardInterrupt:
            close_take(time.perf_counter())
            log("Gestopt.")

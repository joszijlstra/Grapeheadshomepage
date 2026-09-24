"""Afspelen (naspelen) van takes en arrangementen.

Twee manieren:
- naar de piano zelf: de piano speelt je opname na via zijn eigen klank en speakers
  (de meeste digitale piano's ontvangen MIDI via dezelfde USB-kabel);
- naar een virtuele MIDI-poort "Pianotool" (macOS): GarageBand, Logic of Ableton
  pakken die op en spelen het af met hun instrumenten, via de speakers van je Mac.
"""

from __future__ import annotations

import time
from typing import Callable

import mido

from .midi_io import Song, ticks_to_seconds, track_events
from .recorder import IGNORED_PORT_WORDS

VIRTUAL_PORT_NAME = "Pianotool"


def list_outputs() -> list[str]:
    return mido.get_output_names()


def find_output_port(preferred: str | None = None) -> str | None:
    """Kies de uitgang: met ``preferred`` de eerste poort die die tekst bevat, anders de piano."""
    names = list_outputs()
    if preferred:
        return next((n for n in names if preferred.lower() in n.lower()), None)
    return next((n for n in names if not any(w in n.lower() for w in IGNORED_PORT_WORDS)), None)


def schedule(song: Song, tracks: list[str] | None = None) -> list[tuple[float, mido.Message]]:
    """Alle berichten van (een selectie van) de tracks, gesorteerd op tijd in seconden."""
    selected = [
        t for t in song.tracks
        if not tracks or any(sel.lower() in t.name.lower() for sel in tracks)
    ]
    events = []
    for t in selected:
        for tick, order, msg in track_events(t, song.bpm):
            events.append((ticks_to_seconds(tick, song.bpm), order, msg))
    events.sort(key=lambda e: (e[0], e[1]))
    return [(sec, msg) for sec, _, msg in events]


def all_notes_off(port) -> None:
    for ch in range(16):
        port.send(mido.Message("control_change", control=64, value=0, channel=ch))
        port.send(mido.Message("control_change", control=123, value=0, channel=ch))


def play_song(
    song: Song,
    port_name: str | None = None,
    virtual: bool = False,
    tracks: list[str] | None = None,
    open_output: Callable = mido.open_output,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> int:
    """Speel een Song af. Geeft het aantal verstuurde berichten terug. Ctrl+C stopt netjes."""
    events = schedule(song, tracks)
    if not events:
        log("Niets om af te spelen (geen noten in de gekozen tracks).")
        return 0
    if virtual:
        port = open_output(VIRTUAL_PORT_NAME, virtual=True)
        log(f"▶ Speelt af via virtuele poort '{VIRTUAL_PORT_NAME}' (open GarageBand/Logic/Ableton om te horen).")
        sleep(1.0)  # geef de DAW even tijd om de nieuwe poort te zien
    else:
        port = open_output(port_name)
        log(f"▶ Speelt af op '{port_name}' ({events[-1][0]:.1f} s). Ctrl+C om te stoppen.")

    sent = 0
    start = time.perf_counter()
    try:
        for when, msg in events:
            wait = when - (time.perf_counter() - start)
            if wait > 0:
                sleep(wait)
            port.send(msg)
            sent += 1
    except KeyboardInterrupt:
        log("⏹ Gestopt.")
    finally:
        all_notes_off(port)
        port.close()
    return sent


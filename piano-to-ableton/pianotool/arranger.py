"""AI-arrangeur: maakt van een piano-take een compleet, meersporig MIDI-stuk.

Claude krijgt je (gekwantiseerde) melodie plus stijlwensen en schrijft er een
arrangement omheen: songstructuur, akkoorden, bas, drums, pads, tegenmelodie.
Je eigen, ongekwantiseerde spel wordt letterlijk teruggeplaatst op de plekken
die de AI kiest, zodat jouw timing en aanslag behouden blijven.

Het resultaat is één .mid-bestand met een track per instrument, klaar om in
Ableton te slepen (elke track wordt een eigen MIDI-track/clip).
"""

from __future__ import annotations

import json
from dataclasses import replace

from .analysis import describe, to_sixteenths
from .midi_io import Note, Song, Track

MODEL = "claude-opus-5"

ROLES = ["melody", "counter_melody", "chords", "pad", "arp", "bass", "drums", "other"]

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "key", "summary", "sections", "melody_placements", "tracks"],
    "properties": {
        "title": {"type": "string"},
        "key": {"type": "string"},
        "summary": {"type": "string", "description": "Korte uitleg van het arrangement, in het Nederlands."},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "start_bar", "bars"],
                "properties": {
                    "name": {"type": "string"},
                    "start_bar": {"type": "integer"},
                    "bars": {"type": "integer"},
                },
            },
        },
        "melody_placements": {
            "type": "array",
            "description": "0-gebaseerde maatnummers waar de originele piano-take letterlijk begint.",
            "items": {"type": "integer"},
        },
        "tracks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "role", "gm_program", "notes"],
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string", "enum": ROLES},
                    "gm_program": {"type": "integer"},
                    "notes": {
                        "type": "array",
                        "description": "Elke noot is [pitch, start_16e, duur_16e, velocity].",
                        "items": {"type": "array", "items": {"type": "integer"}},
                    },
                },
            },
        },
    },
}

SYSTEM = """Je bent een ervaren componist, arrangeur en producer. Je krijgt een melodie \
die iemand op de piano heeft ingespeeld en maakt daar een compleet muziekstuk van als \
meersporige MIDI, bedoeld om verder te produceren in Ableton Live.

Tijdseenheid: zestiende noten. Positie 0 is de eerste tel van maat 0; een maat in 4/4 \
is 16 zestienden. Elke noot is [MIDI-pitch, start, duur, velocity 1-127].

Richtlijnen:
- De ingespeelde melodie is het hoofdthema. Plaats de originele take via \
`melody_placements` (maatnummers) op de plekken waar het thema letterlijk klinkt; \
schrijf die noten dan NIET opnieuw uit. Varianten, tegenmelodieën en ontwikkelingen \
van het thema schrijf je wel zelf uit in een eigen track.
- Bouw een overtuigende vorm (bijvoorbeeld intro, couplet, refrein, brug, outro) met \
opbouw en afwisseling in dichtheid en dynamiek.
- Harmoniseer passend bij de melodie en de toonsoort; laat bas en akkoorden \
de harmonie duidelijk dragen.
- Drums: gebruik rol "drums" en General MIDI-drumnoten (36 kick, 38 snare, 42 closed \
hihat, 46 open hihat, 49 crash, 51 ride, 39 clap, 45/47/50 toms).
- Kies per track een passend General MIDI-programma (0 = piano, 33 = fingered bass, \
48 = strings, 89 = warm pad, 81 = saw lead, …); voor drums is het programma 0.
- Houd bereik en stemvoering realistisch en laat ruimte rond de hoofdmelodie.
- Schrijf alle noten volledig uit (geen herhalingsinstructies)."""


def build_prompt(take: Song, style: str, bars: int, bpm: float) -> str:
    notes = [n for t in take.tracks for n in t.notes]
    quantized = to_sixteenths(notes, bpm)
    info = describe(notes, bpm)
    take_bars = max(1, -(-max(s + d for _, s, d, _ in quantized) // 16)) if quantized else 1
    return (
        f"Stijl/wensen: {style}\n"
        f"Tempo: {bpm:g} BPM, maatsoort 4/4. Gewenste lengte: ongeveer {bars} maten.\n"
        f"Geschatte toonsoort: {info['toonsoort']}. Bereik melodie: {info['bereik']}.\n"
        f"De take beslaat {take_bars} maat/maten.\n\n"
        "Ingespeelde melodie (gekwantiseerd naar zestienden, [pitch, start, duur, velocity]):\n"
        f"{json.dumps([list(q) for q in quantized])}\n"
    )


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(v)))


def song_from_arrangement(data: dict, take: Song, bpm: float) -> Song:
    """Zet het JSON-antwoord om naar een Song (pure functie, los testbaar)."""
    sixteenth = 60.0 / bpm / 4
    bar_seconds = sixteenth * 16
    tracks: list[Track] = []

    # 1) De originele take, letterlijk (met jouw timing en aanslag) op elke plaatsing.
    original = [n for t in take.tracks for n in t.notes]
    controls = [c for t in take.tracks for c in t.controls]
    placements = sorted({p for p in data.get("melody_placements", []) if p >= 0}) or [0]
    if original:
        piano = Track(name="Piano (jouw take)", program=0, channel=0)
        for bar in placements:
            offset = bar * bar_seconds
            piano.notes += [replace(n, start=n.start + offset, end=n.end + offset, channel=0) for n in original]
            piano.controls += [replace(c, time=c.time + offset, channel=0) for c in controls]
        tracks.append(piano)

    # 2) De tracks die de AI heeft geschreven. Kanaal 9 (10 in MIDI-taal) is voor drums.
    melodic_channels = [c for c in range(16) if c not in (0, 9)]
    for i, t in enumerate(data.get("tracks", [])):
        is_drums = t.get("role") == "drums"
        channel = 9 if is_drums else melodic_channels[i % len(melodic_channels)]
        track = Track(
            name=t.get("name") or t.get("role", f"Track {i + 1}"),
            program=None if is_drums else _clamp(t.get("gm_program", 0), 0, 127),
            channel=channel,
        )
        for raw in t.get("notes", []):
            if len(raw) < 3:
                continue
            pitch, start, dur = raw[0], raw[1], raw[2]
            vel = raw[3] if len(raw) > 3 else 90
            if start < 0 or dur <= 0:
                continue
            track.notes.append(
                Note(
                    pitch=_clamp(pitch, 0, 127),
                    start=start * sixteenth,
                    end=(start + dur) * sixteenth,
                    velocity=_clamp(vel, 1, 127),
                    channel=channel,
                )
            )
        if track.notes:
            track.notes.sort(key=lambda n: (n.start, n.pitch))
            tracks.append(track)

    return Song(bpm=bpm, tracks=tracks)


def arrange(take: Song, style: str, bars: int = 32, bpm: float | None = None, effort: str = "high",
            log=print) -> tuple[Song, dict]:
    """Vraag Claude om een arrangement. Vereist ANTHROPIC_API_KEY (of `ant auth login`)."""
    import anthropic

    bpm = bpm or take.bpm
    client = anthropic.Anthropic()
    log(f"🤖 Claude schrijft een arrangement ({bars} maten, {bpm:g} BPM)… dit kan een paar minuten duren.")

    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": SCHEMA}},
        # Als het model een verzoek onterecht weigert, neemt een ander model het over.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": build_prompt(take, style, bars, bpm)}],
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise RuntimeError("Claude heeft het verzoek geweigerd; probeer een andere stijlomschrijving.")
    if message.stop_reason == "max_tokens":
        raise RuntimeError("Het arrangement werd te lang; probeer minder maten (--bars).")

    text = "".join(b.text for b in message.content if b.type == "text")
    data = json.loads(text)
    return song_from_arrangement(data, take, bpm), data

"""Eenvoudige muzikale analyse: toonsoort, tempo-schatting en kwantisering."""

from __future__ import annotations

import math
from collections import Counter

from .midi_io import Note

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Kessler toonsoortprofielen
_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def _corr(a: list[float], b: list[float]) -> float:
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else 0.0


def detect_key(notes: list[Note]) -> str:
    """Schat de toonsoort (bv. 'A minor') op basis van duur-gewogen toonklassen."""
    if not notes:
        return "C major"
    hist = [0.0] * 12
    for n in notes:
        hist[n.pitch % 12] += n.end - n.start
    best = ("C major", -2.0)
    for tonic in range(12):
        rotated = hist[tonic:] + hist[:tonic]
        for profile, mode in ((_MAJOR, "major"), (_MINOR, "minor")):
            score = _corr(rotated, profile)
            if score > best[1]:
                best = (f"{NOTE_NAMES[tonic]} {mode}", score)
    return best[0]


def estimate_bpm(notes: list[Note], lo: float = 70.0, hi: float = 160.0) -> float | None:
    """Ruwe tempo-schatting uit de afstanden tussen aanslagen.

    Werkt redelijk bij ritmisch spel; bij rubato is ``--bpm`` meegeven beter.
    """
    onsets = sorted({round(n.start, 2) for n in notes})
    if len(onsets) < 8:
        return None
    best_bpm, best_score = None, -1.0
    bpm = lo
    while bpm <= hi:
        beat = 60.0 / bpm
        grid = beat / 2  # achtste noten
        score = 0.0
        for t in onsets:
            phase = (t - onsets[0]) / grid
            score += math.cos(2 * math.pi * phase)
        # lichte voorkeur voor tempo's rond 100-120 om octaaffouten te beperken
        score *= 1.0 - abs(bpm - 110) / 400
        if score > best_score:
            best_bpm, best_score = bpm, score
        bpm += 0.5
    return round(best_bpm, 1) if best_bpm else None


def to_sixteenths(notes: list[Note], bpm: float) -> list[tuple[int, int, int, int]]:
    """Kwantiseer naar 16e noten: (pitch, start_16e, duur_16e, velocity)."""
    sixteenth = 60.0 / bpm / 4
    out = []
    for n in notes:
        start = round(n.start / sixteenth)
        dur = max(1, round((n.end - n.start) / sixteenth))
        out.append((n.pitch, start, dur, n.velocity))
    out.sort(key=lambda x: (x[1], x[0]))
    return out


def describe(notes: list[Note], bpm: float) -> dict:
    pitches = [n.pitch for n in notes]
    common = Counter(p % 12 for p in pitches).most_common(5)
    return {
        "noten": len(notes),
        "duur_s": round(max((n.end for n in notes), default=0.0), 2),
        "toonsoort": detect_key(notes),
        "bereik": f"{name(min(pitches))} – {name(max(pitches))}" if pitches else "-",
        "meest_gespeeld": [NOTE_NAMES[pc] for pc, _ in common],
        "maten_bij_bpm": round(max((n.end for n in notes), default=0.0) / (60.0 / bpm * 4), 1),
    }


def name(pitch: int) -> str:
    return f"{NOTE_NAMES[pitch % 12]}{pitch // 12 - 1}"

"""Command-line interface: `python -m pianotool <commando>`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analysis import describe, estimate_bpm
from .midi_io import Song, load_song, save_song

DEFAULT_DIR = Path.home() / "Music" / "Piano Takes"
DEFAULT_STYLE = "filmische, warme popballad met strijkers, pads, bas en subtiele drums"


def _notes(song: Song):
    return [n for t in song.tracks for n in t.notes]


def cmd_ports(args) -> int:
    from .player import find_output_port, list_outputs
    from .recorder import find_piano_port, list_inputs

    names = list_inputs()
    if not names:
        print("Geen MIDI-ingangen gevonden. Is de piano aangesloten en aangezet?")
        return 1
    print("Ingangen (opnemen):")
    auto = find_piano_port()
    for name in names:
        print(f"  {'→' if name == auto else ' '} {name}")
    print("Uitgangen (naspelen):")
    auto = find_output_port()
    for name in list_outputs():
        print(f"  {'→' if name == auto else ' '} {name}")
    print("\n→ = wordt automatisch gekozen. Andere keuze? Gebruik --port / --to \"deel van de naam\".")
    return 0


def _player(args):
    """Geeft een functie terug die een Song naspeelt volgens --to / --virtual."""
    from .player import find_output_port, play_song

    if args.virtual:
        return lambda song: play_song(song, virtual=True, tracks=args.track)
    port = find_output_port(args.to)
    if not port:
        raise RuntimeError("Geen MIDI-uitgang gevonden. Gebruik --virtual om via GarageBand/Logic/Ableton af te spelen.")
    return lambda song: play_song(song, port, tracks=args.track)


def _arrange_and_save(take: Song, take_path: Path, args) -> Path:
    from .arranger import arrange

    bpm = args.bpm or take.bpm
    song, data = arrange(take, style=args.style, bars=args.bars, bpm=bpm, effort=args.effort)
    out = take_path.with_name(take_path.stem + "_arrangement.mid")
    save_song(song, out)
    (out.with_suffix(".json")).write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"🎼 '{data.get('title', 'Arrangement')}' in {data.get('key', '?')}")
    print(f"   {data.get('summary', '')}")
    for s in data.get("sections", []):
        print(f"   maat {s['start_bar'] + 1:>3}: {s['name']} ({s['bars']} maten)")
    print(f"✔ Arrangement opgeslagen: {out}  ({len(song.tracks)} tracks)")
    return out


def cmd_record(args) -> int:
    from .recorder import find_piano_port, list_inputs, record

    port = find_piano_port(args.port)
    if not port:
        print("Geen piano gevonden. Beschikbare ingangen:", list_inputs() or "geen")
        return 1

    def on_saved(path: Path, song: Song) -> None:
        if args.arrange:
            try:
                _arrange_and_save(song, path, args)
            except Exception as e:  # opname moet doorgaan, ook als de AI faalt
                print(f"⚠ Arrangeren mislukt: {e}")

    record(
        port,
        Path(args.out).expanduser(),
        playback=_player(args) if args.playback else None,
        bpm=args.bpm or 120.0,
        silence=args.silence,
        lead_in=args.lead_in,
        min_notes=args.min_notes,
        on_saved=on_saved,
    )
    return 0


def cmd_analyze(args) -> int:
    song = load_song(args.file)
    notes = _notes(song)
    info = describe(notes, song.bpm)
    info["bpm_in_bestand"] = round(song.bpm, 1)
    info["bpm_geschat"] = estimate_bpm(notes)
    for k, v in info.items():
        print(f"{k:>16}: {v}")
    return 0


def latest_take(folder: Path) -> Path:
    takes = sorted(folder.glob("take_*.mid"), key=lambda p: p.stat().st_mtime)
    if not takes:
        raise RuntimeError(f"Nog geen takes gevonden in {folder}")
    return takes[-1]


def cmd_play(args) -> int:
    path = latest_take(DEFAULT_DIR) if args.file == "laatste" else Path(args.file).expanduser()
    print(f"♪ {path.name}")
    _player(args)(load_song(path))
    return 0


def cmd_arrange(args) -> int:
    path = Path(args.file)
    _arrange_and_save(load_song(path), path, args)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pianotool", description="Piano (MIDI) → Ableton, met optioneel AI-arrangement.")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("ports", help="toon aangesloten MIDI-apparaten").set_defaults(func=cmd_ports)

    def ai_options(sp):
        sp.add_argument("--style", default=DEFAULT_STYLE, help="stijl/wensen voor het arrangement")
        sp.add_argument("--bars", type=int, default=32, help="gewenste lengte in maten (standaard 32)")
        sp.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"],
                        help="hoe hard Claude nadenkt (hoger = beter maar trager/duurder)")

    def play_options(sp):
        sp.add_argument("--to", help="(deel van) de naam van de MIDI-uitgang; standaard de piano")
        sp.add_argument("--virtual", action="store_true",
                        help="speel af via virtuele poort 'Pianotool' (GarageBand/Logic/Ableton, Mac-speakers)")
        sp.add_argument("--track", action="append",
                        help="alleen tracks waarvan de naam dit bevat (herhaalbaar, bv. --track Piano)")

    r = sub.add_parser("record", help="neem op; elke take wordt automatisch een .mid-bestand")
    r.add_argument("--port", help="(deel van) de naam van de MIDI-ingang; standaard automatisch")
    r.add_argument("--out", default=str(DEFAULT_DIR), help=f"map voor de takes (standaard {DEFAULT_DIR})")
    r.add_argument("--bpm", type=float, help="tempo waarin je speelt (standaard 120)")
    r.add_argument("--silence", type=float, default=4.0, help="seconden stilte die een take afsluiten")
    r.add_argument("--lead-in", type=float, default=0.0, help="seconden stilte vóór de eerste noot")
    r.add_argument("--min-notes", type=int, default=3, help="kortere takes worden weggegooid")
    r.add_argument("--arrange", action="store_true", help="laat elke take direct door Claude arrangeren")
    r.add_argument("--playback", action="store_true", help="speel elke take direct na")
    ai_options(r)
    play_options(r)
    r.set_defaults(func=cmd_record)

    pl = sub.add_parser("play", help="speel een take of arrangement na (op de piano of via de Mac)")
    pl.add_argument("file", help="een .mid-bestand, of 'laatste' voor de nieuwste take")
    play_options(pl)
    pl.set_defaults(func=cmd_play)

    a = sub.add_parser("analyze", help="toonsoort, tempo en bereik van een .mid-bestand")
    a.add_argument("file")
    a.set_defaults(func=cmd_analyze)

    ar = sub.add_parser("arrange", help="maak een compleet stuk van een bestaande take")
    ar.add_argument("file")
    ar.add_argument("--bpm", type=float, help="tempo van de take (standaard: uit het bestand)")
    ai_options(ar)
    ar.set_defaults(func=cmd_arrange)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"Fout: {e}", file=sys.stderr)
        if type(e).__name__ == "AuthenticationError":
            print("Tip: zet je Claude API-sleutel in de omgevingsvariabele ANTHROPIC_API_KEY "
                  "(aan te maken op console.anthropic.com).", file=sys.stderr)
        return 1

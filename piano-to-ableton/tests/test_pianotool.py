import mido

from pianotool.analysis import detect_key, estimate_bpm, to_sixteenths
from pianotool.arranger import build_prompt, song_from_arrangement
from pianotool.midi_io import Control, Note, Song, Track, load_song, save_song
from pianotool.recorder import TakeBuilder


def c_major_scale(bpm=120.0):
    beat = 60.0 / bpm
    pitches = [60, 62, 64, 65, 67, 69, 71, 72]
    return [Note(p, i * beat, i * beat + beat * 0.9, 80) for i, p in enumerate(pitches)]


def test_save_and_load_roundtrip(tmp_path):
    notes = c_major_scale()
    song = Song(bpm=120.0, tracks=[Track("Piano", notes, [Control(0.5, "cc", 64, 127), Control(3.0, "cc", 64, 0)], program=0)])
    path = save_song(song, tmp_path / "t.mid")
    loaded = load_song(path)
    assert loaded.bpm == 120.0
    assert [n.pitch for n in loaded.tracks[0].notes] == [n.pitch for n in notes]
    for a, b in zip(loaded.tracks[0].notes, notes):
        assert abs(a.start - b.start) < 0.01 and abs(a.end - b.end) < 0.01
    assert [(c.number, c.value) for c in loaded.tracks[0].controls] == [(64, 127), (64, 0)]


def test_take_builder_handles_pedal_and_open_notes():
    tb = TakeBuilder(t0=10.0)
    tb.feed(mido.Message("note_on", note=60, velocity=100), 10.0)
    tb.feed(mido.Message("control_change", control=64, value=127), 10.2)
    tb.feed(mido.Message("note_on", note=60, velocity=0), 10.5)  # note_on vel 0 = note_off
    assert not tb.idle  # pedaal nog ingedrukt
    tb.feed(mido.Message("note_on", note=64, velocity=90), 11.0)
    song = tb.finish(12.0, bpm=100)
    notes = song.tracks[0].notes
    assert [(n.pitch, round(n.start, 2), round(n.end, 2)) for n in notes] == [(60, 0.0, 0.5), (64, 1.0, 2.0)]
    assert song.tracks[0].controls[-1].value == 0  # pedaal losgelaten aan het eind


def test_detect_key():
    assert detect_key(c_major_scale()) == "C major"
    a_minor = [Note(p, i * 0.5, i * 0.5 + 0.45, 80) for i, p in enumerate([57, 60, 64, 57, 60, 64, 69, 64, 60, 57])]
    assert detect_key(a_minor) == "A minor"


def test_estimate_bpm_on_steady_eighths():
    bpm = 100.0
    eighth = 60.0 / bpm / 2
    notes = [Note(60 + i % 5, i * eighth, i * eighth + eighth * 0.8, 80) for i in range(32)]
    est = estimate_bpm(notes)
    assert est is not None and abs(est - bpm) < 3


def test_to_sixteenths():
    assert to_sixteenths(c_major_scale(), 120.0)[:2] == [(60, 0, 4, 80), (62, 4, 4, 80)]


def test_song_from_arrangement_places_take_and_tracks(tmp_path):
    take = Song(bpm=120.0, tracks=[Track("Piano", c_major_scale(), program=0)])
    data = {
        "title": "Test", "key": "C major", "summary": "", "sections": [],
        "melody_placements": [0, 4],
        "tracks": [
            {"name": "Bas", "role": "bass", "gm_program": 33, "notes": [[36, 0, 16, 90], [43, 16, 16, 90], [1, -1, 2, 3]]},
            {"name": "Drums", "role": "drums", "gm_program": 0, "notes": [[36, 0, 1, 110], [38, 4, 1, 200]]},
        ],
    }
    song = song_from_arrangement(data, take, 120.0)
    names = [t.name for t in song.tracks]
    assert names == ["Piano (jouw take)", "Bas", "Drums"]
    piano = song.tracks[0]
    assert len(piano.notes) == 16  # take twee keer geplaatst
    assert abs(piano.notes[8].start - 8.0) < 1e-6  # maat 4 bij 120 BPM = 8 s
    bass, drums = song.tracks[1], song.tracks[2]
    assert len(bass.notes) == 2 and bass.program == 33
    assert drums.channel == 9 and drums.notes[1].velocity == 127
    # moet een geldig bestand opleveren
    loaded = load_song(save_song(song, tmp_path / "arr.mid"))
    assert len(loaded.tracks) == 3


def test_build_prompt_contains_melody():
    take = Song(bpm=120.0, tracks=[Track("Piano", c_major_scale())])
    prompt = build_prompt(take, "jazz", 16, 120.0)
    assert "jazz" in prompt and "[60, 0, 4, 80]" in prompt and "C major" in prompt


def test_record_loop_splits_takes_on_silence(tmp_path, monkeypatch):
    """Simuleert een piano: twee frasen met een pauze ertussen -> twee .mid-bestanden."""
    import threading
    import time
    from datetime import datetime, timedelta

    from pianotool import recorder

    class FakePort:
        def __init__(self, name, callback):
            self.cb = callback

        def __enter__(self):
            def play():
                for phrase in range(2):
                    for p in (60, 64, 67):
                        self.cb(mido.Message("note_on", note=p + phrase, velocity=90))
                        time.sleep(0.02)
                        self.cb(mido.Message("note_off", note=p + phrase))
                    time.sleep(0.5)  # stilte > silence -> take afsluiten

            threading.Thread(target=play, daemon=True).start()
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(recorder.mido, "open_input", lambda name, callback: FakePort(name, callback))
    stamps = iter(datetime(2026, 1, 1) + timedelta(seconds=i) for i in range(10))
    monkeypatch.setattr(recorder, "take_filename", lambda out, when=None: out / f"take_{next(stamps):%H%M%S}.mid")

    saved = []

    def on_saved(path, song):
        saved.append(path)
        if len(saved) == 2:
            raise KeyboardInterrupt  # stopt de lus zoals Ctrl+C

    recorder.record("Fake Piano", tmp_path, silence=0.2, on_saved=on_saved, log=lambda *_: None)
    assert len(saved) == 2
    assert [n.pitch for n in load_song(saved[1]).tracks[0].notes] == [61, 65, 68]

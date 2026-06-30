"""midi_extract のテスト（Phase1b: vocals/accompaniment 2MIDI化）。"""
from scripts.midi_extract import extract_midi


def _stems_fixture(yoen_mp3) -> dict:
    """テスト用: 生音源を stems 辞書に見立てて両方同じ音源を渡す（分離は別テスト）。"""
    return {"vocals": yoen_mp3, "other": yoen_mp3}


def test_extract_midi_creates_two_mid_files(yoen_mp3, workdir):
    """vocals.mid / accompaniment.mid が2つ生成されること。"""
    out = extract_midi(_stems_fixture(str(yoen_mp3)), workdir)
    assert set(out.keys()) == {"vocals", "accompaniment"}
    for stem, path in out.items():
        assert path == workdir / f"{stem}.mid"
        assert path.exists()
        assert path.stat().st_size > 100  # 空MIDIではない


def test_extract_midi_readable_by_music21(yoen_mp3, workdir):
    """生成MIDIが music21 で読めること。"""
    from music21 import converter

    out = extract_midi(_stems_fixture(str(yoen_mp3)), workdir)
    score = converter.parse(str(out["vocals"]))
    notes = list(score.recurse().notes)
    assert len(notes) > 10

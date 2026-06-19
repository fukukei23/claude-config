"""midi_extract のテスト。basic_pitch で MIDI が生成されること。"""
from scripts.midi_extract import extract_midi


def test_extract_midi_creates_mid_file(yoen_mp3, workdir):
    """yoen-v3_1 から raw.mid が生成され、ノート数が 0 でないこと。"""
    out = extract_midi(str(yoen_mp3), workdir)
    assert out == workdir / "raw.mid"
    assert out.exists()
    assert out.stat().st_size > 100  # 空MIDIではない


def test_extract_midi_readable_by_music21(yoen_mp3, workdir):
    """生成MIDIが music21 で読めること。"""
    from music21 import converter

    out = extract_midi(str(yoen_mp3), workdir)
    score = converter.parse(str(out))
    notes = list(score.recurse().notes)
    assert len(notes) > 10  # 十分なノート数

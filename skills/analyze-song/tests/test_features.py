"""features のテスト。yoen-v3_1 を使う。"""
import pytest

from scripts.features import analyze_features


@pytest.fixture
def midi_path(workdir, yoen_mp3):
    """テスト用 MIDI を生成（basic_pitch）。重いので function scope。"""
    from scripts.midi_extract import extract_midi
    return extract_midi(str(yoen_mp3), workdir)


def test_analyze_features_returns_key(midi_path):
    """キー推定結果に key/scale/confidence が含まれること。"""
    result = analyze_features(str(midi_path))
    assert "key" in result
    assert "key" in result["key"]
    assert "scale" in result["key"]
    assert "confidence" in result["key"]


def test_analyze_features_returns_chords(midi_path):
    """コード進行リストが得られること。"""
    result = analyze_features(str(midi_path))
    assert "chords" in result
    assert isinstance(result["chords"]["progression"], list)
    assert len(result["chords"]["progression"]) > 0


def test_analyze_features_returns_melody_range(midi_path):
    """メロディ音域が得られること。"""
    result = analyze_features(str(midi_path))
    assert "melody" in result
    m = result["melody"]
    assert "range_low" in m
    assert "range_high" in m
    assert "range_semitones" in m
    assert m["range_semitones"] > 0


def test_analyze_features_phrase_repetition(midi_path):
    """phrase_repetition が検出され、一致率が記録されること。"""
    result = analyze_features(str(midi_path))
    assert "melody" in result
    pr = result["melody"].get("phrase_repetition", {})
    assert pr.get("detected") in (True, False)
    if pr.get("detected"):
        assert len(pr.get("pairs", [])) > 0


def test_analyze_features_returns_structure(midi_path):
    """structure（sections/form）が得られること。"""
    result = analyze_features(str(midi_path))
    assert "structure" in result
    s = result["structure"]
    assert isinstance(s["sections"], list)
    assert len(s["sections"]) >= 2
    assert "form" in s

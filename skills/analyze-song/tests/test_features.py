"""features のテスト（Phase1b: vocals/accompaniment 2MIDI + duration_sec）。"""
from pathlib import Path

import pytest

from scripts.features import analyze_features


@pytest.fixture
def stems_midi(workdir, yoen_mp3):
    """テスト用に vocals/accompaniment の2MIDIを生成（重い・function scope）。

    分離を省略するため stems には両方とも元音源を入れる（features 単体テスト用）。
    """
    from scripts.midi_extract import extract_midi
    stems = {"vocals": Path(str(yoen_mp3)), "other": Path(str(yoen_mp3))}
    return extract_midi(stems, workdir)


def _features(stems_midi):
    return analyze_features(
        str(stems_midi["vocals"]), str(stems_midi["accompaniment"]), 126.92
    )


def test_analyze_features_returns_key(stems_midi):
    """キー推定結果に key/scale/confidence が含まれること。"""
    result = _features(stems_midi)
    assert "key" in result
    assert "key" in result["key"]
    assert "scale" in result["key"]
    assert "confidence" in result["key"]


def test_analyze_features_returns_chords(stems_midi):
    """コード進行リストが得られること。"""
    result = _features(stems_midi)
    assert "chords" in result
    assert isinstance(result["chords"]["progression"], list)
    assert len(result["chords"]["progression"]) > 0


def test_analyze_features_returns_melody_range(stems_midi):
    """メロディ音域が得られること。"""
    result = _features(stems_midi)
    assert "melody" in result
    m = result["melody"]
    assert "range_low" in m
    assert "range_high" in m
    assert "range_semitones" in m
    assert m["range_semitones"] > 0


def test_analyze_features_phrase_repetition(stems_midi):
    """phrase_repetition が検出され、一致率が記録されること。"""
    result = _features(stems_midi)
    assert "melody" in result
    pr = result["melody"].get("phrase_repetition", {})
    assert pr.get("detected") in (True, False)
    if pr.get("detected"):
        assert len(pr.get("pairs", [])) > 0


def test_analyze_features_returns_vocals_range(stems_midi):
    """vocals 音域（range_low/range_high）がボーカルMIDIから得られること。"""
    result = _features(stems_midi)
    assert "vocals" in result
    v = result["vocals"]
    assert v["range_low"] != "N/A"
    assert v["range_high"] != "N/A"


def test_analyze_features_returns_vocals_gender(stems_midi):
    """vocals 性別推定が male/female のいずれかになること。"""
    result = _features(stems_midi)
    assert result["vocals"]["gender_estimate"] in ("male", "female")


def test_analyze_features_returns_vocals_timbre(stems_midi):
    """vocals 声域（timbre）が非空文字列で得られること。"""
    result = _features(stems_midi)
    timbre = result["vocals"]["timbre"]
    assert isinstance(timbre, str) and timbre


def test_analyze_features_returns_structure(stems_midi):
    """structure（sections/form）が音源durationで正規化されて得られること。"""
    result = _features(stems_midi)
    assert "structure" in result
    s = result["structure"]
    assert isinstance(s["sections"], list)
    assert len(s["sections"]) >= 2
    assert "form" in s
    # duration_sec(126.92) で正規化されていること
    assert s["sections"][-1]["end"] == 126.92

"""tempo_key のテスト（Phase1b: drums stem 優先・フォールバックはフルミックス）。

実曲検証（Stayin' Alive=104BPM）で drums stem 方式が 103.36 と精度良く動作することを
確認済み。yoen-v3_1（AI生成音源）は drums onset が特殊で 112 となる外れ値。
ここでは後方互換のフルミックスパス（drums_path 省略）で妥当範囲を検証する。
"""
from scripts.tempo_key import analyze_tempo


def test_analyze_tempo_returns_valid_bpm(yoen_mp3):
    """BPM が妥当な音楽テンポ範囲で返ること（drums_path 省略=フルミックス）。"""
    result = analyze_tempo(str(yoen_mp3))
    assert "tempo" in result
    assert "duration_sec" in result
    bpm = result["tempo"]["bpm"]
    assert 40 <= bpm <= 250
    assert result["duration_sec"] > 30


def test_analyze_tempo_bpm_confidence_present(yoen_mp3):
    """bpm_confidence フィールドが存在すること。"""
    result = analyze_tempo(str(yoen_mp3))
    assert "bpm_confidence" in result["tempo"]


def test_analyze_tempo_octave_correction():
    """オクターブ補正（60-180範囲外は半分/2倍）が効くこと。"""
    from scripts.tempo_key import _correct_octave
    assert _correct_octave(240.0) == 120.0
    assert _correct_octave(30.0) == 60.0
    assert _correct_octave(100.0) == 100.0

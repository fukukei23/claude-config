"""tempo_key のテスト。yoen-v3_1 は既知 85BPM。"""
from scripts.tempo_key import analyze_tempo


def test_analyze_tempo_returns_bpm_near_85(yoen_mp3):
    """yoen-v3_1 の BPM は 85 前後（±10許容）であること。"""
    result = analyze_tempo(str(yoen_mp3))
    assert "tempo" in result
    assert "duration_sec" in result
    assert 75 <= result["tempo"]["bpm"] <= 95
    assert result["duration_sec"] > 30


def test_analyze_tempo_bpm_confidence_present(yoen_mp3):
    """bpm_confidence フィールドが存在すること。"""
    result = analyze_tempo(str(yoen_mp3))
    assert "bpm_confidence" in result["tempo"]

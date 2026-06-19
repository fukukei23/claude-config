"""tempo_key のテスト。

yoen-v3_1 は MiniMax 生成時 --bpm 85 指定だが、librosa 音響推定では約112 BPM
（4/3倍誤差・3連符系リズム解釈）となる。Phase 1a ではパイプライン動作を検証し、
BPM 絶対精度は Phase 1b 改善対象（start_bpm ヒント等の検討）。
"""
from scripts.tempo_key import analyze_tempo


def test_analyze_tempo_returns_valid_bpm(yoen_mp3):
    """BPM が妥当な音楽テンポ範囲で返ること（絶対精度は改善対象）。"""
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

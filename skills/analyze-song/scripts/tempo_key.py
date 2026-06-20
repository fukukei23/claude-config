"""librosa で BPM・duration・ビート位置を抽出する（Phase1b）。

Phase1b: ドラムステム（分離済み）で BPM 推定する。ドラムはビートが明確なため、
フルミックス（実測112→正解85）より精度が上がる。ドラム無音時はフルミックスにフォールバック。

※キー推定は扱わない（librosa に API 無し・features.py の music21 で行う）。
"""
import librosa

# テンポの現実的範囲（オクターブ補正の境界）。これを外れたら半分/2倍に直す。
TEMPO_MIN = 60.0
TEMPO_MAX = 180.0


def _estimate_bpm(y, sr):
    """beat_track で BPM・beats・安定度を返す。"""
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(tempo.item() if hasattr(tempo, "item") and tempo.ndim > 0 else tempo)
    beat_times = librosa.frames_to_time(beats, sr=sr)
    diffs = beat_times[1:] - beat_times[:-1]
    stability = float(diffs.std()) if len(diffs) > 1 else 0.0
    mean_interval = float(diffs.mean()) if len(diffs) > 0 else 1.0
    cv = stability / mean_interval if mean_interval > 0 else 1.0
    confidence = max(0.0, min(1.0, 1.0 - cv))
    return bpm, confidence


def _correct_octave(bpm: float) -> float:
    """テンポを現実的範囲(60-180)にオクターブ補正（半分/2倍）。"""
    while bpm > TEMPO_MAX:
        bpm /= 2
    while bpm < TEMPO_MIN:
        bpm *= 2
    return bpm


def analyze_tempo(audio_path: str, drums_path: str | None = None) -> dict:
    """音源から BPM・duration を抽出する。

    Args:
        audio_path: 音源パス（duration 計算用の代表音源・フルミックス想定）。
        drums_path: 分離済みドラムステムのパス（BPM 推定に使う・None なら audio_path）。

    Returns:
        {"tempo": {"bpm": float, "bpm_confidence": float}, "duration_sec": float}
    """
    # BPM 推定: ドラム優先、なければフルミックス
    bpm_source = drums_path if drums_path else audio_path
    y_bpm, sr_bpm = librosa.load(bpm_source, sr=22050, mono=True)
    bpm, confidence = _estimate_bpm(y_bpm, sr_bpm)
    bpm = _correct_octave(bpm)

    # duration はフルミックスで（曲長の真値）
    y_dur, sr_dur = librosa.load(audio_path, sr=22050, mono=True)
    duration = float(librosa.get_duration(y=y_dur, sr=sr_dur))

    return {
        "tempo": {"bpm": round(bpm, 2), "bpm_confidence": round(confidence, 3)},
        "duration_sec": round(duration, 2),
    }

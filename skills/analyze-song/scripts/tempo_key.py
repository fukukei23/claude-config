"""librosa で BPM・duration・ビート位置を抽出する。

※キー推定は扱わない（librosa に API 無し・features.py の music21 で行う）。
"""
import librosa


def analyze_tempo(audio_path: str) -> dict:
    """音源から BPM・duration を抽出する。

    Args:
        audio_path: MP3/WAV 等の音声ファイルパス。

    Returns:
        {"tempo": {"bpm": float, "bpm_confidence": float}, "duration_sec": float}
    """
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    # librosa 0.11+ では tempo が shape (1,) 配列で返るため item() で scalar 抽出
    bpm = float(tempo.item() if hasattr(tempo, "item") and tempo.ndim > 0 else tempo)

    # テンポ安定性の簡易指標: ビート間隔の標準偏差が小さいほど安定
    beat_intervals = librosa.frames_to_time(beats, sr=sr)
    diffs = beat_intervals[1:] - beat_intervals[:-1]
    stability = float(diffs.std()) if len(diffs) > 1 else 0.0
    # 安定なら bpm_confidence 高く（間隔の変動係数から算出）
    mean_interval = float(diffs.mean()) if len(diffs) > 0 else 1.0
    cv = stability / mean_interval if mean_interval > 0 else 1.0
    confidence = max(0.0, min(1.0, 1.0 - cv))

    duration = float(librosa.get_duration(y=y, sr=sr))

    return {
        "tempo": {"bpm": bpm, "bpm_confidence": round(confidence, 3)},
        "duration_sec": round(duration, 2),
    }

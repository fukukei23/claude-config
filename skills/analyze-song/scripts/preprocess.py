"""features.json の前処理（音名変換・ノイズ除外・音域補正・正規化）を担う。"""
import re

_SHARP_PC = {
    "C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
    "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11,
}
_FLAT_TO_SHARP = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#"}

# 音域補正の低域カットオフ（C2 = MIDI 36 = 約65Hz）
_RANGE_LOW_FLOOR_MIDI = 36
# 補正後も非現実的と見なす閾値（4オクターブ=48半音）
_RANGE_VALID_MAX_SEMITONES = 48

_MIDI_RE = re.compile(r"^([A-G][#b]?)(\d+)$")


def note_name_to_pc(name: str) -> int | None:
    """音名（"C"/"F#"/"Bb"/"B-" 等）をピッチクラス(0-11)に変換する。

    music21 はフラットを "-" で出力する（例: "B-" = Bb）ため、"b" に正規化して受理する。

    Args:
        name: 音名。

    Returns:
        ピッチクラス。変換不能なら None。
    """
    if not name:
        return None
    # music21 フラット表記 "-" を "b" に正規化（例: "B-" → "Bb"）
    normalized = name.strip().replace("-", "b")
    upper = normalized.upper()
    if upper in _FLAT_TO_SHARP:
        upper = _FLAT_TO_SHARP[upper]
    return _SHARP_PC.get(upper)


def note_to_midi(name: str) -> int | None:
    """音名+オクターブ（"C4"/"E3"/"E-7" 等）を MIDI 番号に変換する。

    music21 のフラット表記（例: "E-7" = Eb7）を正規化して受理する。

    Args:
        name: 音名+オクターブ。

    Returns:
        MIDI 番号（C4=60）。変換不能なら None。
    """
    if not name:
        return None
    # music21 フラット表記 "-" を "b" に正規化してから regex マッチ
    normalized = name.strip().replace("-", "b")
    m = _MIDI_RE.match(normalized)
    if not m:
        return None
    pc = note_name_to_pc(m.group(1))
    if pc is None:
        return None
    return (int(m.group(2)) + 1) * 12 + pc


def preprocess(features: dict) -> dict | None:
    """features.json 辞書を正規化ベクトルに変換する。

    ノイズ特徴量（gender_estimate/phrase_repetition）は除外。
    range_low に低域カットオフ(C2未満)を適用し range_semitones を再判定。

    Args:
        features: features.json の辞書。

    Returns:
        正規化ベクトル。必須軸（bpm/key_pc）欠損時は None。
    """
    tempo = features.get("tempo", {})
    key = features.get("key", {})
    chords = features.get("chords", {})
    melody = features.get("melody", {})

    bpm = tempo.get("bpm")
    key_pc = note_name_to_pc(key.get("key", ""))
    if bpm is None or key_pc is None:
        return None

    low = note_to_midi(melody.get("range_low", ""))
    high = note_to_midi(melody.get("range_high", ""))
    if low is not None and low < _RANGE_LOW_FLOOR_MIDI:
        low = _RANGE_LOW_FLOOR_MIDI
    range_valid = False
    if low is not None and high is not None and high >= low:
        range_valid = (high - low) <= _RANGE_VALID_MAX_SEMITONES

    return {
        "bpm": float(bpm),
        "bpm_confidence": float(tempo.get("bpm_confidence", 0.0)),
        "key_pc": key_pc,
        "scale": key.get("scale", ""),
        "key_confidence": float(key.get("confidence", 0.0)),
        "progression": list(chords.get("progression", [])),
        "range_low_midi": low,
        "range_high_midi": high,
        "range_valid": range_valid,
    }

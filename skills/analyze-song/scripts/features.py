"""music21 で MIDI から特徴量を抽出する。

設計補正1: キー推定は librosa ではなく music21 の analyze('key') で行う。
設計補正2: basic_pitch MIDI のノイズ除去は chordify + 最小音長フィルタで行う。
"""
from music21 import chord, converter, note

# ノイズ除去: 短音を無視（spec 注意点2 相当）
MIN_NOTE_QUARTER = 0.1


def _load_and_clean(midi_path: str):
    """MIDI を読み、短音ノイズを除去した Stream を返す。"""
    score = converter.parse(midi_path)
    for n in list(score.recurse().notes):
        if isinstance(n, note.Note) and n.quarterLength < MIN_NOTE_QUARTER:
            container = n.activeSite
            if container is not None:
                container.remove(n)
    return score


def _analyze_key(score) -> dict:
    """music21 でキー推定。"""
    k = score.analyze("key")
    return {
        "key": str(k.tonic),
        "scale": k.mode,
        "confidence": round(float(k.correlationCoefficient), 3),
    }


def _analyze_chords(score) -> dict:
    """chordify でコード進行を抽出。"""
    chordified = score.chordify()
    progression = []
    for c in chordified.recurse().getElementsByClass(chord.Chord):
        try:
            name = c.pitchedCommonName
        except Exception:  # noqa: BLE001
            name = "N.C."
        progression.append(name)
    unique = []
    for name in progression:
        if not unique or unique[-1] != name:
            unique.append(name)
    return {
        "progression": unique[:32],
        "unique_progressions": len(set(unique)),
    }


def analyze_features(midi_path: str) -> dict:
    """MIDI からキー・コード特徴量を抽出する（メロディ/音域/構造は順次拡張）。"""
    score = _load_and_clean(midi_path)
    return {
        "key": _analyze_key(score),
        "chords": _analyze_chords(score),
    }

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


def _analyze_melody(score) -> dict:
    """メロディ音域を抽出。"""
    notes_flat = list(score.recurse().notes)
    pitches = []
    for n in notes_flat:
        if isinstance(n, note.Note):
            pitches.append(n.pitch)
        elif hasattr(n, "pitches"):
            pitches.extend(n.pitches)
    if not pitches:
        return {"range_low": "N/A", "range_high": "N/A", "range_semitones": 0}
    low = min(pitches)
    high = max(pitches)
    semitones = int(high.midi - low.midi)
    return {
        "range_low": low.nameWithOctave,
        "range_high": high.nameWithOctave,
        "range_semitones": semitones,
        "phrase_repetition": _analyze_phrase_repetition(score),
    }


def _analyze_phrase_repetition(score) -> dict:
    """前半/後半の音程輪郭を比較し同一性を検出する。

    固定長等分割: 全ノートを時系列で2等分し、各々の音程差列を比較。
    """
    melody_notes = [n for n in score.recurse().notes if isinstance(n, note.Note)]
    if len(melody_notes) < 8:
        return {"detected": False, "pairs": []}
    midis = [n.pitch.midi for n in melody_notes]
    mid = len(midis) // 2
    part_a = midis[:mid]
    part_b = midis[mid:mid * 2]

    def intervals(seq):
        return [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]

    ia = intervals(part_a)
    ib = intervals(part_b)
    n = min(len(ia), len(ib))
    if n == 0:
        return {"detected": False, "pairs": []}
    match = sum(1 for i in range(n) if ia[i] == ib[i])
    detected = match >= n * 0.7
    pair = {"section_a": "first_half", "section_b": "second_half", "match": match, "total": n}
    return {
        "detected": detected,
        "pairs": [pair],
    }


def _analyze_structure(score) -> dict:
    """固定長等分割で sections/form を返す（精度UPは1b/2）。"""
    total = float(score.duration.quarterLength) if score.duration else 0.0
    if total <= 0:
        total = float(score.quarterLength)
    if total <= 0:
        return {"sections": [], "form": "?"}
    mid = total / 2.0
    return {
        "sections": [
            {"name": "first_half", "start": 0.0, "end": mid},
            {"name": "second_half", "start": mid, "end": total},
        ],
        "form": "AB",
    }


def analyze_features(midi_path: str) -> dict:
    """MIDI からキー・コード特徴量を抽出する（メロディ/音域/構造は順次拡張）。"""
    score = _load_and_clean(midi_path)
    return {
        "key": _analyze_key(score),
        "chords": _analyze_chords(score),
        "melody": _analyze_melody(score),
        "structure": _analyze_structure(score),
    }

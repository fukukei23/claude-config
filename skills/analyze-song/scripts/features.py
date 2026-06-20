"""music21 で MIDI から特徴量を抽出する（Phase1b）。

Phase1b 設計:
- キー推定: music21 analyze('key')（ボーカルMIDI基準）
- コード進行: accompaniment（伴奏）MIDI を chordify し、検出キー相対の
  ローマ数字（romanNumeralFromChord）で表記。pitchedCommonName は実測で
  ゴミ名になったため廃止。
- 音域・phrase_repetition: vocals（ボーカル）MIDI のみで算出（ゴーストノート排除）。
- 構造: MIDI の quarterLength ではなく音源 duration_sec で正規化。

ノイズ除去: chordify + 最小音長フィルタ（spec 注意点2 相当）。
"""
from music21 import chord, converter, note, roman

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


def _analyze_chords(score, detected_key) -> dict:
    """chordify でコード進行を抽出し、検出キー相対のローマ数字で表記する。

    pitchedCommonName はmusic21 の内部命名が実用外れだったため、キー相対の
    ローマ数字（I/V/vi 等）に切替。これでダイアトニック和音として読める。
    """
    chordified = score.chordify()
    progression = []
    for c in chordified.recurse().getElementsByClass(chord.Chord):
        try:
            rn = roman.romanNumeralFromChord(c, detected_key)
            name = rn.figure
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
    """メロディ音域を抽出（ボーカルMIDI基準）。"""
    notes_flat = list(score.recurse().notes)
    pitches = []
    for n in notes_flat:
        if isinstance(n, note.Note):
            pitches.append(n.pitch)
        elif hasattr(n, "pitches"):
            pitches.extend(n.pitches)
    if not pitches:
        return {
            "range_low": "N/A",
            "range_high": "N/A",
            "range_semitones": 0,
            "phrase_repetition": {"detected": False, "pairs": []},
        }
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
    """前半/後半の音程輪郭を比較し同一性を検出する（ボーカルMIDI基準）。

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


def _analyze_structure(duration_sec: float) -> dict:
    """音源duration_sec で sections/form を返す。

    Phase1a では MIDI の quarterLength を使っていたが音源長と矛盾したため、
    音源 duration_sec（真値）で正規化する。
    """
    if duration_sec <= 0:
        return {"sections": [], "form": "?"}
    mid = duration_sec / 2.0
    return {
        "sections": [
            {"name": "first_half", "start": 0.0, "end": mid},
            {"name": "second_half", "start": mid, "end": duration_sec},
        ],
        "form": "AB",
    }


def analyze_features(vocals_mid: str, accomp_mid: str, duration_sec: float) -> dict:
    """ボーカル/伴奏MIDI + 音源長から全特徴量を抽出する。

    Args:
        vocals_mid: ボーカルステム由来のMIDIパス（キー/音域/phrase 用）。
        accomp_mid: 伴奏ステム由来のMIDIパス（コード 用）。
        duration_sec: 音源の長さ（構造 正規化用）。
    """
    voc_score = _load_and_clean(vocals_mid)
    acc_score = _load_and_clean(accomp_mid)
    detected_key = voc_score.analyze("key")
    return {
        "key": _analyze_key(voc_score),
        "chords": _analyze_chords(acc_score, detected_key),
        "melody": _analyze_melody(voc_score),
        "structure": _analyze_structure(duration_sec),
    }

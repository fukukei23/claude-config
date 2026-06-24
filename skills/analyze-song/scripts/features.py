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
import librosa
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


# 三和音ラベル組み立て用: scaleDegree(1-7) → 小文字ローマ数字
_ROMAN_DEGREES = ["i", "ii", "iii", "iv", "v", "vi", "vii"]


def _roman_to_triad_label(rn) -> str:
    """RomanNumeral から転回形・テンションを除いた三和音ラベルを組み立てる。

    impliedQuality（転回形/テンションを無視した基本クオリティ）と scaleDegree、
    前置 accidentals から音楽標準表記の三和音ラベルを作る。figure 文字列の
    ノイズ表記（IV654 等）をクリーン化し、曲間共通 n-gram を出現させる目的。

    Args:
        rn: music21 の RomanNumeral オブジェクト。

    Returns:
        三和音ラベル（例: "IV", "vi", "viio", "bIV+", "#i"）。
    """
    base = _ROMAN_DEGREES[rn.scaleDegree - 1]
    quality = rn.impliedQuality
    if quality == "major":
        label = base.upper()
    elif quality == "minor":
        label = base
    elif quality == "diminished":
        label = base + "o"
    elif quality == "augmented":
        label = base.upper() + "+"
    else:
        label = base  # 未知品質のフォールバック（impliedQuality で大半は救済済み）
    acc = rn.frontAlterationAccidental
    if acc is not None:
        if acc.alter < 0:
            label = "b" + label
        elif acc.alter > 0:
            label = "#" + label
    return label


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


def _analyze_vocals(score) -> dict:
    """ボーカルMIDIから音域・性別推定・声域を抽出する（Phase1b）。

    性別推定: ピッチ中央値(median MIDI)で判定。A3(=57)以下=male、超=female。
    声域(timbre): range_high に基づき male=bass/baritone/tenor、
    female=alto/mezzo-soprano/soprano。
    ※ falsetto 判定は倍音構造が必要でMIDI単体では不可（Phase2+課題）。
    """
    pitches = [n.pitch for n in score.recurse().notes if isinstance(n, note.Note)]
    if not pitches:
        return {
            "range_low": "N/A",
            "range_high": "N/A",
            "gender_estimate": "unknown",
            "timbre": "unknown",
        }
    low = min(pitches)
    high = max(pitches)
    midis = [p.midi for p in pitches]
    median_midi = sorted(midis)[len(midis) // 2]
    gender = "male" if median_midi <= 57 else "female"
    high_midi = high.midi
    if gender == "male":
        if high_midi <= 55:
            timbre = "bass"
        elif high_midi <= 62:
            timbre = "baritone"
        else:
            timbre = "tenor"
    else:
        if high_midi <= 69:
            timbre = "alto"
        elif high_midi <= 76:
            timbre = "mezzo-soprano"
        else:
            timbre = "soprano"
    return {
        "range_low": low.nameWithOctave,
        "range_high": high.nameWithOctave,
        "gender_estimate": gender,
        "timbre": timbre,
    }


# Phase1b instrumentation: 4ステム構成（htdemucs の分離ラベル）と無音判定閾値
STEM_PARTS = ("drums", "bass", "vocals", "other")
SILENCE_RMS = 0.01


def _stem_features(wav_path: str) -> dict:
    """stem WAV の音響特徴量を返す（RMS/centroid/zcr/flatness）。"""
    y, sr = librosa.load(wav_path, sr=22050, mono=True)
    return {
        "rms": float(librosa.feature.rms(y=y).mean()),
        "centroid": float(librosa.feature.spectral_centroid(y=y, sr=sr).mean()),
        "zcr": float(librosa.feature.zero_crossing_rate(y=y).mean()),
        "flatness": float(librosa.feature.spectral_flatness(y=y).mean()),
    }


def _classify_part(name: str, feat: dict) -> str | None:
    """stem 名 + 音響特徴量で楽器カテゴリを推定。無音(None)なら除外。

    drums/bass/vocals は Demucs 分離ラベルで確定、other は spectral_centroid
    （音の明るさ）で鍵盤/弦/シンセ系を大別。
    """
    if feat["rms"] < SILENCE_RMS:
        return None
    if name == "drums":
        return "percussion"
    if name == "bass":
        return "bass"
    if name == "vocals":
        return "voice"
    if feat["centroid"] < 1500:
        return "low keys/strings"
    if feat["centroid"] < 3000:
        return "keys/strings"
    return "bright synth/strings"


def _analyze_instrumentation(stems_paths: dict) -> dict:
    """4 stem WAV の音響特徴量から楽器構成を推定する（案2）。

    Args:
        stems_paths: {"drums","bass","vocals","other"} → WAV パス。
    """
    parts = [n for n in STEM_PARTS if n in stems_paths]
    detected = []
    for name in parts:
        cat = _classify_part(name, _stem_features(stems_paths[name]))
        if cat:
            detected.append(cat)
    return {"parts": parts, "instruments_detected": detected}


def analyze_features(
    vocals_mid: str,
    accomp_mid: str,
    duration_sec: float,
    stems_paths: dict | None = None,
) -> dict:
    """ボーカル/伴奏MIDI + 音源長から全特徴量を抽出する。

    Args:
        vocals_mid: ボーカルステム由来のMIDIパス（キー/音域/phrase/vocals 用）。
        accomp_mid: 伴奏ステム由来のMIDIパス（コード 用）。
        duration_sec: 音源の長さ（構造 正規化用）。
        stems_paths: 4ステムWAVパス辞書。渡すと instrumentation を追加（案2）。
    """
    voc_score = _load_and_clean(vocals_mid)
    acc_score = _load_and_clean(accomp_mid)
    detected_key = voc_score.analyze("key")
    result = {
        "key": _analyze_key(voc_score),
        "chords": _analyze_chords(acc_score, detected_key),
        "melody": _analyze_melody(voc_score),
        "vocals": _analyze_vocals(voc_score),
        "structure": _analyze_structure(duration_sec),
    }
    if stems_paths is not None:
        result["instrumentation"] = _analyze_instrumentation(stems_paths)
    return result

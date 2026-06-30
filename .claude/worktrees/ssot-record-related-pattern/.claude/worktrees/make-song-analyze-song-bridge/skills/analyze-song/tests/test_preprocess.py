"""preprocess の単体テスト。"""
from scripts import preprocess


def test_note_name_to_pc():
    assert preprocess.note_name_to_pc("C") == 0
    assert preprocess.note_name_to_pc("F") == 5
    assert preprocess.note_name_to_pc("B") == 11
    assert preprocess.note_name_to_pc("F#") == 6
    assert preprocess.note_name_to_pc("Bb") == 10  # フラット許容
    assert preprocess.note_name_to_pc("") is None
    assert preprocess.note_name_to_pc("X") is None


def test_note_to_midi():
    assert preprocess.note_to_midi("C4") == 60
    assert preprocess.note_to_midi("A4") == 69
    assert preprocess.note_to_midi("E3") == 52
    assert preprocess.note_to_midi("C2") == 36
    assert preprocess.note_to_midi("B0") == 23  # 標準MIDI: (0+1)*12+11
    assert preprocess.note_to_midi("hoge") is None


def test_note_name_to_pc_flat_dash():
    # music21 フラット表記 "-" を受理
    assert preprocess.note_name_to_pc("B-") == 10  # Bb = A# pc
    assert preprocess.note_name_to_pc("E-") == 3   # Eb = D# pc
    assert preprocess.note_name_to_pc("A-") == 8   # Ab = G# pc


def test_note_to_midi_flat_dash():
    assert preprocess.note_to_midi("B-0") == 22  # Bb0
    assert preprocess.note_to_midi("E-7") == 99  # Eb7
    assert preprocess.note_to_midi("A-3") == 56  # Ab3 = (3+1)*12+8 = 56


def _features(bpm=120.0, key="C", scale="major", prog=None,
              range_low="E3", range_high="C7"):
    return {
        "tempo": {"bpm": bpm, "bpm_confidence": 0.9},
        "key": {"key": key, "scale": scale, "confidence": 0.8},
        "chords": {"progression": prog or ["i", "iv", "v"]},
        "melody": {"range_low": range_low, "range_high": range_high,
                   "range_semitones": 44},
        "vocals": {"gender_estimate": "female"},  # ノイズ・除外対象
    }


def test_preprocess_basic():
    v = preprocess.preprocess(_features())
    assert v["bpm"] == 120.0
    assert v["key_pc"] == 0
    assert v["scale"] == "major"
    assert v["progression"] == ["i", "iv", "v"]
    assert "gender_estimate" not in v  # ノイズ除外
    assert v["range_low_midi"] == 52   # E3
    assert v["range_high_midi"] == 96  # C7 = (7+1)*12+0
    assert v["range_valid"] is True


def test_preprocess_low_cutoff_clips_range_low():
    # B0(23) は C2(36) 未満 → クリップ
    v = preprocess.preprocess(_features(range_low="B0", range_high="C7"))
    assert v["range_low_midi"] == 36  # C2 にクリップ
    assert v["range_high_midi"] == 96  # C7 = (7+1)*12+0


def test_preprocess_invalid_range_marks_invalid():
    # 補正後も 5オクターブ超 → range_valid False
    v = preprocess.preprocess(_features(range_low="C2", range_high="C8"))
    # C2=36, C8=108 → 72半音(6oct) > 48
    assert v["range_valid"] is False


def test_preprocess_missing_required_returns_none():
    f = _features()
    f["tempo"]["bpm"] = None
    assert preprocess.preprocess(f) is None


def test_preprocess_missing_key_returns_none():
    f = _features()
    f["key"]["key"] = ""
    assert preprocess.preprocess(f) is None

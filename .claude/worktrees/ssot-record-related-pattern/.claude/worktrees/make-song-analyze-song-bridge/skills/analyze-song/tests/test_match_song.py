"""match_song の単体テスト（fixture ベース・単体）。"""
import json

import pytest

from scripts import match_song


def _feat(bpm, key, scale="major", prog=None, low="E3", high="C7"):
    return {
        "meta": {"title": "q"},
        "tempo": {"bpm": bpm, "bpm_confidence": 0.9},
        "key": {"key": key, "scale": scale, "confidence": 0.8},
        "chords": {"progression": prog or ["i", "iv", "v"]},
        "melody": {"range_low": low, "range_high": high, "range_semitones": 44},
    }


@pytest.fixture
def db_dir(tmp_path):
    d = tmp_path / "db"
    d.mkdir()
    # query と同一曲(JPOP-001) + 違う曲(JPOP-002)
    (d / "JPOP-001").mkdir()
    (d / "JPOP-001" / "features.json").write_text(
        json.dumps(_feat(86.0, "G")), encoding="utf-8")
    (d / "JPOP-002").mkdir()
    (d / "JPOP-002" / "features.json").write_text(
        json.dumps(_feat(140.0, "C")), encoding="utf-8")
    return d


def test_match_returns_report_with_top(db_dir, tmp_path):
    query = tmp_path / "query.json"
    query.write_text(json.dumps(_feat(86.0, "G")), encoding="utf-8")
    rep = match_song.match(query, db_dir)
    assert rep["score"]["top"][0][0] == "JPOP-001"  # 自己再現性
    assert rep["score"]["top"][0][1] > 0.99


def test_match_skips_invalid_db_song(db_dir, tmp_path):
    # JPOP-003 を必須軸欠損で追加
    bad = db_dir / "JPOP-003"
    bad.mkdir()
    bad_feat = _feat(86.0, "G")
    bad_feat["tempo"]["bpm"] = None
    (bad / "features.json").write_text(json.dumps(bad_feat), encoding="utf-8")
    query = tmp_path / "query.json"
    query.write_text(json.dumps(_feat(86.0, "G")), encoding="utf-8")
    rep = match_song.match(query, db_dir)
    ids = [sid for sid, _ in rep["score"]["top"]]
    assert "JPOP-003" not in ids


def test_match_query_missing_required_raises(tmp_path, db_dir):
    query = tmp_path / "query.json"
    qf = _feat(86.0, "G")
    qf["key"]["key"] = ""
    query.write_text(json.dumps(qf), encoding="utf-8")
    with pytest.raises(ValueError):
        match_song.match(query, db_dir)


def test_main_writes_make_song_input_json(tmp_path, monkeypatch):
    """main 実行で make_song_input.json が report.md と同階層に書き出される。"""
    import json
    from scripts import match_song, db_index

    db_dir = tmp_path / "名曲DB"
    song_dir = db_dir / "JPOP-004"
    song_dir.mkdir(parents=True)
    (song_dir / "features.json").write_text(
        json.dumps({
            "meta": {"title": "ドライフラワー"},
            "tempo": {"bpm": 95.0},
            "key": {"key": "F", "scale": "major"},
            "chords": {"progression": ["F", "G", "Am"], "unique_progressions": 1},
            "melody": {"range_low": "F3", "range_high": "A4",
                       "range_semitones": 14, "phrase_repetition": {"detected": False, "pairs": []}},
            "vocals": {"range_low": "F3", "range_high": "A4",
                       "gender_estimate": "female", "timbre": "pop"},
        }, ensure_ascii=False), encoding="utf-8")
    db_index.save_index(db_dir / "_index.yaml", {
        "version": 1, "updated": "2026-06-23",
        "songs": [{"id": "JPOP-004", "status": "registered", "title": "ドライフラワー",
                   "artist": "優里", "genre": "JPOP", "commercial_rank": "long_seller",
                   "era": "2020s", "selection_reason": "test", "source_type": "youtube",
                   "source_url": "", "features_path": "JPOP-004/features.json",
                   "analyzed_at": "2026-06-23", "analyze_phase": "1b"}],
    })
    query_dir = tmp_path / "query"
    query_dir.mkdir()
    query_feat = {
        "meta": {"title": "MySong"},
        "tempo": {"bpm": 90.0},
        "key": {"key": "C", "scale": "major"},
        "chords": {"progression": ["C", "G", "Am"], "unique_progressions": 1},
        "melody": {"range_low": "C3", "range_high": "E4",
                   "range_semitones": 16, "phrase_repetition": {"detected": False, "pairs": []}},
        "vocals": {"range_low": "C3", "range_high": "E4",
                   "gender_estimate": "male", "timbre": "pop"},
    }
    query_path = query_dir / "features.json"
    query_path.write_text(json.dumps(query_feat, ensure_ascii=False), encoding="utf-8")

    match_song.main(str(query_path), str(db_dir))

    msi_path = query_dir / "make_song_input.json"
    assert msi_path.exists(), "make_song_input.json が書き出されていない"
    msi = json.loads(msi_path.read_text(encoding="utf-8"))
    assert msi["schema_version"] == 1
    assert msi["query"]["title"] == "MySong"
    assert msi["query"]["gender_estimate"] == "male"
    assert any(r["id"] == "JPOP-004" for r in msi["reference_songs"])
    assert msi["recommended"]["bpm"] == 95

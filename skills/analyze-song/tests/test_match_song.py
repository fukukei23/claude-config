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

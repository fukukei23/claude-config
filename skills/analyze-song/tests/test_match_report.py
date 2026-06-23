"""match_report の単体テスト。"""
from scripts import match_report


def _ctx(query_bpm=86.0, query_key_pc=7):
    return {
        "query": {"bpm": query_bpm, "key_pc": query_key_pc,
                  "scale": "major", "progression": ["i", "iv", "v"]},
        "top": [("JPOP-001", 0.85), ("JPOP-002", 0.70)],
        "normalized_db": {
            "JPOP-001": {"bpm": 88.0, "key_pc": 7, "scale": "major",
                         "progression": ["i", "iv", "v"]},
            "JPOP-002": {"bpm": 74.0, "key_pc": 7, "scale": "major",
                         "progression": ["i", "iv", "v"]},
        },
        "centroid": {"avg_bpm": 81.0, "mode_key_pc": 7},
        "scores_detail": {
            "JPOP-001": {"bpm": 0.9, "key": 1.0, "chord": 1.0, "range": 0.6},
            "JPOP-002": {"bpm": 0.3, "key": 1.0, "chord": 1.0, "range": 0.6},
        },
    }


def test_build_report_has_score_and_hints():
    rep = match_report.build_report(_ctx())
    assert "score" in rep
    assert "hints" in rep
    assert rep["score"]["top"][0][0] == "JPOP-001"


def test_build_report_hints_mention_bpm():
    rep = match_report.build_report(_ctx(query_bpm=86.0))
    text = " ".join(rep["hints"])
    assert "BPM" in text or "テンポ" in text


def test_build_report_centroid():
    rep = match_report.build_report(_ctx())
    assert rep["score"]["centroid"]["avg_bpm"] == 81.0


def _ctx_mk(top=None):
    """テスト用の照合結果 ctx。"""
    return {
        "top": top or [("JPOP-004", 0.608), ("ROCK-003", 0.412)],
        "centroid": {"avg_bpm": 104.0, "mode_key_pc": 11},
        "scores_detail": {},
        "normalized_db": {},
    }


_DB_META = {
    "JPOP-004": {"id": "JPOP-004", "title": "ドライフラワー", "artist": "優里", "genre": "JPOP"},
    "ROCK-003": {"id": "ROCK-003", "title": "Rocks", "artist": "X", "genre": "ROCK"},
    "HIPHOP-005": {"id": "HIPHOP-005", "title": "Hype", "artist": "Y", "genre": "HIPHOP"},
}

_QUERY_FEATURES = {
    "meta": {"title": "Lemon"},
    "tempo": {"bpm": 87.2},
    "key": {"key": "A minor"},
    "vocals": {"gender_estimate": "female"},
}


def test_build_make_song_input_structure():
    result = match_report.build_make_song_input(
        _ctx_mk(), _DB_META, _QUERY_FEATURES, query_id="JPOP-001"
    )
    assert result["schema_version"] == 1
    assert result["query"]["title"] == "Lemon"
    assert result["query"]["id"] == "JPOP-001"
    assert result["query"]["bpm"] == 87.2
    assert result["query"]["key"] == "A minor"
    assert result["query"]["gender_estimate"] == "female"
    assert len(result["reference_songs"]) == 2
    first = result["reference_songs"][0]
    assert first["rank"] == 1
    assert first["id"] == "JPOP-004"
    assert first["total"] == 0.608
    assert first["title"] == "ドライフラワー"
    assert first["genre"] == "JPOP"
    assert result["centroid"]["avg_bpm"] == 104.0
    assert result["recommended"]["bpm"] == 104
    assert result["recommended"]["key_pc"] == 11
    assert "notes" in result and isinstance(result["notes"], list)


def test_build_make_song_input_excludes_self():
    ctx = _ctx_mk(top=[("JPOP-001", 1.0), ("JPOP-004", 0.608), ("ROCK-003", 0.412)])
    db_meta = {
        "JPOP-001": {"id": "JPOP-001", "title": "Lemon", "artist": "米津玄師", "genre": "JPOP"},
        **_DB_META,
    }
    result = match_report.build_make_song_input(
        ctx, db_meta, _QUERY_FEATURES, query_id="JPOP-001"
    )
    ids = [r["id"] for r in result["reference_songs"]]
    assert "JPOP-001" not in ids
    assert ids == ["JPOP-004", "ROCK-003"]


def test_build_make_song_input_meta_missing():
    ctx = _ctx_mk(top=[("UNKNOWN-999", 0.5), ("JPOP-004", 0.4)])
    result = match_report.build_make_song_input(
        ctx, _DB_META, _QUERY_FEATURES, query_id="JPOP-001"
    )
    unknown = result["reference_songs"][0]
    assert unknown["id"] == "UNKNOWN-999"
    assert unknown["total"] == 0.5
    assert "title" not in unknown
    assert "artist" not in unknown
    assert "genre" not in unknown


def test_build_make_song_input_genre_distribution():
    ctx = _ctx_mk(top=[("JPOP-004", 0.6), ("ROCK-003", 0.4), ("HIPHOP-005", 0.3)])
    result = match_report.build_make_song_input(
        ctx, _DB_META, _QUERY_FEATURES, query_id="JPOP-001"
    )
    assert result["genre_distribution"] == {"JPOP": 1, "ROCK": 1, "HIPHOP": 1}

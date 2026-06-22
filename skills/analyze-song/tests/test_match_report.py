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

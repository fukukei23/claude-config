"""report のテスト。"""
import json

from scripts.report import generate_report


def test_generate_report_writes_markdown(workdir):
    """features.json から report.md が生成されること。"""
    features = {
        "meta": {"title": "テスト曲", "source": "local", "phase": "1a"},
        "tempo": {"bpm": 85.0, "bpm_confidence": 0.9},
        "key": {"key": "G", "scale": "major", "confidence": 0.88},
        "chords": {"progression": ["G", "D"], "unique_progressions": 2},
        "melody": {
            "range_low": "G3", "range_high": "D5", "range_semitones": 14,
            "phrase_repetition": {"detected": True, "pairs": [{"match": 10, "total": 12}]},
        },
        "_log": [
            {"step": "tempo_key", "status": "ok", "sec": 1.2},
            {"step": "score_render", "status": "skip", "reason": "no musescore"},
        ],
    }
    (workdir / "features.json").write_text(json.dumps(features, ensure_ascii=False))
    out = generate_report(workdir)
    assert out == workdir / "report.md"
    text = out.read_text()
    assert "テスト曲" in text
    assert "85.0" in text
    assert "phrase_repetition" in text or "同一性" in text
    assert "tempo_key" in text  # 工程ログ記載

"""tests/test_model_stay_detector.py — glm-5.3滞在検出ロジックのテスト（spec §6）"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "llm"))
from model_stay_detector import detect, scan_file  # noqa: E402

NOW = datetime(2026, 9, 1, 3, 0, 0, tzinfo=timezone.utc)


def _entry(ts: datetime, model: str) -> str:
    return json.dumps(
        {"type": "assistant", "timestamp": ts.isoformat(), "message": {"model": model}},
        ensure_ascii=False)


def make_transcript(tmp_path, entries):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(entries) + "\n", encoding="utf-8")
    return str(p)


def ts_before(minutes: float) -> datetime:
    return NOW - timedelta(minutes=minutes)


def test_flash_only_returns_empty(tmp_path):
    p = make_transcript(tmp_path, [_entry(ts_before(10), "glm-5.3-flash"),
                                   _entry(ts_before(5), "glm-5.3-flash")])
    assert detect([p], NOW) == []


def test_53_run_detected(tmp_path):
    p = make_transcript(tmp_path, [_entry(ts_before(60), "glm-5.3"),
                                   _entry(ts_before(40), "glm-5.3"),
                                   _entry(ts_before(20), "glm-5.3")])
    res = detect([p], NOW)
    assert len(res) == 1
    assert res[0]["model"] == "glm-5.3"
    assert res[0]["since_min"] == 60.0
    assert res[0]["turns"] == 3


def test_switch_midway_measures_from_switch(tmp_path):
    p = make_transcript(tmp_path, [_entry(ts_before(90), "glm-5.3-flash"),
                                   _entry(ts_before(45), "glm-5.3"),
                                   _entry(ts_before(10), "glm-5.3")])
    res = detect([p], NOW)
    assert res[0]["since_min"] == 45.0
    assert res[0]["turns"] == 2


def test_switched_back_returns_empty(tmp_path):
    p = make_transcript(tmp_path, [_entry(ts_before(30), "glm-5.3"),
                                   _entry(ts_before(10), "glm-5.3-flash")])
    assert detect([p], NOW) == []


def test_broken_lines_skipped(tmp_path):
    lines = [_entry(ts_before(40), "glm-5.3"), "{broken json!!!", "",
             _entry(ts_before(20), "glm-5.3")]
    p = make_transcript(tmp_path, lines)
    res = detect([p], NOW)
    assert res[0]["turns"] == 2


def test_missing_file_and_empty_are_none(tmp_path):
    assert scan_file(str(tmp_path / "nope.jsonl"), NOW) is None
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    assert scan_file(str(p), NOW) is None


def test_tail_limit_excludes_old_run(tmp_path):
    entries = [_entry(ts_before(60 * 24), "glm-5.3") for _ in range(550)]
    entries += [_entry(ts_before(10), "glm-5.3-flash") for _ in range(50)]
    p = make_transcript(tmp_path, entries)
    assert detect([p], NOW) == []


def test_non_utc_offset_timestamp(tmp_path):
    jst = timezone(timedelta(hours=9))
    ts_jst = ts_before(45).astimezone(jst)
    p = make_transcript(tmp_path, [_entry(ts_jst, "glm-5.3")])
    res = detect([p], NOW)
    assert res[0]["since_min"] == 45.0


def test_1m_suffix_model_still_matches():
    import model_stay_detector as m
    assert m.is_high_cost("glm-5.3") is True
    assert m.is_high_cost("glm-5.3-flash") is False
    assert m.is_high_cost("minimax-m3") is False
    assert m.is_high_cost(None) is False

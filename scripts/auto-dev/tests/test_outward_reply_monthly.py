"""月次集計ヒントのテスト（spec 2026-08-16 Task4）."""
from datetime import date
from pathlib import Path

from daily_triage import monthly_review_hint


def test_月初で未実施なら提案():
    state = Path("/tmp/fake_state")
    hint = monthly_review_hint(date(2026, 9, 3), state)
    assert "月次集計" in hint
    assert (state / "outward-reply-monthly-2026-09.done").exists()


def test_実施済みフラグがあれば空():
    state = Path("/tmp/fake_state2")
    state.mkdir(parents=True, exist_ok=True)
    (state / "outward-reply-monthly-2026-09.done").write_text("done", encoding="utf-8")
    assert monthly_review_hint(date(2026, 9, 3), state) == ""


def test_8日以降は空():
    assert monthly_review_hint(date(2026, 9, 10), Path("/tmp/fake_state3")) == ""

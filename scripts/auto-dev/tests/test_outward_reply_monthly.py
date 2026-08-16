"""月次集計ヒントのテスト（spec 2026-08-16 Task4）."""
from datetime import date

from daily_triage import monthly_review_hint


def test_月初で未実施なら提案(tmp_path):
    hint = monthly_review_hint(date(2026, 9, 3), tmp_path)
    assert "月次集計" in hint
    assert (tmp_path / "outward-reply-monthly-2026-09.done").exists()


def test_実施済みフラグがあれば空(tmp_path):
    (tmp_path / "outward-reply-monthly-2026-09.done").write_text("done", encoding="utf-8")
    assert monthly_review_hint(date(2026, 9, 3), tmp_path) == ""


def test_8日以降は空(tmp_path):
    assert monthly_review_hint(date(2026, 9, 10), tmp_path) == ""

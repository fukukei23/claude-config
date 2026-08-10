"""aiwatch.guide_generator のユニットテスト。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiwatch.guide_generator import (  # noqa: E402
    html_sanity_ok,
    render_repo_card,
    render_source_md,
)
from aiwatch.models import EvaluatedRepo, RepoStats  # noqa: E402


def _evald(desc="tool", star=3, today=100, total=1000, tag="初見", method="rule_fallback") -> EvaluatedRepo:
    repo = RepoStats("a/b", "https://github.com/a/b", desc, today, total, 0.1, tag)
    return EvaluatedRepo(repo=repo, fit_star=star, eval_text="おすすめ文", eval_method=method)


def test_render_source_md_has_sections():
    md = render_source_md(
        evaluated=[_evald(today=500)],
        metrics={"active": 60, "avg_days": 14, "freshness": 3, "archived": 10, "declined": 5},
        cost={"usd": 0.016, "count": 30, "eval_method_breakdown": "llm:25/rule:5"},
    )
    assert "📈 AI Trending Watch" in md
    assert "📊 在庫健全性" in md
    assert "🤖 今週の評価コスト" in md
    assert "60件" in md  # active
    assert "$0.0160" in md  # cost


def test_render_repo_card_contains_eval_icon():
    card = render_repo_card(_evald(method="llm"))
    assert "🤖" in card
    assert "[a/b]" in card
    assert "★" in card


def test_render_source_md_empty_evaluated():
    md = render_source_md(evaluated=[], metrics={}, cost={})
    assert "今週のバズなし" in md


def test_html_sanity_rejects_empty():
    assert html_sanity_ok("") is False


def test_html_sanity_rejects_no_body():
    assert html_sanity_ok("<html></html>") is False


def test_html_sanity_rejects_too_short():
    assert html_sanity_ok("<html><body>x</body></html>" * 1) is False


def test_html_sanity_accepts_valid():
    html = "<html><body>" + "<h2>repo</h2>" * 5 + "x" * 600 + "</body></html>"
    assert html_sanity_ok(html) is True


def test_render_source_md_sorts_by_star_desc():
    e5 = _evald(star=5, desc="five")
    e1 = _evald(star=1, desc="one")
    md = render_source_md(evaluated=[e1, e5], metrics={}, cost={})
    # ★5が★1より前に出現
    assert md.index("five") < md.index("one")

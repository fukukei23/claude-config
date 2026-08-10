"""aiwatch.cost + aiwatch.safety のユニットテスト。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiwatch import cost, safety  # noqa: E402


def test_estimate_usd_minimax_rates():
    # 17500入力 + 9000出力 → 約$0.016
    usd = cost.estimate_usd(tokens_in=17500, tokens_out=9000)
    assert 0.01 < usd < 0.02


def test_weekly_cap_exceeded_normal():
    assert cost.weekly_cap_exceeded(0.02) is False


def test_weekly_cap_exceeded_runaway():
    assert cost.weekly_cap_exceeded(25.0) is True  # 暴走


def test_record_usage_writes_json(tmp_path):
    cost_file = tmp_path / "cost.json"
    rec = cost.record_usage(
        tokens_in=17500, tokens_out=9000, count=30,
        eval_methods={"llm": 25, "rule_fallback": 5},
        cost_file=cost_file, week_label="2026-W33",
    )
    assert rec["count"] == 30
    assert rec["cap_exceeded"] is False
    data = json.loads(cost_file.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["week"] == "2026-W33"


def test_record_usage_appends(tmp_path):
    cost_file = tmp_path / "cost.json"
    cost.record_usage(100, 100, 1, {}, cost_file=cost_file)
    cost.record_usage(200, 200, 2, {}, cost_file=cost_file)
    data = json.loads(cost_file.read_text(encoding="utf-8"))
    assert len(data) == 2


def test_safety_should_commit_dry_run():
    ok, msg = safety.should_commit(gh_ok=True, html_ok=True, dry_run=True)
    assert ok is False


def test_safety_should_commit_html_fail():
    ok, msg = safety.should_commit(gh_ok=True, html_ok=False, dry_run=False)
    assert ok is False
    assert "HTML" in msg


def test_safety_should_commit_ok():
    ok, msg = safety.should_commit(gh_ok=True, html_ok=True, dry_run=False)
    assert ok is True


def test_safety_should_commit_gh_fail_continues():
    """gh失敗は★N/Aで継続(commit可)。"""
    ok, msg = safety.should_commit(gh_ok=False, html_ok=True, dry_run=False)
    assert ok is True


def test_fallback_to_rulestars():
    assert safety.fallback_to_rulestars(llm_failed=True, cap_exceeded=False) is True
    assert safety.fallback_to_rulestars(llm_failed=False, cap_exceeded=True) is True
    assert safety.fallback_to_rulestars(llm_failed=False, cap_exceeded=False) is False


def test_verify_pages_html(monkeypatch):
    """html_sanity_ok をモックして verify_pages_html 挙動確認。"""
    import aiwatch.guide_generator as gg
    monkeypatch.setattr(gg, "html_sanity_ok", lambda html, **k: True)
    ok, msg = safety.verify_pages_html("<html></html>")
    assert ok is True
    monkeypatch.setattr(gg, "html_sanity_ok", lambda html, **k: False)
    ok, msg = safety.verify_pages_html("")
    assert ok is False

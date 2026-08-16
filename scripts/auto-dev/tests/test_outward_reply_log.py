"""外向き返信ログ収集のテスト（spec 2026-08-16 Task3）."""
from pathlib import Path

from daily_triage import format_outward_reply_section


def test_セクション生成_件数と未入力():
    log = Path("/tmp/fake_orl.md")
    log.write_text(
        "# 外向き返信実績ログ\n\n"
        "## ログ\n\n"
        "| ID | 日付 | 宛先種別 | 対話フェーズ | モード | 質問数 | 断定数 | ⚠️ | 修正回数 | 修正類型 | 本文要約 | 効いた軸 | 結果 |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| 20260816-01 | 2026-08-16 | 応募 | 初手 | 簡易 | 0 | 2 | なし | 1 | 【既知:専門用語】 | （要約） | 速度 | 未定 |\n"
        "| 20260816-02 | 2026-08-16 | ココナラ | 往復 | フル | 1 | 0 | なし | 0 | — | （要約） | 共感 | 返信あり |\n",
        encoding="utf-8",
    )
    sec = format_outward_reply_section(log)
    assert "📮外向き返信ログ: 2件（結果未入力1件）" in sec


def test_未入力率40超で分析停止表示():
    log = Path("/tmp/fake_orl2.md")
    log.write_text(
        "## ログ\n\n"
        "| ID | 結果 |\n|---|---|\n"
        "| 20260816-01 | 未定 |\n| 20260816-02 | 未定 |\n"
        "| 20260816-03 | 返信あり |\n| 20260816-04 | 未定 |\n"
        "| 20260816-05 | 未定 |\n",
        encoding="utf-8",
    )
    sec = format_outward_reply_section(log)
    assert "分析提案停止" in sec


def test_ログ無し():
    sec = format_outward_reply_section(Path("/tmp/nonexistent_orl.md"))
    assert sec == ""

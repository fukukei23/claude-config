"""daily_triage 収集ロジックのテスト"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from daily_triage import (
    collect_backlog,
    collect_active_green,
    collect_handoff_latest,
    build_context,
    validate_repo,
    parse_task_date,  # noqa: E402
)

FIX = Path(__file__).resolve().parent / "fixtures"


def test_collect_backlog_p0_p1_only():
    """P0/P1の未完了([ ])のみ抽出。P2・完了済み・[x]は除外。"""
    result = collect_backlog(FIX / "backlog.md")
    joined = "\n".join(result)

    # P0/P1 は含まれる
    assert "オールブルー応募" in joined
    assert "NexusCoreデモ動画撮影" in joined
    # P2 は除外
    assert "P2タスク" not in joined
    # 完了済みセクションは除外
    assert "完了タスク" not in joined
    # "[ ]" マーカーは取り除かれる（タスク本文のみ）
    assert all(not t.startswith("[ ]") for t in result)


def test_collect_active_green_rows_only():
    """🟢進行中（単一表・状態列）の行のみ抽出。

    2026-07-02 単一表化後の形式対応。状態列末尾が 🟢 の行のみ返し、
    ヘッダー/区切り行/別セクション/✅完了行は除外。
    回帰: 当時「🟢進行中なし」と誤判定され候補重複が発生していたバグ (2026-07-05)。
    """
    result = collect_active_green(FIX / "active-sessions.md")
    joined = "\n".join(result)

    # 🟢 の2行は含まれる
    assert any("analyze-song features改善" in t for t in result)
    assert any("WSL-loop-eng Phase1" in t for t in result)
    # ✅ 完了行は除外
    assert not any("WSL-hoge 検証" in t for t in result)
    assert not any("WSL-fuga 完了" in t for t in result)
    # ヘッダー行・区切り行は除外
    assert not any(t.startswith("| セッション") for t in result)
    assert not any(t.startswith("|---") for t in result)
    # 別セクション（共通ファイル・アーカイブ）の行は含まれない
    assert "settings.json" not in joined
    assert "廃止" not in joined


def test_collect_active_green_uses_dynamic_status_column(tmp_path):
    """状態列を動的特定（列順変更耐性・Geminiレビュー指摘反映）。

    ヘッダー行の「状態」列インデックスを動的に取得し、データ行もその
    インデックスで判定する。列順を変えても正しく動作することを確認。
    """
    from daily_triage import _collect_single_table_green
    md = tmp_path / "test.md"
    # 「状態」列が3番目（先頭からindex=2）にある例
    md.write_text(
        "## セッション状態\n\n"
        "| 環境 | タスク | 状態 |\n"
        "|---|---|---|\n"
        "| WSL | task-A | 🟢 |\n"
        "| WSL | task-B | ✅ |\n",
        encoding="utf-8",
    )
    result = collect_active_green(md)
    assert len(result) == 1
    assert "task-A" in result[0]
    assert "task-B" not in "\n".join(result)


def test_collect_active_green_falls_back_to_legacy(tmp_path):
    """旧形式 "## 🟢" セクションにフォールバック（後方互換）。

    新形式に該当が無い場合のみ旧形式を試す。
    """
    from daily_triage import _collect_legacy_green
    md = tmp_path / "test.md"
    md.write_text(
        "## 🟢 進行中\n\n"
        "| タスク | 環境 |\n"
        "|---|---|\n"
        "| old-task | WSL-old |\n",
        encoding="utf-8",
    )
    result = collect_active_green(md)
    assert len(result) == 1
    assert "old-task" in result[0]


def test_collect_handoff_latest_picks_newest():
    """ファイル名降順で最新1件の全文を返す。"""
    result = collect_handoff_latest(FIX / "handoff")
    assert result is not None
    # 2023 > 0703（文字列比較）で最新が選ばれる
    assert "loop engineering 構築 Phase1" in result
    assert "zenn ランキング自動更新" not in result


def test_collect_handoff_latest_empty_dir():
    """ディレクトリが無い/空なら None。"""
    assert collect_handoff_latest(FIX / "no-such-dir") is None


def test_collect_handoff_latest_ignores_non_date_files(tmp_path):
    """非日付形式ファイル(handoff_prompt.md等)を最新誤認しない。

    文字列降順で日付ファイルより先頭に来る handoff_prompt.md があっても
    無視し、YYYY-MM-DD_HHMM.md 形式の最新を選ぶ。
    回帰: handoff_prompt.md が古い内容で停滞し triage が常にそれを
    「最新」と拾っていたバグ（2026-06-28 修正）。
    """
    hd = tmp_path / "handoff"
    hd.mkdir()
    # "h" > "2" で文字列降順では先頭に来る、古い内容で停滞した非日付ファイル
    (hd / "handoff_prompt.md").write_text("STALE 古い内容", encoding="utf-8")
    # 本来の最新（日付形式）
    (hd / "2026-06-28_0815.md").write_text("最新の日付handoff", encoding="utf-8")
    result = collect_handoff_latest(hd)
    assert result == "最新の日付handoff"


def test_build_context_has_all_sections():
    """収集データを3セクション構造のテキストに組み立てる。"""
    ctx = build_context(
        backlog=["オールブルー応募 — v2完成済み"],
        green=["| analyze-song | WSL | 07:40 | 正規化 |"],
        handoff="## 次のタスク\n- Phase1実装",
    )
    assert "## バックログ" in ctx
    assert "オールブルー応募" in ctx
    assert "## 🟢進行中タスク" in ctx
    assert "analyze-song" in ctx
    assert "## 最新handoff" in ctx
    assert "Phase1実装" in ctx


def test_build_context_empty_inputs():
    """空入力は（なし）で埋める（クラッシュしない）。"""
    ctx = build_context(backlog=[], green=[], handoff=None)
    assert "（なし）" in ctx


def test_validate_repo_returns_abs_path_when_dir_exists(tmp_path):
    """実在するディレクトリ名→絶対パス返却。"""
    (tmp_path / "NexusCore").mkdir()
    assert validate_repo("NexusCore", projects_dir=tmp_path) == str(tmp_path / "NexusCore")


def test_validate_repo_returns_none_when_missing(tmp_path):
    """非実在ディレクトリ名→None。"""
    assert validate_repo("nonexistent-repo", projects_dir=tmp_path) is None


def test_validate_repo_returns_none_for_empty(tmp_path):
    """空文字・None→None。"""
    assert validate_repo("", projects_dir=tmp_path) is None
    assert validate_repo(None, projects_dir=tmp_path) is None  # type: ignore[arg-type]


def test_parse_task_date_extracts_month_day():
    """行末 (M/D...) の最初の日付を抽出。年は today 基準で推定。"""
    today = date(2026, 6, 28)
    assert parse_task_date("オールブルー応募 — 書類完成（5/19）", today=today) == date(2026, 5, 19)
    assert parse_task_date("タスク（6/26完了）", today=today) == date(2026, 6, 26)


def test_parse_task_date_future_month_assumes_prev_year():
    """M/D が today より未来なら前年扱い（年跨ぎの古いタスク）。"""
    today = date(2026, 6, 28)
    # 12/15 は 6/28 より未来の月日→前年 2025
    assert parse_task_date("タスク（12/15）", today=today) == date(2025, 12, 15)


def test_parse_task_date_returns_none_when_no_date():
    """日付無し→None（stale判定不可＝マーク付けず）。"""
    today = date(2026, 6, 28)
    assert parse_task_date("日付のないタスク", today=today) is None


def test_collect_issues_auto_loop候補取得(monkeypatch):
    """fetch_issues.run をモック化し候補リストを返す。"""
    import daily_triage
    fake_tasks = [
        {"title": "Issue #1: バグ", "prompt": "実装せよ", "repo": "/r", "issue": 1}
    ]
    monkeypatch.setattr("fetch_issues.run", lambda: fake_tasks)
    result = daily_triage.collect_issues()
    assert len(result) == 1
    assert "Issue #1: バグ" in result[0]


def test_collect_backlog_marks_stale_tasks(tmp_path):
    """30日超のタスクに ⚠stale マーク付与（鮮度管理・Phase3.1課題3）。

    実装AIが古い前提のタスクで空振りするのを防ぐため、古いタスクを
    LLM判定時に優先度下げる根拠として可視化。
    """
    backlog = tmp_path / "backlog.md"
    backlog.write_text(
        "## P0:\n"
        "- [ ] 新しいタスク — 直近（6/26）\n"
        "- [ ] 古いタスク — 前提腐敗（5/19）\n"
        "## 完了済み\n",
        encoding="utf-8",
    )
    today = date(2026, 6, 28)
    result = collect_backlog(backlog, today=today)
    joined = "\n".join(result)
    # 新しい(6/26=2日前)はマーク無し
    new = [t for t in result if "新しいタスク" in t]
    assert len(new) == 1 and not new[0].startswith("⚠stale")
    # 古い(5/19=40日前)は stale マーク
    old = [t for t in result if "古いタスク" in t]
    assert len(old) == 1 and old[0].startswith("⚠stale")

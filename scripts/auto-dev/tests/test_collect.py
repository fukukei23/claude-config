"""daily_triage 収集ロジックのテスト"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from daily_triage import (
    collect_backlog,
    collect_active_green,
    collect_handoff_latest,
    build_context,
    validate_repo,  # noqa: E402
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
    """🟢セクションの行のみ抽出。ヘッダー/区切り行/別セクションは除外。"""
    result = collect_active_green(FIX / "active-sessions.md")
    joined = "\n".join(result)

    # 🟢セクションのタスク行は含まれる
    assert any("analyze-song features改善" in t for t in result)
    assert any("loop engineering 構築 Phase1" in t for t in result)
    # ヘッダー行・区切り行は除外
    assert not any(t.startswith("| タスク") for t in result)
    assert not any(t.startswith("|---") for t in result)
    # 別セクション（アクティブセッション表）の行は含まれない
    assert "WSL-hoge" not in joined


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

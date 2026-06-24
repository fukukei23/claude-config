"""daily_triage 収集ロジックのテスト"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from daily_triage import collect_backlog, collect_active_green  # まだ無い -> ImportError(RED)

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

"""approve.py の today-tasks.md パース・キュー登録テスト"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from approve import parse_today_tasks, build_task_entry  # noqa: E402


def test_parse_today_tasks_extracts_numbered_candidates():
    """'N. **<タスク>** — <理由>（コスト）' 形式を抽出。"""
    text = """## 今日のタスク候補 (2026-06-25)

1. **Python基礎学習** — キャリア最優先（想定コスト: M）
2. **NexusCore デモ撮影** — ポートフォリオ（想定コスト: L）

---
※ 人間の承認後に実行。
"""
    tasks = parse_today_tasks(text)
    assert len(tasks) == 2
    assert tasks[0] == {
        "n": 1,
        "title": "Python基礎学習",
        "reason": "キャリア最優先",
        "cost": "M",
        "repo": None,
        "manual": False,
    }
    assert tasks[1]["title"] == "NexusCore デモ撮影"


def test_parse_today_tasks_ignores_non_candidate_lines():
    """区切り線や注記は無視。"""
    text = "1. **A** — x（想定コスト: S）\n---\n※ 注記\n"
    tasks = parse_today_tasks(text)
    assert len(tasks) == 1
    assert tasks[0]["title"] == "A"


def test_parse_today_tasks_extracts_repo_marker():
    """'（repo: name）' マーカーを抽出。"""
    text = "1. **NexusCore設定** — 理由（想定コスト: M）（repo: NexusCore）\n"
    tasks = parse_today_tasks(text)
    assert len(tasks) == 1
    assert tasks[0]["repo"] == "NexusCore"
    assert tasks[0]["manual"] is False


def test_parse_today_tasks_extracts_manual_marker():
    """'（手動）' マーカーを抽出。"""
    text = "1. **オールブルー応募** — 理由（想定コスト: S）（手動）\n"
    tasks = parse_today_tasks(text)
    assert len(tasks) == 1
    assert tasks[0]["repo"] is None
    assert tasks[0]["manual"] is True


def test_parse_today_tasks_no_marker_defaults_none():
    """マーカー無し→repo=None・manual=False（後方互換）。"""
    text = "1. **タスク** — 理由（想定コスト: S）\n"
    tasks = parse_today_tasks(text)
    assert len(tasks) == 1
    assert tasks[0]["repo"] is None
    assert tasks[0]["manual"] is False


def test_build_task_entry_creates_pending_item():
    """選択タスクから state.json の pending 要素を生成。"""
    t = {"n": 1, "title": "Python基礎学習", "reason": "キャリア最優先", "cost": "M"}
    entry = build_task_entry(t, repo="/home/yn4416/projects/x")
    assert entry["title"] == "Python基礎学習"
    assert "Python基礎学習" in entry["prompt"]
    assert entry["repo"] == "/home/yn4416/projects/x"
    assert entry["issue"] is None

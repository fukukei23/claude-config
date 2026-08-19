"""fetch_issues.py のテスト。"""
import json
from unittest import mock

import fetch_issues


def test_ensure_state_fields_デフォルト付与():
    state = {"active": False, "pending": []}
    result = fetch_issues.ensure_state_fields(state)
    assert result["mode"] == "manual"
    assert result["max_tasks_per_session"] == 3
    assert result["session_task_count"] == 0


def test_ensure_state_fields_既存値保持():
    state = {"mode": "auto", "max_tasks_per_session": 5, "session_task_count": 2}
    result = fetch_issues.ensure_state_fields(state)
    assert result["mode"] == "auto"
    assert result["max_tasks_per_session"] == 5
    assert result["session_task_count"] == 2


def test_format_issue_pending形式():
    issue = {"number": 42, "title": "バグ修正", "body": "詳細説明"}
    repo_path = "/home/yn4416/projects/NexusCore"
    result = fetch_issues.format_issue(issue, repo_path)
    assert result["title"] == "バグ修正"
    assert result["repo"] == repo_path
    assert result["issue"] == 42
    assert "バグ修正" in result["prompt"]
    assert "詳細説明" in result["prompt"]


def test_filter_duplicate_completed除外():
    new_tasks = [
        {"title": "新規", "repo": "/r", "issue": 1, "prompt": "p"},
        {"title": "完了済", "repo": "/r", "issue": 2, "prompt": "p"},
    ]
    state = {
        "pending": [],
        "current": None,
        "completed": [{"title": "x", "repo": "/r", "issue": 2}],
        "blocked": [],
    }
    result = fetch_issues.filter_duplicates(new_tasks, state)
    assert len(result) == 1
    assert result[0]["issue"] == 1


def test_fetch_from_repo_gh失敗時は空リスト():
    with mock.patch("fetch_issues.subprocess.run") as m:
        m.return_value = mock.Mock(returncode=1, stdout="", stderr="auth error")
        result = fetch_issues.fetch_from_repo(
            "/home/yn4416/projects/NexusCore", "auto-loop"
        )
    assert result == []


def test_fetch_from_repo_正常取得():
    gh_json = json.dumps([{"number": 7, "title": "機能X", "body": "本文"}])
    with mock.patch("fetch_issues.subprocess.run") as m:
        m.return_value = mock.Mock(returncode=0, stdout=gh_json, stderr="")
        result = fetch_issues.fetch_from_repo(
            "/home/yn4416/projects/NexusCore", "auto-loop"
        )
    assert len(result) == 1
    assert result[0]["issue"] == 7
    assert result[0]["repo"] == "/home/yn4416/projects/NexusCore"


# ===== F層: テスト方針宣言（D″案第一段階） =====


def test_extract_issue_test_policy_宣言あり():
    body = "概要\n\nテスト方針: 1"
    result = fetch_issues.extract_issue_test_policy(body)
    assert result == {"choice": 1, "reason": ""}


def test_extract_issue_test_policy_該当なし理由付き():
    body = "テスト方針: 3 該当なし: ドキュメント追記のみのためテスト不要"
    result = fetch_issues.extract_issue_test_policy(body)
    assert result is not None
    assert result["choice"] == 3


def test_extract_issue_test_policy_宣言なしはNone():
    assert fetch_issues.extract_issue_test_policy("本文のみ") is None


def test_extract_issue_test_policy_理由短すぎはNone():
    assert fetch_issues.extract_issue_test_policy("テスト方針: 3 短い") is None


def test_format_issue_test_policy込み():
    issue = {"number": 8, "title": "改修", "body": "テスト方針: 2 既存で網羅"}
    result = fetch_issues.format_issue(issue, "/r")
    assert result["test_policy"] == {"choice": 2, "reason": "既存で網羅"}


def test_filter_missing_test_policy_振り分け():
    tasks = [
        {"issue": 1, "title": "あり", "test_policy": {"choice": 1, "reason": ""}},
        {"issue": 2, "title": "なし", "test_policy": None},
        {"issue": 3, "title": "欄自体なし"},
    ]
    kept, skipped = fetch_issues.filter_missing_test_policy(tasks)
    assert [t["issue"] for t in kept] == [1]
    assert [t["issue"] for t in skipped] == [2, 3]

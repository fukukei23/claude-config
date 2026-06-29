"""fetch_issues.py のテスト。"""
import json
from pathlib import Path
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

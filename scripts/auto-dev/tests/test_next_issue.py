"""next-issue.py 状態遷移ロジックのテスト（純粋関数・外部通信なし）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from next_issue import advance_state, read_verify_result  # noqa: E402


def _initial_state():
    return {
        "active": True,
        "pending": [
            {"title": "task-A", "prompt": "do A", "repo": "/r", "issue": None},
            {"title": "task-B", "prompt": "do B", "repo": "/r", "issue": None},
        ],
        "current": {"title": "prev", "prompt": "do prev", "repo": "/r", "issue": None},
        "completed": [],
        "blocked": [],
    }


def test_advance_ok_moves_current_to_completed_and_pops_next():
    """検証OK: current→completed・pending先頭を次のcurrentに。"""
    state = _initial_state()
    result = advance_state(state, verify_ok=True)
    assert result["completed"] == [{"title": "prev"}]
    assert result["current"]["title"] == "task-A"
    assert result["pending"] == [
        {"title": "task-B", "prompt": "do B", "repo": "/r", "issue": None}
    ]
    assert result["active"] is True


def test_advance_ng_moves_current_to_blocked_and_stops():
    """検証NG: current→blocked・次へ進まず active=False。"""
    state = _initial_state()
    result = advance_state(state, verify_ok=False)
    assert result["blocked"] == [{"title": "prev", "reason": "verify NG"}]
    assert result["current"] is None
    assert result["active"] is False
    assert result["pending"] == [
        {"title": "task-A", "prompt": "do A", "repo": "/r", "issue": None},
        {"title": "task-B", "prompt": "do B", "repo": "/r", "issue": None},
    ]


def test_read_verify_result_ok(tmp_path):
    f = tmp_path / "verify-result.txt"
    f.write_text("OK\nコード品質良好", encoding="utf-8")
    assert read_verify_result(f) is True


def test_read_verify_result_ng(tmp_path):
    f = tmp_path / "verify-result.txt"
    f.write_text("NG\n関数が長すぎる", encoding="utf-8")
    assert read_verify_result(f) is False


def test_read_verify_result_missing_returns_true(tmp_path):
    assert read_verify_result(tmp_path / "nofile.txt") is True


def test_main_ignores_stop_hook_while_running(tmp_path, monkeypatch):
    """running=True の時は next_issue.main は即 return（run-task 実行中の claude
    Stop hook 発火を無視）。state 変更・起動を行わない。"""
    import json
    import next_issue

    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "active": True,
                "running": True,
                "current": {"title": "x", "prompt": "p", "repo": "/r", "issue": None},
                "pending": [],
                "completed": [],
                "blocked": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(next_issue, "STATE", state_file)

    next_issue.main()  # Popen が呼ばれると例外→running ガードで即 return を検証

    after = json.loads(state_file.read_text(encoding="utf-8"))
    assert after["running"] is True
    assert after["current"]["title"] == "x"

"""next-issue.py 状態遷移ロジックのテスト（純粋関数・外部通信なし）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import next_issue  # noqa: E402
from next_issue import advance_state, read_verify_result, _launch_current  # noqa: E402


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
    assert result["completed"] == [{"title": "prev", "repo": "/r"}]
    assert result["current"]["title"] == "task-A"
    assert result["pending"] == [
        {"title": "task-B", "prompt": "do B", "repo": "/r", "issue": None}
    ]
    assert result["active"] is True


def test_advance_ng_moves_current_to_blocked_and_stops():
    """検証NG: current→blocked・次へ進まず active=False。"""
    state = _initial_state()
    result = advance_state(state, verify_ok=False)
    assert result["blocked"] == [{"title": "prev", "reason": "verify NG", "repo": "/r"}]
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


def test_launch_current_uses_task_repo(monkeypatch):
    """_launch_current は current['repo'] を cwd に使う（top-level repo_path に依存しない）。"""
    captured = {}

    class FakePopen:
        def __init__(self, cmd, cwd=None, **kw):
            captured["cmd"] = cmd
            captured["cwd"] = cwd

    monkeypatch.setattr("next_issue.subprocess.Popen", FakePopen)
    current = {"title": "task-X", "repo": "/home/yn4416/projects/NexusCore"}
    _launch_current(current)
    assert captured["cwd"] == "/home/yn4416/projects/NexusCore"
    assert captured["cmd"][0] == "setsid"


def test_should_fetch_auto_枯渇時():
    state = {"mode": "auto", "pending": [], "current": None, "active": True}
    assert next_issue.should_fetch(state) is True


def test_should_fetch_manual_時はFalse():
    state = {"mode": "manual", "pending": [], "current": None, "active": True}
    assert next_issue.should_fetch(state) is False


def test_should_fetch_pending_ありはFalse():
    state = {"mode": "auto", "pending": [{"title": "x"}], "current": None, "active": True}
    assert next_issue.should_fetch(state) is False


def test_max到達で停止():
    state = {
        "mode": "auto",
        "max_tasks_per_session": 3,
        "session_task_count": 3,
        "pending": [{"title": "x"}],
        "current": None,
        "active": True,
    }
    assert next_issue.reached_max(state) is True


def test_max未到達():
    state = {
        "mode": "auto",
        "max_tasks_per_session": 3,
        "session_task_count": 2,
        "pending": [],
        "current": None,
        "active": True,
    }
    assert next_issue.reached_max(state) is False


def test_main_does_not_digest_unstarted_current(tmp_path, monkeypatch):
    """current.started=False（run-task.sh 未起動）なら current を消化しない。

    並行セッションの Stop hook が next_issue.py を発火した際、run-task.sh 起動前の
    current が古い verify-result.txt で事前消化されるのを防ぐ（2026-07-07 バグ対策）。
    run-task.sh が起動して started=True を設定して初めて消化される。
    """
    import json
    import next_issue

    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "active": True,
                "running": False,
                "current": {"title": "x", "prompt": "p", "repo": "/r", "started": False},
                "pending": [],
                "completed": [],
                "blocked": [],
            }
        ),
        encoding="utf-8",
    )
    # verify-result.txt に古い OK が残存していても消化させない
    verify_file = tmp_path / "verify-result.txt"
    verify_file.write_text("OK\n", encoding="utf-8")
    monkeypatch.setattr(next_issue, "STATE", state_file)
    monkeypatch.setattr(next_issue, "VERIFY_RESULT", verify_file)

    next_issue.main()

    after = json.loads(state_file.read_text(encoding="utf-8"))
    assert after["current"] is not None, "未開始 current が事前消化された"
    assert after["current"]["title"] == "x"
    assert after["completed"] == [], "未開始 current が completed に誤移動した"


def test_main_digests_started_current(tmp_path, monkeypatch):
    """current.started=True（run-task.sh 起動済み）なら通常通り消化する（後方互換・正常系）。"""
    import json
    import next_issue

    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "active": True,
                "running": False,
                "current": {
                    "title": "x",
                    "prompt": "p",
                    "repo": "/r",
                    "started": True,
                },
                "pending": [],
                "completed": [],
                "blocked": [],
            }
        ),
        encoding="utf-8",
    )
    verify_file = tmp_path / "verify-result.txt"
    verify_file.write_text("OK\n", encoding="utf-8")
    monkeypatch.setattr(next_issue, "STATE", state_file)
    monkeypatch.setattr(next_issue, "VERIFY_RESULT", verify_file)

    next_issue.main()

    after = json.loads(state_file.read_text(encoding="utf-8"))
    assert after["current"] is None, "開始済み current が消化されなかった"
    assert after["completed"] == [{"title": "x", "repo": "/r"}]


def test_main_clears_stale_running_pid(tmp_path, monkeypatch):
    """running=True だが実プロセス死んでる（存在しないPID）なら stale クリア。

    クラッシュ残留 running フラグの救済（spec セクション2）。
    """
    import json
    import time as _time
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "active": True,
                "running": True,
                "running_pid": 999999,  # 存在しないPID
                "running_create_time": 1000,
                "running_since": _time.time(),
                "current": None,
                "pending": [],
                "completed": [],
                "blocked": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(next_issue, "STATE", state_file)

    next_issue.main()

    after = json.loads(state_file.read_text(encoding="utf-8"))
    assert after["running"] is False, "stale running がクリアされなかった"
    assert after["running_pid"] is None


def test_read_verify_result_tolerates_warning_line(tmp_path):
    """2026-09-01 Q7実発: 1行目のclaude CLI警告行をスキップしOK/NGを正しく判定。"""
    from next_issue import read_verify_result
    ok_file = tmp_path / "ok.txt"
    ok_file.write_text('[claude-code:unrecognized_model] {"model":"x"}\nOK\n\n## 審査結果\n', encoding="utf-8")
    assert read_verify_result(ok_file) is True
    ng_file = tmp_path / "ng.txt"
    ng_file.write_text('[claude-code:unrecognized_model] {"model":"x"}\nNG\n\n## issues\n', encoding="utf-8")
    assert read_verify_result(ng_file) is False
    none_file = tmp_path / "none.txt"
    none_file.write_text('判定行なし\n', encoding="utf-8")
    assert read_verify_result(none_file) is False  # 安全側

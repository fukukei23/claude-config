"""next-issue.py 状態遷移ロジックのテスト（純粋関数・外部通信なし）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from next_issue import advance_state  # noqa: E402


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

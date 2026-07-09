"""state_store.py の atomic + flock + stale + CLI 単体テスト"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import state_store  # noqa: E402


def test_save_is_atomic(tmp_path):
    """save 後 state.json が有効JSON。tmp は残存しない。"""
    state_path = tmp_path / "state.json"
    state_store.save(state_path, {"active": True, "pending": []})
    assert json.loads(state_path.read_text())["active"] is True
    assert not (tmp_path / "state.json.tmp").exists()


def test_load_returns_empty_on_missing(tmp_path):
    """ファイル無しは空dict。"""
    state_path = tmp_path / "state.json"
    assert state_store._load_locked(state_path) == {}


def test_load_recovers_from_corruption(tmp_path):
    """破損JSONはバックアップ退避して空dict。"""
    state_path = tmp_path / "state.json"
    state_path.write_text("{ broken json", encoding="utf-8")
    result = state_store._load_locked(state_path)
    assert result == {}
    backups = list(tmp_path.glob("state.json.corrupted-*"))
    assert len(backups) == 1


def test_update_mutates_atomically(tmp_path):
    """update で read-modify-write が安全に反映される。"""
    state_path = tmp_path / "state.json"
    state_store.save(state_path, {"count": 0})

    def bump(s):
        s["count"] += 1

    state_store.update(state_path, bump)
    assert state_store.read(state_path, lambda s: s["count"]) == 1

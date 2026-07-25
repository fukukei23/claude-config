"""detect_stale_green テスト（L98: stale🟢行 自動検知）

check-stale-sessions.sh の戻り値(JSON配列)を受け取り整形するロジックを検証。
シェルスクリプト呼び出しは本テスト対象外（テストフィクスチャでJSONを直接渡す）。
"""
import sys
import json
import subprocess
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from daily_triage import (  # noqa: E402
    detect_stale_green,
    format_stale_section,
    HEARTBEAT_DEFAULT_THRESHOLD,
    LONG_RUN_DEFAULT_THRESHOLD,
)


# === テスト1: 空リスト → 空文字列 ===
def test_detect_stale_green_empty(tmp_path: Path) -> None:
    """stale無し → 空文字列"""
    active = tmp_path / "00_SYSTEM" / "active-sessions.md"
    active.parent.mkdir(parents=True)
    active.write_text("# empty\n")
    hb = tmp_path / "heartbeat"
    hb.mkdir()
    hd = tmp_path / "handoff"
    hd.mkdir()
    result = detect_stale_green(active, hb, hd)
    assert result == "[]"
    assert format_stale_section(json.loads(result)) == ""


# === テスト2: 閾値デフォルト定数 ===
def test_default_thresholds() -> None:
    """閾値デフォルト値が想定通り(12h/72h)"""
    assert HEARTBEAT_DEFAULT_THRESHOLD == 12
    assert LONG_RUN_DEFAULT_THRESHOLD == 72


# === テスト3: stale JSON を format_stale_section で整形 ===
def test_format_stale_section_basic() -> None:
    """JSON配列→Markdown セクション"""
    data = [
        {"id": "df70", "session": "テスト", "age_hours": 15.2, "threshold_hours": 12, "reason": "heartbeat_timeout", "is_long_run": False},
    ]
    out = format_stale_section(data)
    assert "## ⚠停滞🟢確認" in out
    assert "df70" in out
    assert "15.2h" in out
    assert "12h" in out
    assert "heartbeat_timeout" in out


# === テスト4: [長時間]マーカー付き行の表記 ===
def test_format_stale_section_long_run() -> None:
    """[長時間]マーカー付き行は注釈表示"""
    data = [
        {"id": "abcd", "session": "長時間監視タスク [長時間]", "age_hours": 80.0, "threshold_hours": 72, "reason": "handoff_timeout", "is_long_run": True},
    ]
    out = format_stale_section(data)
    assert "[長時間]" in out
    assert "72h" in out


# === テスト5: no_trace 理由（6d3f型・証跡ゼロ） ===
def test_format_stale_section_no_trace() -> None:
    """証跡ゼロ=no_trace 表示"""
    data = [
        {"id": "6d3f", "session": "強制終了したタブ", "age_hours": None, "threshold_hours": 12, "reason": "no_trace", "is_long_run": False},
    ]
    out = format_stale_section(data)
    assert "6d3f" in out
    assert "no_trace" in out
    assert "不明" in out


# === テスト6: check-stale-sessions.sh が存在しない時 → 空 ===
def test_detect_stale_green_sh_missing(monkeypatch, tmp_path: Path) -> None:
    """check-stale-sessions.sh が存在しないパスでもクラッシュしない"""
    active = tmp_path / "00_SYSTEM" / "active-sessions.md"
    active.parent.mkdir(parents=True)
    active.write_text("# empty\n")
    # detect_stale_green 内部で DEFAULT_SCRIPT 定数を使う想定。存在しないと空。
    result = detect_stale_green(
        active, tmp_path / "hb", tmp_path / "hd",
        script_path=tmp_path / "non-existent.sh",
    )
    assert result == "[]"

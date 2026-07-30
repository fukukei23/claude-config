import json
import sys
from pathlib import Path

HOOKS_DIR = Path.home() / ".claude" / "scripts" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from impact_a.detector import (  # type: ignore
    detect_from_state,
    build_injection_text,
    load_config,
)


def test_load_config_defaults():
    cfg = load_config()
    assert cfg["edit_extensions"] == [".py", ".js", ".ts", ".sh", ".yaml", ".yml", ".json"]
    assert cfg["silent_skip"] is True


def test_build_injection_text_with_match():
    payload = {
        "category": "safety-net-change",
        "matched_keywords": ["BLACKLIST"],
        "files": ["foo.py"],
        "antipattern_id": "AP-001",
        "future_scenario_hint": "除外が正例に被る可能性",
    }
    text = build_injection_text(payload)
    assert "category=safety-net-change" in text
    assert "BLACKLIST" in text
    assert "foo.py" in text
    assert "future_scenario_hint" in text or "想起" in text


def test_build_injection_text_no_match():
    text = build_injection_text(None)
    assert text == ""


def test_detect_from_state_with_match(monkeypatch):
    sample_aps = [{
        "id": "AP-001",
        "category": "safety-net-change",
        "trigger_keywords": ["BLACKLIST"],
        "future_scenario_hint": "test",
        "canonical_source_hint": "test",
    }]
    sample_ops = [{
        "id": "DOP-001",
        "category": "safety-net-change",
        "match_patterns": [r"BLACKLIST\s*="],
    }]

    diff = """--- a/foo.py
+++ b/foo.py
@@ -1,1 +1,2 @@
 x
+BLACKLIST = ["a"]
"""
    result = detect_from_state(
        diff=diff,
        antipatterns=sample_aps,
        dangerous_ops=sample_ops,
    )
    assert result["matched"] is True
    assert result["category"] == "safety-net-change"
    assert "BLACKLIST" in result["matched_keywords"]
    assert result["files"] == ["foo.py"]
    assert result["dangerous_op_match"] == "DOP-001"


def test_detect_from_state_no_match():
    diff = """--- a/foo.py
+++ b/foo.py
@@ -1,1 +1,2 @@
 x
+print("hello")
"""
    result = detect_from_state(
        diff=diff,
        antipatterns=[{
            "id": "AP-001",
            "category": "safety-net-change",
            "trigger_keywords": ["BLACKLIST"],
            "future_scenario_hint": "test",
            "canonical_source_hint": "test",
        }],
        dangerous_ops=[],
    )
    assert result["matched"] is False
import sys
from pathlib import Path

HOOKS_DIR = Path.home() / ".claude" / "scripts" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from impact_a.git_diff import (  # type: ignore
    parse_unified_zero_diff,
    match_keywords,
    normalize_category,
    VALID_CATEGORIES,
)


SAMPLE_DIFF = """diff --git a/foo.py b/foo.py
index 1234567..abcdef0 100644
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 def hello():
     pass
+BLACKLIST = ["foo", "bar"]
+threshold = 0.5
"""


def test_parse_unified_zero_diff_addition_only():
    adds = parse_unified_zero_diff(SAMPLE_DIFF)
    assert len(adds) == 2
    assert any("BLACKLIST" in line for line in adds)
    assert any("threshold" in line for line in adds)


def test_parse_unified_zero_diff_only_additions():
    diff = """--- a/foo.py
+++ b/foo.py
@@ -1,1 +1,2 @@
 unchanged
+added
"""
    adds = parse_unified_zero_diff(diff)
    assert adds == ["added"]


def test_parse_unified_zero_diff_empty():
    assert parse_unified_zero_diff("") == []


def test_match_keywords_case_insensitive():
    lines = ["BLACKLIST = []", "blacklist.add", "Blocklist check"]
    matches = match_keywords(lines, ["BLACKLIST", "blocklist"])
    assert len(matches) == 3
    assert "BLACKLIST" in matches


def test_match_keywords_no_hit():
    lines = ["print('hello')"]
    matches = match_keywords(lines, ["BLACKLIST"])
    assert matches == []


def test_normalize_category_valid():
    assert normalize_category("safety-net-change") == "safety-net-change"
    assert normalize_category("data-mutation") == "data-mutation"


def test_normalize_category_invalid_returns_none():
    assert normalize_category("unknown-category") is None


def test_valid_categories_complete():
    expected = {
        "safety-net-change",
        "data-mutation",
        "schema-change",
        "secret-handling",
        "permission-scope",
        "build-config-change",
    }
    assert VALID_CATEGORIES == expected

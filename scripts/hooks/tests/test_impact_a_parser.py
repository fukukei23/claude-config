import sys
from pathlib import Path

# モジュールインポート: ~/scripts/hooks/impact_a/parser.py を直接ロード
HOOKS_DIR = Path.home() / ".claude" / "scripts" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from impact_a.parser import (  # type: ignore
    parse_antipatterns_md,
    parse_dangerous_ops_yaml,
    extract_yaml_block,
)


def test_extract_yaml_block_normal():
    text = """# header

<!-- impact-mode: antipatterns:v1 -->
```yaml
foo: bar
```
<!-- /impact-mode -->

# footer
"""
    yaml_text = extract_yaml_block(text, "impact-mode: antipatterns:v1")
    assert "foo: bar" in yaml_text


def test_extract_yaml_block_missing():
    text = "# no markers\n"
    yaml_text = extract_yaml_block(text, "impact-mode: antipatterns:v1")
    assert yaml_text == ""


def test_parse_antipatterns_md_minimal():
    fixture = """<!-- impact-mode: antipatterns:v1 -->
```yaml
antipatterns:
  - id: AP-001
    category: safety-net-change
    trigger_keywords: [BLACKLIST, "exclude"]
    severity_hint: high
    future_scenario_hint: "test"
    canonical_source_hint: "test"
```
<!-- /impact-mode -->
"""
    aps = parse_antipatterns_md(fixture)
    assert len(aps) == 1
    assert aps[0]["id"] == "AP-001"
    assert aps[0]["category"] == "safety-net-change"
    assert "BLACKLIST" in aps[0]["trigger_keywords"]


def test_parse_dangerous_ops_yaml_normal():
    yaml_text = """dangerous_ops:
  - id: DOP-001
    name: BLACKLIST/除外追加
    category: safety-net-change
    match_patterns:
      - "BLACKLIST\\\\s*="
"""
    ops = parse_dangerous_ops_yaml(yaml_text)
    assert len(ops) == 1
    assert ops[0]["id"] == "DOP-001"
    assert ops[0]["category"] == "safety-net-change"


def test_parse_dangerous_ops_yaml_empty():
    yaml_text = "dangerous_ops: []\n"
    ops = parse_dangerous_ops_yaml(yaml_text)
    assert ops == []
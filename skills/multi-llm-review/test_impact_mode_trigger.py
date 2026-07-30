"""impactモード トリガー語テスト: SKILL.mdがトリガーワードを含むか"""
from pathlib import Path

SKILL = Path.home() / ".claude" / "skills" / "multi-llm-review" / "SKILL.md"
text = SKILL.read_text()

REQUIRED = ["impact", "未来シナリオ", "影響範囲", "層a", "層b", "ペルソナ分割"]


def test_trigger_section_exists():
    assert "## impact モード" in text or "impactモード" in text


def test_required_keywords_present():
    for kw in REQUIRED:
        assert kw in text, f"missing: {kw}"


def test_layer_a_section():
    assert "層a" in text
    assert "trigger_keywords" in text or "trigger" in text


def test_layer_b_section():
    assert "層b" in text
    assert "ペルソナ" in text


def test_dangerous_ops_section():
    assert "静的危険操作" in text or "dangerous-ops" in text

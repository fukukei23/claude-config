"""test_frontmatter_lint.py — frontmatter_lint の TDD（spec §6.2）"""
from pathlib import Path
import sys

# claude-config repo root をパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.obsidian.frontmatter_lint import parse_frontmatter, lint_file


ALLOWED = {
    "moc": {"files": ["00_SYSTEM/全体マップ_MOC.md"], "allowed_keys": []},
    "index": {"pattern": "01_DECISIONS/.*/_INDEX\\.md$", "allowed_keys": ["project", "status", "last_verified", "approved_themes", "themes"]},
}


def test_parse_frontmatter_present():
    assert parse_frontmatter("---\nproject: x\n---\n# Title") == {"project": "x"}


def test_parse_frontmatter_absent():
    assert parse_frontmatter("# Title only") is None


def test_moc_allows_empty_frontmatter(tmp_path):
    moc = tmp_path / "00_SYSTEM" / "全体マップ_MOC.md"
    moc.parent.mkdir(parents=True)
    moc.write_text("# 全体マップ\n", encoding="utf-8")
    assert lint_file(moc, tmp_path, ALLOWED) == []


def test_moc_blocks_any_key(tmp_path):
    moc = tmp_path / "00_SYSTEM" / "全体マップ_MOC.md"
    moc.parent.mkdir(parents=True)
    moc.write_text("---\ncache_hit: true\n---\n# MOC", encoding="utf-8")
    violations = lint_file(moc, tmp_path, ALLOWED)
    assert any("cache_hit" in v for v in violations)


def test_index_allows_approved_keys(tmp_path):
    idx = tmp_path / "01_DECISIONS" / "x" / "_INDEX.md"
    idx.parent.mkdir(parents=True)
    idx.write_text("---\nproject: x\nstatus: active\n---\n# idx", encoding="utf-8")
    assert lint_file(idx, tmp_path, ALLOWED) == []


def test_index_blocks_created_at(tmp_path):
    idx = tmp_path / "01_DECISIONS" / "x" / "_INDEX.md"
    idx.parent.mkdir(parents=True)
    idx.write_text("---\nproject: x\ncreated_at: 2026-07-28\n---\n# idx", encoding="utf-8")
    violations = lint_file(idx, tmp_path, ALLOWED)
    assert any("created_at" in v for v in violations)


def test_non_target_file_skipped(tmp_path):
    other = tmp_path / "README.md"
    other.write_text("---\ncreated_at: x\n---\n# README", encoding="utf-8")
    assert lint_file(other, tmp_path, ALLOWED) == []

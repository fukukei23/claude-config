"""SSOT体系化 P3-B: frontmatter付与・manifest生成オーケストレータのテスト."""
from pathlib import Path

from scripts.obsidian.dir_manifests import (
    ensure_index_frontmatter,
)


def test_ensure_index_frontmatter_inserts_when_absent(tmp_path: Path) -> None:
    idx = tmp_path / "_INDEX.md"
    idx.write_text("# Title\n\n本文\n", encoding="utf-8")
    changed = ensure_index_frontmatter(idx, project="ai-music", date="2026-07-24")
    text = idx.read_text(encoding="utf-8")
    assert changed is True
    assert text.startswith("---\n")
    assert "project: ai-music" in text
    assert "status: active" in text
    assert "last_verified: 2026-07-24" in text
    assert text.endswith("# Title\n\n本文\n")


def test_ensure_index_frontmatter_idempotent(tmp_path: Path) -> None:
    idx = tmp_path / "_INDEX.md"
    idx.write_text(
        "---\nproject: ai-music\nstatus: active\nlast_verified: 2026-07-01\n---\n# T\n",
        encoding="utf-8",
    )
    changed1 = ensure_index_frontmatter(idx, project="ai-music", date="2026-07-24")
    changed2 = ensure_index_frontmatter(idx, project="ai-music", date="2026-07-24")
    assert changed1 is True
    assert changed2 is False
    assert "last_verified: 2026-07-24" in idx.read_text(encoding="utf-8")


def test_ensure_index_frontmatter_keeps_existing_status(tmp_path: Path) -> None:
    idx = tmp_path / "_INDEX.md"
    idx.write_text(
        "---\nproject: x\nstatus: archived\nlast_verified: 2026-07-01\n---\n# T\n",
        encoding="utf-8",
    )
    ensure_index_frontmatter(idx, project="x", date="2026-07-24", status="active")
    assert "status: archived" in idx.read_text(encoding="utf-8")

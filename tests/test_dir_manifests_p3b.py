"""SSOT体系化 P3-B: frontmatter付与・manifest生成オーケストレータのテスト."""
import json
from pathlib import Path

from scripts.obsidian.dir_manifests import (
    ensure_index_frontmatter,
    generate_manifest_for_project,
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


def test_generate_manifest_for_project_flat_ssot_only(tmp_path, monkeypatch) -> None:
    ssot = tmp_path
    proj_dir = ssot / "01_DECISIONS" / "career"
    proj_dir.mkdir(parents=True)
    idx = proj_dir / "_INDEX.md"
    idx.write_text("# career\n", encoding="utf-8")
    monkeypatch.setattr(
        "scripts.obsidian.dir_manifests.list_project_dirs_in_ssot",
        lambda root, p: [],
    )
    result = generate_manifest_for_project(
        ssot_root=ssot, project="career", repo_path=None, date="2026-07-24"
    )
    assert result["frontmatter_changed"] is True
    assert result["manifest_created"] is True
    assert result["pending_count"] == 0
    m = json.loads((proj_dir / ".dir-manifest.json").read_text(encoding="utf-8"))
    assert m["project"] == "career"
    assert m["has_external_repo"] is False
    assert m["directories"] == []
    assert m["last_verified"] == "2026-07-24"


def test_generate_manifest_for_project_idempotent_second_run(tmp_path, monkeypatch) -> None:
    ssot = tmp_path
    proj_dir = ssot / "01_DECISIONS" / "career"
    proj_dir.mkdir(parents=True)
    (proj_dir / "_INDEX.md").write_text("# career\n", encoding="utf-8")
    monkeypatch.setattr(
        "scripts.obsidian.dir_manifests.list_project_dirs_in_ssot",
        lambda root, p: [],
    )
    generate_manifest_for_project(
        ssot_root=ssot, project="career", repo_path=None, date="2026-07-24"
    )
    result2 = generate_manifest_for_project(
        ssot_root=ssot, project="career", repo_path=None, date="2026-07-24"
    )
    assert result2["frontmatter_changed"] is False
    assert result2["manifest_created"] is False

"""SSOT体系化 P3-B: frontmatter付与・manifest生成オーケストレータのテスト."""
import json
from pathlib import Path

from scripts.obsidian.dir_manifests import (
    discover_manifest_projects,
    ensure_index_frontmatter,
    generate_manifest_for_project,
)


def test_discover_manifest_projects_sorted_manifest_only(tmp_path: Path) -> None:
    """manifest持つプロジェクトを昇順返す・manifest無しは除外."""
    for p in ["career", "zenn", "ai-music"]:
        d = tmp_path / "01_DECISIONS" / p
        d.mkdir(parents=True)
        (d / ".dir-manifest.json").write_text("{}", encoding="utf-8")
    nofm = tmp_path / "01_DECISIONS" / "nomanifest"
    nofm.mkdir(parents=True)  # manifest無し
    result = discover_manifest_projects(tmp_path)
    assert result == ["ai-music", "career", "zenn"]


def test_discover_manifest_projects_empty_when_no_decisions(tmp_path: Path) -> None:
    """01_DECISIONS 無しは空リスト."""
    assert discover_manifest_projects(tmp_path) == []


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


def test_ensure_index_frontmatter_preserves_unknown_keys(tmp_path: Path) -> None:
    """managed3キー以外のfrontmatter(approved_themes等)を保持する(Phase1・§4.4前提)."""
    idx = tmp_path / "_INDEX.md"
    idx.write_text(
        "---\nproject: ai-music\nstatus: active\nlast_verified: 2026-07-01\n"
        "approved_themes: [hiphop, cyber-wa]\n---\n# T\n",
        encoding="utf-8",
    )
    ensure_index_frontmatter(idx, project="ai-music", date="2026-07-24")
    text = idx.read_text(encoding="utf-8")
    assert "approved_themes: [hiphop, cyber-wa]" in text
    assert "last_verified: 2026-07-24" in text
    assert text.count("project: ai-music") == 1  # managed3キーが重複出力されない


def test_ensure_index_frontmatter_idempotent_with_unknown_keys(tmp_path: Path) -> None:
    """未知キーあり状態でも2回目投入は差分無し(False)・順序保持で同一文字列."""
    idx = tmp_path / "_INDEX.md"
    idx.write_text(
        "---\nproject: ai-music\nstatus: active\nlast_verified: 2026-07-24\n"
        "approved_themes: [hiphop]\n---\n# T\n",
        encoding="utf-8",
    )
    changed1 = ensure_index_frontmatter(idx, project="ai-music", date="2026-07-24")
    changed2 = ensure_index_frontmatter(idx, project="ai-music", date="2026-07-24")
    assert changed1 is False  # 初回から同一(last_verified既に2026-07-24)
    assert changed2 is False

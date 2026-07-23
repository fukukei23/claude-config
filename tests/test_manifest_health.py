"""manifest_health.py の単体テスト（SSOT体系化 P3-A: drift 3軸検知）."""
import json
from pathlib import Path

from scripts.obsidian.manifest_health import (
    detect_structural_drift,
)


# --- detect_structural_drift ---


def test_structural_drift_external_repo_added_and_removed(tmp_path, monkeypatch):
    """外部リポ: 新規dir(added)・削除dir(removed)の双方向検知."""
    manifest = {
        "project": "NexusCore",
        "repo_path": str(tmp_path / "repo"),
        "has_external_repo": True,
        "directories": [
            {"path": "src", "meaning": "m", "meaning_hash": "h", "pending_approval": False},
            {"path": "old_dir", "meaning": "m", "meaning_hash": "h", "pending_approval": False},
        ],
    }
    # 実dir: src(既存) + new_dir(新規) / old_dirは削除済
    monkeypatch.setattr(
        "scripts.obsidian.manifest_health.list_dirs_via_git",
        lambda repo_path: ["src", "new_dir"],
    )
    result = detect_structural_drift(manifest, Path(tmp_path / "repo"), tmp_path)
    assert result["added"] == ["new_dir"]
    assert result["removed"] == ["old_dir"]


def test_structural_drift_ssot_internal_project(tmp_path, monkeypatch):
    """SSOT内部プロジェクト: list_project_dirs_in_ssot で列挙."""
    manifest = {
        "project": "claude-code",
        "repo_path": "",
        "has_external_repo": False,
        "directories": [
            {"path": "参考資料", "meaning": "m", "meaning_hash": "h", "pending_approval": False},
        ],
    }
    monkeypatch.setattr(
        "scripts.obsidian.manifest_health.list_project_dirs_in_ssot",
        lambda ssot_root, project: ["参考資料", "新規資料"],
    )
    result = detect_structural_drift(manifest, Path(""), tmp_path)
    assert result["added"] == ["新規資料"]
    assert result["removed"] == []


def test_structural_drift_no_change(tmp_path, monkeypatch):
    """差分なし: added/removed ともに空."""
    manifest = {
        "project": "x",
        "has_external_repo": True,
        "directories": [
            {"path": "src", "meaning": "m", "meaning_hash": "h", "pending_approval": False},
        ],
    }
    monkeypatch.setattr(
        "scripts.obsidian.manifest_health.list_dirs_via_git",
        lambda repo_path: ["src"],
    )
    result = detect_structural_drift(manifest, tmp_path / "repo", tmp_path)
    assert result == {"added": [], "removed": []}


def test_structural_drift_deep_path_normalized_to_toplevel(tmp_path, monkeypatch):
    """深パス(src/handlers)は top-level(src)に集約して突合（偽検知防止）."""
    manifest = {
        "project": "x",
        "has_external_repo": True,
        "directories": [
            {"path": "src", "meaning": "m", "meaning_hash": "h", "pending_approval": False},
        ],
    }
    # git ls-tree は再帰フルパスを返すが top-level 集約で src のみ
    monkeypatch.setattr(
        "scripts.obsidian.manifest_health.list_dirs_via_git",
        lambda repo_path: ["src/handlers", "src/services"],
    )
    result = detect_structural_drift(manifest, tmp_path / "repo", tmp_path)
    assert result == {"added": [], "removed": []}


def test_structural_drift_empty_repo_all_removed(tmp_path, monkeypatch):
    """空リポジトリ(CalledProcessError→[]): recorded は全て removed."""
    manifest = {
        "project": "x",
        "has_external_repo": True,
        "directories": [
            {"path": "src", "meaning": "m", "meaning_hash": "h", "pending_approval": False},
        ],
    }
    monkeypatch.setattr(
        "scripts.obsidian.manifest_health.list_dirs_via_git",
        lambda repo_path: [],
    )
    result = detect_structural_drift(manifest, tmp_path / "repo", tmp_path)
    assert result["added"] == []
    assert result["removed"] == ["src"]

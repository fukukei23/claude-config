"""manifest_health.py の単体テスト（SSOT体系化 P3-A: drift 3軸検知）."""
import json
from pathlib import Path

from scripts.obsidian.manifest_health import (
    check_project_health,
    detect_structural_drift,
    is_freshness_stale,
    is_full_sync_stale,
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


# --- is_freshness_stale / is_full_sync_stale ---


def test_freshness_stale_over_threshold():
    """last_verified 90日超 → stale."""
    m = {"last_verified": "2026-04-23"}  # 91日前(基準2026-07-23)
    assert is_freshness_stale(m, "2026-07-23") is True


def test_freshness_not_stale_at_boundary():
    """last_verified ちょうど90日 → staleでない（>90で判定）."""
    m = {"last_verified": "2026-04-24"}  # 90日前
    assert is_freshness_stale(m, "2026-07-23") is False


def test_freshness_stale_when_missing():
    """last_verified 未設定 → stale."""
    assert is_freshness_stale({}, "2026-07-23") is True


def test_full_sync_stale_over_threshold():
    """last_full_sync 30日超 → stale."""
    m = {"last_full_sync": "2026-06-22"}  # 31日前
    assert is_full_sync_stale(m, "2026-07-23") is True


def test_full_sync_not_stale_at_boundary():
    """last_full_sync ちょうど30日 → staleでない."""
    m = {"last_full_sync": "2026-06-23"}  # 30日前
    assert is_full_sync_stale(m, "2026-07-23") is False


def test_full_sync_stale_when_none():
    """last_full_sync None/未設定 → stale."""
    assert is_full_sync_stale({}, "2026-07-23") is True
    assert is_full_sync_stale({"last_full_sync": None}, "2026-07-23") is True


# --- check_project_health 統合 ---


def _write_manifest(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_check_project_health_healthy(tmp_path, monkeypatch):
    """異常なし: drift無し・鮮度OK・full_sync OK → has_issues False."""
    manifest_path = tmp_path / "proj" / ".dir-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    _write_manifest(manifest_path, {
        "project": "x", "has_external_repo": True,
        "last_verified": "2026-07-22", "last_full_sync": "2026-07-22",
        "directories": [{"path": "src", "meaning": "m", "meaning_hash": "h", "pending_approval": False}],
    })
    monkeypatch.setattr(
        "scripts.obsidian.manifest_health.list_dirs_via_git",
        lambda repo_path: ["src"],
    )
    r = check_project_health(manifest_path, tmp_path / "repo", tmp_path, "2026-07-23")
    assert r.added == [] and r.removed == []
    assert r.freshness_stale is False
    assert r.full_sync_stale is False
    assert r.has_issues is False


def test_check_project_health_all_issues(tmp_path, monkeypatch):
    """3軸全異常: drift有り・freshness stale・full_sync None."""
    manifest_path = tmp_path / "proj" / ".dir-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    _write_manifest(manifest_path, {
        "project": "x", "has_external_repo": True,
        "last_verified": "2026-04-01",  # かなり古い
        "last_full_sync": None,
        "directories": [{"path": "gone", "meaning": "m", "meaning_hash": "h", "pending_approval": False}],
    })
    monkeypatch.setattr(
        "scripts.obsidian.manifest_health.list_dirs_via_git",
        lambda repo_path: ["new"],
    )
    r = check_project_health(manifest_path, tmp_path / "repo", tmp_path, "2026-07-23")
    assert r.added == ["new"]
    assert r.removed == ["gone"]
    assert r.freshness_stale is True
    assert r.full_sync_stale is True
    assert r.has_issues is True


def test_check_project_health_reads_status(tmp_path):
    """check_project_health は manifest の status を HealthResult に含める."""
    import json
    from scripts.obsidian.manifest_health import check_project_health
    mpath = tmp_path / ".dir-manifest.json"
    mpath.write_text(
        json.dumps({"project": "p", "status": "paused", "directories": [],
                    "last_verified": "2026-07-24", "last_full_sync": "2026-07-24"}),
        encoding="utf-8",
    )
    result = check_project_health(mpath, tmp_path, tmp_path, "2026-07-24")
    assert result.status == "paused"


def test_check_project_health_status_defaults_active(tmp_path):
    """status 未設定 manifest は 'active' と解釈する（後方互換・バックフィル前）."""
    import json
    from scripts.obsidian.manifest_health import check_project_health
    mpath = tmp_path / ".dir-manifest.json"
    mpath.write_text(
        json.dumps({"project": "p", "directories": [],
                    "last_verified": "2026-07-24", "last_full_sync": "2026-07-24"}),
        encoding="utf-8",
    )
    result = check_project_health(mpath, tmp_path, tmp_path, "2026-07-24")
    assert result.status == "active"

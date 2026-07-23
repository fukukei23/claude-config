import json

from scripts.obsidian.ssot_daily_batch import (
    BatchResult,
    _check_health_all,
    run_batch,
)
from scripts.obsidian.manifest_health import HealthResult


def test_run_batch_skips_pending_when_index_update_fails(tmp_path, monkeypatch):
    """spec: INDEX更新失敗→pending再生成スキップ（整合性優先）."""
    ssot_root = tmp_path
    proj_dir = ssot_root / "01_DECISIONS" / "reserve-optimizer"
    proj_dir.mkdir(parents=True)
    manifest = proj_dir / ".dir-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "project": "reserve-optimizer",
                "repo_path": str(tmp_path / "repo"),
                "has_external_repo": True,
                "last_verified": "2026-07-01",
                "directories": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (tmp_path / "repo").mkdir()

    steps = {"last_verified": False, "index": False, "pending": False}

    def fail_index(*args, **kwargs):
        steps["index"] = True
        raise RuntimeError("INDEX update failed")

    monkeypatch.setattr(
        "scripts.obsidian.ssot_daily_batch._update_last_verified_all",
        lambda *args: steps.__setitem__("last_verified", True),
    )
    monkeypatch.setattr(
        "scripts.obsidian.ssot_daily_batch._update_index", fail_index
    )
    monkeypatch.setattr(
        "scripts.obsidian.ssot_daily_batch._regenerate_all_pending",
        lambda *args: steps.__setitem__("pending", True),
    )

    result = run_batch(
        ssot_root, today="2026-07-22", projects=["reserve-optimizer"]
    )
    assert steps["last_verified"] is True
    assert steps["index"] is True
    assert steps["pending"] is False
    assert result.index_ok is False
    assert result.pending_skipped is True


def test_run_batch_dry_run_makes_no_changes(tmp_path, monkeypatch):
    ssot_root = tmp_path
    proj_dir = ssot_root / "01_DECISIONS" / "reserve-optimizer"
    proj_dir.mkdir(parents=True)
    manifest = proj_dir / ".dir-manifest.json"
    original = json.dumps(
        {
            "project": "reserve-optimizer",
            "has_external_repo": False,
            "last_verified": "2026-07-01",
            "directories": [],
        },
        ensure_ascii=False,
        indent=2,
    )
    manifest.write_text(original, encoding="utf-8")
    monkeypatch.setattr(
        "scripts.obsidian.ssot_daily_batch._update_last_verified_all",
        lambda *args: None,
    )
    monkeypatch.setattr(
        "scripts.obsidian.ssot_daily_batch._update_index", lambda *args: None
    )
    monkeypatch.setattr(
        "scripts.obsidian.ssot_daily_batch._regenerate_all_pending",
        lambda *args: None,
    )

    run_batch(
        ssot_root,
        today="2026-07-22",
        projects=["reserve-optimizer"],
        dry_run=True,
    )
    assert manifest.read_text(encoding="utf-8") == original


# --- P3-A: _check_health_all + summary ---


def test_check_health_all_aggregates_three_axes(tmp_path, monkeypatch):
    """3軸を per-project 集計: 片方はhealthy・片方は全異常."""
    for proj in ["ok-proj", "bad-proj"]:
        d = tmp_path / "01_DECISIONS" / proj
        d.mkdir(parents=True)
        (d / ".dir-manifest.json").write_text(
            json.dumps({"project": proj, "has_external_repo": False}, ensure_ascii=False),
            encoding="utf-8",
        )

    healthy = HealthResult(project="ok-proj")
    bad = HealthResult(
        project="bad-proj", added=["new"], removed=["gone"],
        freshness_stale=True, full_sync_stale=True,
    )
    calls = {"ok-proj": healthy, "bad-proj": bad}

    def fake_check(manifest_path, repo_path, ssot_root, today):
        name = manifest_path.parent.name
        return calls[name]

    monkeypatch.setattr(
        "scripts.obsidian.ssot_daily_batch.check_project_health", fake_check
    )
    result = BatchResult()
    _check_health_all(tmp_path, ["ok-proj", "bad-proj"], "2026-07-23", False, result)
    assert result.structural_drift == {"bad-proj": {"added": ["new"], "removed": ["gone"]}}
    assert result.freshness_stale == ["bad-proj"]
    assert result.full_sync_stale == ["bad-proj"]


def test_summary_health_ok_when_no_issues():
    """異常なし → summary に health:OK."""
    r = BatchResult()
    r.index_ok = True
    assert "health:OK" in r.summary()


def test_summary_health_reports_issues():
    """異常あり → drift/fresh/sync 件数を報告."""
    r = BatchResult()
    r.index_ok = True
    r.structural_drift = {"p": {"added": ["a", "b"], "removed": ["c"]}}
    r.freshness_stale = ["p"]
    r.full_sync_stale = ["p", "q"]
    s = r.summary()
    assert "drift+2/-1" in s
    assert "fresh1" in s
    assert "sync2" in s


# --- P3-A: フル同期成功時 last_full_sync 更新 ---


def _make_manifest(path, directories, extra=None):
    data = {"project": path.parent.name, "has_external_repo": False,
            "directories": directories}
    if extra:
        data.update(extra)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_mark_full_sync_updates_healthy_project(tmp_path):
    """drift無し AND pending無し → last_full_sync 更新."""
    from scripts.obsidian.ssot_daily_batch import _mark_full_sync
    proj = tmp_path / "01_DECISIONS" / "p"
    proj.mkdir(parents=True)
    m = proj / ".dir-manifest.json"
    _make_manifest(m, [{"path": "src", "meaning": "m", "meaning_hash": "h",
                        "pending_approval": False}])
    result = BatchResult()  # structural_drift 空 = drift無し
    _mark_full_sync(tmp_path, ["p"], "2026-07-23", False, result)
    data = json.loads(m.read_text(encoding="utf-8"))
    assert data["last_full_sync"] == "2026-07-23"


def test_mark_full_sync_skips_project_with_drift(tmp_path):
    """drift有り → last_full_sync 更新しない."""
    from scripts.obsidian.ssot_daily_batch import _mark_full_sync
    proj = tmp_path / "01_DECISIONS" / "p"
    proj.mkdir(parents=True)
    m = proj / ".dir-manifest.json"
    _make_manifest(m, [{"path": "src", "meaning": "m", "meaning_hash": "h",
                        "pending_approval": False}])
    result = BatchResult()
    result.structural_drift = {"p": {"added": ["new"], "removed": []}}
    _mark_full_sync(tmp_path, ["p"], "2026-07-23", False, result)
    data = json.loads(m.read_text(encoding="utf-8"))
    assert "last_full_sync" not in data


def test_mark_full_sync_skips_project_with_pending(tmp_path):
    """pending_approval有り → last_full_sync 更新しない."""
    from scripts.obsidian.ssot_daily_batch import _mark_full_sync
    proj = tmp_path / "01_DECISIONS" / "p"
    proj.mkdir(parents=True)
    m = proj / ".dir-manifest.json"
    _make_manifest(m, [{"path": "src", "meaning": "m", "meaning_hash": "h",
                        "pending_approval": True}])
    result = BatchResult()
    _mark_full_sync(tmp_path, ["p"], "2026-07-23", False, result)
    data = json.loads(m.read_text(encoding="utf-8"))
    assert "last_full_sync" not in data


def test_mark_full_sync_noop_in_dry_run(tmp_path):
    """dry_run → 更新しない."""
    from scripts.obsidian.ssot_daily_batch import _mark_full_sync
    proj = tmp_path / "01_DECISIONS" / "p"
    proj.mkdir(parents=True)
    m = proj / ".dir-manifest.json"
    _make_manifest(m, [{"path": "src", "meaning": "m", "meaning_hash": "h",
                        "pending_approval": False}])
    _mark_full_sync(tmp_path, ["p"], "2026-07-23", True, BatchResult())
    data = json.loads(m.read_text(encoding="utf-8"))
    assert "last_full_sync" not in data

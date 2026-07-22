import json

from scripts.obsidian.ssot_daily_batch import BatchResult, run_batch


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

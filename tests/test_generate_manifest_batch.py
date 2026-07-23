"""SSOT体系化 P3-B: バッチCLI のテスト.

注: monkeypatch はプロセス内のモジュール属性のみ書き換えるため、CLI は
インプロセスで main() を直接起動する（subprocess だとパッチが伝播しない）。
"""
import sys
from pathlib import Path

from scripts.obsidian import generate_manifest_batch
from scripts.obsidian.generate_manifest_batch import main


def _write_idx(proj_dir: Path, name: str) -> None:
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "_INDEX.md").write_text(f"# {name}\n", encoding="utf-8")


def _run_cli(ssot: Path, monkeypatch, *args: str) -> int:
    """sys.argv を差し替えて main() をインプロセス実行."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_manifest_batch", "--ssot-root", str(ssot), *args],
    )
    return main()


def test_batch_dry_run_creates_nothing(tmp_path: Path, monkeypatch) -> None:
    ssot = tmp_path
    _write_idx(ssot / "01_DECISIONS" / "career", "career")
    monkeypatch.setattr(
        "scripts.obsidian.dir_manifests.list_project_dirs_in_ssot",
        lambda root, p: [],
    )
    rc = _run_cli(ssot, monkeypatch, "--projects", "career", "--date", "2026-07-24", "--dry-run")
    assert rc == 0
    assert not (ssot / "01_DECISIONS" / "career" / ".dir-manifest.json").exists()


def test_batch_creates_manifests_and_continues_on_error(tmp_path, monkeypatch) -> None:
    ssot = tmp_path
    _write_idx(ssot / "01_DECISIONS" / "career", "career")
    _write_idx(ssot / "01_DECISIONS" / "infra", "infra")
    calls = {"career": 0, "infra": 0}

    def fake_gen(ssot_root, project, repo_path, date, status="active"):
        calls[project] += 1
        if project == "infra":
            raise RuntimeError("simulated API error")
        from scripts.obsidian.dir_manifests import generate_manifest_for_project as real
        return real(ssot_root=ssot_root, project=project, repo_path=repo_path, date=date, status=status)

    monkeypatch.setattr(
        generate_manifest_batch,
        "generate_manifest_for_project",
        fake_gen,
    )
    monkeypatch.setattr(
        "scripts.obsidian.dir_manifests.list_project_dirs_in_ssot",
        lambda root, p: [],
    )
    rc = _run_cli(ssot, monkeypatch, "--projects", "career,infra", "--date", "2026-07-24")
    assert rc == 0
    assert calls == {"career": 1, "infra": 1}
    assert (ssot / "01_DECISIONS" / "career" / ".dir-manifest.json").exists()
    assert not (ssot / "01_DECISIONS" / "infra" / ".dir-manifest.json").exists()

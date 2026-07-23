"""SSOT体系化 P2: 日次バッチ orchestrator（ステップ依存ルール・dry-run・結果集計）."""

import argparse
import datetime
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from scripts.obsidian.dir_manifests import (
    MeaningGenError,
    regenerate_pending,
    update_last_full_sync,
    update_last_verified,
)
from scripts.obsidian.manifest_health import check_project_health


@dataclass
class BatchResult:
    """バッチ実行結果（Discord通知・ログ用）."""

    last_verified_projects: list[str] = field(default_factory=list)
    index_ok: bool = False
    index_error: str = ""
    pending_added: dict[str, list[str]] = field(default_factory=dict)
    pending_skipped: bool = False
    pending_errors: list[str] = field(default_factory=list)
    dry_run: bool = False
    # P3-A: ヘルス検知（drift 3軸）
    structural_drift: dict[str, dict] = field(default_factory=dict)
    freshness_stale: list[str] = field(default_factory=list)
    full_sync_stale: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """バッチ結果を通知用の1行文字列に整形する."""
        flags = []
        flags.append(
            "INDEX:OK"
            if self.index_ok
            else f"INDEX:FAIL({self.index_error[:40]})"
        )
        flags.append(f"last_verified:{len(self.last_verified_projects)}件")
        if self.pending_skipped:
            flags.append("pending:SKIP(INDEX失敗)")
        else:
            total = sum(len(value) for value in self.pending_added.values())
            error_suffix = (
                f"/err{len(self.pending_errors)}" if self.pending_errors else ""
            )
            flags.append(f"pending:追加{total}件{error_suffix}")
        # P3-A: ヘルス検知行
        added_total = sum(
            len(v.get("added", [])) for v in self.structural_drift.values()
        )
        removed_total = sum(
            len(v.get("removed", [])) for v in self.structural_drift.values()
        )
        if (
            not self.structural_drift
            and not self.freshness_stale
            and not self.full_sync_stale
        ):
            flags.append("health:OK")
        else:
            flags.append(
                f"health:drift+{added_total}/-{removed_total}"
                f"/fresh{len(self.freshness_stale)}"
                f"/sync{len(self.full_sync_stale)}"
            )
        prefix = "[DRY-RUN] " if self.dry_run else ""
        return prefix + " / ".join(flags)


def _update_last_verified_all(
    ssot_root: Path,
    projects: list[str],
    today: str,
    dry_run: bool,
    result: BatchResult,
) -> None:
    """対象プロジェクトの last_verified を更新する."""
    for project in projects:
        manifest = (
            ssot_root / "01_DECISIONS" / project / ".dir-manifest.json"
        )
        if not manifest.is_file():
            continue
        if not dry_run:
            update_last_verified(manifest, today)
        result.last_verified_projects.append(project)


def _check_health_all(
    ssot_root: Path,
    projects: list[str],
    today: str,
    dry_run: bool,
    result: BatchResult,
) -> None:
    """対象プロジェクトの manifest ヘルスを3軸で検知し結果に集計する（read-only）.

    P3-A: last_verified 更新の前に実行（更新前の状態で検知するのが意味論的に正）。
    """
    for project in projects:
        manifest = (
            ssot_root / "01_DECISIONS" / project / ".dir-manifest.json"
        )
        if not manifest.is_file():
            continue
        try:
            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        repo_path = _resolve_repo_path(manifest_data, ssot_root, project)
        health = check_project_health(manifest, repo_path, ssot_root, today)
        if health.added or health.removed:
            result.structural_drift[project] = {
                "added": health.added,
                "removed": health.removed,
            }
        if health.freshness_stale:
            result.freshness_stale.append(project)
        if health.full_sync_stale:
            result.full_sync_stale.append(project)


def _update_index(dry_run: bool) -> None:
    """generate-decision-indexes を呼び出してINDEX差分を更新する."""
    if dry_run:
        return
    subprocess.run(
        ["generate-decision-indexes"],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _regenerate_all_pending(
    ssot_root: Path,
    projects: list[str],
    dry_run: bool,
    result: BatchResult,
) -> None:
    """pending対象のディレクトリ説明を再生成し、結果を集計する."""
    pending_file = ssot_root / ".dir-manifest-pending.json"
    pending_projects: list[str] = []
    if pending_file.is_file():
        try:
            data = json.loads(pending_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                pending_projects = [
                    project for project in data if isinstance(project, str)
                ]
        except Exception:
            pending_projects = []

    targets = [project for project in projects if project in pending_projects]
    for project in targets:
        manifest = (
            ssot_root / "01_DECISIONS" / project / ".dir-manifest.json"
        )
        if not manifest.is_file():
            continue
        try:
            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
            repo_path = _resolve_repo_path(manifest_data, ssot_root, project)
            if dry_run:
                result.pending_added[project] = ["(dry-run)"]
                continue
            regeneration = regenerate_pending(manifest, repo_path)
            result.pending_added[project] = regeneration["added"]
            for directory, kind in regeneration["failed"]:
                result.pending_errors.append(
                    f"{project}:{directory}({kind})"
                )
        except MeaningGenError as error:
            result.pending_errors.append(
                f"{project}:(manifest error:{error})"
            )
        except Exception as error:
            result.pending_errors.append(
                f"{project}:(unexpected:{type(error).__name__})"
            )

    if not dry_run and pending_file.is_file():
        pending_file.write_text("[]\n", encoding="utf-8")


def _resolve_repo_path(data: dict, ssot_root: Path, project: str) -> Path:
    """manifestのrepo_pathを展開し、未設定時はSSOT内を返す."""
    raw = data.get("repo_path", "")
    if not raw:
        return ssot_root / "01_DECISIONS" / project
    return Path(raw.replace("~", str(Path.home())))


def _mark_full_sync(
    ssot_root: Path,
    projects: list[str],
    today: str,
    dry_run: bool,
    result: BatchResult,
) -> None:
    """フル同期成功プロジェクトの last_full_sync を更新する（P3-A・第6形態）.

    成功条件: 「構造drift無し AND pending_approval エントリ無し」。
    drift/pending が残るプロジェクトは更新せず（→30日超で full_sync_stale 警告）。
    """
    if dry_run:
        return
    for project in projects:
        if project in result.structural_drift:
            continue
        manifest = (
            ssot_root / "01_DECISIONS" / project / ".dir-manifest.json"
        )
        if not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        has_pending = any(
            d.get("pending_approval") for d in data.get("directories", [])
        )
        if has_pending:
            continue
        update_last_full_sync(manifest, today)


def run_batch(
    ssot_root: Path,
    today: str,
    projects: list[str],
    dry_run: bool = False,
) -> BatchResult:
    """日次バッチをステップ依存ルール付きで実行する."""
    result = BatchResult(dry_run=dry_run)
    _check_health_all(ssot_root, projects, today, dry_run, result)
    _update_last_verified_all(ssot_root, projects, today, dry_run, result)
    try:
        _update_index(dry_run)
        result.index_ok = True
    except Exception as error:
        result.index_ok = False
        result.index_error = str(error)
        result.pending_skipped = True
        return result
    _regenerate_all_pending(ssot_root, projects, dry_run, result)
    _mark_full_sync(ssot_root, projects, today, dry_run, result)
    return result


def main() -> int:
    """CLI引数を解析して日次バッチを実行する."""
    parser = argparse.ArgumentParser(
        description="SSOT P2 日次バッチ orchestrator"
    )
    parser.add_argument(
        "--ssot-root",
        default=str(Path.home() / "projects/obsidian-ssot"),
    )
    parser.add_argument("--today", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--projects",
        nargs="*",
        default=None,
    )
    args = parser.parse_args()
    today = args.today or datetime.date.today().isoformat()
    if args.projects is None:
        args.projects = discover_manifest_projects(Path(args.ssot_root))
    try:
        datetime.date.fromisoformat(today)
    except ValueError:
        print(
            f"error: --today must be ISO 8601 (YYYY-MM-DD): {today}",
            file=sys.stderr,
        )
        return 2
    result = run_batch(
        Path(args.ssot_root),
        today,
        args.projects,
        dry_run=args.dry_run,
    )
    print(result.summary())
    return 0 if (result.index_ok or args.dry_run) else 1


if __name__ == "__main__":
    sys.exit(main())

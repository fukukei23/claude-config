"""SSOT体系化 承認スキーマ自動化 Phase2 最小観測(A‴′): 新規ファイル観測機構.

spec: docs/superpowers/specs/2026-07-25-ssot-approval-schema-automation-design.md §7.1
01_DECISIONSへの新規ファイル追加時だけ dry-run 自動発火 → 新規テーマ候補を通知/ログ。
承認は人が ``--apply`` で行う(Phase1半自動維持)・本モジュールは分類しない(観測専任)。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

__all__ = ["detect_new_decision_files", "run_observation", "log_observation"]


def detect_new_decision_files(diff_output: str) -> list[tuple[str, str]]:
    """git diff --name-only --diff-filter=A の出力から新規 01_DECISIONS ファイルを抽出.

    Args:
        diff_output: git diff の出力(1行1ファイルパス)。

    Returns:
        ``[(project, filename), ...]``。``_INDEX.md`` は除外。
        パス形式: ``01_DECISIONS/<project>/<filename>.md``。
    """
    results: list[tuple[str, str]] = []
    for raw in diff_output.strip().split("\n"):
        line = raw.strip()
        if not line:
            continue
        parts = line.split("/")
        # 01_DECISIONS/<project>/<file>.md (最低3セグメント)
        if len(parts) < 3 or parts[0] != "01_DECISIONS":
            continue
        filename = parts[-1]
        if not filename.endswith(".md") or filename == "_INDEX.md":
            continue
        project = parts[1]
        results.append((project, filename))
    return results


def run_observation(
    project: str,
    ssot_root: Path | str | None = None,
    dry_run_fn: Callable[..., dict] | None = None,
) -> dict:
    """新規ファイル追加PJで dry-run 発火 → 新規テーマ候補抽出.

    Args:
        project: ``01_DECISIONS/<project>`` のプロジェクト名。
        ssot_root: SSOT ルート(省略時は dry_run_fn デフォルト)。
        dry_run_fn: dry-run 関数(依存注入・テスト用。デフォルト ``run_dry_run``)。

    Returns:
        ``{"project", "new_themes", "file_count", "adoption_rate", "timestamp"}``。
    """
    if dry_run_fn is None:
        from scripts.obsidian.theme_classifier import run_dry_run as dry_run_fn
    from scripts.obsidian.theme_classifier import collect_new_themes

    result = dry_run_fn(project, ssot_root=ssot_root)
    new_themes = collect_new_themes(result["per_file"])
    return {
        "project": project,
        "new_themes": new_themes,
        "file_count": result["total"],
        "adoption_rate": result["adoption_rate"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def log_observation(log_path: Path | str, entry: dict) -> None:
    """観測ログ(JSON Lines)に1エントリ追記.

    Args:
        log_path: ログファイルパス(親ディレクトリは自動作成)。
        entry: 記録するdict(run_observation の戻り値等)。
    """
    p = Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

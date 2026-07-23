"""SSOT体系化 P3-A: .dir-manifest.json のヘルス検知（drift 3軸）.

検知軸（spec R5 + 第6形態）:
- structural_change: manifest ``directories[].path`` と実dir の双方向diff
- freshness_decay: ``last_verified`` の経過日数（90日超で警告）
- full_sync_stale: ``last_full_sync`` の経過日数（30日超 or 未設定で警告）

列挙ロジックは ``dir_manifests.regenerate_pending`` と同一（has_external_repo 分岐）。
"""
from __future__ import annotations

import datetime
from pathlib import Path

from scripts.obsidian.dir_manifests import (
    list_dirs_via_git,
    list_project_dirs_in_ssot,
)


def _days_since(date_str: str | None, today: str) -> int | None:
    """ISO日付文字列から today までの経過日数を返す.

    Args:
        date_str: ``YYYY-MM-DD`` 形式の日付（None/空/不正は None）。
        today: 基準日（``YYYY-MM-DD``）。

    Returns:
        経過日数。``date_str`` が None/空/不正形式なら None。
    """
    if not date_str:
        return None
    try:
        d = datetime.date.fromisoformat(date_str)
        t = datetime.date.fromisoformat(today)
    except ValueError:
        return None
    return (t - d).days


def is_freshness_stale(
    manifest: dict, today: str, threshold_days: int = 90
) -> bool:
    """last_verified の経過日数が閾値超か（freshness_decay・spec R5）.

    Args:
        manifest: ``.dir-manifest.json`` 相当の dict。
        today: 基準日（``YYYY-MM-DD``）。
        threshold_days: 警告閾値（デフォルト90）。

    Returns:
        経過日数 > 閾値 の場合 True。last_verified 未設定/不正も True。
    """
    days = _days_since(manifest.get("last_verified"), today)
    if days is None:
        return True
    return days > threshold_days


def is_full_sync_stale(
    manifest: dict, today: str, threshold_days: int = 30
) -> bool:
    """last_full_sync の経過日数が閾値超か（第6形態・通知陳腐化防止）.

    Args:
        manifest: ``.dir-manifest.json`` 相当の dict。
        today: 基準日（``YYYY-MM-DD``）。
        threshold_days: 警告閾値（デフォルト30）。

    Returns:
        経過日数 > 閾値 の場合 True。last_full_sync 未設定/None/不正も True。
    """
    days = _days_since(manifest.get("last_full_sync"), today)
    if days is None:
        return True
    return days > threshold_days


def detect_structural_drift(
    manifest: dict, repo_path: Path, ssot_root: Path
) -> dict:
    """manifest の directories と実dir を比較し、追加/削除を検知する.

    - spec R5: actual/recorded とも top-level(``split('/')[0]``)集約で偽検知防止
    - ``regenerate_pending`` と同一の列挙ロジック（has_external_repo 分岐）を再利用
    - 本関数は「検知のみ」。manifest への追記は行わない（read-only・べき等）

    Args:
        manifest: ``.dir-manifest.json`` 相当の dict。
        repo_path: 対象リポジトリパス（has_external_repo 時の git ls-tree 用）。
        ssot_root: obsidian-ssot ルート（has_external_repo=False 時の列挙用）。

    Returns:
        ``{"added": [新規dir...], "removed": [削除dir...]}``（top-level・昇順）。
    """
    recorded = {
        d["path"].split("/")[0]
        for d in manifest.get("directories", [])
        if d.get("path")
    }
    if manifest.get("has_external_repo"):
        actual_tops = {p.split("/")[0] for p in list_dirs_via_git(repo_path)}
    else:
        actual_tops = set(
            list_project_dirs_in_ssot(ssot_root, manifest.get("project", ""))
        )
    added = sorted(actual_tops - recorded)
    removed = sorted(recorded - actual_tops)
    return {"added": added, "removed": removed}

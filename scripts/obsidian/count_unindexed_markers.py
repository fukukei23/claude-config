"""SSOT体系化 P3-C: _INDEX.md の未消化マーカー（【要更新】）件数集計.

manifest_health.py の added/removed（構造的drift・top-level dir diff）とは別概念。
generate-decision-indexes が新規01_DECISIONSファイル検知時に _INDEX.md へ付与する
``【要更新】`` マーカーを PJ別・全体で集計し、MOC自動生成(§3.2)のデータソースとなる。

データソース3点確認（2026-08-07 実機検証済）:
- 実在: generate-decision-indexes L83 が ``| $f | $title 【要更新】 | — |`` 形式で付与
- スキーマ: _INDEX.md テーブル行の ``【要更新】`` 文字列（行ベース・count 可能）
- 更新タイミング: generate-decision-indexes 実行時（新規ファイル検知）付与・手動編集で消化
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

MARKER = "【要更新】"


@dataclass
class UnindexedCount:
    """未消化マーカーの集計結果（全体件数 + PJ別内訳）."""

    total: int = 0
    by_project: dict[str, int] = field(default_factory=dict)


def count_unindexed_markers(ssot_root: Path) -> UnindexedCount:
    """全PJの _INDEX.md を走査し ``【要更新】`` マーカー件数を集計する（read-only）.

    Args:
        ssot_root: obsidian-ssot ルートパス（``01_DECISIONS`` を含む）。

    Returns:
        ``UnindexedCount``。マーカー件数0のPJは ``by_project`` から除外し、
        ``_INDEX.md`` が存在しないPJも除外する（read-only・ファイル変更しない）。
    """
    decisions = ssot_root / "01_DECISIONS"
    by_project: dict[str, int] = {}
    for index_path in sorted(decisions.glob("*/_INDEX.md")):
        project = index_path.parent.name
        count = index_path.read_text(encoding="utf-8").count(MARKER)
        if count:
            by_project[project] = count
    return UnindexedCount(total=sum(by_project.values()), by_project=by_project)

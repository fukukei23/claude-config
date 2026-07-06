"""フェーズ7: task-log.md（タスク毎の経緯ログ）を生成する。

保存先: <task_dir>/task-log.md（.auto-loop/<task_id>/ 配下）
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def write_task_log(
    task_id: str,
    task_dir: Path,
    objective: str,
    kpi: Optional[dict],
    plan_summary: str,
    review_result: dict,
    drift_result: dict,
    verdict: str,
) -> Path:
    """task-log.md を生成して task_dir に保存する。

    Returns:
        生成された log ファイルのパス
    """
    task_dir.mkdir(parents=True, exist_ok=True)

    kpi_str = json.dumps(kpi, ensure_ascii=False) if kpi else "なし"
    review_str = json.dumps(review_result, ensure_ascii=False, indent=2)
    drift_str = json.dumps(drift_result, ensure_ascii=False, indent=2)

    content = f"""# 📖 {task_id} — 実装経緯ログ

## 🎯 TL;DR（目的＋結果＋KPI達成度）
- **目的**: {objective}
- **KPI**: {kpi_str}
- **結果**: {verdict}

## 🗺️ 計画（plan.md要約）
{plan_summary}

## 🤔 別LLMレビュー指摘（実装後）
```json
{review_str}
```

## 📋 ズレ検知履歴
```json
{drift_str}
```

## 📦 詳細経緯
- レビュー raw 出力: `logs/impl_review_*.txt`
- 計画 raw 出力: `logs/plan_review_*.txt`
- diff: `git log --stat` 参照

## 🔗 関連
- spec: docs/superpowers/specs/2026-07-06-auto-loop-multi-llm-review-design.md
"""

    log_path = task_dir / "task-log.md"
    log_path.write_text(content, encoding="utf-8")
    return log_path

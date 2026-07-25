"""CLI: auto-approve-themes <project> [--dry-run]（SSOT体系化 承認スキーマ自動化 Phase0）.

spec: docs/superpowers/specs/2026-07-25-ssot-approval-schema-automation-design.md

Phase0 は dry-run 専用（承認せず採用率検証）。本番承認（frontmatter 更新）は Phase1。
実行LLMは Gemini API 直接（spec§2・GLM 不可・theme_classifier._call_gemini 経由）。

使い方:
    auto-approve-themes <project>            # dry-run（デフォルト）
    auto-approve-themes <project> --dry-run  # 明示
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from scripts.obsidian.theme_classifier import run_dry_run  # noqa: E402


def main() -> int:
    """CLI エントリ: dry-run 実行・採用率とゲート判定(≥90%)を表示."""
    p = argparse.ArgumentParser(
        description="承認スキーマ自動化 Phase0 dry-run(§3.1)"
    )
    p.add_argument("project", help="01_DECISIONS/<project>")
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="dry-run（Phase0 は常時・承認しない）",
    )
    args = p.parse_args()

    result = run_dry_run(args.project)
    rate = result["adoption_rate"]
    gate = rate >= 0.90

    print(f"=== dry-run: {args.project} ===")
    print(f"総ファイル数: {result['total']}")
    print(f"既存 approved_themes: {result['approved']}")
    print(f"採用率: {rate:.1%}")
    print(f"Phase1 ゲート(≥90%): {'✅ PASS' if gate else '❌ FAIL'}")
    print("--- per_file ---")
    print(json.dumps(result["per_file"], ensure_ascii=False, indent=2))
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(main())

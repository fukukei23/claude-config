"""CLI: auto-approve-themes <project> [--apply|--dry-run]（承認スキーマ自動化 Phase1）.

spec: docs/superpowers/specs/2026-07-25-ssot-approval-schema-automation-design.md

Phase1 半自動CLI（§3.2）:
- デフォルト: run_approve(apply=False) 新規テーマ候補を提示（承認せず）
- ``--apply``: run_approve(apply=True) 新規テーマ候補を approved_themes に追加・diff表示（§4.4）
- ``--dry-run``: Phase0 互換・採用率検証のみ（run_dry_run）

実行LLMは Gemini API 直接（spec§2・theme_classifier._call_gemini 経由）。

使い方:
    auto-approve-themes <project>            # 新規テーマ候補を提案（承認せず）
    auto-approve-themes <project> --apply    # 本番承認（frontmatter更新・diff）
    auto-approve-themes <project> --dry-run  # Phase0 dry-run（採用率検証）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from scripts.obsidian.theme_classifier import run_approve, run_dry_run  # noqa: E402


def main() -> int:
    """CLI エントリ: 提案 / 本番承認 / dry-run を切り替えて実行."""
    p = argparse.ArgumentParser(
        description="承認スキーマ自動化 Phase1 半自動CLI(§3.2)"
    )
    p.add_argument("project", help="01_DECISIONS/<project>")
    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "--apply",
        action="store_true",
        help="本番承認（新規テーマ候補を approved_themes に追加・diff表示）",
    )
    g.add_argument(
        "--dry-run",
        action="store_true",
        help="Phase0 dry-run（採用率検証のみ・承認しない）",
    )
    args = p.parse_args()

    if args.dry_run:
        result = run_dry_run(args.project)
        rate = result["adoption_rate"]
        gate = rate >= 0.90
        print(f"=== dry-run: {args.project} ===")
        print(f"総ファイル数: {result['total']} / 採用率: {rate:.1%}")
        print(f"Phase1 ゲート(≥90%): {'✅ PASS' if gate else '❌ FAIL'}")
        print("--- per_file ---")
        print(json.dumps(result["per_file"], ensure_ascii=False, indent=2))
        return 0 if gate else 1

    result = run_approve(args.project, apply=args.apply)
    print(f"=== {'APPLY(本番承認)' if args.apply else '提案'}: {args.project} ===")
    print(f"総ファイル数: {result['total']} / 採用率: {result['adoption_rate']:.1%}")
    print(f"既存 approved_themes: {result['approved']}")
    print(f"新規テーマ候補: {result['new_themes']}")
    if result["applied"]:
        print("--- diff（承認内容確認・§4.4「触らず≠確認せず」）---")
        print(result["diff"])
    elif result["new_themes"]:
        print("※ 新規テーマ候補あり。承認するには --apply を指定してください。")
    else:
        print("※ 新規テーマ候補なし（全ファイル既存テーマに分類済み）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

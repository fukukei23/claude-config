#!/usr/bin/env python3
"""aggregate_judgment_ledger.py — 判断収束台帳_計測.md 自動生成.

00_SYSTEM/マルチLLMレビュー/*/revised_proposal.md の frontmatter 3数値を集約し
判断収束台帳_計測.md を全再生成する（冪等・出力に時刻を含まない）。
正典は各レビューの revised_proposal.md frontmatter（台帳は集約view）。

使い方:
  python3 aggregate_judgment_ledger.py                    # デフォルトパスで書込
  python3 aggregate_judgment_ledger.py --dry-run          # 標準出力のみ・書込なし
  python3 aggregate_judgment_ledger.py --target GLOB --output PATH
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from pathlib import Path

DEFAULT_TARGET = str(
    Path.home()
    / "projects/obsidian-ssot/00_SYSTEM/マルチLLMレビュー/*/revised_proposal.md"
)
DEFAULT_OUTPUT = str(
    Path.home() / "projects/obsidian-ssot/00_SYSTEM/判断収束台帳_計測.md"
)

REQUIRED_KEYS = (
    "findings_total",
    "converted_to_cmd",
    "overturned_by_measurement",
)

HEADER = """---
tags: [判断収束ループ, 自動生成]
---

# 判断収束台帳（計測） — 自動生成ファイル

> ⚠️ 本ファイルは `claude-config/scripts/obsidian/aggregate_judgment_ledger.py` が全生成する。
> **人間・LLMともに手編集禁止**（変更は次回生成で消える）。選択肢の系譜は [[判断収束台帳_系譜]] へ。

**tier 定義**: 判定用 = frontmatter自動記録による新規計測（機械検証付き）／ 参考 = 遡及・手集計（判定にもストップにも使わない・A′決定）

**判断ライフサイクル責務表**:

| 段階 | 担当 |
|---|---|
| 発火判定 | 自律開発ループ.md（層1キーワード自動/層2オプトアウト承認/第3カテゴリ誘導） |
| レビュー実行 | multi-llm-review（実測グランド持ち=3機/その他=2機） |
| 計測記録 | revised_proposal.md frontmatter（正典） |
| 集約 | 本スクリプト → この台帳 |
| 系譜記録 | sentaku → [[判断収束台帳_系譜]] |
| 決定記録 | ssot-record（falsification/outcome 付き） |
| 答え合わせ | ssot-record 逆引き1問（観測事実提示→Yes/No） |
"""


def normalize(text: str) -> str:
    """BOM除去・改行のLF正規化."""
    return text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")


def extract_frontmatter(text: str) -> dict[str, str] | None:
    """frontmatterを key: value のフラット辞書として抽出（ネスト構造は使わない）。"""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None
    fm: dict[str, str] = {}
    for line in m.group(1).split("\n"):
        km = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if km:
            fm[km.group(1)] = km.group(2).strip()
    return fm if fm else None


def count_evidence(text: str) -> int:
    """「### 証跡」セクション数を数える（frontmatter機械検証と同じ式）。"""
    return len(re.findall(r"^### 証跡", text, re.MULTILINE))


def to_int(value: str | None) -> int | None:
    """数値変換（失敗時None・クラッシュしない）。"""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def collect(paths: list[str], base_dir: Path) -> tuple[list[dict], list[str]]:
    """対象ファイルを走査し（行, 未解析ファイル）を返す。例外で止まらない。"""
    rows: list[dict] = []
    unparsed: list[str] = []
    for p in sorted(paths):
        try:
            text = normalize(Path(p).read_text(encoding="utf-8", errors="replace"))
            fm = extract_frontmatter(text)
            numbers = [to_int(fm.get(k)) if fm else None for k in REQUIRED_KEYS]
            if fm is None or any(n is None for n in numbers):
                unparsed.append(str(p))
                continue
            ft, cc, ob = numbers  # type: ignore[misc]
        except OSError:
            unparsed.append(str(p))
            continue
        ev = count_evidence(text)
        status = ""
        if ob > 0 and ev == 0:
            status = "⚠️要修正(証跡0)"
        elif ob > ev:
            status = "⚠️要修正(証跡不足)"
        try:
            rel = os.path.relpath(str(p), str(base_dir))
        except ValueError:
            rel = str(p)
        rows.append(
            {
                "date": fm.get("date", "unknown"),
                "target": fm.get("target", Path(p).parent.name),
                "ft": ft,
                "cc": cc,
                "ob": ob,
                "tier": fm.get("tier", "判定用"),
                "status": status,
                "link": rel,
            }
        )
    return rows, unparsed


def render(rows: list[dict], unparsed: list[str]) -> str:
    """台帳本文を生成（時刻等の非決定要素を含めない=冪等）。"""
    lines = [
        HEADER,
        "",
        "## レビュー計測表",
        "",
        "| date | 対象 | findings_total | converted_to_cmd | overturned | tier | 状態 | 正典リンク |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['date']} | {r['target']} | {r['ft']} | {r['cc']} | {r['ob']} "
            f"| {r['tier']} | {r['status']} | [レビュー]({r['link']}) |"
        )
    if not rows:
        lines.append("| （計測対象レビューなし） | | | | | | | |")
    lines += ["", f"- 集約対象: {len(rows)}件 / 未解析: {len(unparsed)}件"]
    if unparsed:
        lines.append("- 未解析（frontmatter無し・数値欠損。参考: 判定外）:")
        for u in unparsed:
            lines.append(f"  - `{u}`")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=DEFAULT_TARGET, help="revised_proposal.md のglob")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="台帳の出力パス")
    parser.add_argument("--dry-run", action="store_true", help="標準出力のみ・書込なし")
    args = parser.parse_args(argv)

    paths = sorted(glob.glob(args.target))
    base_dir = Path(args.output).resolve().parent
    rows, unparsed = collect(paths, base_dir)
    content = render(rows, unparsed)
    if args.dry_run:
        sys.stdout.write(content)
        return 0
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(f"集約完了: {len(rows)}件 / 未解析 {len(unparsed)}件 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

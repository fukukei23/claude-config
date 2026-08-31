#!/usr/bin/env python3
"""aggregate_judgment_ledger.py — 判断収束台帳_計測.md 自動生成.

00_SYSTEM/マルチLLMレビュー/*/revised_proposal.md の frontmatter 数値を集約し
判断収束台帳_計測.md を全再生成する（冪等・出力に時刻を含まない）。
正典は各レビューの revised_proposal.md frontmatter（台帳は集約view）。

二源化（バックログL825・2026-09-01）: ``--ledger-db``（mlr-log.sh annotate --proposal が
書く ingest DB）を一次ソースとし、globは照合用に残す。
- DBにあってファイルが無い round → 「計測未完(未作成)」として台帳に載る（静かな漏れを防ぐ）
- globにあってDBに無い → 「⚠️ingest漏れ」警告付きで載る
- DBとfrontmatterの数値不一致 → 「⚠️不一致」警告（正典はfrontmatter）

使い方:
  python3 aggregate_judgment_ledger.py                    # デフォルトパスで書込
  python3 aggregate_judgment_ledger.py --dry-run          # 標準出力のみ・書込なし
  python3 aggregate_judgment_ledger.py --target GLOB --output PATH
  python3 aggregate_judgment_ledger.py --ledger-db PATH   # ingest DB と照合（二源化）
"""

from __future__ import annotations

import argparse
import glob
import json
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
DEFAULT_LEDGER_DB = str(Path.home() / ".claude/state/judgment-ledger.jsonl")

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

**撤退基準（台帳スキーマv2・2026-08-31確定）**: 過去10回 decision_changed=no 且つ overturned=0 が継続 → レビュー頻度を見直す

**判断ライフサイクル責務表**:

| 段階 | 担当 |
|---|---|
| 発火判定 | 自律開発ループ.md（層1キーワード自動/層2オプトアウト承認/第3カテゴリ誘導） |
| レビュー実行 | multi-llm-review（実測グランド持ち=3機/その他=2機） |
| 計測記録 | revised_proposal.md frontmatter（正典） |
| ingest | mlr-log.sh annotate --proposal → ~/.claude/state/judgment-ledger.jsonl |
| 集約 | 本スクリプト → この台帳 |
| 系譜記録 | sentaku → [[判断収束台帳_系譜]] |
| 決定記録 | ssot-record（falsification/outcome 付き） |
| 答え合わせ | ssot-record 逆引き1問（観測事実提示→Yes/No） |

## 手記載（遡及・frontmatter無しの判定用計測・正典はバックログの集計記録）

| date | 対象 | findings_total | converted_to_cmd | overturned | tier | 正典リンク |
|---|---|---|---|---|---|---|
| 2026-08-13 | atelier LFS偽差分 | 21 | 4 | 2 | 判定用(遡及) | [バックログ](../バックログ.md) |
| 2026-08-17 | ISSUE-106 impact分析 | 10 | 4 | 1 | 判定用(遡及) | [LLMサボりバイアス実例](../参考資料/LLMサボりバイアス実例/2026-08-17_同一観点レビューは前提を検査しない-ISSUE106テスト巻き込み.md) |
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
        dirname = Path(p).parent.name
        dm = re.match(r"^(\d{4}-\d{2}-\d{2})_", dirname)
        date_fb = dm.group(1) if dm else "unknown"
        target_fb = dirname[dm.end():] if dm else dirname
        rows.append(
            {
                "path": str(Path(p).resolve()),
                "date": fm.get("date") or date_fb,
                "target": fm.get("target") or target_fb,
                "ft": ft,
                "cc": cc,
                "ob": ob,
                "dc": _normalize_dc(fm.get("decision_changed")),
                "ne": _normalize_ne(fm.get("negative_effect")),
                "tier": fm.get("tier", "判定用"),
                "status": status,
                "link": rel,
            }
        )
    return rows, unparsed


def _normalize_dc(value: str | None) -> str:
    """decision_changed を台帳表示用に正規化（未記載は — ）."""
    v = (value or "").strip()
    return v or "—"


def _normalize_ne(value: str | None) -> str:
    """negative_effect を台帳表示用に正規化（未記載は — ）."""
    v = (value or "").strip().lower()
    if v in ("true", "false"):
        return v
    return "—"


def collect_db(db_path: str) -> list[dict]:
    """ingest DB（judgment-ledger.jsonl）の行を読む。破損行は読み飛ばす。"""
    rows: list[dict] = []
    if not db_path or not os.path.isfile(db_path):
        return rows
    try:
        for line in open(db_path, encoding="utf-8"):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if isinstance(d, dict) and d.get("schema_ok"):
                rows.append(d)
    except OSError:
        return []
    return rows


def merge_db(
    file_rows: list[dict], db_rows: list[dict], base_dir: Path
) -> tuple[list[dict], int, int]:
    """DB行を一次・glob行を照合にマージする。

    Returns:
        (マージ後の行, 計測未完件数, ingest漏れ件数)
    """
    file_map = {r["path"]: r for r in file_rows}
    matched: set[str] = set()
    out: list[dict] = list(file_rows)
    incomplete = 0
    for d in db_rows:
        prop = str(d.get("proposal_path") or "")
        try:
            prop_resolved = str(Path(prop).resolve())
        except OSError:
            prop_resolved = prop
        fr = file_map.get(prop_resolved)
        if fr is not None:
            # 両方にある: 正典は frontmatter。数値の食い違いは不一致警告。
            matched.add(prop_resolved)
            db_ft, db_ob = d.get("findings_total"), d.get("overturned_by_measurement")
            if (db_ft is not None and db_ft != fr["ft"]) or (
                db_ob is not None and db_ob != fr["ob"]
            ):
                fr["status"] = (fr["status"] + " " if fr["status"] else "") + "⚠️不一致"
            # v2列は frontmatter に欠けていれば DB 値で補完表示（— より情報がある）
            if fr["dc"] == "—":
                fr["dc"] = _normalize_dc(d.get("decision_changed"))
            if fr["ne"] == "—":
                ne_db = d.get("negative_effect")
                if ne_db is not None:
                    fr["ne"] = _normalize_ne(str(ne_db))
        else:
            # DBにあってファイルが無い: 計測未完（fail条件①・静かに漏れない）
            incomplete += 1
            try:
                rel = os.path.relpath(prop, str(base_dir))
            except ValueError:
                rel = prop
            out.append(
                {
                    "path": prop_resolved,
                    "date": (d.get("date") or (d.get("ts") or "")[:10] or "unknown"),
                    "target": d.get("target") or d.get("topic") or "(topic未記録)",
                    "ft": d.get("findings_total"),
                    "cc": d.get("converted_to_cmd", "—"),
                    "ob": d.get("overturned_by_measurement"),
                    "dc": _normalize_dc(d.get("decision_changed")),
                    "ne": _normalize_ne(str(d.get("negative_effect"))
                                       if d.get("negative_effect") is not None else None),
                    "tier": d.get("tier", "判定用"),
                    "status": "計測未完(未作成)",
                    "link": rel,
                }
            )
    # globにあってDBに無い: ingest漏れ（fail条件②）
    leaks = 0
    for r in file_rows:
        if r["path"] not in matched:
            leaks += 1
            r["status"] = (r["status"] + " " if r["status"] else "") + "⚠️ingest漏れ"
    out.sort(key=lambda r: (str(r.get("date")), str(r.get("target"))))
    return out, incomplete, leaks


def render(
    rows: list[dict],
    unparsed: list[str],
    incomplete: int = 0,
    leaks: int = 0,
) -> str:
    """台帳本文を生成（時刻等の非決定要素を含めない=冪等）。"""
    lines = [
        HEADER,
        "",
        "## レビュー計測表",
        "",
        "| date | 対象 | findings_total | converted_to_cmd | overturned"
        " | decision_changed | negative_effect | tier | 状態 | 正典リンク |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['date']} | {r['target']} | {r['ft']} | {r['cc']} | {r['ob']} "
            f"| {r['dc']} | {r['ne']} | {r['tier']} | {r['status']} | [レビュー]({r['link']}) |"
        )
    if not rows:
        lines.append("| （計測対象レビューなし） | | | | | | | | | |")
    lines += ["", f"- 集約対象: {len(rows)}件 / 未解析: {len(unparsed)}件"]
    if incomplete:
        lines.append(f"- 計測未完(未作成): {incomplete}件（ingest されたが revised_proposal.md が未作成）")
    if leaks:
        lines.append(f"- ⚠️ingest漏れ: {leaks}件（frontmatterはあるが ingest DB に無い・annotate --proposal 忘れ）")
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
    parser.add_argument(
        "--ledger-db",
        default=None,
        help="ingest DB (judgment-ledger.jsonl) と照合する（指定時のみ二源化）",
    )
    args = parser.parse_args(argv)

    paths = sorted(glob.glob(args.target))
    base_dir = Path(args.output).resolve().parent
    rows, unparsed = collect(paths, base_dir)
    incomplete = leaks = 0
    if args.ledger_db:
        db_rows = collect_db(args.ledger_db)
        rows, incomplete, leaks = merge_db(rows, db_rows, base_dir)
    content = render(rows, unparsed, incomplete, leaks)
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

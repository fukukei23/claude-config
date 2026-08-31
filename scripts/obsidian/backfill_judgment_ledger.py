#!/usr/bin/env python3
"""backfill_judgment_ledger.py — ingest DB 未登録の revised_proposal.md を全件DBへ取込.

- 対象: 00_SYSTEM/マルチLLMレビュー/*/revised_proposal.md のうち
  findings_total/converted_to_cmd/overturned_by_measurement が数値で読め
  かつ judgment-ledger.jsonl に proposal_path が未登録のもの
- 数値はfrontmatterから直接読む（正典・捏造なし）・source: backfill
- 冪等: DBに既にある proposal_path は追記しない
- 用途: DB破損時の復旧・annotate --proposal 導入前の遡及取込
  （2026-09-01 初回実行: 旧18件frontmatter補完分+既存51件を取込）

使い方:
  python3 scripts/obsidian/backfill_judgment_ledger.py
  python3 scripts/obsidian/aggregate_judgment_ledger.py --ledger-db ~/.claude/state/judgment-ledger.jsonl  # 取込後に台帳再生成
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

BASE = Path.home() / "projects/obsidian-ssot/00_SYSTEM/マルチLLMレビュー"
DB = Path.home() / ".claude/state/judgment-ledger.jsonl"

REQUIRED = ("findings_total", "converted_to_cmd", "overturned_by_measurement")


def extract_fm(text: str) -> dict:
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).split("\n"):
        km = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if km:
            fm[km.group(1)] = km.group(2).strip()
    return fm


def main() -> int:
    existing = set()
    if DB.is_file():
        for line in open(DB, encoding="utf-8"):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                existing.add(str(d.get("proposal_path")))
            except ValueError:
                continue
    now = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    added = skipped_nofm = skipped_exists = 0
    new_rows = []
    for path in sorted(BASE.glob("*/revised_proposal.md")):
        rp = str(path.resolve())
        if rp in existing:
            skipped_exists += 1
            continue
        fm = extract_fm(path.read_text(encoding="utf-8", errors="replace"))
        nums = []
        for k in REQUIRED:
            try:
                nums.append(int(fm[k]))
            except (KeyError, ValueError):
                nums.append(None)
        if any(n is None for n in nums):
            skipped_nofm += 1
            print(f"  skip（数値読めず）: {path.parent.name}")
            continue
        ft, cc, ob = nums
        dirname = path.parent.name
        dm = re.match(r"^(\d{4}-\d{2}-\d{2})_", dirname)
        ne = fm.get("negative_effect", "").strip().lower()
        row = {
            "ts": now,
            "round_id": f"backfill-{dirname[:10]}",
            "topic": dirname[11:] if dm else dirname,
            "proposal_path": rp,
            "findings_total": ft,
            "converted_to_cmd": cc,
            "overturned_by_measurement": ob,
            "decision_changed": fm.get("decision_changed") or "n/a(遡及)",
            "negative_effect": (ne == "true") if ne in ("true", "false") else False,
            "date": fm.get("date") or (dirname[:10] if dm else "unknown"),
            "target": fm.get("target") or (dirname[11:] if dm else dirname),
            "evidence": len(re.findall(r"^### 証跡",
                                       path.read_text(encoding="utf-8", errors="replace"),
                                       re.MULTILINE)),
            "schema_ok": True,
            "source": "backfill",
        }
        new_rows.append(row)
        added += 1
    if new_rows:
        with open(DB, "a", encoding="utf-8", newline="\n") as f:
            for r in new_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"結果: 追加={added} / 既存skip={skipped_exists} / 数値不可skip={skipped_nofm}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

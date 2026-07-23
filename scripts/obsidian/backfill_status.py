#!/usr/bin/env python3
"""SSOT体系化 P3-C Phase 0: 既存28manifestへ status='active' をバックフィル（冪等）.

status 未設定の .dir-manifest.json に限り 'active' を付与。既存 status は保持。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts.obsidian.dir_manifests import discover_manifest_projects


def backfill(ssot_root: Path) -> dict:
    """status 未設定の manifest に 'active' を付与する.

    Args:
        ssot_root: obsidian-ssot ルート。

    Returns:
        ``{"updated": [project...], "skipped": [project...]}``。
    """
    updated: list[str] = []
    skipped: list[str] = []
    for project in discover_manifest_projects(ssot_root):
        mpath = ssot_root / "01_DECISIONS" / project / ".dir-manifest.json"
        data = json.loads(mpath.read_text(encoding="utf-8"))
        if "status" in data:
            skipped.append(project)
            continue
        data["status"] = "active"
        mpath.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        updated.append(project)
    return {"updated": sorted(updated), "skipped": sorted(skipped)}


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="backfill status=active to manifests")
    p.add_argument("--ssot-root", default="/home/yn4416/projects/obsidian-ssot")
    args = p.parse_args()
    result = backfill(Path(args.ssot_root))
    print(f"updated: {len(result['updated'])} / skipped: {len(result['skipped'])}")
    if result["updated"]:
        print("  updated:", ", ".join(result["updated"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

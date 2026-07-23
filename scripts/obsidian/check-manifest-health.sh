#!/bin/bash
# SSOT体系化 P3-A: manifest ヘルス状態を /tmp/claude-startup/manifest-health.status へ出力
# SessionStart hook（banner が .status を自動集約・表示）
# 重い処理は日次バッチ(4:23)担当・本hookは既存3プロジェクトのread-only検知のみ
set -uo pipefail

SSOT_ROOT="${SSOT_ROOT:-$HOME/projects/obsidian-ssot}"
CLAUDE_CONFIG="${CLAUDE_CONFIG:-$HOME/projects/claude-config}"
STATUS_FILE="/tmp/claude-startup/manifest-health.status"
mkdir -p /tmp/claude-startup

RESULT=$(PYTHONPATH="$CLAUDE_CONFIG" SSOT_ROOT="$SSOT_ROOT" python3 << 'PYEOF' 2>/dev/null
import datetime
import json
import os
import sys
from pathlib import Path

from scripts.obsidian.manifest_health import check_project_health
from scripts.obsidian.ssot_daily_batch import _resolve_repo_path

ssot_root = Path(os.environ["SSOT_ROOT"])
today = datetime.date.today().isoformat()
projects = ["reserve-optimizer", "NexusCore", "claude-code"]

added = removed = fresh = sync = 0
checked = 0
for project in projects:
    manifest = ssot_root / "01_DECISIONS" / project / ".dir-manifest.json"
    if not manifest.is_file():
        continue
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        continue
    checked += 1
    repo_path = _resolve_repo_path(data, ssot_root, project)
    h = check_project_health(manifest, repo_path, ssot_root, today)
    added += len(h.added)
    removed += len(h.removed)
    fresh += int(h.freshness_stale)
    sync += int(h.full_sync_stale)

issues = []
if added or removed:
    issues.append(f"drift+{added}/-{removed}")
if fresh:
    issues.append(f"fresh{fresh}")
if sync:
    issues.append(f"sync{sync}")
if issues:
    print(f"⚠️ manifestヘルス: {'/'.join(issues)} ({checked}proj)")
else:
    print(f"✅ manifestヘルス: 全プロジェクト健全 ({checked}proj)")
PYEOF
)

# 先頭スペース+絵文字（bannerの ^ ✅ / ^ ⚠️ 判定に合せる）
echo " ${RESULT:-⚠️ manifestヘルス: 検知エラー}" > "$STATUS_FILE"
exit 0

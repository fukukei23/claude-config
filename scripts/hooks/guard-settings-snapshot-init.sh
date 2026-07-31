#!/bin/bash
# guard-settings-snapshot-init.sh — SessionStart で settings.json のスナップショット保存
# 初回フォールバック用（主役は PreToolUse で毎回保存・spec §6 設計転換）
set -uo pipefail
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SNAP_DIR="$CLAUDE_DIR/state/guard-settings-snapshots"
mkdir -p "$SNAP_DIR"
for f in settings.json settings.local.json; do
    src="$CLAUDE_DIR/$f"
    [ -f "$src" ] && cp -p "$src" "$SNAP_DIR/$f.before"
done

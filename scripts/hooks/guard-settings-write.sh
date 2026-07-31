#!/bin/bash
# guard-settings-write.sh — settings.json への TOKEN 書込 Post差分検知(C'案) + Pre補助
# spec: docs/superpowers/specs/2026-07-30-guard-settings-write-post-detection-design.md
#
# 仕組み:
# - PreToolUse(Bash): コマンド文字列に「settings.json言及+ネットワーク送信」チェインがあれば exit2
# - PostToolUse(Bash|Edit|Write|MultiEdit|NotebookEdit): settings.json の before/after を意味的差分+4層判定
#   - TOKEN_DETECTED → cp -p 復元 + exit2 + ログ
#   - CLEAN → 無音
# - TTL bypass: ~/.claude/guard-bypass-<ts> が5分内有効なら何もしない
# - 既存 guard-config-secrets.sh は Bash 経由の本体書換をスルーする盲点を本hookが補完
#
# stdin 受け渡し: cat | python3 -c 構成(stdin=JSON・script=-c・既存hook準拠)

set -uo pipefail

CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SETTINGS="$CLAUDE_DIR/settings.json"
SETTINGS_LOCAL="$CLAUDE_DIR/settings.local.json"
SNAPSHOT_DIR="$CLAUDE_DIR/state/guard-settings-snapshots"
LOG_PATH="$CLAUDE_DIR/logs/guard-settings-write.log"
CORE="$(dirname "$0")/guard_settings_write_core.py"
BYPASS_TTL=300

mkdir -p "$SNAPSHOT_DIR" "$CLAUDE_DIR/logs"

cat | python3 -c '
import sys, os, json, shutil, importlib.util
core_path, settings_path, local_path, snap_dir, log_path = sys.argv[1:6]
bypass_ttl = int(sys.argv[6])

spec = importlib.util.spec_from_file_location("core", core_path)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)  # パース不能は許可

tool = d.get("tool_name", "")
hook_event = d.get("hook_event_name", "")  # PreToolUse / PostToolUse

# TTL bypass チェック
if core.is_bypass_active(os.path.expanduser("~/.claude"), ttl_seconds=bypass_ttl):
    sys.exit(0)

# === PreToolUse: settings.json beforeスナップショット保存 + Bash チェインブロック ===
if hook_event == "PreToolUse":
    for target in [p for p in [settings_path, local_path] if os.path.exists(p)]:
        snap = os.path.join(snap_dir, os.path.basename(target) + ".before")
        try:
            shutil.copy2(target, snap)
        except OSError:
            pass
    if tool == "Bash":
        cmd = d.get("tool_input", {}).get("command", "")
        if core.pre_detect_exfil_chain(cmd):
            core.write_log(log_path, "PRE_BLOCKED", "settings.json言及+送信チェイン事前ブロック", suspect_value=cmd[:60])
            print(json.dumps({"decision": "block", "reason": "guard-settings-write: settings.json 言及 + ネットワーク送信の同一チェインを検知（Pre補助・事前ブロック）"}, ensure_ascii=False), file=sys.stderr)
            sys.exit(2)
    sys.exit(0)

# === PostToolUse: スナップショット比較 ===
if hook_event == "PostToolUse":
    targets = [p for p in [settings_path, local_path] if os.path.exists(p)]
    for target in targets:
        snap = os.path.join(snap_dir, os.path.basename(target) + ".before")
        if not os.path.exists(snap):
            continue  # スナップショット無しは初回スキップ
        result = core.detect_token_write(snap, target)
        if result == "TOKEN_DETECTED":
            restore = core.restore_snapshot(snap, target)
            core.write_log(log_path, "TOKEN_DETECTED", f"{os.path.basename(target)} にTOKEN書込検出・復元={restore}", suspect_value="detected")
            print(json.dumps({"decision": "block", "reason": f"guard-settings-write: {os.path.basename(target)} への TOKEN 書込を検知・復元しました（{restore}）"}, ensure_ascii=False), file=sys.stderr)
            sys.exit(2)
    sys.exit(0)

sys.exit(0)
' "$CORE" "$SETTINGS" "$SETTINGS_LOCAL" "$SNAPSHOT_DIR" "$LOG_PATH" "$BYPASS_TTL"

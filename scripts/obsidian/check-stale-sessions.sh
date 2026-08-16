#!/usr/bin/env bash
# check-stale-sessions.sh — active-sessions.md の 🟢行のうち「死んだセッション」を検知
#
# 検知ロジック:
#   各🟢行のID(WT4)について、優先度順に活動時刻を引く:
#     1. ~/.claude/state/heartbeat/$WT4 mtime（PostToolUse hook毎にtouch）
#     2. hover:<ssot>/00_SYSTEM/handoff/*_$WT4.md 最古の mtime（new-session実行時刻）
#     3. どちらも無し → 証跡ゼロ → stale とみなす（6d3f型：強制終了で何も残らない）
#   age > 閾値（デフォルト12h / [長時間]マーカー行は72h）→ stale候補
#
# 出力:
#   --json         JSON配列 1行 / stdout（Daily Triage 連携用）
#   (デフォルト)   人間可読 / stale有りで exit 0（stderr無しでstdout警告を SessionStart コンテキストとして表示・2026-08-17 hook error 誤表示対策）
#
# オプション:
#   --threshold H        デフォル閾値（時間）省略時12
#   --long-threshold H   [長時間]行の閾値（時間）省略時72
#   --ssot-path PATH     obsidian-ssot root 省略時 ~/projects/obsidian-ssot
#   --heartbeat-dir DIR  heartbeat dir 省略時 ~/.claude/state/heartbeat
#   --handoff-dir DIR    handoff dir 省略時 <ssot>/00_SYSTEM/handoff
#
# 完了: 2026-07-25 L98 spec化→実装（案α+heartbeat初手）

set -u

# === オプション解析 ===
THRESHOLD=12
LONG_THRESHOLD=72
SSOT_PATH="${HOME}/projects/obsidian-ssot"
HEARTBEAT_DIR="${HOME}/.claude/state/heartbeat"
HANDOFF_DIR=""
JSON_OUT=0

while [ $# -gt 0 ]; do
  case "$1" in
    --threshold)         THRESHOLD="$2"; shift 2 ;;
    --long-threshold)    LONG_THRESHOLD="$2"; shift 2 ;;
    --ssot-path)         SSOT_PATH="$2"; shift 2 ;;
    --heartbeat-dir)     HEARTBEAT_DIR="$2"; shift 2 ;;
    --handoff-dir)       HANDOFF_DIR="$2"; shift 2 ;;
    --json)              JSON_OUT=1; shift ;;
    -h|--help)           sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -z "$HANDOFF_DIR" ] && HANDOFF_DIR="${SSOT_PATH}/00_SYSTEM/handoff"
ACTIVE_SESSIONS="${SSOT_PATH}/00_SYSTEM/active-sessions.md"

[ -f "$ACTIVE_SESSIONS" ] || { echo "❌ active-sessions.md not found: $ACTIVE_SESSIONS" >&2; exit 2; }

NOW_EPOCH=$(date +%s)

# === 🟢行抽出 + stale判定（python3 に委譲） ===
exec 3>&1
exec 1>&2  # ログ系はstderr(メイン出力を汚さない)
RESULT=$(python3 <<PY
import os, re, json, sys
from pathlib import Path
from datetime import datetime

active_sessions = "${ACTIVE_SESSIONS}"
heartbeat_dir = Path("${HEARTBEAT_DIR}")
handoff_dir = Path("${HANDOFF_DIR}")
threshold = ${THRESHOLD}
long_threshold = ${LONG_THRESHOLD}
now_epoch = ${NOW_EPOCH}

# ---- 単一表から🟢行抽出（daily_triage.pyの _collect_single_table_green と同等） ----
text = Path(active_sessions).read_text(encoding="utf-8")
green_rows = []
in_section = False
status_col_index = -1
id_col_index = -1
session_col_index = -1

def is_table_row(line: str) -> bool:
    return line.startswith("| ") and not line.startswith("|---") and not line.startswith("|- ")

def is_header_row(line: str) -> bool:
    l = line.lower()
    return any(h in l for h in ("セッション", "タスク", "環境", "開始", "状態", "触る共通ファイル", "方針"))

for line in text.splitlines():
    if line.startswith("## セッション状態"):
        in_section = True
        status_col_index = -1
        id_col_index = -1
        session_col_index = -1
        continue
    if in_section and line.startswith("## ") and not line.startswith("## セッション状態"):
        in_section = False
        continue
    if not in_section:
        continue
    if is_header_row(line):
        header_cells = [c.strip() for c in line.split("|") if c.strip()]
        if "状態" in header_cells:
            status_col_index = header_cells.index("状態")
        if "ID" in header_cells:
            id_col_index = header_cells.index("ID")
        if "セッション" in header_cells:
            session_col_index = header_cells.index("セッション")
        continue
    if not is_table_row(line):
        continue
    if status_col_index == -1:
        continue
    cells = [c.strip() for c in line.split("|") if c.strip()]
    if len(cells) > status_col_index and cells[status_col_index] == "🟢":
        green_rows.append(cells)

# ---- 各🟢行の最終活動時刻を判定 ----
stale = []
for cells in green_rows:
    if id_col_index == -1 or id_col_index >= len(cells):
        continue
    id_val = cells[id_col_index]
    session_name = cells[session_col_index] if session_col_index != -1 and session_col_index < len(cells) else ""
    is_long = "[長時間]" in session_name

    # 情報源を順に試す
    hb_path = heartbeat_dir / id_val if id_val else None
    trace = None
    source = None

    if hb_path and hb_path.exists():
        trace = hb_path.stat().st_mtime
        source = "heartbeat"
    else:
        # handoff フォールバック（複数あれば最新を使用）
        if handoff_dir.exists() and id_val:
            try:
                candidates = sorted(handoff_dir.glob(f"*_{id_val}.md"))
                if candidates:
                    trace = max(p.stat().st_mtime for p in candidates)
                    source = "handoff"
            except Exception:
                pass

    if trace is None:
        # 証跡ゼロ＝6d3f型（強制終了で何も残らない）
        stale.append({
            "id": id_val,
            "session": session_name,
            "age_hours": None,
            "threshold_hours": long_threshold if is_long else threshold,
            "reason": "no_trace",
            "is_long_run": is_long,
        })
        continue

    age_sec = now_epoch - trace
    age_hours = age_sec / 3600.0
    limit = long_threshold if is_long else threshold
    if age_hours > limit:
        stale.append({
            "id": id_val,
            "session": session_name,
            "age_hours": round(age_hours, 1),
            "threshold_hours": limit,
            "reason": f"{source}_timeout",
            "is_long_run": is_long,
        })

print(json.dumps(stale, ensure_ascii=False))
PY
)
exec 1>&3  # 復元
exec 3>&-

# === 出力整形 ===
if [ "$JSON_OUT" = "1" ]; then
  echo "$RESULT"
else
  cnt=$(echo "$RESULT" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
  if [ "$cnt" = "0" ]; then
    echo "✅ active-sessions.md にstale🟢行なし"
    exit 0
  fi
  echo "⚠️  active-sessions.md にstale🟢行 ${cnt}件（人間が✅化してください）"
  echo ""
  echo "$RESULT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for r in d:
    age = r['age_hours']
    age_str = f'{age}h' if age is not None else '不明(証跡無)'
    long_marker = ' [長時間]' if r['is_long_run'] else ''
    print(f\"  - {r['id']}{long_marker} | 経過: {age_str} | 閾値: {r['threshold_hours']}h | 理由: {r['reason']}\")
    print(f\"    タスク: {r['session']}\")
"
  exit 1
fi

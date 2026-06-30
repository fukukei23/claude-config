#!/usr/bin/env bash
# state.json の mode を切替（manual/auto）。
# 切替時に session_task_count をリセット（新セッション開始の意味）。
# Usage: set-mode.sh manual | set-mode.sh auto
set -euo pipefail

STATE="/home/yn4416/.claude/scripts/auto-dev/state.json"
MODE="${1:-}"

if [[ "$MODE" != "manual" && "$MODE" != "auto" ]]; then
  echo "Usage: $0 manual|auto" >&2
  exit 1
fi

if [[ ! -f "$STATE" ]]; then
  echo "{}" > "$STATE"
fi

python3 - "$STATE" "$MODE" <<'PY'
import json, sys
state_path, mode = sys.argv[1], sys.argv[2]
with open(state_path, encoding="utf-8") as f:
    state = json.load(f)
state.setdefault("mode", "manual")
state.setdefault("max_tasks_per_session", 3)
state["mode"] = mode
state["session_task_count"] = 0  # 切替時にリセット
if mode == "auto":
    state["active"] = True  # auto モードは即時活性化
with open(state_path, "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
print(f"✅ mode={mode} / session_task_count=0")
PY

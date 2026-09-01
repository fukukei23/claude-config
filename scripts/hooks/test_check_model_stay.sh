#!/usr/bin/env bash
# test_check_model_stay.sh — Stop hookの実測テスト（fixture + 一時PROJECTS_DIRで隔離）
set -uo pipefail
HOOK="$HOME/.claude/scripts/hooks/check-model-stay.sh"
TD=$(mktemp -d)
trap 'rm -rf "$TD"' EXIT
mkdir -p "$TD/state" "$TD/proj"
python3 - "$TD" <<'EOF'
import json, sys
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone.utc)
lines = [json.dumps({"type": "assistant", "timestamp": (now - timedelta(minutes=40)).isoformat(),
                     "message": {"model": "glm-5.3"}}) for _ in range(6)]
open(sys.argv[1] + "/proj/t53.jsonl", "w").write("\n".join(lines) + "\n")
EOF
export MODEL_STAY_PROJECTS_DIR="$TD/proj"
export MODEL_STAY_FORCE=1

# ケース1: 該当 → exit 2 + stderr警告
out=$(echo '{"session_id":"testsess"}' | bash "$HOOK" 2>&1 >/dev/null); rc=$?
[ "$rc" -eq 2 ] && echo "$out" | grep -q "戻し忘れ" && echo "CASE1 PASS (rc=$rc)" || { echo "CASE1 FAIL (rc=$rc out=$out)"; exit 1; }

# ケース2: flashのみ → exit 0（静観）
python3 - "$TD" <<'EOF'
import json, sys
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone.utc)
lines = [json.dumps({"type": "assistant", "timestamp": (now - timedelta(minutes=40)).isoformat(),
                     "message": {"model": "glm-5.3-flash"}}) for _ in range(9)]
open(sys.argv[1] + "/proj/tflash.jsonl", "w").write("\n".join(lines) + "\n")
EOF
rm -f "$TD/proj/t53.jsonl"
echo '{"session_id":"testsess2"}' | bash "$HOOK" >/dev/null 2>&1; rc=$?
[ "$rc" -eq 0 ] && echo "CASE2 PASS (rc=$rc)" || { echo "CASE2 FAIL (rc=$rc)"; exit 1; }

# ケース3: 効果測定ログへ1行追記されている（ケース1の副作用）
grep -q '"session_id": "testsess"' "$HOME/.claude/state/model5-3-warn-log.jsonl" \
  && echo "CASE3 PASS (warn-log追記あり)" || { echo "CASE3 FAIL"; exit 1; }

echo "ALL PASS"

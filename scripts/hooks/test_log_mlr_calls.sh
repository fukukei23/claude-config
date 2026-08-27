#!/usr/bin/env bash
# test_log_mlr_calls.sh — log-mlr-calls.sh のテスト
# spec: obsidian-ssot/docs/superpowers/specs/2026-08-21-multi-llm-review-failure-log-design.md
#
# 実行: bash scripts/hooks/test_log_mlr_calls.sh
# 前提: python3 が PATH にあること（Windows/WSL どちらでも可）

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$SCRIPT_DIR/log-mlr-calls.sh"

PASS=0
FAIL=0

ok()   { PASS=$((PASS+1)); echo "  ✅ $1"; }
ng()   { FAIL=$((FAIL+1)); echo "  ❌ $1"; [ -n "${2:-}" ] && echo "     └ $2"; }

# 一時 state ディレクトリ（本番ログを汚さない）
TMP_STATE="$(mktemp -d)"
trap 'rm -rf "$TMP_STATE"' EXIT
LOG="$TMP_STATE/multi-llm-review.jsonl"

# hook を隔離環境で実行（stdin=JSON・stdout/stderrは捨てる）
run_hook() {
  MLR_STATE_DIR="$TMP_STATE" bash "$HOOK" >/dev/null 2>&1
  echo $?
}

reset_log() { : > "$LOG"; }

# JSONL の最終行から特定フィールドを取り出す
last_field() {
  PYTHONIOENCODING=utf-8 python3 -c "
import json,sys
p=sys.argv[1]; k=sys.argv[2]
try:
    lines=[l for l in open(p,encoding='utf-8').read().splitlines() if l.strip()]
except FileNotFoundError:
    print('__NOFILE__'); raise SystemExit
if not lines:
    print('__EMPTY__'); raise SystemExit
d=json.loads(lines[-1])
v=d.get(k,'__MISSING__')
print('null' if v is None else v)
" "$LOG" "$1"
}

line_count() {
  [ -f "$LOG" ] || { echo 0; return; }
  PYTHONIOENCODING=utf-8 python3 -c "
import sys
print(sum(1 for l in open(sys.argv[1],encoding='utf-8') if l.strip()))
" "$LOG"
}

echo "=== log-mlr-calls.sh テスト ==="

# ---------------------------------------------------------------
echo "[1] 構文チェック（bash -n）"
if bash -n "$HOOK" 2>/dev/null; then
  ok "bash -n 通過"
else
  ng "bash -n 失敗（構文エラー）" "これがあると全PostToolUseが止まる"
  echo "構文エラーのため以降のテストを中止"; exit 1
fi

# ---------------------------------------------------------------
echo "[2] 対象外ツールは記録しない（早期リターン）"
reset_log
rc=$(echo '{"tool_name":"Read","tool_input":{"file_path":"/tmp/a"},"tool_response":{}}' | run_hook)
[ "$rc" = "0" ] && ok "exit 0" || ng "exit $rc（0であるべき）"
[ "$(line_count)" = "0" ] && ok "1行も書かれない" || ng "行が書かれた（$(line_count)行）"

# ---------------------------------------------------------------
echo "[3] MiniMax MCP 呼出を記録する"
reset_log
rc=$(echo '{"tool_name":"mcp__minimax__minimax_ask","tool_input":{"prompt":"review this"},"tool_response":"[{\"issue\":\"x\"}]"}' | run_hook)
[ "$rc" = "0" ] && ok "exit 0" || ng "exit $rc"
[ "$(line_count)" = "1" ] && ok "1行 append" || ng "行数 $(line_count)（1であるべき）"
[ "$(last_field llm)" = "minimax" ] && ok "llm=minimax" || ng "llm=$(last_field llm)"
[ "$(last_field status)" = "raw" ] && ok "status=raw" || ng "status=$(last_field status)"
[ "$(last_field result)" = "ok" ] && ok "result=ok（本文あり）" || ng "result=$(last_field result)"
[ "$(last_field http)" = "null" ] && ok "http=null（MCP経由）" || ng "http=$(last_field http)"
[ "$(last_field finish_reason)" = "null" ] && ok "finish_reason=null（MCP経由）" || ng "finish_reason=$(last_field finish_reason)"
[ "$(last_field findings)" = "null" ] && ok "findings=null（ホスト補記待ち）" || ng "findings=$(last_field findings)"
[ "$(last_field round_id)" = "null" ] && ok "round_id=null（ホスト補記待ち）" || ng "round_id=$(last_field round_id)"
[ "$(last_field backlogged)" = "False" ] && ok "backlogged=false" || ng "backlogged=$(last_field backlogged)"

# ---------------------------------------------------------------
echo "[4] GLM MCP 呼出を記録する"
reset_log
echo '{"tool_name":"mcp__glm__glm_ask","tool_input":{"prompt":"x"},"tool_response":"result text"}' | run_hook >/dev/null
[ "$(last_field llm)" = "glm" ] && ok "llm=glm" || ng "llm=$(last_field llm)"

# ---------------------------------------------------------------
echo "[5] Gemini curl（ドメイン一致）を記録しモデルを抽出する"
reset_log
cat <<'EOF' | run_hook >/dev/null
{"tool_name":"Bash","tool_input":{"command":"curl -s -H 'Content-Type: application/json' -d @/tmp/req_gemini.json \"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-pro-preview:generateContent?key=$GEMINI_API_KEY\""},"tool_response":{"stdout":"{\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"[{\\\"issue\\\":\\\"a\\\"}]\"}]},\"finishReason\":\"STOP\"}]}","stderr":"","interrupted":false}}
EOF
[ "$(last_field llm)" = "gemini" ] && ok "llm=gemini" || ng "llm=$(last_field llm)"
[ "$(last_field model)" = "gemini-3.1-pro-preview" ] && ok "model 抽出成功" || ng "model=$(last_field model)"
[ "$(last_field result)" = "ok" ] && ok "result=ok" || ng "result=$(last_field result)"
[ "$(last_field finish_reason)" = "STOP" ] && ok "finish_reason=STOP" || ng "finish_reason=$(last_field finish_reason)"

# ---------------------------------------------------------------
echo "[6] 機密を書かない（コマンド全文・APIキーを記録しない）"
reset_log
cat <<'EOF' | run_hook >/dev/null
{"tool_name":"Bash","tool_input":{"command":"curl -s -H 'Authorization: Bearer sk-or-v1-SECRETVALUE123' https://openrouter.ai/api/v1/chat/completions -d @/tmp/req_or.json"},"tool_response":{"stdout":"{\"choices\":[{\"message\":{\"content\":\"ok\"},\"finish_reason\":\"stop\"}]}","stderr":""}}
EOF
if grep -q 'SECRETVALUE123' "$LOG" 2>/dev/null; then
  ng "APIキーがログに混入した" "spec §3 機密の扱い違反"
else
  ok "APIキーがログに含まれない"
fi
if grep -q 'curl -s' "$LOG" 2>/dev/null; then
  ng "コマンド全文がログに混入した"
else
  ok "コマンド全文がログに含まれない"
fi
[ "$(last_field llm)" = "openrouter" ] && ok "llm=openrouter" || ng "llm=$(last_field llm)"

# ---------------------------------------------------------------
echo "[7] 無関係な curl は記録しない（allowlist 完全一致）"
reset_log
echo '{"tool_name":"Bash","tool_input":{"command":"curl -s https://api.github.com/repos/foo/bar"},"tool_response":{"stdout":"{}","stderr":""}}' | run_hook >/dev/null
[ "$(line_count)" = "0" ] && ok "github.com は記録されない" || ng "無関係curlが記録された"

reset_log
echo '{"tool_name":"Bash","tool_input":{"command":"curl -s https://openrouter.ai/api/v1/key -H \"Authorization: Bearer $OPENROUTER_API_KEY\""},"tool_response":{"stdout":"{\"data\":{}}","stderr":""}}' | run_hook >/dev/null
[ "$(line_count)" = "0" ] && ok "/api/v1/key（疎通確認）は除外される" || ng "疎通確認が記録された"

reset_log
echo '{"tool_name":"Bash","tool_input":{"command":"curl -s https://openrouter.ai/api/v1/models"},"tool_response":{"stdout":"{\"data\":[]}","stderr":""}}' | run_hook >/dev/null
[ "$(line_count)" = "0" ] && ok "/api/v1/models（モデル一覧）は除外される" || ng "モデル一覧取得が記録された"

# ---------------------------------------------------------------
echo "[8] 判定表 §5: HTTP 200 だが本文が空 → fail/empty_body_keepalive_only"
reset_log
cat <<'EOF' | run_hook >/dev/null
{"tool_name":"Bash","tool_input":{"command":"curl -s https://openrouter.ai/api/v1/chat/completions -d @/tmp/req_or.json"},"tool_response":{"stdout":"{\"choices\":[{\"message\":{\"content\":\"\"},\"finish_reason\":\"stop\"}]}","stderr":""}}
EOF
[ "$(last_field result)" = "fail" ] && ok "result=fail" || ng "result=$(last_field result)"
[ "$(last_field reason)" = "empty_body_keepalive_only" ] && ok "reason=empty_body_keepalive_only" || ng "reason=$(last_field reason)"

# ---------------------------------------------------------------
echo "[9] 判定表 §5: 思考のみで枠切れ → fail/thinking_overflow"
reset_log
cat <<'EOF' | run_hook >/dev/null
{"tool_name":"Bash","tool_input":{"command":"curl -s https://openrouter.ai/api/v1/chat/completions -d @/tmp/req_or.json"},"tool_response":{"stdout":"{\"choices\":[{\"message\":{\"content\":null,\"reasoning\":\"let me think about this deeply...\"},\"finish_reason\":\"length\"}]}","stderr":""}}
EOF
[ "$(last_field result)" = "fail" ] && ok "result=fail" || ng "result=$(last_field result)"
[ "$(last_field reason)" = "thinking_overflow" ] && ok "reason=thinking_overflow（2026-08-21真因）" || ng "reason=$(last_field reason)"
[ "$(last_field finish_reason)" = "length" ] && ok "finish_reason=length" || ng "finish_reason=$(last_field finish_reason)"

# ---------------------------------------------------------------
echo "[10] Gemini MAX_TOKENS 空応答 → fail/thinking_overflow"
reset_log
cat <<'EOF' | run_hook >/dev/null
{"tool_name":"Bash","tool_input":{"command":"curl -s -d @/tmp/req_gemini.json https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-pro-preview:generateContent"},"tool_response":{"stdout":"{\"candidates\":[{\"content\":{\"parts\":[]},\"finishReason\":\"MAX_TOKENS\"}]}","stderr":""}}
EOF
[ "$(last_field result)" = "fail" ] && ok "result=fail" || ng "result=$(last_field result)"
[ "$(last_field reason)" = "thinking_overflow" ] && ok "reason=thinking_overflow" || ng "reason=$(last_field reason)"

# ---------------------------------------------------------------
echo "[11] エラー応答のマッピング（401 / 429 / 402）"
for pair in "401 auth_401" "429 rate_limited_429" "402 payment_required_402"; do
  code="${pair% *}"; expect="${pair#* }"
  reset_log
  printf '{"tool_name":"Bash","tool_input":{"command":"curl -s https://openrouter.ai/api/v1/chat/completions -d @/tmp/req_or.json"},"tool_response":{"stdout":"{\\"error\\":{\\"code\\":%s,\\"message\\":\\"nope\\"}}","stderr":""}}\n' "$code" | run_hook >/dev/null
  got_r="$(last_field result)"; got_reason="$(last_field reason)"; got_http="$(last_field http)"
  [ "$got_r" = "fail" ] && [ "$got_reason" = "$expect" ] && [ "$got_http" = "$code" ] \
    && ok "code=$code → fail/$expect/http=$code" \
    || ng "code=$code → result=$got_r reason=$got_reason http=$got_http（期待 fail/$expect/$code）"
done

# ---------------------------------------------------------------
echo "[12] 壊れた入力でもクラッシュしない（exit 0・記録なし）"
reset_log
rc=$(echo 'this is not json at all' | run_hook)
[ "$rc" = "0" ] && ok "不正JSONで exit 0" || ng "exit $rc（0であるべき・非0だとツール実行が阻害される）"
[ "$(line_count)" = "0" ] && ok "記録なし" || ng "壊れた入力が記録された"

reset_log
rc=$(printf '' | run_hook)
[ "$rc" = "0" ] && ok "空入力で exit 0" || ng "exit $rc"

reset_log
rc=$(echo '{"tool_name":"Bash"}' | run_hook)
[ "$rc" = "0" ] && ok "tool_input 欠落で exit 0" || ng "exit $rc"
[ "$(line_count)" = "0" ] && ok "記録なし" || ng "記録された"

# ---------------------------------------------------------------
echo "[13] 追記であって上書きでない（複数呼出が積み上がる）"
reset_log
for i in 1 2 3; do
  echo '{"tool_name":"mcp__minimax__minimax_ask","tool_input":{},"tool_response":"x"}' | run_hook >/dev/null
done
[ "$(line_count)" = "3" ] && ok "3行に積み上がる" || ng "行数 $(line_count)（3であるべき）"

# ---------------------------------------------------------------
echo "[14] state ディレクトリが無くても自動作成する"
rm -rf "$TMP_STATE/sub"
MLR_STATE_DIR="$TMP_STATE/sub" bash "$HOOK" >/dev/null 2>&1 <<'EOF'
{"tool_name":"mcp__minimax__minimax_ask","tool_input":{},"tool_response":"x"}
EOF
[ -f "$TMP_STATE/sub/multi-llm-review.jsonl" ] && ok "ディレクトリを作って書き込む" || ng "書き込めなかった"

# ---------------------------------------------------------------
echo "[15] ts が ISO8601 形式"
reset_log
echo '{"tool_name":"mcp__minimax__minimax_ask","tool_input":{},"tool_response":"x"}' | run_hook >/dev/null
ts="$(last_field ts)"
if echo "$ts" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}'; then
  ok "ts=$ts"
else
  ng "ts の形式が不正: $ts"
fi

echo
echo "=== 結果: PASS=$PASS FAIL=$FAIL ==="
[ "$FAIL" -eq 0 ] || exit 1

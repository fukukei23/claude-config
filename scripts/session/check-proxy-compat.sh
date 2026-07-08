#!/usr/bin/env bash
# check-proxy-compat.sh — CC版変化時にプロキシ互換性を検証（SessionStart hook・Phase1手動）
# spec: docs/superpowers/specs/2026-07-08-proxy-compat-check-hook-design.md (v2)
# 立ち位置: 致命的即死のみ防止（表面チェックはすり抜ける前提・常にexit 0・ブロックしない）
# Phase1: settings.json未登録・手動 `bash check-proxy-compat.sh` で検証
set -uo pipefail

# 絶対パス固定（CLAUDE.md指示: $HOMEがWindows側に解決されるCron対策・本環境1ユーザー固定）
STATE_FILE="/home/yn4416/.claude/state/proxy-compat.json"
SETTINGS="/home/yn4416/.claude/settings.json"
BASE_URL="${BASE_URL:-http://127.0.0.1:8787}"
MODEL="glm-4.5-air"
TIMEOUT_CONNECT=2
TIMEOUT_MAX=5
PROXY_UNIT="glm-rate-proxy"

# state読込（cc_version/status/last_ok_version を3行で出力・不正時は空行3つ）
read_state() {
  if [ -f "$STATE_FILE" ]; then
    STATE_FILE="$STATE_FILE" python3 -c "
import json,os
try:
    d=json.load(open(os.environ['STATE_FILE']))
    print(d.get('cc_version','')); print(d.get('status','')); print(d.get('last_ok_version',''))
except Exception:
    print(''); print(''); print('')
" 2>/dev/null
  else
    printf '\n\n\n'
  fi
}

# state原子的書込み（mktemp→os.replace・書込み失敗時は非0）
write_state() {
  WS_CC="$1" WS_STATUS="$2" WS_DETAIL="$3" WS_LAST_OK="$4" \
  STATE_FILE="$STATE_FILE" python3 -c "
import json,datetime,os,tempfile
d={'cc_version':os.environ['WS_CC'],'status':os.environ['WS_STATUS'],
   'checked_at':datetime.datetime.now().isoformat(timespec='seconds'),
   'detail':os.environ['WS_DETAIL'],'last_ok_version':os.environ['WS_LAST_OK']}
sf=os.environ['STATE_FILE']
os.makedirs(os.path.dirname(sf),exist_ok=True)
tf=tempfile.NamedTemporaryFile('w',dir=os.path.dirname(sf),delete=False,encoding='utf-8')
json.dump(d,tf,ensure_ascii=False,indent=2);tf.close()
os.replace(tf.name,sf)
" 2>/dev/null
}

# 警告バナー（fail/proxy_down時）
banner() {
  printf '\n\033[1;33m⚠️ [proxy-compat] %s\033[0m\n\n' "$1"
}

# --- メイン ---

# 1. 現在版取得（SemVer抽出・失敗時は静かにexit）
# 0. 依存コマンド事前チェック（不在→静かにskip・推奨A反映）
for cmd in claude python3 curl systemctl; do
  command -v "$cmd" >/dev/null 2>&1 || exit 0
done

# 1. 現在版取得（SemVer抽出・pipefail対策で || true・推奨D反映）
CURRENT=$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
if [ -z "$CURRENT" ]; then exit 0; fi

# 2-3. state読込・検証要否判定（同版かつ前回ok→省略・#1反映: 非okなら再検証）
STATE_LINES=$(read_state)
STATE_CC=$(echo "$STATE_LINES" | sed -n '1p')
STATE_STATUS=$(echo "$STATE_LINES" | sed -n '2p')
STATE_LAST_OK=$(echo "$STATE_LINES" | sed -n '3p')
if [ "$CURRENT" = "$STATE_CC" ] && [ "$STATE_STATUS" = "ok" ]; then
  exit 0
fi

# 4. プロキシ稼働確認（active以外→proxy_down分離・#1 doubt）
PROXY_STATE=$(systemctl --user is-active "$PROXY_UNIT" 2>/dev/null || echo "inactive")
if [ "$PROXY_STATE" != "active" ]; then
  write_state "$CURRENT" "proxy_down" "プロキシ $PROXY_STATE" "${STATE_LAST_OK:-}" || true
  banner "プロキシ停止中($PROXY_STATE)・互換性検証スキップ. 起動: systemctl --user start $PROXY_UNIT"
  exit 0
fi

# 5. token取得（空→skipped・安全側）
TOKEN=$(SETTINGS="$SETTINGS" python3 -c "import json,os;print(json.load(open(os.environ['SETTINGS']))['env'].get('ANTHROPIC_AUTH_TOKEN',''))" 2>/dev/null || echo "")
if [ -z "$TOKEN" ]; then
  write_state "$CURRENT" "skipped" "token未設定" "${STATE_LAST_OK:-}" || true
  exit 0
fi

# 6. 検証実行（curl二段化・tokenはstdin経由で漏洩防止・trapで確実クリーンアップ）
BODY_FILE=$(mktemp) || { exit 0; }
trap 'rm -f "$BODY_FILE"' EXIT
: > "$BODY_FILE"
PAYLOAD=$(printf '{"model":"%s","max_tokens":64,"tools":[{"name":"probe","description":"compat check","input_schema":{"type":"object","properties":{}}}],"messages":[{"role":"user","content":"Call the probe tool"}]}' "$MODEL")
HEADERS=$(printf 'x-api-key: %s\nanthropic-version: 2023-06-01\ncontent-type: application/json\n' "$TOKEN")
CODE=$(curl -s --connect-timeout "$TIMEOUT_CONNECT" --max-time "$TIMEOUT_MAX" \
    -X POST "$BASE_URL/v1/messages" \
    --header @- \
    -d "$PAYLOAD" \
    -o "$BODY_FILE" -w '%{http_code}' <<< "$HEADERS" 2>/dev/null) || CODE="000"
BODY=$(cat "$BODY_FILE" 2>/dev/null)
DOWNGRADE="npm install -g @anthropic-ai/claude-code@${STATE_LAST_OK:-<1つ前の版>}"

# 7-8. 判定・state更新・警告
if [ "$CODE" = "200" ]; then
  HAS_TU=$(echo "$BODY" | python3 -c "import sys,json;d=json.load(sys.stdin);print(any(b.get('type')=='tool_use' for b in d.get('content',[])))" 2>/dev/null || echo "False")
  if [ "$HAS_TU" = "True" ]; then
    write_state "$CURRENT" "ok" "tool_use正常応答" "$CURRENT" || true
    exit 0
  else
    write_state "$CURRENT" "fail" "HTTP200だがtool_use不在" "${STATE_LAST_OK:-}" || true
    banner "プロキシ互換性異常の可能性($CURRENT)・tool_use応答なし. ダウングレード検討: $DOWNGRADE"
    exit 0
  fi
else
  write_state "$CURRENT" "fail" "HTTP $CODE" "${STATE_LAST_OK:-}" || true
  banner "プロキシ互換性異常の可能性($CURRENT)・HTTP $CODE. ダウングレード検討: $DOWNGRADE"
  exit 0
fi

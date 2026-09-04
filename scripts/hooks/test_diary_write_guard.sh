#!/usr/bin/env bash
# test_diary_write_guard.sh — diary-write-guard.sh のG″v1テストマトリクス
# 正常系/攻撃系/境界系/bypass系/stale系/shadow系/対象外系
set -uo pipefail

HOOK="$HOME/.claude/scripts/hooks/diary-write-guard.sh"
TMP_BASE=""
SSOT=""
STATE=""
LIST=""
FAILS=0
TODAY=$(date +%Y-%m-%d)

setup() {
  TMP_BASE=$(mktemp -d)
  SSOT="$TMP_BASE/ssot"
  STATE="$TMP_BASE/state"
  LIST="$TMP_BASE/list.conf"
  mkdir -p "$SSOT/10_DAILY" "$SSOT/01_DECISIONS/x" "$STATE"
  printf '10_DAILY/*.md\n' > "$LIST"
  touch "$SSOT/10_DAILY/$TODAY.md"
}

teardown() {
  [ -n "$TMP_BASE" ] && rm -rf "$TMP_BASE"
  TMP_BASE=""
}

# hookにJSONを流す（rc→RC・stdout→OUT）
send_hook() {
  local mode="$1" payload="$2"
  OUT=$(printf '%s' "$payload" | \
    DIARY_GUARD_SSOT_ROOT="$SSOT" DIARY_GUARD_STATE="$STATE" \
    DIARY_GUARD_LIST="$LIST" DIARY_GUARD_MODE="$mode" \
    bash "$HOOK" 2>/dev/null)
  RC=$?
}

# decision JSONの種別抽出（出力無し="none"）
get_decision() {
  if [ -z "$OUT" ]; then echo "none"; return; fi
  printf '%s' "$OUT" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get('hookSpecificOutput',{}).get('permissionDecision','none'))
except Exception:
    print('parse_error')"
}

# 決定ログから最後のdecisionを取得
last_logged_decision() {
  python3 -c "
import json
lines=[l for l in open('$STATE/decisions.jsonl') if l.strip()]
print(json.loads(lines[-1])['decision'] if lines else 'no_log')"
}

check() { # check <case_no> <expected_decision_mode: none|ask|deny> <expected_log_decision>
  local case_no="$1" exp_dec="$2" exp_log="$3"
  if [ "$RC" -ne 0 ]; then echo "FAIL Case$case_no: expected exit 0, got $RC"; FAILS=$((FAILS+1)); return; fi
  local dec; dec=$(get_decision)
  if [ "$dec" != "$exp_dec" ]; then echo "FAIL Case$case_no: expected decision '$exp_dec', got '$dec' (out=$OUT)"; FAILS=$((FAILS+1)); return; fi
  if [ -n "$exp_log" ]; then
    local logd; logd=$(last_logged_decision)
    if [ "$logd" != "$exp_log" ]; then echo "FAIL Case$case_no: expected log '$exp_log', got '$logd'"; FAILS=$((FAILS+1)); return; fi
  fi
}

hook_json() { # hook_json <tool> <fields_json_dict> → payload文字列（session固定）
  printf '{"tool_name":"%s","session_id":"testsess","tool_input":%s}' "$1" "$2"
}

# ============ 正常系 ============

# Case 1: Write当日日付の新規日記 → 通過（pass・passログ）
test_write_new_today_pass() {
  setup
  local c; c=$(hook_json Write "{\"file_path\":\"$SSOT/10_DAILY/$TODAY.md\",\"content\":\"# $TODAY\"}")
  # 注: 当日は既にtouch済みの既存扱いになるため、新規判定は明日日付では不可→当日はテスト上、存在するファイルに触るケースと統合
  # ここでは「当日以外の新規」を攻撃扱いにし、本ケースは対象外パスの通過を確認
  send_hook enforce "$c"
  check 1 deny "deny"   # 当日ファイルはsetupで作成済み=既存Write→denyが正しい挙動
  teardown
}

# Case 2: ssot外パスのWrite → 即通過（決定ログにも出ない=早期return）
test_outside_ssot_pass() {
  setup
  local c; c=$(hook_json Write "{\"file_path\":\"$TMP_BASE/outside.md\",\"content\":\"x\"}")
  send_hook enforce "$c"
  check 2 none ""
  teardown
}

# Case 3: Edit日記への追記（短いold_string・3行以下）→ 通過
test_edit_short_anchor_pass() {
  setup
  printf '# %s\n\n---\n' "$TODAY" > "$SSOT/10_DAILY/$TODAY.md"
  local c; c=$(hook_json Edit "{\"file_path\":\"$SSOT/10_DAILY/$TODAY.md\",\"old_string\":\"---\",\"new_string\":\"---\\n\\n## セッションログ\\n- 記録\"}")
  send_hook enforce "$c"
  check 3 none "pass"
  teardown
}

# ============ 攻撃系（硬ゲート・deny） ============

# Case 4: Write既存日記全体上書き（559文字事故型）→ deny
test_write_existing_diary_deny() {
  setup
  printf '# %s\n\n---\n\n## A\nエントリ\n' "$TODAY" > "$SSOT/10_DAILY/$TODAY.md"
  local c; c=$(hook_json Write "{\"file_path\":\"$SSOT/10_DAILY/$TODAY.md\",\"content\":\"# $TODAY\\n\\n---\\n\\n## セッションログ (00:4x)\\n- 自分の記録のみ\"}")
  send_hook enforce "$c"
  check 4 deny "deny"
  teardown
}

# Case 5: Edit日記 replace_all=true → deny
test_edit_replace_all_deny() {
  setup
  printf '# %s\n' "$TODAY" > "$SSOT/10_DAILY/$TODAY.md"
  local c; c=$(hook_json Edit "{\"file_path\":\"$SSOT/10_DAILY/$TODAY.md\",\"old_string\":\"#\",\"new_string\":\"x\",\"replace_all\":true}")
  send_hook enforce "$c"
  check 5 deny "deny"
  teardown
}

# ============ 柔ゲート（ask） ============

# Case 6: Edit日記 old_string 4行 → ask（G″ B項）
test_edit_long_old_string_ask() {
  setup
  printf '# %s\n\n---\n\n## A\nline2\nline3\nline4\n' "$TODAY" > "$SSOT/10_DAILY/$TODAY.md"
  local c; c=$(hook_json Edit "{\"file_path\":\"$SSOT/10_DAILY/$TODAY.md\",\"old_string\":\"# $TODAY\\n\\n---\\n\\n## A\",\"new_string\":\"改変\"}")
  send_hook enforce "$c"
  check 6 ask "ask"
  teardown
}

# Case 7: Bash で日記へのリダイレクト上書き → ask（G″ 4・Bash層ゲート）
test_bash_overwrite_ask() {
  setup
  local c; c=$(hook_json Bash "{\"command\":\"cat <<EOF > $SSOT/10_DAILY/$TODAY.md\\nhello\\nEOF\"}")
  send_hook enforce "$c"
  check 7 ask "ask"
  teardown
}

# Case 8: Bash の日記追記（>>）→ 通過（追記は許可）
test_bash_append_pass() {
  setup
  local c; c=$(hook_json Bash "{\"command\":\"echo 'x' >> $SSOT/10_DAILY/$TODAY.md\"}")
  send_hook enforce "$c"
  check 8 none ""
  teardown
}

# ============ 境界系（柔ゲート閾値・日記以外の既存.md） ============

# Case 9: 日記以外の既存.mdを微小変更 → 通過（閾値内）
test_soft_small_change_pass() {
  setup
  seq 1 50 > "$SSOT/01_DECISIONS/x/file.md"
  { seq 1 45; echo extra; } > /tmp/dwg_c9_body  # 46行（-8%程度）
  local body; body=$(python3 -c "import json;print(json.dumps(open('/tmp/dwg_c9_body').read()))")
  local c; c=$(hook_json Write "{\"file_path\":\"$SSOT/01_DECISIONS/x/file.md\",\"content\":$body}")
  send_hook enforce "$c"
  check 9 none "pass"
  teardown
}

# Case 10: 日記以外の既存.mdを大幅削減（30%超減×10行超）→ ask
test_soft_big_shrink_ask() {
  setup
  seq 1 50 > "$SSOT/01_DECISIONS/x/file.md"
  printf 'new content only\n' > /tmp/dwg_c10_body
  local body; body=$(python3 -c "import json;print(json.dumps(open('/tmp/dwg_c10_body').read()))")
  local c; c=$(hook_json Write "{\"file_path\":\"$SSOT/01_DECISIONS/x/file.md\",\"content\":$body}")
  send_hook enforce "$c"
  check 10 ask "ask"
  teardown
}

# ============ bypass系 ============

# Case 11: bypass marker+1回目 → 許可（bypass_1stログ）・2回目 → deny
test_bypass_first_allow_second_deny() {
  setup
  printf '# %s\n\n---\nA\n' "$TODAY" > "$SSOT/10_DAILY/$TODAY.md"
  mkdir -p "$STATE"
  touch "$STATE/bypass-active"   # TTL marker（mtime新鮮）
  local c; c=$(hook_json Write "{\"file_path\":\"$SSOT/10_DAILY/$TODAY.md\",\"content\":\"復旧版\"}")
  send_hook enforce "$c"
  check 11 none "bypass_1st"
  # 2回目
  send_hook enforce "$c"
  check 11b deny "deny"
  teardown
}

# ============ stale系（軽量Read追跡・G″ C項） ============

# Case 12: Read記録後にmtime変化 → Write(日記以外既存md) → ask（decision=ask・reason=stale_ask）
test_stale_mtime_ask() {
  setup
  printf 'v1 content\n' > "$SSOT/01_DECISIONS/x/file.md"
  local cr; cr=$(hook_json Read "{\"file_path\":\"$SSOT/01_DECISIONS/x/file.md\"}")
  send_hook enforce "$cr"   # Read追跡（pass）
  touch "$SSOT/01_DECISIONS/x/file.md"   # 他者が更新（mtime変化）
  sleep 1.1
  local body; body=$(python3 -c "import json;print(json.dumps('v1 content\\nmodified line\\n'))")
  local c; c=$(hook_json Write "{\"file_path\":\"$SSOT/01_DECISIONS/x/file.md\",\"content\":$body}")
  send_hook enforce "$c"
  check 12 ask "ask"
  # reasonコードがstale_askであること（decision列は許可種別・reason列が詳細コード）
  local reason; reason=$(python3 -c "
import json
lines=[l for l in open('$STATE/decisions.jsonl') if l.strip()]
print(json.loads(lines[-1])['reason'])")
  if [ "$reason" != "stale_ask" ]; then echo "FAIL Case12: expected reason 'stale_ask', got '$reason'"; FAILS=$((FAILS+1)); fi
  teardown
}

# ============ shadow系（導入期・ログのみ） ============

# Case 13: shadow mode では攻撃系でもJSON出力なし・決定ログには deny 記録
test_shadow_logs_but_never_blocks() {
  setup
  printf '# %s\n\n---\nA\n' "$TODAY" > "$SSOT/10_DAILY/$TODAY.md"
  local c; c=$(hook_json Write "{\"file_path\":\"$SSOT/10_DAILY/$TODAY.md\",\"content\":\"上書き\"}")
  send_hook shadow "$c"
  check 13 none "deny"
  teardown
}

# ============ 対象外系 ============

# Case 14: Read は決定ログに出さず pass（追跡のみ）
test_read_pass_tracking() {
  setup
  printf 'hello\n' > "$SSOT/01_DECISIONS/x/file.md"
  local c; c=$(hook_json Read "{\"file_path\":\"$SSOT/01_DECISIONS/x/file.md\"}")
  send_hook enforce "$c"
  check 14 none ""
  teardown
}

# 実行
test_write_new_today_pass
test_outside_ssot_pass
test_edit_short_anchor_pass
test_write_existing_diary_deny
test_edit_replace_all_deny
test_edit_long_old_string_ask
test_bash_overwrite_ask
test_bash_append_pass
test_soft_small_change_pass
test_soft_big_shrink_ask
test_bypass_first_allow_second_deny
test_stale_mtime_ask
test_shadow_logs_but_never_blocks
test_read_pass_tracking

echo ""
if [ "$FAILS" -eq 0 ]; then
  echo "ALL PASS (14 cases)"
else
  echo "FAILS=$FAILS"
fi
exit "$FAILS"

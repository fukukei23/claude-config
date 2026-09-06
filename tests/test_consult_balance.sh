#!/usr/bin/env bash
# test_consult_balance.sh — consult-balance 2 hooksのテスト
# T1 inject: 相談トリガーで注入される / T2: 非相談で注入されない / T3: 短文無視
# T4 stop: 同意+反証なし→exit2 / T5: 反証あり→exit0 / T6: 同意なし→exit0
# T7: 同一メッセージ2回目は通過 / T8: shadowは通過(ログのみ) / T9: disabledでinject無効
set -uo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")/../scripts/session" && pwd)"
INJECT="$SCRIPTS_DIR/consult-balance-inject.sh"
CHECK="$SCRIPTS_DIR/check-consult-balance.sh"
TMP="$(mktemp -d)"
GUARD_DIR="$TMP/guard"
PASS=0; FAIL=0

note() { echo "  $1"; }
ok()   { PASS=$((PASS+1)); note "PASS: $1"; }
ng()   { FAIL=$((FAIL+1)); note "FAIL: $1"; }

make_transcript() { # $1=file $2=user_text $3=asst_text
  cat > "$1" <<EOF
{"type":"user","message":{"content":"$2"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"$3"}]}}
EOF
}

# T1 inject: 相談トリガー
OUT=$(echo '{"prompt":"この戦略でいいと思う？判断の参考にしたい"}' | GUARD_DIR="$GUARD_DIR" "$INJECT")
if echo "$OUT" | grep -q "\[consult-balance"; then ok "T1 相談トリガーで注入"; else ng "T1 相談トリガーで注入(out=$OUT)"; fi

# T2 inject: 非相談
OUT=$(echo '{"prompt":"昨日の問006について自分で解いてみた記録を整理していた"}' | GUARD_DIR="$GUARD_DIR" "$INJECT")
if [ -z "$OUT" ]; then ok "T2 非相談で注入なし"; else ng "T2 非相談で注入なし(out=$OUT)"; fi

# T3 inject: 短文
OUT=$(echo '{"prompt":"どう?"}' | GUARD_DIR="$GUARD_DIR" "$INJECT")
if [ -z "$OUT" ]; then ok "T3 短文は無視"; else ng "T3 短文は無視(out=$OUT)"; fi

# T4 stop: 同意+反証なし → exit2
GUARD_DIR="$TMP/g4" bash -c "mkdir -p '$TMP/g4'"
make_transcript "$TMP/t4.jsonl" "この戦略でいいと思う？判断の参考にしたい" "あなたの読みは正しいです。資格と受託実績の2本柱が良いでしょう。"
OUT=$(GUARD_DIR="$TMP/g4" MODE="warn" CLAUDE_CODE_SESSION_ID=testsess bash "$CHECK" < <(python3 -c "
import json; print(json.dumps({'transcript_path':'$TMP/t4.jsonl','session_id':'testsess'}))") 2>&1)
RC=$?
if [ "$RC" -eq 2 ] && echo "$OUT" | grep -q "反証"; then ok "T4 同意+反証なしでexit2"; else ng "T4 同意+反証なしでexit2(rc=$RC out=$OUT)"; fi

# T5 stop: 反証あり → exit0
make_transcript "$TMP/t5.jsonl" "この戦略でいいと思う？判断の参考にしたい" "方向性は賛成です。【反証】面接官がガイドを評価した実例があり、読まれない説は前提が崩れうる。"
OUT=$(GUARD_DIR="$TMP/g5" MODE="warn" CLAUDE_CODE_SESSION_ID=testsess5 bash "$CHECK" < <(python3 -c "
import json; print(json.dumps({'transcript_path':'$TMP/t5.jsonl','session_id':'testsess5'}))") 2>&1)
RC=$?
if [ "$RC" -eq 0 ]; then ok "T5 反証ありでexit0"; else ng "T5 反証ありでexit0(rc=$RC out=$OUT)"; fi

# T5b stop: 根拠付き同意 → exit0（案B・3機レビュー収束・「正しいことは正しいと言える」）
make_transcript "$TMP/t5b.jsonl" "この戦略でいいと思う？判断の参考にしたい" "賛成です。【根拠】AWS公式ドキュメント(2026-09)に日本語対応の記載があり、実測でも日本語受験を確認済みです。"
OUT=$(GUARD_DIR="$TMP/g5b" MODE="warn" CLAUDE_CODE_SESSION_ID=testsess5b bash "$CHECK" < <(python3 -c "
import json; print(json.dumps({'transcript_path':'$TMP/t5b.jsonl','session_id':'testsess5b'}))") 2>&1)
RC=$?
if [ "$RC" -eq 0 ]; then ok "T5b 根拠付き同意はexit0"; else ng "T5b 根拠付き同意はexit0(rc=$RC out=$OUT)"; fi

# T6 stop: 同意なし → exit0
make_transcript "$TMP/t6.jsonl" "この戦略でいいと思う？判断の参考にしたい" "2案を比較します。案Aは未検証の仮説と整合します。"
OUT=$(GUARD_DIR="$TMP/g6" MODE="warn" CLAUDE_CODE_SESSION_ID=testsess6 bash "$CHECK" < <(python3 -c "
import json; print(json.dumps({'transcript_path':'$TMP/t6.jsonl','session_id':'testsess6'}))") 2>&1)
RC=$?
if [ "$RC" -eq 0 ]; then ok "T6 同意なしでexit0"; else ng "T6 同意なしでexit0(rc=$RC)"; fi

# T7 stop: 同一メッセージ2回目は通過（hashガード）
OUT=$(GUARD_DIR="$TMP/g4" MODE="warn" CLAUDE_CODE_SESSION_ID=testsess bash "$CHECK" < <(python3 -c "
import json; print(json.dumps({'transcript_path':'$TMP/t4.jsonl','session_id':'testsess'}))") 2>&1)
RC=$?
if [ "$RC" -eq 0 ]; then ok "T7 同一メッセージ2回目は通過"; else ng "T7 同一メッセージ2回目は通過(rc=$RC)"; fi

# T8 stop: shadowモードは通過（ログのみ）
make_transcript "$TMP/t8.jsonl" "この方向でいいですか？意見を聞かせて" "その通りです。"
OUT=$(GUARD_DIR="$TMP/g8" CLAUDE_CONSULT_BALANCE_MODE=shadow CLAUDE_CODE_SESSION_ID=testsess8 bash "$CHECK" < <(python3 -c "
import json; print(json.dumps({'transcript_path':'$TMP/t8.jsonl','session_id':'testsess8'}))") 2>&1)
RC=$?
if [ "$RC" -eq 0 ] && grep -q "shadow-would-block" "$TMP/g8/dispatch.log" 2>/dev/null; then ok "T8 shadowで通過+ログ"; else ng "T8 shadowで通過+ログ(rc=$RC)"; fi

# T9 inject: disabled で無効
mkdir -p "$GUARD_DIR"
touch "$GUARD_DIR/disabled"
OUT=$(echo '{"prompt":"この戦略でいいと思う？判断の参考にしたい"}' | GUARD_DIR="$GUARD_DIR" "$INJECT")
if [ -z "$OUT" ]; then ok "T9 disabledで注入なし"; else ng "T9 disabledで注入なし(out=$OUT)"; fi

echo ""
echo "結果: PASS=$PASS FAIL=$FAIL"
rm -rf "$TMP"
[ "$FAIL" -eq 0 ]

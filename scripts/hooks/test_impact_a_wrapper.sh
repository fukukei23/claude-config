#!/bin/bash
# test_impact_a_wrapper.sh — PostToolUse 連携テスト

set -uo pipefail

HOOKS_DIR="$HOME/.claude/scripts/hooks"
WRAPPER="$HOOKS_DIR/impact-a-wrapper.sh"
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# 失敗カウンタファイル初期化
COUNTER="$HOME/.claude/state/impact-a-fail-count"
mkdir -p "$(dirname "$COUNTER")"
echo "0" > "$COUNTER"

# テスト1: BLACKLIST追加 → 注入される
echo "=== Test 1: BLACKLIST追加 → 推奨注入 ==="
INPUT='{"tool_name":"Edit","tool_input":{"file_path":"/tmp/test_impact_a.py","new_string":"BLACKLIST = [\"new\"]"},"tool_response":{}}'
OUT=$(echo "$INPUT" | bash "$WRAPPER" 2>/dev/null)
echo "出力: '$OUT'"
if echo "$OUT" | grep -q "impact-mode"; then
    echo "PASS: 注入確認"
else
    echo "FAIL: 注入なし"
    exit 1
fi

# テスト2: 通常変更 → 注入なし
echo ""
echo "=== Test 2: 通常変更 → 注入なし ==="
INPUT='{"tool_name":"Edit","tool_input":{"file_path":"/tmp/test_normal.py","new_string":"x = 1"},"tool_response":{}}'
OUT=$(echo "$INPUT" | bash "$WRAPPER" 2>/dev/null)
echo "出力: '$OUT'"
if [ -z "$OUT" ]; then
    echo "PASS: silent skip"
else
    echo "FAIL: 不要な注入"
    exit 1
fi

# テスト3: 検知失敗 → カウンタ増加
echo ""
echo "=== Test 3: 検知失敗 → カウンタ増加 ==="
ORIG="$HOME/projects/obsidian-ssot/00_SYSTEM/impact-antipatterns.md"
BAK="${ORIG}.bak"
cp "$ORIG" "$BAK"
# マーカー内の YAML を壊す（parser が例外を投げる＝検知失敗パスを強制）
cat > "$ORIG" <<'BROKEN'
<!-- impact-mode: antipatterns:v1 -->
```yaml
antipatterns:
  - id: AP-001
    trigger_keywords: [BLACKLIST
   broken
```
<!-- /impact-mode -->
BROKEN
INPUT='{"tool_name":"Edit","tool_input":{"file_path":"/tmp/foo.py","new_string":"BLACKLIST = []"},"tool_response":{}}'
echo "$INPUT" | bash "$WRAPPER" >/dev/null 2>&1
COUNTER_VAL=$(cat "$COUNTER")
echo "カウンタ: $COUNTER_VAL"
if [ "$COUNTER_VAL" -ge 1 ]; then
    echo "PASS: カウンタ記録"
else
    echo "FAIL: カウンタ未更新"
    cp "$BAK" "$ORIG"
    exit 1
fi
cp "$BAK" "$ORIG"
rm "$BAK"

echo ""
echo "=== ALL TESTS PASSED ==="
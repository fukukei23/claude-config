#!/bin/bash
# enforce-ssot-record.sh — 01_DECISIONS/ への手動Write/Editをブロックし ssot-record スキル経由を強制
#
# 仕組み:
# - PreToolUse hook で Write/Edit/MultiEdit ツールの file_path を検査
# - file_path が 01_DECISIONS/ を含み・フラグがない → exit 2（ブロック）
# - フラグ = ~/.claude/state/ssot-record-active-${CLAUDE_CODE_SESSION_ID}
#   （ssot-record スキルが開始時に作成・終了時に削除）
# - セッションID分離で並行セッションの誤許可を防止（他セッションのフラグで通らない）
#
# 2026-07-03 問題対策: 手動Writeで01_DECISIONS作成→_INDEX/frontmatter/自動化.mdの連携更新漏れ
# 2026-07-08 改修: /tmp(一時領域・sandbox で Bash 呼出間に消滅し機能不全) →
#                  ~/.claude/state/(永続領域) + セッションID分離。
#                  SESSION_ID 未取得時は glob フォールバック（いずれかのフラグ存在で許可・案1相当）。

set -euo pipefail

STATE_DIR="$HOME/.claude/state"
SID="${CLAUDE_CODE_SESSION_ID:-}"

# stdin から tool_input を読込
INPUT=$(cat)

# file_path を抽出（Write/Edit/MultiEdit の tool_input.file_path）
FILE_PATH=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    fp = d.get('file_path', '') or d.get('tool_input', {}).get('file_path', '')
    print(fp)
except Exception:
    print('')
" 2>/dev/null || echo "")

# フラグ判定（スキル経由か・TTL=6時間でstale扱い）
is_skill_active() {
    local TTL_SECONDS=$((6 * 3600))
    if [ -n "$SID" ]; then
        # セッションID別フラグ（自分のセッションのみ参照・並行セッション隔離）
        local flag="$STATE_DIR/ssot-record-active-$SID"
        if [ ! -f "$flag" ]; then
            return 1
        fi
        # TTL判定（2026-08-23 L26追加: 古いフラグは無効扱い）
        local mtime now age
        mtime=$(stat -c %Y "$flag" 2>/dev/null || echo 0)
        now=$(date +%s)
        age=$((now - mtime))
        if [ "$age" -ge "$TTL_SECONDS" ]; then
            # 古いフラグを削除してブロック
            rm -f "$flag"
            return 1
        fi
        return 0
    else
        # SESSION_ID未取得時フォールバック: いずれかのフラグ存在で許可（案1相当）
        compgen -G "$STATE_DIR/ssot-record-active-*" >/dev/null 2>&1
    fi
}

# 01_DECISIONS 配下でなければ許可
case "$FILE_PATH" in
    *01_DECISIONS/*)
        # 01_DECISIONS 配下・フラグ確認
        if is_skill_active; then
            # スキル経由（フラグあり）→ 許可
            exit 0
        else
            # 手動Write（フラグなし）→ ブロック
            cat <<'EOF' >&2
{
  "decision": "block",
  "reason": "01_DECISIONS/ への直接 Write/Edit は禁止です。ssot-record スキル経由のみ許可（_INDEX.md/frontmatter/自動化.md の連携更新を担保するため）。\n\n対応: 'ssot-record' スキルを Skill ツールで発動してください（ユーザーが「記録して」と言わなくても自発的に）。スキルが ~/.claude/state/ssot-record-active フラグを作成し、このブロックを通過できます。"
}
EOF
            exit 2
        fi
        ;;
    *)
        # 01_DECISIONS 配下以外は許可
        exit 0
        ;;
esac

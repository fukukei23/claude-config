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
# 2026-08-31 追加: 01_DECISIONS判定時に SID 有無を ~/.claude/state/ssot-record-sid-observe.jsonl へ
#                  観測記録（2026-07-08記録 L70-71 の残課題「取得実績の蓄積」「頻発なら別経路」の判定材料）。

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
# セキュリティ強化（2026-08-23 security review対応）:
#   - SID あり分岐: mtime を now で cap（未来日付改ざん対策）+ 所有者チェック
#   - SID なし分岐: 個別ファイルTTL判定で生きているもの1個以上が必要
is_skill_active() {
    local TTL_SECONDS=$((6 * 3600))
    local now
    now=$(date +%s)

    if [ -n "$SID" ]; then
        # セッションID別フラグ（自分のセッションのみ参照・並行セッション隔離）
        local flag="$STATE_DIR/ssot-record-active-$SID"
        if [ ! -f "$flag" ]; then
            return 1
        fi
        # 所有者チェック（symlink-to-other-user bypass 対策）
        if [ ! -O "$flag" ]; then
            return 1
        fi
        # TTL判定（mtime を now で cap → 未来日付は now 扱い → TTL超過）
        local mtime age
        mtime=$(stat -c %Y "$flag" 2>/dev/null || echo 0)
        mtime=$((mtime > now ? now : mtime))  # fail-open-state-drift 対策
        age=$((now - mtime))
        if [ "$age" -ge "$TTL_SECONDS" ]; then
            # 古いフラグを削除してブロック
            rm -f "$flag"
            return 1
        fi
        return 0
    else
        # SESSION_ID未取得時フォールバック（sibling-path-gate-parity 対策）:
        # いずれかのフラグが生きていれば許可、全部staleなら不許可
        local flag mtime age any_alive=1
        for flag in "$STATE_DIR"/ssot-record-active-*; do
            [ -f "$flag" ] || continue
            # 所有者チェック
            [ -O "$flag" ] || continue
            mtime=$(stat -c %Y "$flag" 2>/dev/null || echo 0)
            mtime=$((mtime > now ? now : mtime))
            age=$((now - mtime))
            if [ "$age" -lt "$TTL_SECONDS" ]; then
                any_alive=0
                break
            fi
        done
        return $any_alive
    fi
}

# SID取得実績の観測ログ（2026-08-31 追加）
# 2026-07-08記録 L70-71 の残課題「稼働後ログで SESSION_ID 取得実績を蓄積」
#   「globフォールバック（案1相当）が頻発するようなら SESSION_ID 取得を別経路で担保」
# の判定材料を貯める。判定が確定する 01_DECISIONS 分岐でのみ呼ぶ（他パスでは書かない＝肥大防止）。
# 追記失敗（state読取専用・ディスクフル等）で hook 本体を止めない（2026-07-08 の機能不全再発防止）。
SID_LOG="$STATE_DIR/ssot-record-sid-observe.jsonl"
log_sid_observation() {
    local decision="$1" present branch
    if [ -n "$SID" ]; then
        present=true
        branch=exact
    else
        present=false
        branch=glob_fallback
    fi
    { printf '{"ts":"%s","sid_present":%s,"branch":"%s","decision":"%s"}\n' \
        "$(date -Is)" "$present" "$branch" "$decision" >> "$SID_LOG"; } 2>/dev/null || true
}

# Windows Desktop版のパス区切り正規化（2026-08-30）
# Windows Desktop版は file_path を "\\\\wsl.localhost\\Ubuntu\\..." と
# バックスラッシュ区切りで渡すため、下の *01_DECISIONS/* に一致せず素通りしていた。
FILE_PATH=$(printf '%s' "$FILE_PATH" | tr '\\' '/')

# 01_DECISIONS 配下でなければ許可
case "$FILE_PATH" in
    *01_DECISIONS/*)
        # 01_DECISIONS 配下・フラグ確認
        if is_skill_active; then
            # スキル経由（フラグあり）→ 許可
            log_sid_observation allow
            exit 0
        else
            # 手動Write（フラグなし）→ ブロック
            log_sid_observation block
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

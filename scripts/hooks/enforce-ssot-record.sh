#!/bin/bash
# enforce-ssot-record.sh — 01_DECISIONS/ への手動Write/Editをブロックし ssot-record スキル経由を強制
#
# 仕組み:
# - PreToolUse hook で Write/Edit/MultiEdit ツールの file_path を検査
# - file_path が 01_DECISIONS/ を含み・/tmp/ssot-record-active フラグがない → exit 2（ブロック）
# - /tmp/ssot-record-active は ssot-record スキルが開始時に作成・終了時に削除
# - これにより「スキル経由のみ通る＝手動Writeでの連携更新抜け漏れを構造的根絶」
#
# 2026-07-03 問題対策: 手動Writeで01_DECISIONS作成→_INDEX/frontmatter/自動化.mdの連携更新漏れ

set -euo pipefail

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

# 01_DECISIONS 配下でなければ許可
case "$FILE_PATH" in
    *01_DECISIONS/*)
        # 01_DECISIONS 配下・フラグ確認
        if [ -f /tmp/ssot-record-active ]; then
            # スキル経由（フラグあり）→ 許可
            exit 0
        else
            # 手動Write（フラグなし）→ ブロック
            cat <<'EOF' >&2
{
  "decision": "block",
  "reason": "01_DECISIONS/ への直接 Write/Edit は禁止です。ssot-record スキル経由のみ許可（_INDEX.md/frontmatter/自動化.md の連携更新を担保するため）。\n\n対応: 'ssot-record' スキルを Skill ツールで発動してください（ユーザーが「記録して」と言わなくても自発的に）。スキルが /tmp/ssot-record-active フラグを作成し、このブロックを通過できます。"
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

#!/bin/bash
# PostToolUse hook: git commit を検出して SSOT記録トリガーを注入する

input=$(cat)

tool_name=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)
if [ "$tool_name" != "Bash" ]; then
    exit 0
fi

command=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)

if echo "$command" | grep -qE 'git\s+commit'; then
    commit_msg=$(echo "$command" | grep -oP '(?<=-m ")[^"]+' | head -1)
    if [ -z "$commit_msg" ]; then
        commit_msg="(メッセージ抽出不可)"
    fi

    echo ""
    echo "---"
    echo "[SSOT-RECORD-TRIGGER]"
    echo "git commit を検出しました。コミットメッセージ: $commit_msg"
    echo "このコミット内容を SSOT に自動記録してください（record-decision スキルを実行）。"
    echo "記録完了後、必ず '✅ SSOT記録完了: [保存先パス]' をレスポンスの末尾に表示すること。"
    echo "---"
fi

exit 0

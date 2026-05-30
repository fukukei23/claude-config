#!/bin/bash
# 自律タスクループ 手動起動スクリプト
#
# 使い方:
#   bash start.sh 76 77 78          # Issue番号を指定して実行
#   bash start.sh --auto <repo>     # GitHubから自動取得（priority順）
#
# 例:
#   bash start.sh 76 77
#   bash start.sh --auto atelier-kyo-manager

set -euo pipefail

STATE="$HOME/.claude/scripts/auto-dev/state.json"
LOG="$HOME/.claude/scripts/auto-dev/loop.log"
CLAUDE="/home/yn4416/.local/share/fnm/node-versions/v22.22.2/installation/bin/claude"

# ── --auto モード ──────────────────────────────────────────────
if [[ "${1:-}" == "--auto" ]]; then
    REPO="${2:-}"
    if [[ -z "$REPO" ]]; then
        echo "使い方: $0 --auto <repo名>"
        echo "例:     $0 --auto atelier-kyo-manager"
        exit 1
    fi

    echo "GitHub Issues を取得中: fukukei23/$REPO ..."

    ISSUES=$(python3 - <<EOF
import yaml, json, urllib.request

hosts = yaml.safe_load(open('/home/yn4416/.config/gh/hosts.yml'))
token = hosts['github.com']['oauth_token']

url = f'https://api.github.com/repos/fukukei23/$REPO/issues?state=open&per_page=50'
req = urllib.request.Request(url, headers={
    'Authorization': f'token {token}',
    'Accept': 'application/vnd.github.v3+json'
})
issues = json.load(urllib.request.urlopen(req))

# priority: high > medium > low、その他は末尾
priority_order = {'priority:high': 0, 'priority:medium': 1, 'priority:low': 2}

def get_priority(issue):
    labels = [l['name'] for l in issue['labels']]
    for p, v in priority_order.items():
        if p in labels:
            return v
    return 9

sorted_issues = sorted(issues, key=get_priority)
for i in sorted_issues:
    labels = [l['name'] for l in i['labels']]
    print(i['number'])
EOF
    )

    if [[ -z "$ISSUES" ]]; then
        echo "オープン Issue が見つかりませんでした"
        exit 0
    fi

    echo "取得した Issue 順: $(echo $ISSUES | tr '\n' ' ')"

    # state.json に repo_path を設定
    REPO_PATH=$(python3 -c "
import json
s=json.load(open('$STATE'))
# repo名からパスを推測
import os
candidates = [
    f'/home/yn4416/projects/$REPO',
    f'/home/yn4416/projects/{\"$REPO\".replace(\"-\",\"_\")}',
]
for c in candidates:
    if os.path.isdir(c):
        print(c)
        break
else:
    print(f'/home/yn4416/projects/$REPO')
")

    python3 - <<EOF2
import json
with open("$STATE") as f:
    state = json.load(f)
state['pending']   = [int(x) for x in """$ISSUES""".strip().split()]
state['active']    = True
state['current']   = None
state['completed'] = []
state['project']   = '$REPO'
state['repo_path'] = '$REPO_PATH'
with open("$STATE", 'w') as f:
    json.dump(state, f, indent=2)
print('キュー登録:', state['pending'])
EOF2

    FIRST_ISSUE=$(echo "$ISSUES" | head -1)

# ── 番号指定モード ─────────────────────────────────────────────
else
    if [[ $# -eq 0 ]]; then
        echo "使い方: $0 <issue番号> [issue番号 ...]"
        echo "       $0 --auto <repo名>"
        echo ""
        echo "現在の状態:"
        cat "$STATE"
        exit 1
    fi

    FIRST_ISSUE="${1}"

    python3 - <<EOF
import json
with open("$STATE") as f:
    state = json.load(f)
state['pending']   = [int(x) for x in "$*".split()]
state['active']    = True
state['current']   = None
state['completed'] = []
with open("$STATE", 'w') as f:
    json.dump(state, f, indent=2)
print('キュー登録:', state['pending'])
EOF
fi

# ── 共通: 最初の Issue を起動 ──────────────────────────────────
REPO_PATH=$(python3 -c "import json; print(json.load(open('$STATE'))['repo_path'])")
PROJECT=$(python3 -c "import json; print(json.load(open('$STATE'))['project'])")

echo ""
echo "=== 自律タスクループ 開始 ==="
echo "  プロジェクト: $PROJECT"
echo "  最初の Issue: #${FIRST_ISSUE}"
echo "  ログ: $LOG"
echo "=========================="

mkdir -p "$(dirname "$LOG")"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] === ループ開始: project=$PROJECT first=#$FIRST_ISSUE ===" >> "$LOG"

setsid bash /home/yn4416/.claude/scripts/auto-dev/run-issue.sh "$FIRST_ISSUE" &
echo "起動完了 (PID: $!)"

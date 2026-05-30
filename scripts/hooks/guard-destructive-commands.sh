#!/usr/bin/env bash
# guard-destructive-commands.sh — 破壊的コマンドをブロックするPreToolUse Hook
# exit 2 = ツール実行を中止 + メッセージ表示

INPUT=$(cat)

# python3でJSONパース（jq未インストール環境対応）
tool_name=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)
cmd=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)

if [[ "$tool_name" != "Bash" ]]; then
  exit 0
fi

# 危険パターン
DANGEROUS_PATTERNS=(
  'rm\s+-rf\s+/'
  'rm\s+--no-preserve-root'
  'rm\s+-r\s+/\s'
  'sudo\s+rm\s+(-r|-rf)\s+/'
  'dd\s+if=.*of=/dev/'
  'mkfs\.'
  '>\s*/dev/sd'
  'chmod\s+-R\s+777\s+/'
  'chown\s+-R\s+\w+\s+/'
  'git\s+push\s+--force\s+origin\s+(main|master)'
  'git\s+push\s+-f\s+origin\s+(main|master)'
  'git\s+reset\s+--hard'
  'DROP\s+DATABASE'
  'TRUNCATE\s+TABLE'
  'DELETE\s+FROM\s+\w+\s*;'
  'curl\s+.*\|\s*(ba)?sh'
  'wget\s+.*\|\s*(ba)?sh'
  'docker\s+system\s+prune\s+(-a|--all)'
  'docker\s+rm\s+-f\s+'
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$cmd" | grep -qiE "$pattern"; then
    echo "⛔ BLOCKED: 危険なコマンドを検出"
    echo "   コマンド: $cmd"
    echo "   理由: 元に戻せない破壊的操作の可能性"
    exit 2
  fi
done

exit 0

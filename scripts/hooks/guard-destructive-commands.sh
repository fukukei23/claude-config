#!/usr/bin/env bash
# guard-destructive-commands.sh — 破壊的コマンドをブロックするPreToolUse Hook
# exit 2 = ツール実行を中止 + メッセージ表示
#
# クロスプラットフォーム対応: python3/jq に依存せず純bashでJSON解析

INPUT=$(cat)

# --- JSON解析（python3/jq 不要）---
# tool_name を抽出: "tool_name":"Bash" → Bash
tool_name=$(printf '%s' "$INPUT" | grep -o '"tool_name":"[^"]*"' | head -1 | sed 's/^"tool_name":"//;s/"$//')

# command を抽出: "command":"..." → ...
cmd=$(printf '%s' "$INPUT" | sed -n 's/.*"command" *: *"\(.*\)".*/\1/p' | head -1)

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
  # --- Tier-1: インフラ破壊・スキーマ破壊（誤爆最小・明確に破壊的）---
  'terraform\s+destroy'
  'kubectl\s+delete\s+namespace'
  'helm\s+uninstall'
  'ALTER\s+TABLE\s+\w+\s+.*(DROP|RENAME)\s+COLUMN'
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

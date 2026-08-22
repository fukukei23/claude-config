#!/usr/bin/env bash
# guard-destructive-commands.sh — 破壊的コマンドをブロックするPreToolUse Hook
# exit 2 = ツール実行を中止 + メッセージ表示
#
# クロスプラットフォーム対応: python3/jq に依存せず純bashでJSON解析

INPUT=$(cat)

# --- JSON解析（python3/jq 不要）---
# tool_name を抽出: "tool_name":"Bash" / "tool_name": "Bash" のどちらも拾う
# ⚠️ コロン後の空白を許容すること（2026-08-22 事故）。Claude Code が渡すのは整形済みJSON
#    （"tool_name": "Bash"）で、空白非対応だと抽出が空になり全呼び出しが素通りしていた。
tool_name=$(printf '%s' "$INPUT" | grep -oE '"tool_name" *: *"[^"]*"' | head -1 | sed 's/^"tool_name" *: *"//;s/"$//')

# command を抽出: "command":"..." → ...
cmd=$(printf '%s' "$INPUT" | sed -n 's/.*"command" *: *"\(.*\)".*/\1/p' | head -1)

# tool_name が取れた上で Bash 以外なら対象外。
# 取れなかった場合（未知の入力形）は fail-closed で走査を続ける——
# 「解析できなかったから素通り」は防護層の意味を失わせるため。
if [[ -n "$tool_name" && "$tool_name" != "Bash" ]]; then
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
    # ブロック機構は2系統を併用する（2026-08-22 事故）:
    #   (1) stdout に {"decision":"block"} — Windows Desktop 版はこちらしか見ない。
    #       実証: 同じ PreToolUse グループの check-command-safety.py が本方式で実際に止めている。
    #   (2) exit 2 — 従来方式。WSL CLI 版はこちらを honor する。
    # (2) だけだと Windows Desktop 版で無言素通りする（実測済み）。
    esc=$(printf '%s' "$cmd" | sed 's/\\/\\\\/g; s/"/\\"/g')
    printf '{"decision": "block", "reason": "⛔ 破壊的コマンドを検出: %s — 元に戻せない操作の可能性があります"}\n' "$esc"
    echo "⛔ BLOCKED: 危険なコマンドを検出" >&2
    echo "   コマンド: $cmd" >&2
    echo "   理由: 元に戻せない破壊的操作の可能性" >&2
    # exit 0 で終えること。exit 2 を返すと stdout の JSON が無視され、
    # 実セッションで素通りする（2026-08-22 実測）。check-command-safety.py と同方式。
    exit 0
  fi
done

exit 0

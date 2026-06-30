#!/bin/bash
# MCPツール使い分けガイド と settings.json のMCPサーバー数を比較

SETTINGS="$HOME/.claude/settings.json"
GUIDE="$HOME/projects/obsidian-ssot/00_SYSTEM/MCPツール使い分けガイド.md"

if [ ! -f "$SETTINGS" ] || [ ! -f "$GUIDE" ]; then
  exit 0
fi

MCP_SERVERS=$(python3 -c "
import json
with open('$SETTINGS') as f:
    data = json.load(f)
servers = sorted(data.get('mcpServers', {}).keys())
print(' '.join(servers))
" 2>/dev/null)

if [ -z "$MCP_SERVERS" ]; then
  exit 0
fi

GUIDE_TOOLS=$(grep -oP '\*\*\K[a-zA-Z0-9_-]+(?=\*\*)' "$GUIDE" 2>/dev/null | sort -u)

MISSING=""
for server in $MCP_SERVERS; do
    if ! echo "$GUIDE_TOOLS" | grep -qi "^${server}$"; then
        MISSING="$MISSING $server"
    fi
done

if [ -n "$MISSING" ]; then
  MCP_MSG=" ⚠️ MCPガイド: 未記載${MISSING}"
fi

# --- Hooks差分検知 ---
SNAPSHOT="$HOME/projects/obsidian-ssot/00_SYSTEM/.hooks-snapshot.txt"

CURRENT_HOOKS=$(python3 -c "
import json
with open('$SETTINGS') as f:
    data = json.load(f)
hooks = data.get('hooks', {})
for event, matchers in hooks.items():
    for m in matchers:
        for h in m.get('hooks', []):
            print(f\"{event}\t{h.get('command', '')[:80]}\")
" 2>/dev/null)

if [ -n "$CURRENT_HOOKS" ]; then
  if [ -f "$SNAPSHOT" ]; then
    DIFF=$(diff <(cat "$SNAPSHOT") <(echo "$CURRENT_HOOKS") 2>/dev/null)
    if [ -n "$DIFF" ]; then
      HOOKS_MSG=" ⚠️ Hooks差分: automation.md更新が必要"
    fi
  fi
  echo "$CURRENT_HOOKS" > "$SNAPSHOT"
fi

# 問題なければOK
if [ -z "$MISSING" ] && [ -z "${DIFF:-}" ]; then
  MCP_MSG=" ✅ MCPガイド: 同期済み"
fi
mkdir -p /tmp/claude-startup
{ [ -n "${MCP_MSG:-}" ] && echo "$MCP_MSG"; [ -n "${HOOKS_MSG:-}" ] && echo "$HOOKS_MSG"; } > /tmp/claude-startup/mcp-guide.status
exit 0

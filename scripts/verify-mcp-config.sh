#!/bin/bash
# verify-mcp-config.sh — PC移行後のMCP設定一括検証
# Claude Code CLI + Claude Desktop の両環境をチェック
# 使用法: bash ~/projects/claude-config/scripts/verify-mcp-config.sh

set -uo pipefail

PASS=0; FAIL=0; WARN=0

ok()   { ((PASS++)); echo "  ✅ $1"; }
warn() { ((WARN++)); echo "  ⚠️  $1"; }
fail() { ((FAIL++)); echo "  ❌ $1"; }
sep()  { echo ""; echo "--- $1 ---"; }

WSL_USER=$(whoami)
WIN_USER=$(ls /mnt/c/Users/ 2>/dev/null | grep -v -E 'Public|Default|All|Default User|desktop.ini' | head -1)

sep "1. CLI側 (WSL2) — settings.json"

CLI_SETTINGS="$HOME/.claude/settings.json"
if [ -f "$CLI_SETTINGS" ]; then
    ok "settings.json 存在: $CLI_SETTINGS"

    # mcpServers エントリの確認
    MCS=$(python3 -c "import json; d=json.load(open('$CLI_SETTINGS')); print(' '.join(d.get('mcpServers',{}).keys()))" 2>/dev/null || echo "")
    if [ -n "$MCS" ]; then
        ok "MCPサーバー一覧: $MCS"
        for srv in $MCS; do
            cmd=$(python3 -c "import json; d=json.load(open('$CLI_SETTINGS')); print(d['mcpServers']['$srv'].get('command',''))" 2>/dev/null)
            args=$(python3 -c "import json; d=json.load(open('$CLI_SETTINGS')); print(d['mcpServers']['$srv'].get('args',[''])[-1])" 2>/dev/null)
            if [ "$cmd" = "bash" ] && [ -n "$args" ]; then
                if [ -f "$args" ]; then
                    ok "$srv: スクリプト存在 ($args)"
                else
                    fail "$srv: スクリプト不存在 ($args)"
                fi
            fi
        done
    else
        warn "mcpServers エントリなし"
    fi
else
    fail "settings.json 不存在: $CLI_SETTINGS"
fi

sep "2. Desktop側 (Windows) — claude_desktop_config.json"

# 配置場所を2パターン検索
DESKTOP_CONFIG=""
CANDIDATES=(
    "/mnt/c/Users/$WIN_USER/AppData/Roaming/Claude/claude_desktop_config.json"
)
# ストアアプリ版も検索
STORE_PATH=$(find "/mnt/c/Users/$WIN_USER/AppData/Local/Packages/" -name "claude_desktop_config.json" 2>/dev/null | head -1)
if [ -n "$STORE_PATH" ]; then
    CANDIDATES+=("$STORE_PATH")
fi

for candidate in "${CANDIDATES[@]}"; do
    if [ -f "$candidate" ]; then
        DESKTOP_CONFIG="$candidate"
        break
    fi
done

if [ -n "$DESKTOP_CONFIG" ] && [ -f "$DESKTOP_CONFIG" ]; then
    ok "claude_desktop_config.json 存在: $DESKTOP_CONFIG"

    # glm/minimax エントリの確認
    for srv in glm minimax; do
        has=$(python3 -c "import json; d=json.load(open('$DESKTOP_CONFIG')); print('yes' if '$srv' in d.get('mcpServers',{}) else 'no')" 2>/dev/null || echo "no")
        if [ "$has" = "yes" ]; then
            ok "Desktop MCP '$srv' エントリあり"
            # WSLユーザー名の確認
            args_str=$(python3 -c "import json; d=json.load(open('$DESKTOP_CONFIG')); print(' '.join(d['mcpServers']['$srv'].get('args',[])))" 2>/dev/null)
            if echo "$args_str" | grep -q "/home/$WSL_USER/"; then
                ok "$srv: WSLパス整合 ($WSL_USER)"
            else
                fail "$srv: WSLパス不整合 — args内に '/home/$WSL_USER/' が含まれない ($args_str)"
            fi
        else
            fail "Desktop MCP '$srv' エントリなし"
        fi
    done
else
    fail "claude_desktop_config.json 不存在"
    echo "     → 以下のいずれかで作成してください:"
    echo "     （従来版） /mnt/c/Users/$WIN_USER/AppData/Roaming/Claude/claude_desktop_config.json"
    echo "     （ストア版） /mnt/c/Users/$WIN_USER/AppData/Local/Packages/Claude_*/.../claude_desktop_config.json"
    echo "     テンプレート: ~/projects/claude-config/mcp-cheap-llm/claude_desktop_config.example.json"
fi

sep "3. secrets.env — APIキー（キー名のみ確認）"

SECRETS="$HOME/.secrets.env"
if [ -f "$SECRETS" ]; then
    ok "secrets.env 存在"
    for key in GLM_API_KEY MINIMAX_API_KEY; do
        if grep -qE "^(export )?${key}=" "$SECRETS" 2>/dev/null; then
            ok "$key 定義あり"
        else
            fail "$key 未定義"
        fi
    done
else
    fail "secrets.env 不存在: $SECRETS"
fi

sep "4. MCP起動スクリプト（WSL側）"

for script in start-glm-mcp.sh start-minimax-mcp.sh; do
    path="$HOME/.claude/scripts/$script"
    if [ -f "$path" ]; then
        ok "$script 存在"
        if [ -x "$path" ]; then
            ok "$script 実行権限あり"
        else
            fail "$script 実行権限なし → chmod +x $path"
        fi
        if grep -q "set -a" "$path"; then
            ok "$script 'set -a' あり（env export対応）"
        else
            fail "$script 'set -a' なし → 子プロセスにAPIキーが渡らない"
        fi
    else
        fail "$script 不存在: $path"
    fi
done

sep "5. .bashrc依存ツール（インストール漏れ検出）"

check_tool() {
    local name="$1" cmd="$2"
    if which "$cmd" &>/dev/null || [ -f "$HOME/.atuin/bin/$cmd" ] || [ -f "$HOME/.fzf/bin/$cmd" ]; then
        ok "$name インストール済み"
    else
        fail "$name 未インストール — .bashrcが参照しているがバイナリが存在しない"
    fi
}

check_tool "atuin" "atuin"
check_tool "fzf" "fzf"
check_tool "zoxide" "zoxide"

sep "結果"

TOTAL=$((PASS + FAIL + WARN))
echo "  ✅ OK: $PASS  ❌ FAIL: $FAIL  ⚠️  WARN: $WARN  （計 $TOTAL）"
echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "  🎉 全チェック通過。移行設定は正常です。"
else
    echo "  ⚡ $FAIL 件の問題があります。上記を修正してください。"
fi

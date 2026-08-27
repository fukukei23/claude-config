#!/bin/bash
# sync-secrets-to-settings.sh
# .secrets.env → settings.json のシークレット自動同期

SECRETS_FILE="$HOME/.secrets.env"
SETTINGS_FILE="$HOME/.claude/settings.json"
TEMP_FILE="${SETTINGS_FILE}.sync.tmp"

[[ ! -f "$SECRETS_FILE" ]] && exit 0
[[ ! -f "$SETTINGS_FILE" ]] && { echo " ❌ Secrets同期: settings.json不在"; exit 1; }
command -v jq &>/dev/null || { echo " ❌ Secrets同期: jq未インストール"; exit 1; }

set -a
source "$SECRETS_FILE" 2>/dev/null
set +a

# --- プロキシ生存チェック: 生きていればURLをプロキシに上書き ---
PROXY_URL="http://127.0.0.1:8787"
if curl -sf -m 2 "${PROXY_URL}/proxy/status" > /dev/null 2>&1; then
  ANTHROPIC_BASE_URL="$PROXY_URL"
fi

HASH_BEFORE=$(md5sum "$SETTINGS_FILE" | cut -d' ' -f1)

RESULT=$(jq \
  --arg anthropic_token "${ANTHROPIC_AUTH_TOKEN:-}" \
  --arg anthropic_url "${ANTHROPIC_BASE_URL:-}" \
  --arg brave_key "${BRAVE_API_KEY:-}" \
  --arg minimax_key "${MINIMAX_API_KEY:-}" \
'
  .env.ANTHROPIC_AUTH_TOKEN = (if $anthropic_token != "" then $anthropic_token else .env.ANTHROPIC_AUTH_TOKEN end) |
  .env.ANTHROPIC_BASE_URL   = (if $anthropic_url  != "" then $anthropic_url  else .env.ANTHROPIC_BASE_URL  end) |
  .env.BRAVE_API_KEY        = (if $brave_key      != "" then $brave_key      else .env.BRAVE_API_KEY       end) |
  .mcpServers["brave-search"].env.BRAVE_API_KEY = (if $brave_key != "" then $brave_key else .mcpServers["brave-search"].env.BRAVE_API_KEY end) |
  .mcpServers.minimax.env.MINIMAX_API_KEY = (if $minimax_key != "" then $minimax_key else .mcpServers.minimax.env.MINIMAX_API_KEY end)
' "$SETTINGS_FILE")
# ⚠️ glm MCPエントリは2026-08-25 doctor決定で削除済み。GLM_API_KEYの同期行を復活させると
# jqパス代入が .mcpServers.glm を自動再生成し「死にエントリ」が毎セッション復活する
# （08-25→08-27→08-28の3回回帰の根因・2026-08-28 ssot-check auto で除去）。glm再有効化時は
# MCPサーバー定義ごと手動追加すること。

if [[ $? -ne 0 ]]; then
  echo " ❌ Secrets同期: jqパースエラー"
  exit 1
fi

echo "$RESULT" > "$TEMP_FILE" && mv "$TEMP_FILE" "$SETTINGS_FILE"
HASH_AFTER=$(md5sum "$SETTINGS_FILE" | cut -d' ' -f1)
if [[ "$HASH_BEFORE" != "$HASH_AFTER" ]]; then
  MSG=" ✅ Secrets同期: 更新済み"
else
  MSG=" ✅ Secrets同期: 変更なし"
fi
mkdir -p /tmp/claude-startup
echo "$MSG" > /tmp/claude-startup/secrets-sync.status
exit 0

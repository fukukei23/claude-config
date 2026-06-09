#!/bin/bash
# sync-settings-to-example.sh
# settings.json のシークレット値を "" に置換して settings.example.json を更新する
# 呼び出し元: SessionStart hook / PostToolUse hook (settings.json 変更時)

SETTINGS_WSL="/home/yn4416/.claude/settings.json"
EXAMPLE_WSL="/home/yn4416/projects/claude-config/settings.example.json"

[[ ! -f "$SETTINGS_WSL" ]] && exit 0

HASH_BEFORE=""
[[ -f "$EXAMPLE_WSL" ]] && HASH_BEFORE=$(md5sum "$EXAMPLE_WSL" | cut -d' ' -f1)

if command -v jq &>/dev/null; then
  # jq が使える場合
  jq '
    .env |= with_entries(
      if (.key | test("KEY|TOKEN|SECRET|PASSWORD|AUTH"; "i"))
      then .value = ""
      else .
      end
    ) |
    .mcpServers = (
      .mcpServers // {} | to_entries | map(
        .value.env = (.value.env // {} | with_entries(.value = ""))
      ) | from_entries
    ) |
    .permissions.allow = (
      .permissions.allow | map(
        if (type == "string" and test("TOKEN="; "i") and length > 30)
        then "Bash(TOKEN=\"<DISCORD_BOT_TOKEN>\")"
        else .
        end
      )
    )
  ' "$SETTINGS_WSL" > "$EXAMPLE_WSL"
  [[ $? -ne 0 ]] && { echo " ❌ settings.example同期: jqエラー"; exit 1; }

elif command -v python3 &>/dev/null; then
  # python3 フォールバック
  python3 - <<'PYEOF'
import json, re, sys

src = "/home/yn4416/.claude/settings.json"
dst = "/home/yn4416/projects/claude-config/settings.example.json"
secret_pat = re.compile(r'(?i)(KEY|TOKEN|SECRET|PASSWORD|AUTH)')

def sanitize(obj):
    if isinstance(obj, dict):
        return {k: ('' if isinstance(v, str) and secret_pat.search(k) else sanitize(v))
                for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize(i) for i in obj]
    return obj

with open(src) as f:
    data = json.load(f)

out = sanitize(data)
for srv in out.get('mcpServers', {}).values():
    if 'env' in srv:
        srv['env'] = {k: '' for k in srv['env']}

# permissions.allow 内の TOKEN=<値> をマスク（Discord Bot Token等）
perms = out.get('permissions', {})
if 'allow' in perms:
    masked = []
    for item in perms['allow']:
        if isinstance(item, str) and 'TOKEN=' in item and len(item) > 30:
            item = 'Bash(TOKEN="<DISCORD_BOT_TOKEN>")'
        masked.append(item)
    perms['allow'] = masked

with open(dst, 'w') as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
PYEOF
  [[ $? -ne 0 ]] && { echo " ❌ settings.example同期: python3エラー"; exit 1; }

else
  echo " ❌ settings.example同期: jq も python3 も未インストール"
  exit 1
fi

HASH_AFTER=$(md5sum "$EXAMPLE_WSL" | cut -d' ' -f1)
if [[ "$HASH_BEFORE" != "$HASH_AFTER" ]]; then
  echo " ✅ settings.example同期: 更新済み → $EXAMPLE_WSL"
else
  echo " ✅ settings.example同期: 変更なし"
fi

exit 0

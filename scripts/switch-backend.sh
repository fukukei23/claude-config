#!/bin/bash
# switch-backend.sh — Claude Code CLI のLLM接続先を切替（プロキシ死亡時の自救）
#
# モード:
#   normal  - プロキシ経由(127.0.0.1:8787)・通常運用
#   zai     - ZAI直結(api.z.ai/api/anthropic)・GLM直・プロキシ不要（推奨自救）
#   minimax - MiniMax直結(api.minimax.io/anthropic/v1)・MiniMax直（※実機検証要）
#   status  - 現在の設定確認（変更なし）
#
# 認証ヘッダー使い分け（重要）:
#   - ANTHROPIC_AUTH_TOKEN → CLI が "Authorization: Bearer" を送信（ZAI用）
#   - ANTHROPIC_API_KEY    → CLI が "x-api-key" を送信（MiniMax用・プロキシと同じ方式）
#
# キー供給元: ~/.claude/.env（ANTHROPIC_AUTH_TOKEN / MINIMAX_API_KEY）
# 書換後は Claude Code CLI の再起動が必須（環境変数は起動時読込）

set -euo pipefail
SETTINGS="$HOME/.claude/settings.json"
ENV_FILE="$HOME/.claude/.env"

usage() {
    cat <<'EOF'
Claude Code CLI 接続先切替（プロキシ死亡時の自救）

使い方: switch-backend.sh {normal|zai|minimax|status}

  normal   プロキシ経由(127.0.0.1:8787)・通常運用
  zai      ZAI直結・GLM直接（推奨自救・課金増なし）
  minimax  MiniMax直結（※認証方式の実機検証が必要）
  status   現在の設定確認（変更なし）
EOF
}

# 前提チェック
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 が必要です"; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "❌ curl が必要です"; exit 1; }
[ -f "$SETTINGS" ] || { echo "❌ settings.json が見つかりません: $SETTINGS"; exit 1; }
[ $# -eq 1 ] || { usage; exit 1; }
MODE="$1"

# ~/.claude/.env ロード（キー取得・値は展開のみで表示しない）
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck source=/dev/null
    . "$ENV_FILE" 2>/dev/null || true
    set +a
fi

# === 3世代バックアップローテーション ===
[ -f "$SETTINGS.bak.3" ] && rm -f "$SETTINGS.bak.3"
[ -f "$SETTINGS.bak.2" ] && mv "$SETTINGS.bak.2" "$SETTINGS.bak.3"
[ -f "$SETTINGS.bak.1" ] && mv "$SETTINGS.bak.1" "$SETTINGS.bak.2"
cp "$SETTINGS" "$SETTINGS.bak.1"

case "$MODE" in
    status)
        python3 - "$SETTINGS" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
env = d.get('env', {})
url = env.get('ANTHROPIC_BASE_URL', '(未設定=Anthropic直結)')
has_token = 'ANTHROPIC_AUTH_TOKEN' in env
has_apikey = 'ANTHROPIC_API_KEY' in env
print(f'BASE_URL: {url}')
if '127.0.0.1:8787' in str(url):
    print('モード: normal (プロキシ経由)')
elif 'api.z.ai' in str(url):
    print('モード: zai (ZAI直結)')
elif 'api.minimax.io' in str(url):
    print('モード: minimax (MiniMax直結)')
print(f'AUTH_TOKEN(Bearer用): {"設定あり" if has_token else "未設定"}')
print(f'API_KEY(x-api-key用): {"設定あり" if has_apikey else "未設定"}')
PY
        # プロキシ生存確認
        if curl -s --max-time 1 http://127.0.0.1:8787/proxy/status >/dev/null 2>&1; then
            curl -s http://127.0.0.1:8787/proxy/status | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'プロキシ: 生存 (mode={d.get(\"mode\")} provider={d.get(\"provider\")} usage={d.get(\"usage_pct\")}%)')
" 2>/dev/null || echo 'プロキシ: 生存（status取得エラー）'
        else
            echo 'プロキシ: 応答なし（死亡の可能性・zai/minimaxで自救可）'
        fi
        exit 0
        ;;
    normal)
        BASE_URL="http://127.0.0.1:8787"
        USE_MODE="token"
        TOKEN="${ANTHROPIC_AUTH_TOKEN:-}"
        [ -n "$TOKEN" ] || { echo "❌ ANTHROPIC_AUTH_TOKEN が .env に未設定"; exit 1; }
        ;;
    zai)
        BASE_URL="https://api.z.ai/api/anthropic"
        USE_MODE="token"
        TOKEN="${ANTHROPIC_AUTH_TOKEN:-}"
        [ -n "$TOKEN" ] || { echo "❌ ANTHROPIC_AUTH_TOKEN が .env に未設定"; exit 1; }
        ;;
    minimax)
        BASE_URL="https://api.minimax.io/anthropic/v1"
        USE_MODE="apikey"
        APIKEY="${MINIMAX_API_KEY:-}"
        [ -n "$APIKEY" ] || { echo "❌ MINIMAX_API_KEY が .env に未設定"; exit 1; }
        ;;
    *)
        usage
        exit 1
        ;;
esac

# === atomic書換（tmp→mv・中断でも破損しない）===
TMP=$(mktemp)
python3 - "$SETTINGS" "$TMP" "$BASE_URL" "$USE_MODE" "${TOKEN:-}" "${APIKEY:-}" <<'PY'
import json, sys
path, tmp, base_url, use_mode, token, apikey = sys.argv[1:7]
d = json.load(open(path))
env = d.setdefault('env', {})
env['ANTHROPIC_BASE_URL'] = base_url
if use_mode == 'token':
    env['ANTHROPIC_AUTH_TOKEN'] = token
    env.pop('ANTHROPIC_API_KEY', None)   # Bearer送信に統一
else:
    env['ANTHROPIC_API_KEY'] = apikey
    env.pop('ANTHROPIC_AUTH_TOKEN', None)  # x-api-key送信に統一
with open(tmp, 'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
PY
mv "$TMP" "$SETTINGS"

echo "✅ 切替完了: $MODE モード"
echo "   BASE_URL: $BASE_URL"
echo "   認証: $([ "$USE_MODE" = token ] && echo 'AUTH_TOKEN(Bearer)' || echo 'API_KEY(x-api-key)')"
echo "   バックアップ: $SETTINGS.bak.1 (最大3世代)"
echo ""
echo "⚠️  Claude Code CLI を再起動してください（環境変数は起動時読込）"
[ "$MODE" = "minimax" ] && echo "ℹ️  minimaxモードは認証方式の実機検証が未完・動かなければ zai モードで確実"
#!/bin/bash
# glm-rate-proxy: フェイルセーフ付き起動スクリプト

SETTINGS="/home/yn4416/.claude/settings.json"
PROXY_DIR="/home/yn4416/.claude/scripts/glm-rate-proxy"
PROXY_URL="http://127.0.0.1:8787"
ZAI_URL="https://api.z.ai/api/anthropic"
LOG="/tmp/glm-proxy.log"

ensure_settings_url() {
    if [ -f "$SETTINGS" ]; then
        sed -i "s|\"ANTHROPIC_BASE_URL\": \"[^\"]*\"|\"ANTHROPIC_BASE_URL\": \"$1\"|" "$SETTINGS"
    fi
}

# 既に起動中か確認
if pgrep -f "python3 -m glm_rate_proxy" > /dev/null 2>&1; then
    if curl -sf -m 2 http://127.0.0.1:8787/proxy/status > /dev/null 2>&1; then
        ensure_settings_url "$PROXY_URL"
        mkdir -p /tmp/claude-startup
        echo " ✅ GLM Proxy: healthy" > /tmp/claude-startup/glm-proxy.status
        exit 0
    else
        pkill -f "python3 -m glm_rate_proxy" 2>/dev/null
        sleep 1
    fi
fi

# プロキシ起動
source ~/.secrets.env 2>/dev/null
cd "$PROXY_DIR"
PYTHONPATH=src nohup python3 -m glm_rate_proxy > "$LOG" 2>&1 &
PROXY_PID=$!
sleep 2

# 起動確認
if pgrep -f "python3 -m glm_rate_proxy" > /dev/null 2>&1 && \
   curl -sf -m 2 http://127.0.0.1:8787/proxy/status > /dev/null 2>&1; then
    ensure_settings_url "$PROXY_URL"
    mkdir -p /tmp/claude-startup
    echo " ✅ GLM Proxy: 起動済み (PID=$PROXY_PID)" > /tmp/claude-startup/glm-proxy.status
else
    ensure_settings_url "$ZAI_URL"
    mkdir -p /tmp/claude-startup
    echo " ⚠️ GLM Proxy: 起動失敗 (ZAI直結)" > /tmp/claude-startup/glm-proxy.status
fi

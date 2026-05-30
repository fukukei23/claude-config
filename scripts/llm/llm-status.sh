#!/bin/bash
# Claude Code ステータスライン
# stdin JSONからベースモデル名・コンテキスト使用率・レート制限を表示
#
# 表示例: GLM-5.1 | ctx: 45% | 5h: 23% (2h15m) | 7d: 12%
#
# LLM名の判定優先度:
#   1. stdin JSON の model フィールド（ベースURLの実際のモデル）
#   2. /tmp/llm-last-used.txt（MCPツール使用時のフォールバック）
#   3. "unknown"（データなし）

INPUT=$(cat)

python3 -c "
import sys, json, datetime, os

input_data = sys.stdin.read().strip()
parts = []

# --- LLM名（ベースモデル） ---
model_name = 'unknown'
try:
    d = json.loads(input_data) if input_data else {}

    # stdin JSON の model フィールド（実際のベースURLモデル）
    m = d.get('model')
    if m:
        model_name = m
except:
    d = {}

# MCP経由のLLM使用記録（フォールバック）
status_file = '/tmp/llm-last-used.txt'
if model_name == 'unknown':
    try:
        if os.path.exists(status_file):
            with open(status_file) as f:
                mcp_llm = f.read().strip()
            if mcp_llm:
                model_name = mcp_llm
    except:
        pass

parts.append(model_name)

try:
    # --- コンテキストウィンドウ使用率 ---
    ctx = d.get('context_window', {})
    ctx_pct = ctx.get('used_percentage')
    if ctx_pct is not None:
        parts.append(f'ctx: {ctx_pct:.0f}%')

    # --- 5時間レート制限 ---
    rl5 = d.get('rate_limits', {}).get('five_hour', {})
    pct5 = rl5.get('used_percentage', -1)
    if pct5 is not None and pct5 >= 0:
        reset5 = rl5.get('reset_at', '')
        suffix = ''
        if reset5:
            try:
                rt = datetime.datetime.fromisoformat(reset5.replace('Z', '+00:00'))
                now = datetime.datetime.now(datetime.timezone.utc)
                diff = rt - now
                mins = int(diff.total_seconds() / 60)
                if mins > 60:
                    suffix = f' ({mins // 60}h{mins % 60}m)'
                elif mins > 0:
                    suffix = f' ({mins}m)'
            except:
                pass
        parts.append(f'5h: {pct5:.0f}%{suffix}')

    # --- 7日レート制限 ---
    rl7 = d.get('rate_limits', {}).get('seven_day', {})
    pct7 = rl7.get('used_percentage', -1)
    if pct7 is not None and pct7 >= 0:
        parts.append(f'7d: {pct7:.0f}%')

except:
    pass

print(' | '.join(parts))
" 2>/dev/null || echo "statusline-error"

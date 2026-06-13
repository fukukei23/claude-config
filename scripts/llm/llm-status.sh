#!/bin/bash
# Claude Code ステータスライン
# stdin JSON（公式スキーマ）からモデル名・コスト・作業量を表示
#
# 表示例: GLM-5.1 | $0.12 | +100 -50
#
# LLM名の判定優先度:
#   1. stdin JSON の model フィールド（display_name → id）
#   2. /tmp/llm-last-used.txt（MCPツール使用時のフォールバック）
#   3. "unknown"

python3 -c "
import sys, json, os

input_data = sys.stdin.read().strip()
parts = []

# --- LLM名（ベースモデル） ---
model_name = 'unknown'
d = {}
try:
    d = json.loads(input_data) if input_data else {}
    m = d.get('model')
    if isinstance(m, dict):
        model_name = m.get('display_name') or m.get('id') or 'unknown'
    elif m:
        model_name = m
except:
    pass

# MCP経由のLLM使用記録（フォールバック）
if model_name == 'unknown':
    try:
        if os.path.exists('/tmp/llm-last-used.txt'):
            mcp_llm = open('/tmp/llm-last-used.txt').read().strip()
            if mcp_llm:
                model_name = mcp_llm
    except:
        pass

parts.append(model_name)

try:
    # --- コスト（公式JSONの cost.total_cost_usd） ---
    cost = d.get('cost', {}).get('total_cost_usd')
    if cost is not None:
        parts.append(f'\${cost:.2f}')

    # --- 行追加/削除（作業量の目安） ---
    cost_d = d.get('cost', {})
    added = cost_d.get('total_lines_added')
    removed = cost_d.get('total_lines_removed')
    if added is not None and removed is not None:
        parts.append(f'+{added} -{removed}')
except:
    pass

# str() で包む: 万が一 dict が混入しても TypeError を起こさない安全策
print(' | '.join(str(p) for p in parts))
" 2>/dev/null || echo 'statusline-error'

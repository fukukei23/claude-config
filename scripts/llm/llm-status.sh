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

# --- コンテキスト残量（最新assistant usage合計 / 200k閾値）---
# stdin JSON の transcript_path から最新 usage を直接読み、auto-compact目安の%を算出。
# 注意: Claude Code ネイティブの右下警告（動的閾値）とは厳密には一致しない近似値。
try:
    transcript_path = d.get('transcript_path')
    ctx_tokens = 0
    if transcript_path and os.path.exists(transcript_path):
        # JSONL を行単位で走査し、最後の assistant usage を取得（最後が最新）
        with open(transcript_path) as tf:
            for line in tf:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except:
                    continue
                if entry.get('type') == 'assistant':
                    msg = entry.get('message')
                    if isinstance(msg, dict):
                        usage = msg.get('usage')
                        if isinstance(usage, dict):
                            ctx_tokens = (
                                usage.get('input_tokens', 0)
                                + usage.get('cache_creation_input_tokens', 0)
                                + usage.get('cache_read_input_tokens', 0)
                            )
    if ctx_tokens > 0:
        LIMIT = 200000  # auto-compact目安（固定）
        pct = ctx_tokens / LIMIT * 100
        k_used = ctx_tokens / 1000
        # 色: >=85%赤(危険) / >=70%黄(注意) / それ以外緑(快適)
        if pct >= 85:
            color = '\033[31m'
        elif pct >= 70:
            color = '\033[33m'
        else:
            color = '\033[32m'
        reset = '\033[0m'
        parts.append(f'{color}Ctx {pct:.0f}% ({k_used:.0f}k){reset}')
    elif d.get('exceeds_200k_tokens'):
        parts.append('\033[31mCtx >200k!\033[0m')
except:
    pass

# str() で包む: 万が一 dict が混入しても TypeError を起こさない安全策
print(' | '.join(str(p) for p in parts))
" 2>/dev/null || echo 'statusline-error'

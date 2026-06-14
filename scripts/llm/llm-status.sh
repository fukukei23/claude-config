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
import sys, json, os, urllib.request, time

input_data = sys.stdin.read().strip()
parts = []

# --- LLM名（ベースモデル） ---
# 優先度:
#   1. glm-rate-proxy の /proxy/status (実動作中のprovider/model) ← 実態を反映
#   2. stdin JSON の model フィールド（公式statuslineスキーマ）
#   3. /tmp/llm-last-used.txt (MCP経由)
#   4. 'unknown'
model_name = 'unknown'
proxy_mode = None
proxy_provider = None
proxy_actual = None
try:
    with urllib.request.urlopen('http://localhost:8787/proxy/status', timeout=0.3) as r:
        ps = json.loads(r.read().decode('utf-8'))
        proxy_mode = ps.get('mode')
        proxy_provider = ps.get('provider')
        proxy_actual = ps.get('last_actual_model')
except Exception:
    pass

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

# プロキシの実情報があれば表示名に [mode] バッジを付与
if proxy_mode == 'peak_block' and proxy_provider == 'minimax':
    # peak時間帯は minimax フォールバック中
    suffix = proxy_actual or 'MiniMax-M3'
    if model_name == 'unknown' or 'GLM' in model_name or 'Sonnet' in model_name:
        model_name = f'{model_name}→{suffix}'
    parts.append(f'\033[33m🟠[peak→minimax]\033[0m {model_name}')
elif proxy_provider == 'zai':
    parts.append(f'\033[32m🟡[GLM]\033[0m {model_name}')
else:
    parts.append(model_name)

# MCP経由のLLM使用記録（フォールバック）
if model_name == 'unknown' and proxy_provider != 'minimax':
    try:
        if os.path.exists('/tmp/llm-last-used.txt'):
            mcp_llm = open('/tmp/llm-last-used.txt').read().strip()
            if mcp_llm:
                model_name = mcp_llm
    except:
        pass

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

# --- コンテキスト残量（窓使用量 / 動的窓サイズ）---
# transcript_path から最新 assistant usage を読み、窓使用量を算出。
# 窓使用量 = input + cache_creation + cache_read（cache_readも窓を占有する）。
# 窓サイズは動的判定: exceeds_200k フラグ or 窓使用量>200k → 1M窓（Opus[1m]/GLM-5.2等）
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
        # 窓サイズ: CLAUDE_CODE_AUTO_COMPACT_WINDOW 環境変数から（デフォルト200k）
        LIMIT = int(os.environ.get('CLAUDE_CODE_AUTO_COMPACT_WINDOW', '200000'))
        if LIMIT >= 1000000:
            win_label = f'{LIMIT//1000000}M'
        else:
            win_label = f'{LIMIT//1000}k'
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
        parts.append(f'{color}Ctx {pct:.0f}% ({k_used:.0f}k/{win_label}){reset}')
    elif d.get('exceeds_200k_tokens'):
        parts.append('\033[33mCtx >200k (1M窓)\033[0m')
except:
    pass

# str() で包む: 万が一 dict が混入しても TypeError を起こさない安全策
print(' | '.join(str(p) for p in parts))
" 2>/dev/null || echo 'statusline-error'

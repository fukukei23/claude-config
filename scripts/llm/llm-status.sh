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
proxy_req_mb = None
try:
    with urllib.request.urlopen('http://localhost:8787/proxy/status', timeout=0.3) as r:
        ps = json.loads(r.read().decode('utf-8'))
        proxy_mode = ps.get('mode')
        proxy_provider = ps.get('provider')
        proxy_actual = ps.get('last_actual_model')
        proxy_req_mb = ps.get('last_request_mb')
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

# --- 作業量（優先度低・末尾に追加。コストは非表示→claude-costコマンドで確認）---
work_str = None
try:
    cost_d = d.get('cost', {})
    added = cost_d.get('total_lines_added')
    removed = cost_d.get('total_lines_removed')
    if added is not None and removed is not None:
        work_str = f'+{added} -{removed}'
except:
    pass

# --- コンテキスト残量（窓使用量 / 動的窓サイズ）---
# transcript_path から最新 assistant usage を読み、窓使用量を算出。
# 窓使用量 = input + cache_creation + cache_read（cache_readも窓を占有する）。
# 窓サイズは動的判定: exceeds_200k フラグ or 窓使用量>200k → 1M窓（Opus[1m]/GLM-5.2等）
try:
    transcript_path = d.get('transcript_path')
    ctx_tokens = 0
    req_mb = None
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
        # 会話サイズ（トランスクリプト）= 32MBリクエスト上限の目安
        req_mb = os.path.getsize(transcript_path) / 1048576
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
    # 会話サイズ表示（32MB APIリクエスト上限の目安）
    # JSONLファイルサイズ（transcript_path）= 画像base64を含む実会話サイズ。
    # proxy_req_mb（last_request_mb）は GLM送信後のCDN化サイズで常に0.4MB前後・
    # 32MB到達を反映しないため不使用（測定ポイントが送信後なので画像が軽く見える）。
    # ※ JSONLサイズは履歴のみ（システムプロンプト+ツール定義は含まない）で実サイズより過小評価だが、
    #    32MBの主犯は画像蓄積なので実用的な目安として十分。
    if req_mb is not None:
        if req_mb >= 30:
            rcolor = '\033[31m'
        elif req_mb >= 27:
            rcolor = '\033[33m'
        else:
            rcolor = '\033[32m'
        parts.append(f'{rcolor}Req {req_mb:.1f}MB/32\033[0m')
except:
    pass

# 作業量は末尾（優先度低）
if work_str:
    parts.append(work_str)

# タブ識別子を末尾に（WT_SESSION先頭4桁・/clearで不変・タブ単位の識別子。
# WT_SESSION未設定時は session_id 先頭4桁でフォールバック。
# 2026-08-16 並び順変更: モデル→Ctx→Req→作業量→🪟タブID（スマホ表示で末尾が見切れるため
# 重要度順にモデル/コンテキストを先頭へ・🪟は末尾へ）
wt = os.environ.get('WT_SESSION', '')
if wt:
    tab_id = wt[:4]
else:
    sid = d.get('session_id', '')
    tab_id = sid[:4] if sid else '----'
parts.append(f'\033[36m🪟{tab_id}\033[0m')

# str() で包む: 万が一 dict が混入しても TypeError を起こさない安全策
print(' | '.join(str(p) for p in parts))
" 2>/dev/null || echo 'statusline-error'

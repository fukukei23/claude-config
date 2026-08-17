#!/usr/bin/env bash
# check-plain-explanation.sh — Stop hook
# 完了報告と思われる長い応答(600字超)に平易な解説(💡 一言でいうと 等)が無い場合、
# 1回だけstopを差し戻して併記を促す（CLAUDE.md「説明・報告時の平易な解説併記」の機械的担保・2026-08-18新設）。
# 誤検知対策: ①同一メッセージへの差戻しは1回限定(hashガード) ②短い応答は無視 ③理由文に「誤検知ならそのまま終了可」を明記
set -euo pipefail

MIN_LEN=600
GUARD_DIR="$HOME/.claude/state/plain-explanation-guard"
mkdir -p "$GUARD_DIR"

# hookのstdin JSONを先読みして環境変数で渡す（python3 - のプログラムstdinと競合しないように）
PAYLOAD_JSON="$(cat)"

exec env PAYLOAD_JSON="$PAYLOAD_JSON" MIN_LEN="$MIN_LEN" GUARD_DIR="$GUARD_DIR" python3 - <<'PYEOF'
import sys, json, os, hashlib

payload = json.loads(os.environ['PAYLOAD_JSON'])
min_len = int(os.environ['MIN_LEN'])
guard_dir = os.environ['GUARD_DIR']
markers = ['💡', '📖', '一言でいうと', 'かみ砕くと', '素人向け解説']

transcript = payload.get('transcript_path', '')
session_id = payload.get('session_id', 'unknown')

if not transcript or not os.path.exists(transcript):
    sys.exit(0)

# 末尾から最新の「テキストを持つ assistant メッセージ」を探す
last_text = ''
with open(transcript, 'r', errors='replace') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get('type') != 'assistant':
            continue
        msg = rec.get('message', {})
        for block in (msg.get('content') or []):
            if isinstance(block, dict) and block.get('type') == 'text' and block.get('text', '').strip():
                last_text = block['text']  # ファイル順に上書き=最後のものが残る

if len(last_text) < min_len:
    sys.exit(0)  # 短い応答は対象外（ルールの対象外と一致）

if any(m in last_text for m in markers):
    sys.exit(0)  # 平易な解説あり

# ループガード: 同一メッセージへの差戻しは1回だけ
h = hashlib.sha256(last_text.encode('utf-8')).hexdigest()[:16]
guard_file = os.path.join(guard_dir, f'{session_id}.last')
if os.path.exists(guard_file) and open(guard_file).read().strip() == h:
    sys.exit(0)  # 既に1回差戻し済み → 通す
with open(guard_file, 'w') as f:
    f.write(h)

reason = (
    '平易な解説の併記忘れの可能性: 最後の応答が報告と思われる長さですが '
    '「💡 一言でいうと」等の平易な解説が見つかりません。'
    'CLAUDE.md「説明・報告時の平易な解説併記」ルールに従い、専門説明に加えた平易な解説を併記してください。'
    '（コードのみの返答等の誤検知なら、そのまま終了して構いません・この差戻しは1回だけです）'
)
print(json.dumps({'decision': 'block', 'reason': reason}, ensure_ascii=False))
sys.exit(0)
PYEOF

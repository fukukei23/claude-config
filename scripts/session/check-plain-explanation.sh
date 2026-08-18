#!/usr/bin/env bash
# check-plain-explanation.sh — Stop hook
# 完了報告と思われる長い応答(600字超)に平易な解説(💡 一言でいうと 等)が無い場合、
# 1回だけstopを差戻して併記を促す（CLAUDE.md「説明・報告時の平易な解説併記」の機械的担保・2026-08-18新設）。
# 誤検知対策: ①同一メッセージへの差戻しは1回限定(hashガード) ②短い応答は無視 ③理由文に「誤検知ならそのまま終了可」を明記
# 改訂(2026-08-18・multi-llm-review MiniMax14+Gemini3・H主F副):
#   H層=CLAUDE_DISABLE_PLAIN_EXPLANATION_CHECK=1 で無条件exit（明示オプトアウト・機械呼び出し側が申告）
#   F層=実userメッセージが1個以下のtranscriptは機械呼び出し(claude --print)と判定して素通り（H層フラグ忘れの保険・誤除外の実害は💡が付かないのみ）
#   dispatch.log=どの経路でexitしたか1行記録（post-mortem用・256KB超で初期化）
set -euo pipefail

MIN_LEN=600
GUARD_DIR="$HOME/.claude/state/plain-explanation-guard"
mkdir -p "$GUARD_DIR"

# H層（主防御・明示オプトアウト）: envフラグがあれば以降の判定を一切走らせず終了
if [ "${CLAUDE_DISABLE_PLAIN_EXPLANATION_CHECK:-}" = "1" ]; then
  printf '%s session=%s exit=env-flag\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "${CLAUDE_CODE_SESSION_ID:-unknown}" >> "$GUARD_DIR/dispatch.log" 2>/dev/null || true
  exit 0
fi

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


def _dispatch(reason: str) -> None:
    """dispatch.logへexit経路を1行記録（書込失敗はhookを止めない）。"""
    try:
        import datetime
        sid = (os.environ.get('CLAUDE_CODE_SESSION_ID') or str(session_id))[:8]
        line = f"{datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} session={sid} exit={reason}\n"
        p = os.path.join(guard_dir, 'dispatch.log')
        if os.path.exists(p) and os.path.getsize(p) > 262144:  # 256KB超で初期化
            open(p, 'w').close()
        with open(p, 'a') as f:
            f.write(line)
    except Exception:
        pass


if not transcript or not os.path.exists(transcript):
    _dispatch('no-transcript')
    sys.exit(0)

# assistant末尾テキスト抽出と並行して実userメッセージ数をカウント（F層用）。
# 実user = type:user かつ本文が「Stop hook feedback:」で始まらない（差戻しfeedbackは除外）。
last_text = ''
real_user_count = 0
with open(transcript, 'r', errors='replace') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get('type') == 'user':
            content = (rec.get('message') or {}).get('content')
            if isinstance(content, str):
                texts = [content]
            elif isinstance(content, list):
                texts = [b.get('text', '') for b in content
                         if isinstance(b, dict) and b.get('type') == 'text']
            else:
                texts = []
            joined = '\n'.join(t for t in texts if t).strip()
            if not joined.startswith('Stop hook feedback:'):
                real_user_count += 1
            continue
        if rec.get('type') != 'assistant':
            continue
        msg = rec.get('message', {})
        for block in (msg.get('content') or []):
            if isinstance(block, dict) and block.get('type') == 'text' and block.get('text', '').strip():
                last_text = block['text']  # ファイル順に上書き=最後のものが残る

if len(last_text) < min_len:
    _dispatch('short')
    sys.exit(0)  # 短い応答は対象外（ルールの対象外と一致）

if any(m in last_text for m in markers):
    _dispatch('plain-marker')
    sys.exit(0)  # 平易な解説あり

# F層（副防御）: 実user 1個以下 = 機械呼び出し(claude --print)と判定して素通り。
# 誤判定（人間の単発初回ターン）の実害は「💡が1回付かない」のみ（hook導入前と同じ・機能破壊でない）。
if real_user_count <= 1:
    _dispatch('machine-fallback')
    sys.exit(0)

# ループガード: 同一メッセージへの差戻しは1回だけ
h = hashlib.sha256(last_text.encode('utf-8')).hexdigest()[:16]
guard_file = os.path.join(guard_dir, f'{session_id}.last')
if os.path.exists(guard_file) and open(guard_file).read().strip() == h:
    _dispatch('guard-pass')
    sys.exit(0)  # 既に1回差戻し済み → 通す
with open(guard_file, 'w') as f:
    f.write(h)

reason = (
    '平易な解説の併記忘れの可能性: 最後の応答が報告と思われる長さですが '
    '「💡 一言でいうと」等の平易な解説が見つかりません。'
    'CLAUDE.md「説明・報告時の平易な解説併記」ルールに従い、専門説明に加えた平易な解説を併記してください。'
    '（コードのみの返答等の誤検知なら、そのまま終了して構いません・この差戻しは1回だけです）'
)
_dispatch('blocked')
print(json.dumps({'decision': 'block', 'reason': reason}, ensure_ascii=False))
sys.exit(0)
PYEOF

#!/usr/bin/env bash
# check-yagi-output.sh — Stop hook
# sentaku等の推奨案を含む応答で、サボりバイアス防止4項目（反証シナリオ/最悪ケース/
# 見送った案の再評価点/省略デメリット）のいずれかが欠けている場合、
# 1回だけstopを差戻して併記を促す（rules/_shared/LLMサボりバイアス防止.md 実行前チェックの機械的担保・2026-08-27新設）。
# 誤検知対策: ①同一メッセージへの差戻しは1回限定(hashガード) ②推奨案を含まない応答は無視
#   ③理由文に「誤検知ならそのまま終了可」を明記（check-plain-explanation.sh と同形式）
# 層構造（平易解説hook準拠）:
#   H層=CLAUDE_DISABLE_YAGI_CHECK=1 で無条件exit（明示オプトアウト・機械呼び出し側が申告）
#   F層=実userメッセージが1個以下のtranscriptは機械呼び出し(claude --print)と判定して素通り
#   dispatch.log=どの経路でexitしたか1行記録（post-mortem用・256KB超で初期化）
set -euo pipefail

MIN_LEN=300
GUARD_DIR="$HOME/.claude/state/yagi-check-guard"
mkdir -p "$GUARD_DIR"

# H層（主防御・明示オプトアウト）: envフラグがあれば以降の判定を一切走らせず終了
if [ "${CLAUDE_DISABLE_YAGI_CHECK:-}" = "1" ]; then
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

# 推奨案を提示した応答と判定する語（sentaku L1/L1.5出力の固定形式に依存）
trigger_markers = ['⭐ 推奨', '推奨：', '⭐推奨']
# 義務付け4項目（sentaku SKILL.md「禁止事項」+ 2026-08-27 省略デメリット追加）
required_markers = {
    '反証シナリオ': '反証',
    '最悪ケース': '最悪ケース',
    '見送った案の再評価点': '見送った案',
    '省略デメリット': '省略デメリット',
}

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
    sys.exit(0)  # 短い応答は対象外

if not any(m in last_text for m in trigger_markers):
    _dispatch('no-recommendation')
    sys.exit(0)  # 推奨案を含まない応答は対象外

missing = [label for label, kw in required_markers.items() if kw not in last_text]
if not missing:
    _dispatch('all-markers-present')
    sys.exit(0)  # 4項目すべてあり

# F層（副防御）: 実user 1個以下 = 機械呼び出し(claude --print)と判定して素通り。
# 誤判定（人間の単発初回ターン）の実害は「指摘が1回付かない」のみ（hook導入前と同じ・機能破壊でない）。
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
    '推奨案へのサボりバイアス防止項目の欠落可能性: 推奨案を含む応答ですが '
    '次の項目が見つかりません: ' + '・'.join(missing) + '。'
    'sentaku SKILL.md「禁止事項」および rules/_shared/LLMサボりバイアス防止.md「実行前チェック」に従い、'
    '推奨には「反証シナリオ1つ＋最悪ケース＋見送った案の再評価点＋省略デメリット」を併記してください。'
    '（比較や推奨でない応答等の誤検知なら、そのまま終了して構いません・この差戻しは1回だけです）'
)
_dispatch('blocked:' + ','.join(missing))
print(json.dumps({'decision': 'block', 'reason': reason}, ensure_ascii=False))
sys.exit(0)
PYEOF

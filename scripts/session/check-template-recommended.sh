#!/usr/bin/env bash
# check-template-recommended.sh — Stop hook
# スキルテンプレート由来の推奨表記「Subagent-Driven (recommended)/（推奨）」を含む応答で、
# 自タスクへの適合評価（「評価/目安/本タスク/私の推奨」等の言及）が一切無い場合、
# 1回だけstopを差戻して評価を促す（2026-08-29事故の機械的封じ・memory再発実例対応）。
# 事象: writing-plans等スキルのハンドオフ表示に埋め込まれた (recommended) 固定文言を
#   そのまま転記し、直後の自評価（Inline推奨）と矛盾する案内を出した（ユーザー指摘で発覚）。
#   memory「Subagent-Drivenを機械的推奨しない」は存在したが行動時に不適用だったため、
#   文字列マッチで機械検出する（判断不要・check-yagi-output.sh と同形式）。
# 誤検知対策: ①同一メッセージへの差戻しは1回限定(hashガード) ②評価言及があれば素通り
#   ③テンプレートを引用して注意喚起する応答（「テンプレート」語を含む）も素通り
#   ④理由文に「誤検知ならそのまま終了可」を明記
# 層構造（check-yagi-output.sh準拠）:
#   H層=CLAUDE_DISABLE_TEMPLATE_RECO_CHECK=1 で無条件exit（明示オプトアウト）
#   F層=実userメッセージが1個以下のtranscriptは機械呼び出し(claude --print)と判定して素通り
#   dispatch.log=どの経路でexitしたか1行記録（post-mortem用・256KB超で初期化）
set -euo pipefail

GUARD_DIR="$HOME/.claude/state/template-reco-check-guard"
mkdir -p "$GUARD_DIR"

# H層（主防御・明示オプトアウト）: envフラグがあれば以降の判定を一切走らせず終了
if [ "${CLAUDE_DISABLE_TEMPLATE_RECO_CHECK:-}" = "1" ]; then
  printf '%s session=%s exit=env-flag\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "${CLAUDE_CODE_SESSION_ID:-unknown}" >> "$GUARD_DIR/dispatch.log" 2>/dev/null || true
  exit 0
fi

# hookのstdin JSONを先読みして環境変数で渡す（python3 - のプログラムstdinと競合しないように）
PAYLOAD_JSON="$(cat)"

exec env PAYLOAD_JSON="$PAYLOAD_JSON" GUARD_DIR="$GUARD_DIR" python3 - <<'PYEOF'
import sys, json, os, hashlib

payload = json.loads(os.environ['PAYLOAD_JSON'])
guard_dir = os.environ['GUARD_DIR']

# テンプレート由来の推奨表記（writing-plans等スキル本文に埋め込まれた固定文言）
template_markers = ['Subagent-Driven (recommended)', 'Subagent-Driven（推奨）']
# 自タスク評価の存在を示す語（いずれかがあれば評価を経た提示と判定して素通り）
eval_markers = ['評価', '目安', '本タスク', '私の推奨', 'どちらも当てはまり', 'テンプレート', 'おすすめは', 'お勧めは']

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

if not any(m in last_text for m in template_markers):
    _dispatch('no-template-phrase')
    sys.exit(0)  # テンプレート推奨表記を含まない応答は対象外

if any(m in last_text for m in eval_markers):
    _dispatch('eval-present')
    sys.exit(0)  # 評価言及あり = 評価を経た提示（または事故の分析文）→ 対象外

# F層（副防御）: 実user 1個以下 = 機械呼び出し(claude --print)と判定して素通り。
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
    'テンプレート推奨表記の無批判転記疑義: スキルテンプレート由来の「Subagent-Driven (recommended)/（推奨）」'
    '表記が含まれていますが、自タスクへの適合評価（規模・性質・ファイル構造等）の言及が見つかりません。'
    'memory「Subagent-Drivenを機械的推奨しない」および実例集 2026-08-29 に従い、'
    'テンプレート文言をそのまま転記せず、評価結果を先に示し適性の方を「推奨」として提示してください'
    '（テンプレートと評価結果が異なる場合は「テンプレートは○○だが本タスクは△△を推奨」と併記）。'
    '（テンプレートを引用した注意喚起・分析等の誤検知なら、そのまま終了して構いません・この差戻しは1回だけです）'
)
_dispatch('blocked')
print(json.dumps({'decision': 'block', 'reason': reason}, ensure_ascii=False))
sys.exit(0)
PYEOF

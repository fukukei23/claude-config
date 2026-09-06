#!/usr/bin/env bash
# check-consult-balance.sh — Stop hook
# 直前のユーザー発言が「判断の相談」で、CCの回答に同意表現（正しい/賛成/その通り 等）が出ており
# 反証セクション（【反証】等）が無い場合、1回だけstopを差戻して反証の併記を促す。
# 背景: 2026-09-05 就活戦略相談での迎合同調（実例集記録済み）の機械的防止。
# 誤検知対策: ①同一メッセージへの差戻しは1回限定(hashガード・check-plain-explanationと同一方式)
#            ②consult-balance-injectが発動しなかった発言(非相談)は無視
#            ③注入マーカー([consult-balance)が会話内に無い場合は非適用対象として素通り
#            ④「誤検知ならそのまま終了可」を理由文に明記
# モード: GUARD_DIR/mode = warn(既定: 1回差戻し) / shadow(ログのみ) / enforce(繰り返し差戻し)
set -euo pipefail

GUARD_DIR="${GUARD_DIR:-$HOME/.claude/state/consult-balance-guard}"
mkdir -p "$GUARD_DIR"
MODE_FILE="$GUARD_DIR/mode"
# 優先順位: 環境変数（テスト用）> modeファイル > 既定warn
MODE="${CLAUDE_CONSULT_BALANCE_MODE:-}"
[ -z "$MODE" ] && MODE="warn"
[ -f "$MODE_FILE" ] && MODE="$(cat "$MODE_FILE" 2>/dev/null || echo warn)"

if [ -f "$GUARD_DIR/disabled" ]; then
  exit 0
fi

PAYLOAD_JSON="$(cat)"
exec env PAYLOAD_JSON="$PAYLOAD_JSON" GUARD_DIR="$GUARD_DIR" MODE="$MODE" python3 - <<'PYEOF'
import sys, json, os, re, hashlib

payload = json.loads(os.environ['PAYLOAD_JSON'])
guard_dir = os.environ['GUARD_DIR']
mode = os.environ['MODE']

AGREE = re.compile(r'正しいです|正しい。|正解です|賛成です|賛成します|その通り|そう思います|お勧めします|おすすめします|推奨します|同感です')
# 根拠マーカー: 同意に根拠（出典・実測・論拠）が伴っていれば迎合でない（案B・3機レビューr1収束）
BASIS = re.compile(r'【根拠|根拠:|根拠：|出典|参照[:：]|実測|引用|データ上|計算上|公式ドキュメント|エビデンス|[\d.]+[%％]|\(\d{4}\)|\(\d{4}-\d{2}\)')
# 反証マーカー: 根拠を示せない場合の代替逃げ道（反証があれば差戻さない）
DENY  = re.compile(r'【反証|反証シナリオ|反証:|反証：|反証1つ|デメリット|懸念点|異論|注意点|限界|未検証|誤検知')
INJECT_MARK = re.compile(r'\[consult-balance[・\]]')
CONSULT = [
    r'どう思う', r'どうですか', r'どうだろう', r'意見を?聞かせ', r'意見して',
    r'判断(の参考|材料|を?頼)', r'相談', r'提案して', r'お勧め', r'おすすめ',
    r'教えて', r'これでいい', r'これで良い', r'賛同', r'賛成', r'レビューして',
    r'正しい(ですか|か)', r'あってる', r'合ってる',
]

transcript = payload.get('transcript_path', '')
session_id = payload.get('session_id', 'unknown')


def log(reason: str) -> None:
    try:
        import datetime
        sid = (os.environ.get('CLAUDE_CODE_SESSION_ID') or str(session_id))[:8]
        with open(os.path.join(guard_dir, 'dispatch.log'), 'a') as f:
            f.write(f"{datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} session={sid} mode={mode} exit={reason}\n")
    except Exception:
        pass


if not transcript or not os.path.exists(transcript):
    log('no-transcript')
    sys.exit(0)

# transcript走査: 最後の実userメッセージと最後のassistantテキストを抽出
last_user, last_asst = '', ''
try:
    with open(transcript, encoding='utf-8') as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('type') == 'user':
                c = d.get('message', {}).get('content', '')
                if isinstance(c, list):
                    c = ' '.join(x.get('text', '') for x in c if isinstance(x, dict))
                if isinstance(c, str) and not c.startswith('Stop hook feedback'):
                    last_user = c
            elif d.get('type') == 'assistant':
                c = d.get('message', {}).get('content', [])
                if isinstance(c, list):
                    t = ' '.join(x.get('text', '') for x in c if isinstance(x, dict) and x.get('type') == 'text')
                    if t.strip():
                        last_asst = t
except Exception:
    log('transcript-error')
    sys.exit(0)

# 適用条件: ①直前user発言が相談トリガー ②会話内に注入マーカーがある（inject hookが発動した証跡）
if not any(re.search(t, last_user) for t in CONSULT):
    log('not-consult')
    sys.exit(0)

# 会話全体の再走査は重いので、注入マーカーは last_user以降のasst/直近で判定せず
# 単純に「last_asst内にマーカーが引用されている場合」のみならず、
# 注入が効いている前提で同意語を検査する（マーカー条件は誤検知時の緩和でなく本条件としない）
if not last_asst:
    log('no-asst')
    sys.exit(0)

has_agree = bool(AGREE.search(last_asst))
if not has_agree:
    log('no-agreement')
    sys.exit(0)

# 案B（2026-09-06 3機レビュー収束・ふくけい設計批判の採用）:
# 根拠付きの同意は正当な同意であり差戻さない。差戻しは「同意+根拠ゼロ+反証ゼロ」のみ。
if BASIS.search(last_asst):
    log('has-basis')
    sys.exit(0)

if DENY.search(last_asst):
    log('has-deny-section')
    sys.exit(0)

# 同意表現あり+根拠なし+反証なし → 差戻し対象
h = hashlib.sha256(f"{session_id}:{last_user[:200]}".encode()).hexdigest()[:16]
seen = os.path.join(guard_dir, f"seen-{h}")

if mode == 'shadow':
    log('shadow-would-block')
    sys.exit(0)

if os.path.exists(seen) and mode != 'enforce':
    log('already-retried')
    sys.exit(0)

try:
    open(seen, 'w').close()
except Exception:
    pass

log('block')
msg = (
    "⚠️(consult-balance) 相談への回答に同意表現がありますが、根拠（出典・実測・論拠）と反証のどちらも見つかりません。"
    "正しいと判断するなら根拠を出典・実測付きで示すこと（根拠付きの同意は歓迎・反証は不要）。"
    "根拠を示せないなら「未検証の仮説と整合する」に留めるか、反証1つ（この判断が誤りと分かる観測事実）を追加すること。"
    "誤検知（相談でない・既に根拠を含む等）ならそのまま終了して構いません。"
    "（差戻し1回目・同一メッセージへの再差戻しはありません）"
)
print(msg, file=sys.stderr)
sys.exit(2)
PYEOF

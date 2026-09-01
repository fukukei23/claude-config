#!/usr/bin/env bash
# check-fail-coverage.sh — Stop hook（検証網羅性ゲート・5層設計b′層・2026-08-28）
# 完了宣言に「確定語(✅/合格/PASS)×検証語(検証/テスト/実測/確認)」が共起する場合、
# a′4要素（fail条件ケース/生ログ引用/閾値/環境指紋）を検査し、欠落なら差戻す。
# 発火語はPhase 0.5実測(2026-08-28・真の誤検知率25%)で確定語から「完了」を除外。
# spec v2 critical対策:
#   - 引用照合はtranscriptのtool_result側のみ（LLM自己生成テキスト/echo捏造は無効）
#   - 承認は実ユーザー入力ターン（type:userの文字列content）のみ有効
# 層構造（check-yagi-output.sh準拠）:
#   H層=CLAUDE_DISABLE_FC_CHECK=1 で無条件exit / F層=実user発言1個以下は機械呼び出しと判定し素通り
#   / dispatch.log=$GUARD_DIR/dispatch.log（256KB超で初期化）
set -euo pipefail
GUARD_DIR="$HOME/.claude/state/fc-check-guard"; mkdir -p "$GUARD_DIR"

if [ "${CLAUDE_DISABLE_FC_CHECK:-}" = "1" ]; then
  printf '%s session=%s exit=env-flag\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "${CLAUDE_CODE_SESSION_ID:-unknown}" >> "$GUARD_DIR/dispatch.log" 2>/dev/null || true
  exit 0
fi
PAYLOAD_JSON="$(cat)"
exec env PAYLOAD_JSON="$PAYLOAD_JSON" GUARD_DIR="$GUARD_DIR" python3 - <<'PYEOF'
import json, os, hashlib, datetime, re, sys

payload = json.loads(os.environ['PAYLOAD_JSON'])
guard = os.environ['GUARD_DIR']
tpath = payload.get('transcript_path', '')
sid = payload.get('session_id', 'unknown')

# 発火語（Phase 0.5実測確定・2026-08-28）: 確定語から「完了」除外（挨拶誤検知対策）
CONFIRM = ['✅', '合格', 'PASS']
VERIFY = ['検証', 'テスト', '実測', '確認']


def dispatch(reason: str) -> None:
    """dispatch.logへexit経路を1行記録（書込失敗はhookを止めない・256KB超で初期化）。"""
    try:
        p = os.path.join(guard, 'dispatch.log')
        if os.path.exists(p) and os.path.getsize(p) > 262144:
            open(p, 'w').close()
        with open(p, 'a') as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%dT%H:%M:%S} session={sid[:8]} exit={reason}\n")
    except Exception:
        pass


user_texts, tool_texts, assistant_texts = [], [], []
try:
    with open(tpath) as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get('type') == 'user':
                c = e.get('message', {}).get('content')
                if isinstance(c, str):
                    user_texts.append(c)
                elif isinstance(c, list):
                    for item in c:
                        if isinstance(item, dict) and item.get('type') == 'tool_result':
                            tool_texts.append(str(item.get('content', '')))
            elif e.get('type') == 'assistant':
                for item in e.get('message', {}).get('content', []):
                    if isinstance(item, dict) and item.get('type') == 'text':
                        assistant_texts.append(item.get('text', ''))
except FileNotFoundError:
    exit(0)

# F層: 実ユーザー発言1個以下 = 機械呼び出し(claude --print等) → 素通り
if len(user_texts) <= 1:
    dispatch('machine')
    exit(0)

# 発火判定: 最終assistantメッセージに確定語×検証語の共起
last = assistant_texts[-1] if assistant_texts else ''
if not (any(k in last for k in CONFIRM) and any(k in last for k in VERIFY)):
    exit(0)  # 検証系完了宣言ではない

# --- a′4要素検査 ---
joined_tools = '\n'.join(tool_texts[-40:])  # 直近40ツール結果のみ照合対象
errs = []
if 'fail条件' not in last and '不合格' not in last:
    errs.append('fail条件を再現する具体ケースと検証有無の記載')
# 引用検査: EXIT=N の引用がtool_result側に実在するか（偽ログ排除）
cites = re.findall(r'EXIT=\d+', last)
if cites:
    for c in cites[:3]:
        if c not in joined_tools:
            errs.append(f'引用({c})がtool実行結果に存在しない=未実施扱い')
            break
elif '未実施' not in last and '限定条件' not in last:
    errs.append('生exit code引用（実際に実行した結果からのコピペ）')
# 恒真閾値検査
if re.search(r'0[-〜~]255', last):
    errs.append('恒真閾値（exit code 0-255等）は不可・事前固定参照値と突合せよ')
# 環境指紋
if '実施済み' in last and '[fp:' not in last:
    errs.append('環境指紋suffix [fp:時刻/l1=キャッシュ行サイズ] の記載')

# --- 検証範囲宣言セクション検査（spec v5 3-1・2026-09-01） ---
# grace期間(〜2026-09-15)は警告のみ・FCC_FORCE_ENFORCE=1で強制enforce（テスト用）
DECL_LABELS = ['検証範囲宣言', '検証範囲:', '宣言:']
in_grace = datetime.date.today() <= datetime.date(2026, 9, 15) and os.environ.get('FCC_FORCE_ENFORCE') != '1'

def warn(msg: str) -> None:
    """grace中は警告表示のみ（exitに影響させない・r4 G#5アラート疲労対策）。"""
    if in_grace:
        print(f"⚠️(grace期間・警告のみ) {msg}", file=sys.stderr)
    else:
        errs.append(msg)

if not any(lbl in last for lbl in DECL_LABELS):
    warn('検証範囲宣言セクション（タイプ/正常系/異常系/境界/各ケース理由）の記載')
else:
    # タイプIII: 反証可能性チェックリスト必須
    if re.search(r'タイプ:\s*III', last) and not re.search(r'誤り|反証|気づけ|気付ける|再発', last):
        warn('タイプIIIは反証可能性チェックリスト必須（誤りの場合どういう観測で気付けるか）')
    # 異常系: min(2,N)（Phase 1は2種要求・N=1例外は「カテゴリ: 1種」形式＋理由）
    if not re.search(r'異常系[::]', last) and 'カテゴリ: 1種' not in last:
        warn('異常系ケースの宣言（min(2,N)種・1種例外は引用付き理由必須）')
    elif re.search(r'異常系[::]\s*省略', last) and '理由' not in last:
        warn('異常系の省略には理由必須')
    # 検証済宣言の証跡突合: 宣言内 EXIT=N がtool_result側に実在（エコー偽装排除）
    lbl = next(l for l in DECL_LABELS if l in last)
    decl_part = last[last.find(lbl):]
    for c in re.findall(r'EXIT=\d+', decl_part)[:5]:
        if c not in joined_tools:
            warn(f'宣言内証跡({c})がtool実行結果に存在しない=未実施扱い')
            break
    # 境界: 記載または省略理由
    if not re.search(r'境界[::]', last):
        warn('境界ケースの宣言（または省略理由）')
    elif re.search(r'境界[::]\s*省略', last) and '理由' not in last.split('境界')[1][:60]:
        warn('境界の省略には理由必須')
    # 理由欄テンプレ文検出
    if re.search(r'理由[::]\s*(バグ混入防止|品質確保のため|のため)\s*$', last, re.M):
        warn('各ケース理由がテンプレ文（fail条件欄の語と共起する具体を書く）')

# --- 判定（ errs無し=通過 / 実ユーザー承認あり=通過 / 他は差戻し） ---
if not errs:
    dispatch('pass')
    exit(0)
approved = any('承認' in u for u in user_texts[-5:])
if approved:
    dispatch('approved')
    exit(0)
key = hashlib.md5((str(sid) + last[:120]).encode()).hexdigest()[:12]
cnt_file = os.path.join(guard, f"{key}.cnt")
cnt = 0
try:
    cnt = int(open(cnt_file).read()) if os.path.exists(cnt_file) else 0
except Exception:
    cnt = 0
try:
    open(cnt_file, 'w').write(str(cnt + 1))
except Exception:
    pass
reason = '、'.join(errs[:3])
print(f"⚠️ 検証網羅性ゲート: 検証系完了宣言に以下が不足 → {reason}", file=sys.stderr)
print("　(a)fail条件ケースと検証有無 (b)tool実行結果からの生ログ引用(実際に実行した結果のみ有効)", file=sys.stderr)
print("　(c)不合格閾値(事前固定参照値と突合・恒真閾値禁止) (d)環境指紋[fp:時刻/l1]", file=sys.stderr)
print(f"　差戻し{cnt + 1}回目。誤検知なら要点を添えて終了可 / 本当に通す必要がある時はユーザーの「承認」入力で通過", file=sys.stderr)
dispatch(f"blocked:{errs[0][:30]}")
exit(2)
PYEOF

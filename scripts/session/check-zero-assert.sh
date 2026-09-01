#!/usr/bin/env bash
# check-zero-assert.sh — Stop hook（ゼロ断定ゲート・spec v5 3-2・2026-09-01）
# 「ゼロ/のみ/見つからない」断定語×検索語の共起時、固定プロトコル再検索の
# M>N事実（transcript tool_result内）を要求し、無ければ差戻す。
# 逆用封じ（r3レビュー）: 再検索はLLMが固定プロトコルをコピー実行する方式で、
# hookは検証のみ（hook内で検索を実行しない=コンテキスト喪失回避）。
# 層構造（check-fail-coverage.sh準拠）:
#   H層=CLAUDE_DISABLE_ZA_CHECK=1 で無条件exit / F層=実user発言1個以下は機械呼び出しと判定し素通り
#   / dispatch.log=$GUARD_DIR/dispatch.log（256KB超で初期化）
set -euo pipefail
GUARD_DIR="$HOME/.claude/state/za-check-guard"; mkdir -p "$GUARD_DIR"

if [ "${CLAUDE_DISABLE_ZA_CHECK:-}" = "1" ]; then
  printf '%s session=%s exit=env-flag\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "${CLAUDE_CODE_SESSION_ID:-unknown}" >> "$GUARD_DIR/dispatch.log" 2>/dev/null || true
  exit 0
fi
PAYLOAD_JSON="$(cat)"
exec env PAYLOAD_JSON="$PAYLOAD_JSON" GUARD_DIR="$GUARD_DIR" python3 - <<'PYEOF'
import json, os, re, sys, hashlib, datetime

payload = json.loads(os.environ['PAYLOAD_JSON'])
guard = os.environ['GUARD_DIR']
tpath = payload.get('transcript_path', '')
sid = payload.get('session_id', 'unknown')

def log(reason: str) -> None:
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
    log('machine')
    exit(0)

# 発火判定: ゼロ断定語×検索文脈の共起
last = assistant_texts[-1] if assistant_texts else ''
ZERO_WORDS = ['ゼロ件', 'ゼロだった', '0件だった', '見つからなかった', '見つからない',
              '参照元はゼロ', '参照元はない', '存在しない', '該当なし']
search_ctx = re.search(r'(grep|find |rg |検索|参照元|参照|ヒット)', last)
is_zero_assert = any(w in last for w in ZERO_WORDS) and bool(search_ctx)
if not is_zero_assert:
    exit(0)  # ゼロ断定ではない

# M>N再検索事実の検証: 「再検索」ラベル + tool_result側にgrep -rln が2回以上
# （1回目＋固定プロトコル再検索・r3「セレモニー再検索」封じの最低条件）
joined = '\n'.join(tool_texts[-40:])
has_research = bool(re.search(r'再検索', last)) and len(re.findall(r'grep -rln', joined)) >= 2
override = any('!override' in u for u in user_texts[-5:])
if has_research or override:
    log('pass' if has_research else 'override')
    exit(0)

print("⚠️ ゼロ断定ゲート: 「ゼロ件」断定に固定プロトコル再検索（M>N差分）の実行事実がありません。", file=sys.stderr)
print("　再検索: grep -rln --include={py,sh,md,ts,js,json,yaml} <検索語> <対象ルート>（head無し）を実行し、", file=sys.stderr)
print("　1回目件数N→再検索件数M を報告してください（M>Nを確認・r3レビュー固定プロトコル）。", file=sys.stderr)
print("　ゼロで正しい場合は !override <理由> を入力で通過できます。誤検知なら要点を添えて終了可。", file=sys.stderr)
log('blocked')
exit(2)
PYEOF

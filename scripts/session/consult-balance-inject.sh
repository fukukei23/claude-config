#!/usr/bin/env bash
# consult-balance-inject.sh — UserPromptSubmit hook
# ふくけいの発言が「判断の相談」と判定された場合、CCへの応答コンテキストに
# 迎合防止の回答フォーマット指示（【根拠】【反証1つ】【意見】）を自動注入する。
# 背景: 2026-09-05 就活戦略相談でCCが未検証の市場読みに「正しい」と同調（迎合）。
# 実例: 00_SYSTEM/参考資料/LLMサボりバイアス実例/2026-09-05_就活戦略相談での迎合同調-未検証の市場読みを正しいと肯定.md
# 誤検知対策: ①トリガーは語彙+文末疑問の組合せ ②短い発言(<8字)は無視 ③注入はexit 0のstdout追加のみ（ブロックしない）
# 設定: ~/.claude/state/consult-balance-guard/disabled があれば無効（オプトアウト）
set -euo pipefail

GUARD_DIR="${GUARD_DIR:-$HOME/.claude/state/consult-balance-guard}"
if [ -f "$GUARD_DIR/disabled" ]; then
  exit 0
fi

PAYLOAD_JSON="$(cat)"
exec env PAYLOAD_JSON="$PAYLOAD_JSON" python3 - <<'PYEOF'
import sys, json, os, re

payload = json.loads(os.environ['PAYLOAD_JSON'])
prompt = payload.get('prompt', '') or ''

if len(prompt.strip()) < 8:
    sys.exit(0)

# 相談トリガー（判断・意見・提案を求める語彙）
TRIGGERS = [
    r'どう思う', r'どうですか', r'どうだろう', r'意見を?聞かせ', r'意見して',
    r'判断(の参考|材料|を?頼)', r'相談', r'提案して', r'お勧め', r'おすすめ',
    r'教えて', r'これでいい', r'これで良い', r'賛同', r'賛成', r'レビューして',
    r'正しい(ですか|か)', r'あってる', r'合ってる',
]
if not any(re.search(t, prompt) for t in TRIGGERS):
    sys.exit(0)

msg = (
    "[consult-balance・迎合防止] この発言は判断の相談と判定されました。"
    "①相談者の主張を事実主張と意見主張に分けて扱うこと: 事実主張は自身の知識で裏取りし、"
    "知識外なら「検証できない」と明示する。意見主張はその論拠に対して支持か反論かを述べる。"
    "②「正しい/賛成」は根拠（出典・実測・論拠）とセットなら積極的に使ってよい（正しいことは正しいと言う）。"
    "根拠を示せない場合は「未検証の仮説と整合する」までに留め、反証1つ（誤りと分かる観測事実）を添えること。"
    "③無理やり反論を作らなくてよい。ただし賛成の場合も考慮すべき論点があれば1つ添える（強制しない）。"
    "④相談者の主観的実体験はCCに裏取り不能であることを明示してから扱うこと。"
)
print(msg)
PYEOF

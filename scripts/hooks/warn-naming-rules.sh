#!/bin/bash
# warn-naming-rules.sh — 呼称ルール違反の警告表示（ブロックなし・spec 2026-08-29承認）
# 対象: obsidian-ssot配下 + ~/.claude/rules配下 + claude-config配下のmd編集で
#       (私|ユーザー)(が|の|に|を|から|へ|は|も) を含む箇所
# 除外: 外向きディレクトリ(20_PUBLISHING/40_CAREER)・第三者意味の複合語（**単語単位判定**）
# 出力: exit 0 常時 + 違反時に additionalContext JSON（exit 2 にしない=ブロックしない）
# 改訂履歴: r2=助詞は/も追加+MultiEdit対応+対象拡張 / r3=検出をpython単一パス化（行全体grep除外の
#           同行混在検知漏れを修正・Gemini#1 critical）+ stdin渡し化
set -euo pipefail
INPUT=$(cat)

RESULT=$(echo "$INPUT" | python3 -c '
import json, sys, re
try:
    d = json.load(sys.stdin)
except Exception:
    print(""); sys.exit(0)
ti = d.get("tool_input", {})
fp = (ti.get("file_path", "") or "").replace("\\", "/")  # Windows Desktop版のパス区切り正規化(2026-08-30)
# 対象パス判定（obsidian-ssot / .claude/rules / claude-config）
if not ("obsidian-ssot" in fp or "/.claude/rules" in fp or fp.startswith(".claude/rules") or "claude-config" in fp):
    print(""); sys.exit(0)
# 外向き除外
if "20_PUBLISHING" in fp or "40_CAREER" in fp:
    print(""); sys.exit(0)
text = "\n".join([ti.get("new_string","") or "", ti.get("content","") or ""] +
                 [e.get("new_string","") or "" for e in (ti.get("edits") or [])])
# 第三者複合語を単語単位で除去してから検出（同行混在でも取りこぼさない・r3）
third = re.compile(r"(エンド|一般|対象|他の|第三者の|API|サービス|顧客|クライアント|リリースノート)ユーザー")
pat = re.compile(r"(私|ユーザー)(が|の|に|を|から|へ|は|も)")
hits = []
for i, line in enumerate(text.split("\n"), 1):
    cleaned = third.sub("__THIRD__", line)
    for m in pat.finditer(cleaned):
        hits.append("%d:%d:%s" % (i, m.start()+1, m.group(0)))
        if len(hits) >= 5: break
    if len(hits) >= 5: break
print("\n".join(hits))
' 2>/dev/null || echo "")

if [ -n "$RESULT" ]; then
  printf '%s' "$RESULT" | python3 -c "
import json, sys
hits = sys.stdin.read()
msg = '⚠️ 呼称ルール違反の疑い（spec 2026-08-29）: 人間=「ふくけい」/LLM=「CC」の固定名詞を使用（「私」「ユーザー（人間意味）」は書かない。機械的置換でなく主体判定で書き分け）。該当行:行内位置:語:\n' + hits
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': msg}}, ensure_ascii=False))"
fi
exit 0

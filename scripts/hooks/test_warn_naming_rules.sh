#!/bin/bash
# test_warn_naming_rules.sh — warn-naming-rules.sh の単体テスト
HOOK="$HOME/.claude/scripts/hooks/warn-naming-rules.sh"
pass=0; fail=0
check() { # name, expected(0=警告なし,1=警告あり), stdin_json
  local name="$1" exp="$2" json="$3"
  out=$(echo "$json" | bash "$HOOK" 2>/dev/null); rc=$?
  if [ $rc -ne 0 ]; then echo "FAIL($name): exit=$rc (常時0であるべき)"; fail=$((fail+1)); return; fi
  if echo "$out" | grep -q "additionalContext"; then got=1; else got=0; fi
  if [ "$got" = "$exp" ]; then pass=$((pass+1)); else echo "FAIL($name): expected=$exp got=$got"; fail=$((fail+1)); fi
}
# 1: 私が → 警告
check "watakushi-ga" 1 '{"tool_name":"Edit","tool_input":{"file_path":"/home/yn4416/projects/obsidian-ssot/10_DAILY/2026-08-29.md","new_string":"私が実装した"}}'
# 2: ユーザーが → 警告
check "user-ga" 1 '{"tool_name":"Write","tool_input":{"file_path":"/home/yn4416/projects/obsidian-ssot/01_DECISIONS/x.md","content":"ユーザーが承認"}}'
# 3: 助詞違い（私に）→ 警告（spec §5正規表現）
check "watakushi-ni" 1 '{"tool_name":"Edit","tool_input":{"file_path":"/home/yn4416/projects/obsidian-ssot/10_DAILY/x.md","new_string":"私に任せて"}}'
# 4: 違反なし → 警告なし
check "clean" 0 '{"tool_name":"Edit","tool_input":{"file_path":"/home/yn4416/projects/obsidian-ssot/10_DAILY/x.md","new_string":"CCが実装した"}}'
# 5: エンドユーザー（他文脈）→ 警告なし
check "end-user" 0 '{"tool_name":"Edit","tool_input":{"file_path":"/home/yn4416/projects/obsidian-ssot/30_RESEARCH/x.md","new_string":"エンドユーザーが使う"}}'
# 6: 外向きディレクトリ → exclude（警告なし）
check "external" 0 '{"tool_name":"Edit","tool_input":{"file_path":"/home/yn4416/projects/obsidian-ssot/20_PUBLISHING/x.md","new_string":"私が作りました"}}'
# 7: SSOT外のファイル → 対象外（警告なし）
check "outside" 0 '{"tool_name":"Edit","tool_input":{"file_path":"/home/yn4416/projects/atelier/x.md","new_string":"私が直した"}}'
# 8: 「私は」助詞は → 警告（r2レビューGemini#1・最頻出形式）
check "watakushi-wa" 1 '{"tool_name":"Edit","tool_input":{"file_path":"/home/yn4416/projects/obsidian-ssot/10_DAILY/x.md","new_string":"私は実装した"}}'
# 9: 「ユーザーは」→ 警告（r2レビューGemini#1）
check "user-wa" 1 '{"tool_name":"Edit","tool_input":{"file_path":"/home/yn4416/projects/obsidian-ssot/10_DAILY/x.md","new_string":"ユーザーは承認した"}}'
# 10: MultiEdit edits配列のnew_string → 警告（r2レビューGemini#2）
check "multiedit" 1 '{"tool_name":"MultiEdit","tool_input":{"file_path":"/home/yn4416/projects/obsidian-ssot/10_DAILY/x.md","edits":[{"old_string":"a","new_string":"私が直した"}]}}'
# 11: 層1ルール配下 → 対象（警告あり・r2レビューGemini#4）
check "rules-path" 1 '{"tool_name":"Edit","tool_input":{"file_path":"/home/yn4416/.claude/rules/_shared/呼称.md","new_string":"ユーザーが確認"}}'
# 12: APIユーザー（第三者・r2レビューOR#4の除外ワード拡張）→ 警告なし
check "api-user" 0 '{"tool_name":"Edit","tool_input":{"file_path":"/home/yn4416/projects/obsidian-ssot/30_RESEARCH/x.md","new_string":"APIユーザーが増えた"}}'
# 13: 同行混在（エンドユーザー＋私が）→ 警告あり（r3レビューGemini#1 criticalの回帰テスト）
check "mixed-line" 1 '{"tool_name":"Edit","tool_input":{"file_path":"/home/yn4416/projects/obsidian-ssot/10_DAILY/x.md","new_string":"エンドユーザーの要件を確認し、私が実装しました"}}'
echo "PASS=$pass FAIL=$fail"; [ $fail -eq 0 ]

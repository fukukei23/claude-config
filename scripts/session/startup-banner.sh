#!/bin/bash
# startup-banner.sh — 各フックのステータスを集約して1つのバナーを出力
# SessionStart hooks の最後に配置すること
# stdoutに出力（Desktop App対応 — /dev/ttyはDesktopアプリで使用不可）

STATUS_DIR="/tmp/claude-startup"
mkdir -p "$STATUS_DIR"

# --- 全ステータスファイルを読み込んで集計 ---
ok_count=0
warn_count=0
warn_names=()
warn_messages=()

for f in "$STATUS_DIR"/*.status; do
  [ -f "$f" ] || continue
  name=$(basename "$f" .status)
  content=$(cat "$f")
  [ -z "$content" ] && continue

  if echo "$content" | grep -q '^ ✅'; then
    ok_count=$((ok_count + 1))
  elif echo "$content" | grep -qE '^ (⚠️|❌)'; then
    warn_count=$((warn_count + 1))
    warn_names+=("$name")
    warn_messages+=("$content")
  fi
done

total=$((ok_count + warn_count))

# --- ハンドオフ情報 ---
HANDOFF_FILE="$HOME/.claude/state/handoff.md"
handoff_line="（初回セッション）"
if [ -f "$HANDOFF_FILE" ]; then
  handoff_line=$(head -1 "$HANDOFF_FILE" | sed 's/^# //')
fi

# --- 本日セッション数 ---
SSOT_PATH="/home/yn4416/projects/obsidian-ssot"
TODAY=$(date +%Y-%m-%d)
DAILY_LOG="$SSOT_PATH/10_DAILY/$TODAY.md"
session_info="本日初回"
if [ -f "$DAILY_LOG" ]; then
  SESSION_COUNT=$(grep -c "^## セッションログ" "$DAILY_LOG" 2>/dev/null)
  if [ "$SESSION_COUNT" -gt 0 ]; then
    LAST_TASK=$(grep "^## セッションログ" "$DAILY_LOG" | tail -1 | sed 's/.* — //; s/^## セッションログ$//' | cut -c1-30)
    END_TIME=$(grep "^セッション終了:" "$DAILY_LOG" | tail -1 | sed 's/セッション終了: //')
    session_info="本日${SESSION_COUNT}セッション | 最終: ${LAST_TASK} (${END_TIME}終了)"
  fi
fi

# --- バナー生成 ---
SEP="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$total" -eq 0 ]; then
  hook_summary=" フック: ステータスなし"
elif [ "$warn_count" -eq 0 ]; then
  hook_summary=" ✅ フック: ${total}/${total} 全正常"
else
  name_list=$(IFS=', '; echo "${warn_names[*]}")
  hook_summary=" ⚠️  フック: ${ok_count}/${total} 正常 | 要確認: ${name_list}"
fi

banner=""
banner+="$(printf '%s\n' "$SEP")"$'\n'
banner+="$(printf ' 🚀 Claude Code セッション開始\n')"$'\n'
banner+="$(printf '%s\n' "$hook_summary")"$'\n'

if [ "$warn_count" -gt 0 ]; then
  for msg in "${warn_messages[@]}"; do
    banner+="$(printf '%s\n' "$msg")"$'\n'
  done
fi

banner+="$(printf '%s\n' "$SEP")"$'\n'
banner+="$(printf ' 📋 前回: %s\n' "$handoff_line")"$'\n'
banner+="$(printf ' 📝 %s\n' "$session_info")"$'\n'
banner+="$(printf '%s\n' "$SEP")"$'\n'

# --- スキルトリガーマップ（各スキルのトリガーワード欄から自動生成） ---
SKILLS_DIR="$HOME/.claude/skills"
if [ -d "$SKILLS_DIR" ]; then
  trigger_map=""
  for skill_entry in "$SKILLS_DIR"/*; do
    # ディレクトリならSKILL.md、ファイルならそのまま
    if [ -d "$skill_entry" ]; then
      skill_file="$skill_entry/SKILL.md"
      [ -f "$skill_file" ] || continue
    elif [ -f "$skill_entry" ]; then
      skill_file="$skill_entry"
    else
      continue
    fi
    skill_name=$(basename "$skill_entry" .md)
    # トリガーワード行を抽出
    triggers=$(grep -A3 'トリガーワード' "$skill_file" 2>/dev/null | grep -v 'トリガーワード' | grep -v '^--' | grep -v '^$' | head -2 | sed 's/^[[:space:]]*//' | tr '\n' ' ' | sed 's/  */ /g' | sed 's/ *$//')
    if [ -n "$triggers" ]; then
      trigger_map+="  ${skill_name}: ${triggers}"$'\n'
    fi
  done
  if [ -n "$trigger_map" ]; then
    banner+="$(printf ' 🔧 スキルトリガーマップ:\n')"$'\n'
    banner+="$trigger_map"
  fi
fi


# ── 層1読込検証（@取り込み実働チェック・2026-08-17）──
# CLAUDE.mdの@参照ファイルの存在確認 + LLM引用チャレンジ（中身は表示しない=引用できれば読込証明）
banner+=" ── 層1読込検証 ──"$'\n'
missing=0
while IFS= read -r rel; do
  p="$HOME/.claude/$rel"
  if [ -f "$p" ]; then
    banner+="   ✅ ${rel##*/} ($(wc -c < "$p")B)"$'\n'
  else
    banner+="   ❌ $rel 不在（@取り込みが空読みになる）"$'\n'
    missing=1
  fi
done < <(grep -oE '@rules/[^[:space:]]+\.md' "$HOME/.claude/CLAUDE.md" 2>/dev/null | sed 's/^@//')
target="$HOME/.claude/rules/_shared/LLMサボりバイアス防止.md"
if [ -f "$target" ]; then
  mapfile -t head_lines < <(grep -n '^## ' "$target" | cut -d: -f1)
  if [ "${#head_lines[@]}" -gt 0 ]; then
    chal=${head_lines[$((RANDOM % ${#head_lines[@]}))]}
    banner+="   ▶ 挑戦: 『LLMサボりバイアス防止.md』${chal}行目の見出し（## 始まり）を返答冒頭で引用せよ。引用できなければ層1読込不調の疑い（同期・再起動を確認）"$'\n'
  fi
fi
[ "$missing" = 1 ] && banner+="   ⚠️ 不在ファイルあり: 層1が正しく読み込まれていない可能性"$'\n'

printf '%s\n' "$banner"

#!/usr/bin/env bash
# git-commit-diff-check.sh — git commit の stage 内容を行数ベースで検査するPreToolUse Hook
# ±10行超=warn(stderr/exit0)・±20行超=block(exit2)・DRY_RUN=1で全warn・SSOT_AUTO_SYNC=1で除外
# 8/4型(他タブ48行巻き込み)事故の再発防止・spec §1
set -uo pipefail

# 観測ロガー(F案・spec §1.6) — flock排他・|| true fallback・1MB rotation
# 書込失敗はhook本体に影響させない（doubt-driven #4 fallback）
LOG_FILE="${GIT_COMMIT_DIFF_CHECK_LOG:-$HOME/.claude/state/git-commit-diff-check.log}"
log_append() {
  local entry="$1"
  (
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    flock -w 1 200 2>/dev/null || true
    printf '[%s] %s\n' "$(date '+%F %T')" "$entry" >> "$LOG_FILE" 2>/dev/null || true
    local sz
    sz=$(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$sz" -gt 1048576 ]; then
      tail -c 524288 "$LOG_FILE" > "${LOG_FILE}.tmp" 2>/dev/null && mv "${LOG_FILE}.tmp" "$LOG_FILE" 2>/dev/null || true
    fi
  ) 200>"${LOG_FILE}.lock" 2>/dev/null || true
}

INPUT=$(cat)

# tool_name 抽出（純bash）
tool_name=$(printf '%s' "$INPUT" | grep -o '"tool_name":"[^"]*"' | head -1 | sed 's/^"tool_name":"//;s/"$//')

if [[ "$tool_name" != "Bash" ]]; then
  exit 0
fi

# command 抽出
cmd=$(printf '%s' "$INPUT" | sed -n 's/.*"command" *: *"\(.*\)".*/\1/p' | head -1)

# git commit 以外は対象外
if ! echo "$cmd" | grep -qE 'git[[:space:]]+commit'; then
  exit 0
fi

# auto-sync経路除外（層1のauto-sync誤block防止・spec §4.2）
if [[ "${SSOT_AUTO_SYNC:-}" == "1" ]]; then
  exit 0
fi

# staged diff の行数取得
numstat=$(git diff --cached --numstat 2>/dev/null)
if [ -z "$numstat" ]; then
  exit 0  # staged empty or not a git repo
fi

# max delta 計算（insertions/deletions の大きい方）
max_delta=0
max_file=""
while IFS=$'\t' read -r ins del file; do
  # バイナリ等の "-" は除外
  [[ "$ins" == "-" || "$del" == "-" ]] && continue
  delta=$(( ins > del ? ins : del ))
  if [ "$delta" -gt "$max_delta" ]; then
    max_delta=$delta
    max_file=$file
  fi
done <<< "$numstat"

# max_file の status 判定（A=新規/M=修正/R=リネーム・doubt-driven #7 正規/非正規タグ基盤）
file_status="?"
if [ -n "$max_file" ]; then
  ns_line=$(git diff --cached --name-status -- "$max_file" 2>/dev/null | head -1 | cut -f1)
  [ -n "$ns_line" ] && file_status="${ns_line:0:1}"
fi

WARN_THRESHOLD=10
BLOCK_THRESHOLD=20
# dry-run mode: block無効化（Phase 0運用・spec §3）
if [[ "${DRY_RUN:-}" == "1" ]]; then
  BLOCK_THRESHOLD=999999
fi

if [ "$max_delta" -gt "$BLOCK_THRESHOLD" ]; then
  cat >&2 <<EOF
[GIT-COMMIT-DIFF-CHECK]
EXIT_CODE=2
REASON=stage変動が1ファイル±${BLOCK_THRESHOLD}行超を検出: ${max_file} (max delta=${max_delta})
MAX_DELTA=${max_delta}
FILE=${max_file}
REQUIRED_ACTION=git diff --cached --stat で内容確認後にcommit再実行 または git restore --staged ${max_file} で巻き込みファイル除外
---
EOF
  log_append "BLOCK delta=${max_delta} file=${max_file} status=${file_status} exit=2"
  exit 2
fi

if [ "$max_delta" -gt "$WARN_THRESHOLD" ]; then
  cat >&2 <<EOF
[GIT-COMMIT-DIFF-CHECK]
EXIT_CODE=0
REASON=stage変動が1ファイル±${WARN_THRESHOLD}行超を検出: ${max_file} (max delta=${max_delta})・確認推奨
MAX_DELTA=${max_delta}
FILE=${max_file}
REQUIRED_ACTION=git diff --cached --stat で内容確認推奨（block無・commit継続）
---
EOF
  log_append "WARN delta=${max_delta} file=${max_file} status=${file_status} exit=0"
fi

exit 0

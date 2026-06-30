#!/bin/bash
# check-link-policy.sh — 禁止層への [[ ]] 増分を SessionStart で検知
# 方針ファイル: obsidian-ssot/00_SYSTEM/リンク運用方針.md (frontmatter: forbidden_dirs)
# 既存 [[ ]] は放置。**git diff 増分のみ**を違反として警告する。
set -uo pipefail

SSOT_PATH="/home/yn4416/projects/obsidian-ssot"
[ -d "$SSOT_PATH" ] || exit 0
[ -d "$SSOT_PATH/.git" ] || exit 0

STATUS_DIR="/tmp/claude-startup"
mkdir -p "$STATUS_DIR"

# 方針ファイルから forbidden_dirs を抽出（Pythonで frontmatter 簡易パース）
FORBIDDEN=$(cd "$SSOT_PATH" && /usr/bin/python3 - <<'PYEOF'
import re, sys
from pathlib import Path
p = Path("00_SYSTEM/リンク運用方針.md")
if not p.exists():
    sys.exit(0)
text = p.read_text(encoding="utf-8")
# YAML リスト抜粋
m = re.search(r"^forbidden_dirs:\s*\n((?:\s+-\s+.+\n)+)", text, re.MULTILINE)
if not m:
    sys.exit(0)
dirs = re.findall(r"-\s+\"([^\"]+)\"", m.group(1))
print(" ".join(dirs))
PYEOF
)

if [ -z "$FORBIDDEN" ]; then
    echo " ✅ リンク方針: 方針ファイル未読込" > "$STATUS_DIR/link-policy.status"
    exit 0
fi

# git diff で HEAD からの追加行を抽出し、forbidden_dirs 配下の .md で [[ ]] 増えてないか確認
# awk 内で diff ヘッダ/diffマーカ/追加行を全て判定（grep 前段フィルタは使わない）
VIOLATIONS=$(cd "$SSOT_PATH" && git diff HEAD --unified=0 -- '*.md' 2>/dev/null \
  | awk -v dirs="$FORBIDDEN" '
      /^diff --git a\/[^ ]+ b\// {
          match($0, /b\/(.+)$/, arr); current = arr[1]; next
      }
      /^\+\+\+ / || /^@@/ { next }
      /^\+[^+]/ {
          # コメント通り「[[ ]] 増分のみ」を違反とするため、
          # [[ を含まない追加行（通常のテキスト追記など）は対象外
          if (index($0, "[[") == 0) next
          n = split(dirs, d, " ")
          for (i=1; i<=n; i++) {
              if (index(current, d[i]) == 1) {
                  print current ":" $0
                  break
              }
          }
      }
  ')

if [ -z "$VIOLATIONS" ]; then
    echo " ✅ リンク方針: 違反なし（禁止層に新規 [[ ]] 増分なし）" > "$STATUS_DIR/link-policy.status"
else
    COUNT=$(echo "$VIOLATIONS" | wc -l)
    echo " ⚠️ リンク方針: 禁止層に新規 [[ ]] ${COUNT}件（詳細は link-policy.log）" > "$STATUS_DIR/link-policy.status"
    echo "$VIOLATIONS" > "$STATUS_DIR/link-policy.log"
fi

exit 0

#!/bin/bash
# check-broken-links.sh — SSOT内のリンク切れを検出
# 対象: 00_SYSTEM/ + 01_DECISIONS/ + 10_DAILY/(直近60日) + 40_CAREER/
# 除外: 99_ARCHIVE/, 50_PROJECTS/(サブモジュール), 古い日記, 外部URL, コードブロック内
set -uo pipefail

SSOT_PATH="/home/yn4416/projects/obsidian-ssot"
[ -d "$SSOT_PATH" ] || exit 0

STATUS_DIR="/tmp/claude-startup"
mkdir -p "$STATUS_DIR"

RESULT=$(/usr/bin/python3 - "$SSOT_PATH" <<'PYEOF'
import sys, os, re
from pathlib import Path
from datetime import datetime, timedelta

vault = Path(sys.argv[1])
os.chdir(vault)

# --- 対象ファイルの収集 ---
cutoff = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
target_files = []

for md in vault.rglob('*.md'):
    rel = str(md.relative_to(vault))
    # 除外
    if rel.startswith('99_ARCHIVE/'):
        continue
    if rel.startswith('50_PROJECTS/'):
        continue
    # 10_DAILYは直近60日のみ
    if rel.startswith('10_DAILY/'):
        date_part = rel.replace('10_DAILY/', '').replace('.md', '')
        if date_part < cutoff:
            continue
    target_files.append(md)

# --- リンク抽出と検証 ---
wikilink_re = re.compile(r'\[\[([^\]|#]+)')
mdlink_re = re.compile(r'\[([^\]]*)\]\(([^)]+\.md)\)')

broken = []

for md in target_files:
    rel = str(md.relative_to(vault))
    try:
        content = md.read_text(errors='ignore')
    except:
        continue

    # コードブロック・インラインコードを除去（誤検知防止）
    clean = re.sub(r'```[\s\S]*?```', '', content)
    clean = re.sub(r'`[^`]+`', '', clean)

    # [[wikilinks]] — セクション(#)は除去済み
    for m in wikilink_re.finditer(clean):
        target = m.group(1).strip()
        # 外部リンク・特殊リンク・シェル変数は除外
        if target.startswith('http') or target.startswith('x-') or target in ('x', 'projects/MOC'):
            continue
        if any(c in target for c in ('$', '~', '#!', '-z ', '-f ', '-n ', '-d ', '-e ')):
            continue
        # ファイルを探す
        found = False
        # 1. 相対パス
        resolved = (md.parent / target).resolve()
        if resolved.exists() and resolved.is_file():
            found = True
        # 2. vaultルートからの相対パス
        if not found:
            resolved2 = (vault / target)
            if resolved2.exists() and resolved2.is_file():
                found = True
        # 3. ファイル名でvault内検索
        if not found:
            basename = Path(target).name
            if basename:
                for candidate in vault.rglob(basename):
                    found = True
                    break
                if not found:
                    for candidate in vault.rglob(basename + '.md'):
                        found = True
                        break
                # 4. 部分一致（日付プレフィックスなしのwikilink用）
                if not found:
                    for candidate in vault.rglob('*' + basename + '*'):
                        if candidate.suffix == '.md':
                            found = True
                            break
        if not found:
            broken.append((rel, f'[[{target}]]'))

    # [text](path.md)
    for m in mdlink_re.finditer(clean):
        target = m.group(2)
        if target.startswith('http'):
            continue
        resolved = (md.parent / target)
        # .claude/plans等のvault外は除外
        if '..' in target and str(resolved.resolve()).startswith(str(vault)):
            if not resolved.resolve().exists():
                broken.append((rel, f'[]({target})'))
        elif '..' not in target:
            if not resolved.exists():
                broken.append((rel, f'[]({target})'))

# --- 出力 ---
total = len(target_files)
broken_count = len(broken)
print(f"TOTAL:{total}")
print(f"BROKEN:{broken_count}")

# 重複排除して上位表示
seen = set()
unique = 0
for src, link in broken:
    key = f"{src}:{link}"
    if key not in seen:
        seen.add(key)
        unique += 1
        if unique <= 15:
            print(f"  {src}: {link}")

if unique > 15:
    print(f"  ... 他{unique - 15}件")
PYEOF
)

TOTAL=$(echo "$RESULT" | grep '^TOTAL:' | cut -d: -f2)
BROKEN=$(echo "$RESULT" | grep '^BROKEN:' | cut -d: -f2)
DETAILS=$(echo "$RESULT" | grep -v '^TOTAL:' | grep -v '^BROKEN:' | grep -v '^$')

if [ "$BROKEN" = "0" ]; then
  MSG=" ✅ リンク: 全${TOTAL}ファイル問題なし"
else
  MSG=" ⚠️ リンク切れ: ${BROKEN}件（アクティブファイル）"
fi

echo "$MSG" > "$STATUS_DIR/broken-links.status"

# 詳細レポート（デバッグ用）
if [ "$BROKEN" != "0" ]; then
  echo "$DETAILS" > "$STATUS_DIR/broken-links.detail"
fi

exit 0

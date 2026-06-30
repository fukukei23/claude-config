#!/bin/bash
# auto-fix-links.sh — リンク切れを自動修正
# check-broken-links.sh の後に実行。検出→候補探索→一意なら自動修正
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

cutoff = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')

# --- 対象ファイル収集 ---
target_files = []
for md in vault.rglob('*.md'):
    rel = str(md.relative_to(vault))
    if rel.startswith('99_ARCHIVE/') or rel.startswith('50_PROJECTS/'):
        continue
    if rel.startswith('10_DAILY/'):
        date_part = rel.replace('10_DAILY/', '').replace('.md', '')
        if date_part < cutoff:
            continue
    target_files.append(md)

wikilink_re = re.compile(r'\[\[([^\]|#]+?)(\|[^]]+)?\]\]')
mdlink_re = re.compile(r'\[([^\]]*)\]\(([^)]+\.md)\)')

fixed = 0
unfixed = []

for md in target_files:
    rel = str(md.relative_to(vault))
    try:
        content = md.read_text(errors='ignore')
    except:
        continue

    # コードブロック除去
    clean = re.sub(r'```[\s\S]*?```', '', content)
    clean = re.sub(r'`[^`]+`', '', clean)

    original = content
    modified = content

    # === [[wikilink]] の修正 ===
    for m in wikilink_re.finditer(clean):
        target = m.group(1).strip()
        display = m.group(2) or ''  # |text or empty

        if target.startswith('http') or target.startswith('x-'):
            continue
        if any(c in target for c in ('$', '~', '#!', '-z ', '-f ', '-n ', '-d ', '-e ')):
            continue
        if target in ('x', 'projects/MOC'):
            continue

        # 既に解決できるならスキップ
        if (md.parent / target).resolve().exists():
            continue
        if (vault / target).exists():
            continue

        # --- 自動修正ロジック ---

        # A. ファイル名部分一致（日付プレフィックスなし）
        basename = Path(target).name
        candidates = list(vault.rglob('*' + basename + '*'))
        candidates = [c for c in candidates if c.suffix == '.md' and '50_PROJECTS' not in str(c)]
        # ディレクトリパス付きの場合はパスも一致させる
        if '/' in target:
            dir_part = str(Path(target).parent)
            candidates = [c for c in candidates if dir_part in str(c.relative_to(vault))]
        if len(candidates) == 1:
            new_path = str(candidates[0].relative_to(vault))
            old_link = f'[[{target}{display}]]'
            new_link = f'[[{new_path}{display}]]'
            modified = modified.replace(old_link, new_link)
            fixed += 1
            continue

        # B. vaultルート相対で解決
        vault_target = vault / target
        if vault_target.exists() and vault_target.is_file():
            # リンクは正しい（vaultルートから）→何もしない
            continue

        # C. 日付プレフィックスなしのwikilink（ディレクトリパスなし）
        if '/' not in target:
            cands = list(vault.rglob('*' + target + '*'))
            cands = [c for c in cands if c.suffix == '.md' and '50_PROJECTS' not in str(c)]
            if len(cands) == 1:
                new_name = cands[0].name.replace('.md', '')
                old_link = f'[[{target}{display}]]'
                new_link = f'[[{new_name}{display}]]'
                modified = modified.replace(old_link, new_link)
                fixed += 1
                continue

    # === [text](path.md) の修正 ===
    for m in mdlink_re.finditer(clean):
        target = m.group(2)
        text = m.group(1)
        if target.startswith('http'):
            continue

        resolved = (md.parent / target)
        if resolved.exists():
            continue
        # vault外への..パスはスキップ
        if '..' in target and not str(resolved.resolve()).startswith(str(vault)):
            continue

        # D. ../ 不足（同階層になく、1つ上にある）
        parent_target = md.parent.parent / target
        if not resolved.exists() and parent_target.exists():
            dirname = md.parent.name
            new_target = f'../{target}'
            old = f'[{text}]({target})'
            new = f'[{text}]({new_target})'
            modified = modified.replace(old, new)
            fixed += 1
            continue

        # E. ファイル名検索（リネームされたファイル）
        basename = Path(target).name
        if basename:
            cands = list(vault.rglob(basename))
            cands = [c for c in cands if '50_PROJECTS' not in str(c)]
            if len(cands) == 1:
                new_rel = os.path.relpath(str(cands[0]), str(md.parent))
                old = f'[{text}]({target})'
                new = f'[{text}]({new_rel})'
                modified = modified.replace(old, new)
                fixed += 1
                continue

    # ファイルに書き戻し
    if modified != original:
        md.write_text(modified, encoding='utf-8')

print(f"FIXED:{fixed}")
PYEOF
)

FIXED=$(echo "$RESULT" | grep '^FIXED:' | cut -d: -f2)

# 修正後にチェッカーを再実行してステータス更新
/home/yn4416/.claude/scripts/obsidian/check-broken-links.sh

NEW_STATUS=$(cat "$STATUS_DIR/broken-links.status" 2>/dev/null || echo "不明")

if [ "$FIXED" = "0" ]; then
  MSG=" ✅ リンク: 自動修正不要（問題なし）"
else
  MSG=" ✅ リンク: ${FIXED}件自動修正済み"
fi

echo "$MSG" > "$STATUS_DIR/broken-links.status"

exit 0

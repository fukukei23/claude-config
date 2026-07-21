#!/bin/bash
# post-commit hook: obsidian-ssot コミット後の構造変化を検知し pending キューへ投入
#
# 設計（spec R3・Task 4）:
#   - LLM 呼出なし・検知のみ・即時・コストゼロ
#   - has_external_repo で検知対象を切替:
#       true  → repo_path(外部リポ) の git ls-tree と manifest の directories[].path 比較
#       false → obsidian-ssot の 01_DECISIONS/<project>/ 配下と比較
#   - 比較軸: top-level(path.split("/")[0]) の集合 diff（dir 追加/削除検知・ノイズ回避）
#   - 差分あり → pending キュー(.dir-manifest-pending.json)へプロジェクト名追加（重複回避）
#   - cron(Task 5) が pending を処理し LLM meaning 再生成候補作成
#
# post-chat 特性: stdout を汚さない（exit 0 必須・commit 自体は完了済み）

set -uo pipefail

OBSIDIAN_SSOT="$HOME/projects/obsidian-ssot"
PENDING_FILE="$OBSIDIAN_SSOT/.dir-manifest-pending.json"
CLAUDE_CONFIG="$HOME/projects/claude-config"

# pending file 無ければ空配列で初期化
[ -f "$PENDING_FILE" ] || echo '[]' > "$PENDING_FILE"

# 直前の commit で変更された 01_DECISIONS/<project>/ 配下のプロジェクト名を抽出
# (空コミット・01_DECISIONS 外の変更なら PROJECTS は空 → ループ回らず skip)
PROJECTS=$(git -C "$OBSIDIAN_SSOT" diff --name-only HEAD~1 HEAD 2>/dev/null \
  | grep '^01_DECISIONS/' | cut -d/ -f2 | sort -u || true)

# claude-config の dir_manifests.py を import 可能に
export PYTHONPATH="$CLAUDE_CONFIG${PYTHONPATH:+:$PYTHONPATH}"

for proj in $PROJECTS; do
  MANIFEST="$OBSIDIAN_SSOT/01_DECISIONS/$proj/.dir-manifest.json"
  [ -f "$MANIFEST" ] || continue

  # 構造変化検知（list_dirs_via_git / list_project_dirs_in_ssot 再利用）
  # stdout: 変化ありならプロジェクト名 / 無ければ空
  RESULT=$(PYTHONPATH="$CLAUDE_CONFIG" python3 -c "
import json, sys
from pathlib import Path
from scripts.obsidian.dir_manifests import list_dirs_via_git, list_project_dirs_in_ssot

manifest_path = Path('$MANIFEST')
ssot_root = Path('$OBSIDIAN_SSOT')
project = '$proj'

try:
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
except Exception:
    sys.exit(2)

# manifest 側: directories[].path の top-level 集合
recorded = {d['path'].split('/')[0] for d in manifest.get('directories', []) if d.get('path')}

# 実dir 側: has_external_repo で切替
if manifest.get('has_external_repo'):
    raw = manifest.get('repo_path', '')
    repo_path = Path(raw.replace('~', str(Path.home()))) if raw else Path()
    if not repo_path.is_dir():
        sys.exit(3)
    actual = {p.split('/')[0] for p in list_dirs_via_git(repo_path)}
else:
    actual = set(list_project_dirs_in_ssot(ssot_root, project))

added = actual - recorded
removed = recorded - actual
if added or removed:
    print(project)
" 2>/dev/null) || continue

  # 変化あり → pending キューへ重複回避で追加
  if [ -n "$RESULT" ]; then
    python3 -c "
import json
from pathlib import Path
pending_path = Path('$PENDING_FILE')
project = '$RESULT'
try:
    data = json.loads(pending_path.read_text(encoding='utf-8'))
except Exception:
    data = []
if not isinstance(data, list):
    data = []
if project not in data:
    data.append(project)
    pending_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
" 2>/dev/null || true
  fi
done

exit 0

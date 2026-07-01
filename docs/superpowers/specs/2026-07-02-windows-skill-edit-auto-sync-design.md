# Windows Desktop側スキル編集オートシンク 設計

## 背景・課題

`~/.claude/skills/`（Claude Codeのスキル定義群）は、WSL側では`/home/yn4416/.claude/skills`がシンボリックリンクで`~/projects/claude-config/skills/`（git管理下）を指している。一方、**Windows Desktop側の`C:\Users\yn441\.claude\skills\`はシンボリックリンクではなく、物理的に独立したNTFS上のコピー**であり、WSL側のgit正典とは同期スクリプト経由でしか繋がっていない。

既存の同期は`sync-skills-windows.sh`（Windows Desktop側の`Stop`フックから`wsl bash`経由で起動）による**WSL→Windows一方向のみ**（mtime比較で新しい方を採用）。

2026-07-01のセッションで、Windows Desktop側で`ssot-record`スキルにフェーズ7.5（セッション横断総括機能）を実装したが、後から別のWSL側セッションが同名スキルファイルの古い版をベースに別の正当な改修を行いgit commitしたところ、次のStop hook発火時にWSL→Windows一方向同期が働き、Windows側にしか存在しなかったフェーズ7.5の実装が上書き消失した（後に手動で復元済み）。

根本原因は「Windows Desktop側での編集がWSL側の実git正典に一切伝播しない」という非対称構造。`Read`/`Edit`/`Write`ツールでWindowsネイティブパス（`C:\Users\yn441\...`）を指定した場合、PreToolUseの`path-rewrite.py`フック（Bashツール限定でパスをUNC変換する仕組み）の対象外となるため、この非対称性は解消されない。

## 採用設計

### 新設スクリプト: `sync-windows-edit-to-wsl.sh`

配置先: `~/projects/claude-config/scripts/skills/sync-windows-edit-to-wsl.sh`

既存の`scripts/skills/mirror-to-custom.sh`（プラグインスキル変更をskills-custom/へ自動ミラーする既存のPostToolUseフック）と同一パターンを踏襲する。

```bash
#!/bin/bash
# sync-windows-edit-to-wsl.sh
# PostToolUse (Edit/Write) で Windows Desktop 側の ~/.claude/skills/ 編集を検知し、
# WSL側の実git正典（claude-config/skills/ のsymlink先）へ即座にコピー＋軽量commitする。
# 目的: sync-skills-windows.sh（WSL→Windows一方向）による、
#       Windows側編集の上書き消失事故を防ぐ。

TOOL_INPUT=$(cat)
FILE_PATH=$(echo "$TOOL_INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input', {}).get('file_path',''))" 2>/dev/null)

WIN_SKILLS_PREFIX_1="C:\\Users\\yn441\\.claude\\skills\\"
WIN_SKILLS_PREFIX_2="C:/Users/yn441/.claude/skills/"
WSL_SKILLS_DIR="/home/yn4416/.claude/skills"

REL=""
case "$FILE_PATH" in
  "$WIN_SKILLS_PREFIX_1"*) REL="${FILE_PATH#$WIN_SKILLS_PREFIX_1}" ;;
  "$WIN_SKILLS_PREFIX_2"*) REL="${FILE_PATH#$WIN_SKILLS_PREFIX_2}" ;;
  *) exit 0 ;;
esac

[[ -z "$REL" ]] && exit 0

# バックスラッシュ区切りの相対パスをスラッシュに正規化
REL="${REL//\\//}"

WIN_SRC="/mnt/c/Users/yn441/.claude/skills/$REL"
WSL_DEST="$WSL_SKILLS_DIR/$REL"

[[ -f "$WIN_SRC" ]] || exit 0

mkdir -p "$(dirname "$WSL_DEST")"
cp "$WIN_SRC" "$WSL_DEST" 2>/dev/null || exit 0

cd /home/yn4416/projects/claude-config || exit 0
git add "skills/" 2>/dev/null || exit 0
if ! git diff --cached --quiet; then
  SKILL_NAME=$(echo "$REL" | cut -d/ -f1)
  git commit -m "chore: Windows Desktop編集を自動同期(${SKILL_NAME})" --quiet 2>/dev/null || true
fi

exit 0
```

### 登録

Windows Desktop側`settings.json`のPostToolUse配列に、既存2エントリと並列で以下を追加する:

```json
{
  "type": "command",
  "command": "wsl bash /home/yn4416/projects/claude-config/scripts/skills/sync-windows-edit-to-wsl.sh",
  "timeout": 8000
}
```

matcherは既存のPostToolUseエントリと同様に空文字（全ツール呼び出しで発火し、スクリプト内でパス判定して即exitする方式。`mirror-to-custom.sh`と同じ設計）。

### データフロー

```
Edit/Writeツール実行（Windows側パス C:\Users\yn441\.claude\skills\...）
  → PostToolUse発火（既存2フック + 新設フックが並列実行）
  → 新設フック:
      1. file_pathがWindows側skills配下か判定（違えばexit 0）
      2. WSL側実体（symlink先=claude-config/skills/）へコピー
      3. claude-configリポジトリで git add + 軽量commit（diffがある場合のみ）
      4. push はしない（既存のStop hook起点の自動push機構に委ねる）
```

### エラーハンドリング

- パス不一致・コピー失敗・git操作失敗のいずれでも**exit 0で無害化**（既存の`path-rewrite.py`・`mirror-to-custom.sh`と同じ設計思想。フック失敗でセッションをブロックしない）
- commit対象の差分がない場合はcommitをスキップ（空コミット防止。`git diff --cached --quiet`で判定）
- 新規スキル作成（新しいディレクトリ）の場合も`mkdir -p`で対応

### 対象範囲外（このspecでは扱わない）

- Windows→WSLの**逆方向のpush**は自動化しない（既存のStop hook起点の自動push機構が担う）
- `rules/_shared/`・`CLAUDE.md`等、他の同期対象ファイル群への同種の保護は本specのスコープ外（今回の事故がSKILL.md群に限定されるため）
- WSL側とWindows側が**同時に異なる内容を編集していた場合の競合検知・マージ**は行わない（考慮するとしても稀なケースであり、今回のような「Windows側が先に編集→後からWSL側が古い版に基づいて上書き」という非対称構造の解消のみを目的とする。git commitが即座に入ることで、万一の競合時も`git log`から両方の変更を復元可能にする、という点で十分な安全性を確保する）

## テスト方針（plan策定時に詳細化）

- Windows側パスでSKILL.mdを編集→新設フックが発火し、WSL側実体（symlink先）に同一内容が反映されることを確認
- 新規スキル作成（新しいディレクトリ配下のSKILL.md）でも正しくコピー・commitされることを確認
- スキルと無関係なファイル（例: SSOTファイル）編集時にフックが即exitし何もしないことを確認
- 変更後、`claude-config`リポジトリで`git log`にcommitが作成されることを確認
- 同じ内容を2回連続で編集（diffなし）した場合、2回目はcommitがスキップされることを確認
- 既存の`sync-skills-windows.sh`（WSL→Windows）と組み合わせても無限ループ・競合が起きないことを確認（片方向コピーの往復にならないか）

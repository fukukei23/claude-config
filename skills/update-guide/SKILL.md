---
name: update-guide
description: claude-code-guide の更新キューを処理し、変更されたスクリプト・設定ファイルに合わせてガイドのHTMLを最新化する。ユーザーが「/update-guide」を実行した時にトリガーする。
user-invocable: true
---

# update-guide — ガイド手動更新スキル

ユーザーが `/update-guide` を呼び出したら以下を実行する。

## オプション

- `/update-guide` — 差分確認 → ユーザー承認 → 適用
- `/update-guide --dry-run` — 差分確認のみ、変更しない
- `/update-guide --apply` — 確認なしで即適用

---

## 実行手順

### STEP 0: SSOTマスターからの同期（CCガイドページ）

ssot-record等で `00_SYSTEM/Claude-Codeガイド/` が更新された場合、マスターを公開版にコピーする:

```bash
# 差分確認
diff /home/yn4416/projects/obsidian-ssot/00_SYSTEM/Claude-Codeガイド/<page>.md \
     /home/yn4416/projects/claude-code-guide/source/<page>.md

# 同期（差分がある場合）
cp /home/yn4416/projects/obsidian-ssot/00_SYSTEM/Claude-Codeガイド/<page>.md \
   /home/yn4416/projects/claude-code-guide/source/<page>.md
```

SSOTがマスター。`claude-code-guide/source/` は派生物。

### STEP 1: キュー確認

```
Read: ~/projects/claude-code-guide/.update-queue.md
```

キューが空 → 「更新対象がありません」と表示して終了。

対象章のリストを抽出する（`| 日付 | 変更内容 | 章ファイル |` 形式）。

---

### STEP 2: 変更ファイルを読む

対象章に対応するsourceファイルを読む:

```
~/projects/claude-code-guide/source/
  00_早見表.md → 00-cheatsheet.html（なければスキップ）
  01_基礎概念.md → 01-basics.html
  02_コマンド一覧.md → 02-commands.html
  03_スキルシステム.md → 03-skills.html
  04_MCPサーバー.md → 04-mcp.html
  05_フック.md → 05-hooks.html
  06_メモリ.md → 06-memory.html
  07_エージェント.md → 07-agents.html
  08_設定ファイル.md → 08-config.html
  09_統合.md → 09-integration.html
  10_用語集.md → 10-glossary.html
  11_現場の知見.md → 11-tips.html
  12_dev-cycle.md → 12-dev-cycle.html
```

また、キュー行の「変更内容」列に記載されたファイルも読む（例: `settings.json`, `scripts/hooks/`）。

---

### STEP 3: 現HTMLを読む

対象章の現在の `~/projects/claude-code-guide/docs/chapters/<章>.html` を読む。

PROTECTED セクションを確認する:
```html
<!-- GUIDE:PROTECTED -->
...ここは変更しない...
<!-- /GUIDE:PROTECTED -->
```

---

### STEP 4: 🟡[GLM] で章を更新

以下のプロンプトで GLM（`glm_ask`）を呼び出す:

```
以下のHTMLガイド章を最新のスクリプト・設定に合わせて更新してください。

## ルール
1. <!-- GUIDE:PROTECTED --> ～ <!-- /GUIDE:PROTECTED --> の間は絶対に変更しない
2. <!-- GUIDE:AUTO-UPDATE --> セクションとマーカーなしセクションを更新してよい
3. HTML構造・スタイルを維持する（タグ・クラス・id を勝手に変えない）
4. 実際のスクリプト内容・設定値を正確に反映する
5. 更新後の完全なHTMLを出力する（省略なし）

## 現在のHTML
<現在のHTML>

## 参照するスクリプト・設定
<変更されたファイル内容>
```

GLM の出力を受け取り、HTMLとして保存する。

---

### STEP 5: HTMLバリデーション

```python
python3 -c "
from html.parser import HTMLParser
try:
    p = HTMLParser()
    with open('docs/chapters/<章>.html') as f: p.feed(f.read())
    print('OK')
except Exception as e:
    print('FAIL:', e); exit(1)
"
```

失敗時 → エラー表示して中断。GLMの出力が不完全な場合はユーザーに報告。

---

### STEP 6: diff表示と確認

```bash
git diff docs/chapters/<章>.html
```

差分をユーザーに表示する。

`--dry-run` の場合はここで終了。

`--apply` でない場合はユーザーに「適用しますか？ (y/n)」と確認する。

---

### STEP 7: commit & push

```bash
cd ~/projects/claude-code-guide
git add docs/chapters/<章>.html
git commit -m "update: <章> - <変更内容の要約>"
git push origin main
```

---

### STEP 8: キュークリア

処理した章をキューから削除する:

```bash
sed -i "/| <章> |/d" ~/projects/claude-code-guide/.update-queue.md
```

---

### STEP 9: 完了報告

```
✅ update-guide 完了
更新章: <章リスト>
コミット: <hash>
```

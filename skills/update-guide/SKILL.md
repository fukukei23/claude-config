---
name: update-guide
description: claude-code-guide の更新キューを処理し、変更されたスクリプト・設定ファイルに合わせてガイドのsource Markdownを更新し convert.py で再生成する。ユーザーが「/update-guide」を実行した時にトリガーする。
user-invocable: true
---

# update-guide — ガイド手動更新スキル

ユーザーが `/update-guide` を呼び出したら以下を実行する。

## オプション

- `/update-guide` — 差分確認 → ユーザー承認 → 適用
- `/update-guide --dry-run` — 差分確認のみ、変更しない
- `/update-guide --apply` — 確認なしで即適用

---

## ⚠️ 核心ルール（必読）

**`docs/chapters/*.html` を直接編集してはならない。** HTML は `convert.py` の**生成物**。直接編集すると次回 `convert` 実行で消える。

正しいパイプライン:
```
source/*.md  (マスター — ここを編集)
   ↓  python3 convert.py  (全体再生成・部分不可)
docs/chapters/*.html  (生成物 — commit対象だが手編集禁止)
```

- `docs/` は `.gitignore` 対象だが**既存 track**（過去に force-add 済み）。commit時 `-f` 不要・更新は検知される
- `convert.py` は **source/ 全ファイルをループして docs/ を全再生成**（1章だけ部分生成は不可）
- 個人識別子は convert.py が自動サニタイズ: `yn4416`→`<USER>`, `fukukei23`→`<USERNAME>`, `GLM-5.1`等→`Claude`, `obsidian-ssot`→`knowledge-base` 等。source に書いても公開版で自動置換される

---

## 実行手順

### STEP 0: SSOTマスターからの同期（CCガイドページ）

ssot-record等で `00_SYSTEM/Claude-Codeガイド/` が更新された場合、マスターを公開版 source にコピーする:

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

**⚠️ 誤積載チェック**: キュー行の「変更内容」に書かれたファイル（例: `startup-banner.sh`）の内容が、対象 source/*.md に**既に反映済みか**を必ず確認（`grep` で検索）。反映済みなら「誤積載・対応不要」として STEP 8 へ飛び、その行だけクリアする。`queue-guide-updates.sh` はファイル変更を検知して積むが、中身の反映有無までは見ていない。

---

### STEP 2: 変更ファイル + 対象 source を読む

1. キュー行の「変更内容」列に記載された実体ファイルを読む（`~/.claude/scripts/...`, `settings.example.json`, `skills-custom/.../SKILL.md` 等）。これが「反映すべき事実」
2. 対象章の **source Markdown** を読む（HTML ではない）:

```
~/projects/claude-code-guide/source/
  00_早見表.md    01_基礎概念.md   02_コマンド一覧.md
  03_スキルシステム.md   04_MCPサーバー.md   05_フック.md
  06_メモリ.md    07_エージェント.md   08_設定ファイル.md
  09_統合.md     10_用語集.md      11_現場の知見.md
  12_dev-cycle.md   13_glm-rate-proxy.md   15_コスト最適化構成.md
```

source ファイル名と slug の対応は `convert.py` の `CHAPTER_MAP` を参照（新規章を追加する場合は CHAPTER_MAP へのエントリも必要）。

---

### STEP 3: source Markdown を編集

対象の `source/<章>.md` に、実体ファイルの内容を反映する編集を加える。

**ルール:**
1. Markdown を編集する（HTML タグ・クラス・id は書かない — `convert.py` が付与する）
2. 実際のスクリプト内容・設定値を正確に反映する
3. 個人識別子（`yn4416`, `GLM-5.1`, `obsidian-ssot` 等）はそのまま書いてよい（convert.py が公開版で自動サニタイズ）
4. Surgical Changes — 必要な箇所だけ触る
5. 新規章追加時は `convert.py` の `CHAPTER_MAP` にもエントリを追加する

---

### STEP 4: convert.py で再生成

```bash
cd ~/projects/claude-code-guide
python3 convert.py
```

source/ 全章から docs/ が全再生成される。エラーが出たら source Markdown の構文を確認。

---

### STEP 5: diff 確認

```bash
git diff source/<章>.md          # source の変更内容
git diff docs/chapters/<章>.html # 生成された HTML の差分
```

`--dry-run` の場合はここで終了。

---

### STEP 6: ユーザー承認

`--apply` でない場合は、差分サマリを表示して「適用しますか？ (y/n)」と確認する。

**⚠️ 未コミット作業の混入に注意**: 既に source/ や docs/ に別セッションの未コミット変更がある場合、STEP 4 の `convert.py` 実行でそれらも再生成の対象になる。commit すると前セッション作業も巻き込まれるため、混入状況は必ずユーザーに報告してから進めること。

---

### STEP 7: commit & push

```bash
cd ~/projects/claude-code-guide
git add source/<章>.md convert.py docs/
git commit -m "update: <章> - <変更内容の要約>"
git push origin main
```

- `docs/` 全体を add する（convert.py が全章再生成するため、対象章以外の HTML も更新されることがある）
- `convert.py` を編集した（CHAPTER_MAP 追加等）場合は忘れずに add

---

### STEP 8: キュークリア

処理した章をキューから削除する:

```bash
sed -i "/| <章ファイル名> |/d" ~/projects/claude-code-guide/.update-queue.md
```

誤積載と判定した行もここで削除する。

---

### STEP 9: 完了報告

```
✅ update-guide 完了
更新章: <章リスト>
コミット: <hash>
```

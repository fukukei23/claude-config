---
name: record-ssot
description: >
  SSOTへの記録・振り分けを自動化するスキル。
  ユーザーが「記録して」「書き留めて」「保存して」「メモして」「残しておいて」「忘れないようにして」
  「SSOTに入れて」「ガイドに追加して」「書いておいて」と言った時、
  または /record-ssot を呼び出した時にトリガーする。
  record-decision の上位互換。内容をGLMで分析して最適な振り分け先を判定し、
  フォーマット生成・リンク付与・ガイド転記提案まで一気に実行する。
user-invocable: true
---

# record-ssot スキル

## 概要

「記録して」と言うだけで以下を自動実行する:

1. **分類** — 内容をGLMで分析して振り分け先を判定
2. **確認** — 判定結果をユーザーに提示して承認を得る
3. **記録** — SSOT・日記・_INDEX.md に書き込む
4. **提案** — ガイド転記が必要な場合は案を提示してから書く

---

## フェーズ0: 情報収集

会話の文脈から以下を自動収集する。不足分だけ聞く（1行ずつ）:

- **内容** — 何を記録したいか（会話から読み取れる場合はスキップ）
- **プロジェクト名** — 不明な場合のみ確認（例: `claude-code`, `atelier-kyo-manager`）
- **未解決** — 残タスクがあれば（なければスキップ）

---

## フェーズ1: GLMで分類判定

以下のプロンプトで `glm_ask` に問い合わせる。**デフォルト値なし・全フィールドを内容から判断させること**:

```
以下の内容をSSOTに記録します。最適な振り分け先を判定し、JSON のみを返してください（説明文不要）。

【記録する内容】
{ユーザーの記録内容}

【SSOTフォルダ構成】
- 01_DECISIONS/<project>/ — 技術的決定・バグ修正・設計変更・「なぜそうしたか」の記録
- 00_SYSTEM/ — システム設定変更（hooks, cron, settings.json 等）
- 10_DAILY/ — 日記ハブ（直接の記録先ではない。サマリー追記のみ）
- 20_PUBLISHING/ — 外部公開コンテンツ（Zenn記事, note等）の草稿・管理
- 30_RESEARCH/ — LLMモデル・価格・外部サービスの調査結果（時系列で陳腐化する情報）
- 40_CAREER/ — ポートフォリオ・キャリア資料・求人関連

【ガイドサイト（転記判断基準）】
- claude-code-guide — Claude Codeの使い方・手順・チュートリアル（再利用できる手順のみ）
- ssot-guide — SSOTシステムの設計・使い方の説明

【判定ルール】
- also_daily は「セッションの主要な作業成果」の場合のみ true。途中メモ・調査記録・設定追記は false
- guide_needed は「他人や将来の自分が手順として再利用できる内容」の場合のみ true
- primary が 00_SYSTEM の場合、project は "claude-code" とする

返答フォーマット（JSON のみ、コードブロック不要）:
{
  "primary": "01_DECISIONS",
  "project": "プロジェクト名",
  "category": "技術的決定 or ノウハウ or 調査 or キャリア or システム設定 or 公開コンテンツ",
  "also_daily": true or false,
  "guide_needed": true or false,
  "guide_target": null or "claude-code-guide" or "ssot-guide",
  "tags": ["タグ1", "タグ2", "タグ3"],
  "filename_hint": "ファイル名に使う日本語の短い説明",
  "reason": "判定理由（1行）"
}
```

**GLMがJSONを返さなかった場合（説明文が混入・エラー等）**:
- レスポンスから `{...}` 部分を正規表現で抽出して再パースを試みる
- それでも失敗した場合は自分（Claude）でデフォルト判定して進み、フェーズ2でユーザーに確認する

---

## フェーズ2: 判定結果の確認

GLMの判定結果をユーザーに以下の形式で提示する:

```
📋 記録先の判定結果

📁 メイン: 01_DECISIONS/claude-code/2026-05-31_スクリプト修正.md
📅 日記追記: あり（10_DAILY/2026-05-31.md）  ← also_daily が false なら「なし」と表示
📖 ガイド転記: なし
🏷️ タグ: #claude-code #バグ修正 #スクリプト
💬 理由: 技術的バグ修正のため01_DECISIONSが最適

この振り分けでよいですか？[yes/修正指示]
```

ユーザーが承認したら次のフェーズへ。修正指示があれば反映してから再確認。

---

## フェーズ3: ファイル作成・更新

### 3-1. メイン記録ファイルの作成

振り分け先に応じてファイルを作成する:

**01_DECISIONS の場合** (`/home/yn4416/projects/obsidian-ssot/01_DECISIONS/<project>/YYYY-MM-DD_<内容>.md`):
```markdown
---
project: <project>
date: YYYY-MM-DD
tags: [tag1, tag2, tag3]
---

# <タイトル>

## 概要
<2-3行>

## 詳細
<技術的詳細・コマンド・コード・トラブルシューティング>

## コミット
- `<hash>` <説明>  ← あれば

## 未解決
- <残タスク>  ← なければ「なし」
```

**00_SYSTEM の場合** (`/home/yn4416/projects/obsidian-ssot/00_SYSTEM/<適切なサブフォルダ or 直下>/<ファイル名>.md`):
まず `ls /home/yn4416/projects/obsidian-ssot/00_SYSTEM/` でフォルダ構成を確認してから配置する。
設定変更の場合は既存ファイルへの追記を優先する（`自動化.md` や `MCPツール使い分けガイド.md` 等）。
```markdown
---
updated: YYYY-MM-DD
tags: [tag1, tag2]
---

# <設定変更タイトル>

## 変更内容
<何を・どこで・どのように変更したか>

## 理由
<なぜ変更したか>

## 関連ファイル
- <設定ファイルパス>
```

**30_RESEARCH の場合** (`/home/yn4416/projects/obsidian-ssot/30_RESEARCH/<分野>/<ファイル名>.md`):
`ls /home/yn4416/projects/obsidian-ssot/30_RESEARCH/` で既存の分野フォルダを確認してから配置する。
```markdown
---
updated: YYYY-MM-DD
source: <調査元URL（あれば）>
tags: [tag1, tag2]
---

# <調査テーマ>

<調査内容>
```

**40_CAREER の場合** (`/home/yn4416/projects/obsidian-ssot/40_CAREER/<適切なサブフォルダ>/<ファイル名>.md`):
`ls /home/yn4416/projects/obsidian-ssot/40_CAREER/` でフォルダ構成を確認してから適切な場所に配置する。

**20_PUBLISHING の場合** (`/home/yn4416/projects/obsidian-ssot/20_PUBLISHING/<フォルダ>/`):
作成後に `20_PUBLISHING/_INDEX.md` のステータスを更新する。

### 3-2. _INDEX.md への追記

`01_DECISIONS/<project>/_INDEX.md` の扱い:
- **存在する場合**: 末尾のテーブルに1行追記する
- **存在しない場合**: スキップ（_INDEX.md を新規作成しない）

追記フォーマット（【要更新】マーカーは絶対に使わない）:
```markdown
| [YYYY-MM-DD_<ファイル名>](YYYY-MM-DD_<ファイル名>.md) | <1行説明> | <状況・参照タイミング> |
```

### 3-3. 10_DAILY への追記

**`also_daily: true` の場合のみ**追記する。`false` の場合は何もしない。

追記先: `/home/yn4416/projects/obsidian-ssot/10_DAILY/YYYY-MM-DD.md`

- **ファイルが存在する場合**: 末尾に追記
- **ファイルが存在しない場合**: 以下のヘッダーで新規作成してから追記
  ```markdown
  # YYYY-MM-DD

  ---
  ```

追記フォーマット:
```markdown
## セッションログ (HH:MM)
- <作業サマリー 3〜5行>
- 詳細: 01_DECISIONS/<project>/YYYY-MM-DD_<ファイル名>.md
- 未解決: <あれば>  ← なければ省略
```
日記には詳細を直書きしない（サマリー + リンクのみ）。

---

## フェーズ4: ガイド転記（`guide_needed: true` の場合のみ）

### 4-1. ガイドリポジトリのパス確認

```bash
# guide_target に応じてパスを確認
ls ~/projects/claude-code-guide/source/   # claude-code-guide の場合
ls ~/projects/ssot-guide/source/          # ssot-guide の場合
```

既存の章ファイル一覧を確認し、追記先（または新規章）を決める。

### 4-2. 転記案の提示

```
📖 ガイド転記案（claude-code-guide）

追記先: source/XX_<章名>.md
追記内容:
---
[ここに転記内容の案]
---

この内容でガイドに追記しますか？[yes/修正/不要]
```

### 4-3. 承認後の処理

ユーザーが承認した場合のみ実行:
1. `source/XX_<章名>.md` を編集
2. `update-guide` スキルを呼び出してHTML再生成
3. ガイドリポジトリで git commit & push

`ssot-guide` の場合も手順は同じ（パスが `~/projects/ssot-guide/source/`）。

---

## フェーズ5: git commit & push

```bash
cd /home/yn4416/projects/obsidian-ssot
git add -A
git commit -m "record: <内容の1行説明>"
git push
```

ガイドを更新した場合は別途ガイドリポジトリもコミット（フェーズ4で実施済みの場合はスキップ）。

---

## フェーズ6: 完了報告

```
✅ SSOT記録完了

📁 01_DECISIONS/claude-code/2026-05-31_<ファイル名>.md
📅 10_DAILY/2026-05-31.md（追記）  ← also_daily: false の場合は「日記追記: なし」
🏷️ タグ: #claude-code #バグ修正
📖 ガイド転記: なし（または「あり → <章名>」）
🔗 コミット: <hash>
```

---

## 制約・禁止事項

- APIキー・シークレットの値は絶対に書かない（キー名はOK）
- 日記に詳細を直書きしない（サマリー + リンクのみ）
- _INDEX.md に【要更新】マーカーを残さない
- ガイド転記はユーザー承認なしに実行しない
- 1トピック = 1ファイル（複数の無関係な作業は別々のファイルに）
- `also_daily: false` の時は 10_DAILY に何も書かない

---

## このスキルのトリガーワード

以下のいずれかでトリガー（`/record-ssot` コマンドでも可）:
- 記録して / 書き留めて / 保存して / メモして
- 残しておいて / 忘れないようにして
- SSOTに入れて / SSOTに書いて
- ガイドに追加して / ガイドに書いて / ガイドに入れて
- 書いておいて / 記しておいて

`record-decision` スキルの上位互換。`/record-decision` が呼ばれた場合もこのスキルで処理する。

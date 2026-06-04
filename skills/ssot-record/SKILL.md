---
name: ssot-record
description: >
  SSOTへの記録・振り分けを自動化するスキル。
  ユーザーが「記録して」「書き留めて」「保存して」「メモして」「残しておいて」「忘れないようにして」
  「SSOTに入れて」「ガイドに追加して」「書いておいて」と言った時、
  または /ssot-record を呼び出した時にトリガーする。
  record-decision の上位互換。内容をLLMで分析して最適な振り分け先を判定し、
  フォーマット生成・リンク付与・ガイド転記まで一気に実行する。
user-invocable: true
---

# ssot-record スキル

## 概要

「記録して」と言うだけで以下を自動実行する:

1. **分類** — 内容をGLMで分析して振り分け先を判定
2. **確認** — 判定結果（ガイド転記先・概要を含む）をユーザーに提示して一括承認を得る
3. **記録** — SSOT・日記・_INDEX.md に書き込む
4. **転記** — 承認済みならガイドに追記してビルド・push

---

## フェーズ0: 情報収集

会話の文脈から以下を自動収集する。不足分だけ聞く（1行ずつ）:

- **内容** — 何を記録したいか（会話から読み取れる場合はスキップ）
- **プロジェクト名** — 不明な場合のみ確認（例: `claude-code`, `atelier-kyo-manager`）
- **未解決** — 残タスクがあれば（なければスキップ）

---

## フェーズ1: 分類判定

### 環境別の判定方法

- **WSL CLI版**: セッション自体がGLMで動作中 → **自分自身で直接判定**（外部LLM呼び出し不要・不可）
- **Windows Desktop版**: MCP経由で外部LLM呼び出し可能 → glm MCP等で判定してもよい

### 判定に使うプロンプト
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

【Claude Codeガイド自動判定（CC Guide Auto-sync）】
記録内容がClaude Code機能の設定・変更の場合、CCガイドページへの追記が必要かを判定する。

| 内容カテゴリ | 対象ガイドページ |
|---|---|
| スキル自作・登録 | `03_スキルシステム.md` |
| MCP追加・設定変更 | `04_MCPサーバー.md` |
| フック追加・変更 | `05_フック.md` |
| メモリ設定変更 | `06_メモリ.md` |
| エージェント設定 | `07_エージェント.md` |
| settings.json変更 | `08_設定ファイル.md` |

- CC機能に関係ない場合は `cc_guide_page: null` にする
- 複数ページに該当する場合は最初の1つだけを返す

返答フォーマット（JSON のみ、コードブロック不要）:
{
  "primary": "01_DECISIONS",
  "project": "プロジェクト名",
  "category": "技術的決定 or ノウハウ or 調査 or キャリア or システム設定 or 公開コンテンツ",
  "also_daily": true or false,
  "guide_needed": true or false,
  "guide_target": null or "claude-code-guide" or "ssot-guide",
  "cc_guide_page": "03_スキルシステム.md" or null,
  "cc_guide_entry": {
    "name": "<スキル/MCP/フック名>",
    "description": "<1行説明>",
    "trigger": "<トリガー例>",
    "usage_section": "### `<name>`\n\n<Markdown形式の使い方説明>\n"
  },
  "tags": ["タグ1", "タグ2", "タグ3"],
  "filename_hint": "ファイル名に使う日本語の短い説明",
  "reason": "判定理由（1行）"
}
```

**LLMがJSONを返さなかった場合（説明文が混入・エラー等）**:
- レスポンスから `{...}` 部分を正規表現で抽出して再パースを試みる
- それでも失敗した場合は自分（Claude）でデフォルト判定して進み、フェーズ2でユーザーに確認する

**LLMが不正なプロジェクト名を返した場合の照合**:
- `primary: "01_DECISIONS"` のとき、返された `project` が実在するか確認する:
  ```
  ls /home/yn4416/projects/obsidian-ssot/01_DECISIONS/
  ```
  （Windows: `//wsl.localhost/Ubuntu/home/yn4416/projects/obsidian-ssot/01_DECISIONS/`）
- 返された `project` がフォルダ一覧に**存在しない**場合はフェーズ2で「このプロジェクト名でよいですか？」と確認する
- `primary: "10_DAILY"` が返った場合は誤判定とみなし `01_DECISIONS` にフォールバックして再判定する

---

## フェーズ2: 判定結果の確認

GLMの判定結果をユーザーに以下の形式で**一画面**で提示する。ガイド転記がある場合は追記先と概要もここに含め、**別途「転記案を見せますか？」は聞かない**:

**ガイド転記の種類:**
- `📖 ガイド転記` — ssot-guide / claude-code-guide（他プロジェクト参照用）
- `📖 CCガイド追記` — 00_SYSTEM/Claude-Codeガイド/（Claude Code機能の一覧と使い方）

```
📋 記録先の判定結果

📁 メイン: 01_DECISIONS/claude-code/2026-05-31_スクリプト修正.md
📅 日記追記: あり（10_DAILY/2026-05-31.md）  ← also_daily が false なら「なし」と表示
📖 ガイド転記: なし                           ← guide_needed: false の場合
🏷️ タグ: #claude-code #バグ修正 #スクリプト
💬 理由: 技術的バグ修正のため01_DECISIONSが最適

この振り分けでよいですか？[yes/修正指示]
```

**ガイド転記ありの場合（guide_needed: true）は以下の形式:**

```
📋 記録先の判定結果

📁 メイン: 01_DECISIONS/ssot-guide/2026-05-31_テスト構成.md
📅 日記追記: あり（10_DAILY/2026-05-31.md）
📖 ガイド転記: あり → ssot-guide「09_ガイドサイト構築.md」
   └ 追記内容: test_convert.py の書き方・9クラス構成・テスト保護パターン
🏷️ タグ: #テスト #品質管理
💬 理由: 再利用できるテスト設計のノウハウのため

この振り分けでよいですか？[yes/修正指示]
```

- `📖 ガイド転記` の行に「追記先ファイル名」と「何を書くかの1行概要」を必ず記載する
- 「転記内容の詳細を先に見せますか？」は**聞かない** — yes承認後に直接書く
- ユーザーが承認したら次のフェーズへ。修正指示があれば反映してから再確認。

**CCガイド追記ありの場合（cc_guide_page が null でない場合）:**

```
📋 記録先の判定結果

📁 メイン: 01_DECISIONS/claude-code/2026-06-03_teian軽量提案スキル実装.md
📅 日記追記: あり（10_DAILY/2026-06-03.md）
📖 ガイド転記: なし
📖 CCガイド追記: あり → 00_SYSTEM/Claude-Codeガイド/03_スキルシステム.md
   └ テーブル行: `teian` — 軽量提案スキル...
   └ 使い方セクション: ### `teian` — 軽量提案...
🏷️ タグ: #claude-code #スキル設計
💬 理由: スキル登録のため03_スキルシステムに追記

この振り分けでよいですか？[yes/修正指示]
```

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
- **存在する場合**: ファイル内の**最後のテーブルの末尾行**に1行追記する
- **存在しない場合**: スキップ（_INDEX.md を新規作成しない）
- 複数テーブルがある場合は必ずファイル末尾のテーブルに追記する（セクション冒頭のテーブルに誤追記しない）

追記フォーマット（【要更新】マーカーは絶対に使わない）:
```markdown
| [YYYY-MM-DD_<ファイル名>](YYYY-MM-DD_<ファイル名>.md) | <1行説明> | <状況・参照タイミング> |
```

### 3-3. 10_DAILY への追記

**`also_daily: true` の場合のみ**追記する。`false` の場合は何もしない。

追記先: `/home/yn4416/projects/obsidian-ssot/10_DAILY/YYYY-MM-DD.md`

- **ファイルが存在する場合**: 末尾に追記する。ただし末尾に `セッション終了: HH:MM` 行がある場合はその**前**（`---` の前）に挿入する
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

### 3-4. 自動化タグ時の `自動化.md` 更新

**tags に「自動化」が含まれる場合のみ**実行する。

更新先: `/home/yn4416/projects/obsidian-ssot/00_SYSTEM/自動化.md`

以下の該当箇所を確認し、必要に応じて追記する:

1. **Hook追加・変更時**: 「SessionStart / PostToolUse / PreToolUse / Stop / Notification」の該当テーブルに1行追加
2. **Cron追加・変更時**: 「Cron」テーブルに1行追加
3. **スクリプト追加時**: 「スクリプト一覧」の該当セクションに1行追加
4. **変更履歴**: テーブル末尾に `| YYYY-MM-DD | <概要> | <理由> |` を追加

追記フォーマットは既存行に合わせる。該当なし（自動化に関係ない内容）の場合はスキップ。

### 3-5. Claude Code関連の記録時 → CCガイドにも自動追記

**記録内容がClaude Code関連の場合（project が `claude-code`、またはtagsに `Claude-Code` が含まれる場合）**、以下のCCガイドにも追記する。

**対象ガイド**: `/home/yn4416/projects/obsidian-ssot/00_SYSTEM/Claude-Codeガイド/`

#### 追記先の判定

| 内容カテゴリ | 追記先ファイル | 追記箇所 |
|---|---|---|
| 新機能・新コマンド | `00_早見表.md` | 該当セクションのテーブル末尾 |
| 新用語・新概念 | `10_用語集.md` | 該当するアルファベットセクション |
| スキル自作・登録 | `03_スキルシステム.md` | カスタムスキルテーブル末尾 |
| MCP追加・設定変更 | `04_MCPサーバー.md` | 現在の構成テーブル末尾 |
| フック追加・変更 | `05_フック.md` | 該当フック種別テーブル末尾 |
| 設定ファイル変更 | `08_設定ファイル.md` | 該当セクション末尾 |
| その他Claude Code情報 | `10_用語集.md` | 該当するアルファベットセクション |

#### 実行手順

1. CCガイドの該当ファイルをReadして既存フォーマットを確認
2. 内容に応じた追記先（上表）に1行〜数行を追加
3. 既存行のフォーマットに統一すること
4. 早見表と用語集の**両方**に反映すべき場合は両方に追記する

#### 判定基準

- **常に追記**: 新しい用語・機能・コマンドが登場した場合
- **スキップ**: 単なるバグ修正・既存機能の微調整・プロジェクト固有の作業
- **目安**: 「将来のセッションでこの情報を引く可能性があるか？」→ Yes なら追記

---

## フェーズ4: ガイド転記（`guide_needed: true` かつユーザー承認済みの場合のみ）

フェーズ2でユーザーが承認した時点で転記も承認済みとみなす。**追加確認は不要**。

### 4-0. CCガイド追記（`cc_guide_page` が null でない場合）

`cc_guide_page` が null でない場合、SSOT内のCCガイドに追記する。

**対象:**
- SSOT内部（マスター）: `/home/yn4416/projects/obsidian-ssot/00_SYSTEM/Claude-Codeガイド/<cc_guide_page>`
- 公開版（派生物）: `/home/yn4416/projects/claude-code-guide/source/<cc_guide_page>` — update-guideが同期

#### スキルの場合（cc_guide_page: "03_スキルシステム.md"）

1. ファイルをReadして「カスタムスキル」テーブルの末尾を確認
2. テーブル末尾に1行追加:
   ```markdown
   | `teian` | 軽量提案スキル。2〜3の選択肢＋メリット/デメリット＋推奨案をさっと提示。複雑な場合はbrainstormingへ誘導 | 「提案して」「どう思う」「教えて」「アドバイス」 |
   ```
3. 「主要スキルの使い方」セクションの末尾に `cc_guide_entry.usage_section` を追記

#### MCPの場合（cc_guide_page: "04_MCPサーバー.md"）

1. ファイルをReadして「現在の構成」テーブルの末尾を確認
2. テーブル行を追加（既存行のフォーマットに合わせる）
3. サーバー説明セクションを追加（既存のフォーマットに従う）

#### フックの場合（cc_guide_page: "05_フック.md"）

1. ファイルをReadして該当フック種別のテーブル末尾を確認
2. テーブル行を追加（既存行のフォーマットに合わせる）

#### メモリ/エージェント/設定の場合（cc_guide_page: "06〜08"）

1. ファイルをReadして該当セクションを確認
2. 設定変更内容を追記（既存フォーマットに合わせる）

#### 共通ルール

- **追記前に必ず既存行をRead**してフォーマットを統一する
- `cc_guide_entry` の内容を使ってテーブル行と使い方セクションを生成
- 完了後、update-guideスキルを呼び出して公開版に同期

### 4-1. 追記先の特定

```bash
# guide_target に応じてsource/を確認（WSL CLI の場合）
ls /home/yn4416/projects/claude-code-guide/source/
ls /home/yn4416/projects/ssot-guide/source/

# Windows Desktop Claude Code の場合（UNCパス）
ls //wsl.localhost/Ubuntu/home/yn4416/projects/claude-code-guide/source/
ls //wsl.localhost/Ubuntu/home/yn4416/projects/ssot-guide/source/
```

フェーズ2で提示した追記先ファイルに直接書く。

### 4-2. 追記・ビルド・push

1. `source/XX_<章名>.md` に内容を追記（Markdownで書く）
2. テスト実行: `python3 -m pytest test_convert.py -q`
3. ビルド: `python3 convert.py`
4. ガイドリポジトリで `git add -A && git commit -m "docs: ..." && git push`

`ssot-guide` の場合も手順は同じ（パスが `~/projects/ssot-guide/`）。  
`claude-code-guide` の場合は `update-guide` スキルを呼び出してもよい。

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
- ガイド転記はフェーズ2の yes 承認をもって承認済みとみなす（追加確認は不要）
- 1トピック = 1ファイル（複数の無関係な作業は別々のファイルに）
- `also_daily: false` の時は 10_DAILY に何も書かない

---

## このスキルのトリガーワード

以下のいずれかでトリガー（`/ssot-record` コマンドでも可）:
- 記録して / 書き留めて / 保存して / メモして
- 残しておいて / 忘れないようにして
- SSOTに入れて / SSOTに書いて
- ガイドに追加して / ガイドに書いて / ガイドに入れて
- 書いておいて / 記しておいて

`record-decision` スキルの上位互換。`/record-decision` が呼ばれた場合もこのスキルで処理する。

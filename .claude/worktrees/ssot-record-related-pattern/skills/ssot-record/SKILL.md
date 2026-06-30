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

1. **分類** — 内容を稼働中のLLM（WSL CLI版=GLM / Windows デスクトップアプリ版=Sonnet）で分析して振り分け先を判定
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

## フェーズ0.5: 関連ファイル自動検出

フェーズ1の分類判定で tags が確定した後に実行する。
SSOT内のタグマッピング設定ファイルを読み込み、プロジェクト側の更新対象ドキュメントを自動検出する。

### 設定ファイル

`obsidian-ssot/00_SYSTEM/タグマッピング.md` — タグと更新対象ファイルのマッピング定義。

### 検出手順

1. **設定ファイル読込**: `obsidian-ssot/00_SYSTEM/タグマッピング.md` をRead
2. **タグ照合**: 分類判定で決まった tags とマッピングテーブルの「必須タグ」を照合
3. **追加タグ照合**: マッチした行の「追加タグ」と tags を照合（OR条件）
4. **ファイル存在確認**: 更新対象ファイルが存在するか `ls` で確認
5. **結果をフェーズ2に渡す**: 更新対象リスト（ファイルパス + 更新の種類）を生成

### 検出結果の例

```
📦 プロジェクトドキュメント更新対象（3ファイル）:
   ✅ docs/変更履歴.md             — 末尾にエントリ追加
   ✅ docs/経営者判断.md           — セクション5に追記
   ✅ docs/プロダクトビジョン.md   — 既存資産テーブルに1行追加
```

### タグがマッチしない場合

プロジェクトにマッピング定義がない場合は「プロジェクトドキュメント更新対象: なし」と表示し、従来通りSSOT記録のみ実行する。

---

## フェーズ0.8: 関連パターン候補収集（LLM呼び出しなし）

フェーズ1の分類判定LLM呼び出しの**前**に、過去の記録との根本原因の一致を判定するための候補をファイルI/Oだけで収集する（追加のLLM呼び出しは発生しない）。

### 候補収集パイプライン

「過去7日」「直近5件」は、繁忙期も閑散期も取りこぼさないための折衷値（詳細はspec参照）。一時ファイル名には`$$`（プロセスID）を含め、並行セッションでの衝突を避ける。

```bash
SEVEN_DAYS_AGO=$(date -d "7 days ago" +%Y-%m-%d)

# 全01_DECISIONSエントリのfrontmatter date:行を、ファイルパス付きで抽出し日付降順ソート
grep -rH "^date: " ~/projects/obsidian-ssot/01_DECISIONS/*/2*.md 2>/dev/null \
  | sed -E 's/^(.*):date: *([0-9-]+)$/\2 \1/' \
  | sort -r > /tmp/ssot-record-candidates-sorted-$$.txt

# 集合A: 過去7日以内（当日含む）
awk -v d="$SEVEN_DAYS_AGO" '$1 >= d' /tmp/ssot-record-candidates-sorted-$$.txt > /tmp/ssot-record-setA-$$.txt

# 集合B: 日付に関係なく直近5件
head -5 /tmp/ssot-record-candidates-sorted-$$.txt > /tmp/ssot-record-setB-$$.txt

# 候補 = A ∪ B（重複排除）
cat /tmp/ssot-record-setA-$$.txt /tmp/ssot-record-setB-$$.txt | sort -u > /tmp/ssot-record-candidates-$$.txt
rm -f /tmp/ssot-record-candidates-sorted-$$.txt /tmp/ssot-record-setA-$$.txt /tmp/ssot-record-setB-$$.txt
```

ファイル名やパス文字列ではなく、**frontmatterの`date:`行のみ**を対象にする（誤爆防止。詳細はspec参照）。

### 候補情報の整形

`/tmp/ssot-record-candidates-$$.txt`の各行（`日付 ファイルパス`）について、以下を取得する:

1. 各ファイルをReadし、frontmatterの`tags`・`root_cause`（あれば）を取得
2. 対応する`01_DECISIONS/<project>/_INDEX.md`の該当行（1行サマリー）を取得（既に開いている場合は再読込不要）

整形した候補リストはフェーズ1のプロンプトに渡す（Task 2参照）。

### 候補が0件の場合

`/tmp/ssot-record-candidates-$$.txt`が空（grep該当0件）の場合、候補リストを空のままフェーズ1に進む。フェーズ1のJSON出力では`related_pattern: null`になる（Task 2のプロンプト仕様に従う）。

### 後片付け

一時ファイル（`/tmp/ssot-record-candidates*-$$.txt`）はこのフェーズ内で使い切ったら削除する。

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

【関連パターン判定（フェーズ0.8の候補を使う）】
フェーズ0.8で収集した候補リスト（あれば）を以下のように提示し、今回の記録内容と根本原因が共通していないか判定させる。候補が0件の場合はこのセクション自体を省略してよい。

候補リストの提示形式:
```
過去の関連候補（参考情報。project/tagsの分類には使わないこと）:
1. [project: <project>] <_INDEX.mdの1行サマリー>（root_cause: <あれば category+description、なければ「未記録」>）
2. ...
```

判定ルール:
- **思考順序を分離すること**: まず「今回の記録内容」だけを見て`project`・`tags`・`category`等の通常の分類判定を完了させる。その後で初めて、別タスクとして候補リストと照合して`related_pattern`を判定する。候補リストを見ながら分類判定を行わない（過去ログの語彙に引っ張られて`tags`がブレるのを防ぐため）
- 今回の記録内容と候補の間に、表面的な症状ではなく**根本原因・構造的な前提**が共通すると判断できる場合のみ`related_pattern`を埋める
- 少しでも確信が持てない場合は`related_pattern: null`を返す（過剰検出を避ける）

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
  "reason": "判定理由（1行）",
  "root_cause": {
    "category": "code_defect or design_mismatch or requirement_change or external_dependency or operational_error or unknown",
    "description": "1行の根本原因説明（categoryがunknownの場合は空でもよい）"
  },
  "related_pattern": null
}
```

**出力例1（関連パターンあり）:**
```json
{
  "primary": "01_DECISIONS",
  "project": "claude-code",
  "category": "技術的決定",
  "also_daily": true,
  "guide_needed": false,
  "guide_target": null,
  "cc_guide_page": null,
  "tags": ["claude-code", "cron", "Windows-Desktop"],
  "filename_hint": "Windows-Desktop版cron実行状況確認問題",
  "reason": "Windows Desktop環境固有の技術的問題解決のため",
  "root_cause": {
    "category": "design_mismatch",
    "description": "Windows DesktopとWSL2は別ホームディレクトリを持つ別OSである"
  },
  "related_pattern": {
    "entry": "01_DECISIONS/claude-code/2026-06-30_Windows-Desktop版WSLパス変換フック実装.md",
    "reason": "Windows DesktopとWSL2が別ホームディレクトリを持つことに起因する点で根本原因が共通",
    "common_tags": ["claude-code", "Windows-Desktop"]
  }
}
```

**出力例2（関連パターンなし）:**
```json
{
  "primary": "01_DECISIONS",
  "project": "reserve-optimizer",
  "category": "技術的決定",
  "also_daily": true,
  "guide_needed": false,
  "guide_target": null,
  "cc_guide_page": null,
  "tags": ["reserve-optimizer", "CRMService"],
  "filename_hint": "CRMService匿名ID化実装",
  "reason": "プロジェクト固有の機能実装のため",
  "root_cause": {
    "category": "design_mismatch",
    "description": "顧客IDの主キーに電話番号(PII)を使っていた"
  },
  "related_pattern": null
}
```

**出力例3（root_cause不明な単純記録）:**
```json
{
  "primary": "01_DECISIONS",
  "project": "claude-code-guide",
  "category": "ノウハウ",
  "also_daily": false,
  "guide_needed": false,
  "guide_target": null,
  "cc_guide_page": null,
  "tags": ["claude-code-guide", "typo"],
  "filename_hint": "READMEのtypo修正",
  "reason": "単純な誤字修正で根本原因の分析対象ではないため",
  "root_cause": {
    "category": "unknown",
    "description": ""
  },
  "related_pattern": null
}
```

**LLMがJSONを返さなかった場合（説明文が混入・エラー等）**:
- レスポンスから `{...}` 部分を正規表現で抽出して再パースを試みる
- それでも失敗した場合は自分（Claude）でデフォルト判定して進み、フェーズ2でユーザーに確認する
- いずれのフォールバックでも`related_pattern`は無理に判定せず`null`扱いとする

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

LLMの判定結果をユーザーに以下の形式で**一画面**で提示する。ガイド転記がある場合は追記先と概要もここに含め、**別途「転記案を見せますか？」は聞かない**:

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

**関連パターン検知ありの場合（`related_pattern`が非nullの場合）:**

全パターン（基本/ガイド転記あり/プロジェクトドキュメント更新あり/CCガイド追記あり）の末尾に、以下のブロックを追加する:

```
🔗 関連パターン検知（過去7日 + 直近5件・横断）
「<related_pattern.entry>」と根本原因が共通する可能性があります
（理由: <related_pattern.reason>・共通タグ: #<common_tags[0]> #<common_tags[1]>）
構造的な文書への追記も検討しますか？[y/N]
```

- `y`の場合: 「この洞察はどこに書くのが適切だと思いますか？（既存ドキュメント名 or『なし』）」とユーザーに一言確認し、回答をフェーズ3のファイル作成・更新タスクに追加タスクとして組み込む
- `N`の場合: 何もせずフェーズ3へ進む
- このブロックは「この振り分けでよいですか？」の確認とは独立した別の確認事項として扱う（同じ`[yes/修正指示]`の応答に混ぜず、関連パターンの`y/N`は別途聞く）
- **非対話実行時のフォールバック**: 自律ループ等の自動実行コンテキストから`ssot-record`が呼ばれ、ユーザーの応答を待てない場合は、構造的文書への追記は行わずデフォルトで`N`相当として扱う。この場合も`related_pattern`自体はTask4の`related_entries`としてfrontmatterには記録する（検知結果そのものは失わない）
- **追記時のガードレール**: `y`の流れで既存の構造的文書（例: `01_基礎概念.md`等）に追記する場合、**末尾への追加のみとし、既存の見出し・本文・他のセクションは一切編集・削除しない**。対象ファイルの構造を壊さないことを最優先する

**プロジェクトドキュメント更新対象ありの場合（フェーズ0.5で検出された場合）:**

全パターンの末尾に `📦 プロジェクトドキュメント更新対象` ブロックを追加する:

```
📋 記録先の判定結果

📁 メイン: 01_DECISIONS/atelier-kyo-manager/2026-06-07_セール価格スクレイパー実装.md
📅 日記追記: あり（10_DAILY/2026-06-07.md）
📖 ガイド転記: なし
🏷️ タグ: #atelier-kyo-manager #スクレイピング #セール価格
💬 理由: プロジェクト固有の機能実装のため01_DECISIONSが最適

📦 プロジェクトドキュメント更新対象（3ファイル）:
   ✅ docs/変更履歴.md             — 末尾にエントリ追加
   ✅ docs/経営者判断.md           — セクション5に追記
   ✅ docs/プロダクトビジョン.md   — 既存資産テーブルに1行追加

この振り分け・更新対象でよいですか？[yes/修正指示]
```

- フェーズ0.5で検出されたファイルが **0件** の場合は `📦 プロジェクトドキュメント更新対象: なし` と表示
- ユーザー承認でSSOT記録 + プロジェクトドキュメント更新を一括実行

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
root_cause:
  category: <フェーズ1のroot_cause.category>
  description: <フェーズ1のroot_cause.description>
related_entries:  ← related_patternが非nullだった場合のみ追加。nullならこのフィールド自体を省略
  - <related_pattern.entry>
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

`root_cause`の`category`は以下から選ぶ: `code_defect`（コード上の不具合） / `design_mismatch`（設計・前提のズレ） / `requirement_change`（要件変更） / `external_dependency`（外部要因） / `operational_error`（運用ミス） / `unknown`（不明）。フェーズ1のJSON出力をそのまま転記する。

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

### 3-6. プロジェクトドキュメント更新（フェーズ0.5で検出された場合のみ）

フェーズ0.5で検出されたプロジェクト側ドキュメントを更新する。

#### 更新手順

1. **設定ファイル参照**: `obsidian-ssot/00_SYSTEM/タグマッピング.md` の「更新の種類 詳細」に従う
2. **各ファイルの更新**: 検出されたファイルごとに Read → 既存パターン確認 → Edit/Write で更新

#### 更新の種類別の実装

**末尾エントリ追加** — `docs/変更履歴.md` 等:
- ファイルをReadして最新エントリのフォーマットを確認
- 同じフォーマットで新しいエントリをファイル冒頭に追加
- フォーマット: `## YYYY-MM-DD\n\n### タイトル\n- 変更ファイルと内容`

**セクション追記** — `docs/経営者判断.md` 等:
- ファイルをReadして該当セクションの末尾を特定
- セクション末尾に内容を追記 + 最終更新日時を更新

**テーブル行追加** — `docs/プロダクトビジョン.md` `_INDEX.md` 等:
- ファイルをReadして該当テーブルの末尾行を確認
- 同じフォーマットで1行追加

**ステータス更新** — `docs/scraping-status.md` 等:
- ファイルをReadして該当行を特定
- 該当セルを更新

### 3-7. active-sessions ボードの自分エントリ更新（共通ファイルを触った場合）

今回の記録で**共通ファイル（9種: settings.json/CLAUDE.md/SKILL.md群/hook群/自動化.md/全体マップ_MOC.md/repo-index.yaml・リポジトリ索引.md/MCPツール使い分けガイド.md/リンク運用方針.md）を触った場合**、自分のボードエントリを更新する。

手順:
1. `obsidian-ssot/00_SYSTEM/active-sessions.md` を読み、自分のセッション(環境+トピック)のエントリを特定
   - **エントリが無い場合**（resume-sessionで追加し忘れた等）: 先頭行に追加（セッション/触る共通ファイル/方針/開始/🟢進行）
2. 「触る共通ファイル」欄に今回触ったファイルを追記（既存なら重複回避）
3. **即commit+push**（フェーズ5のcommitとは別に、ボードは時間感度高め）:
   ```bash
   cd ~/projects/obsidian-ssot && git add 00_SYSTEM/active-sessions.md && git commit -m "chore: active-sessions 更新(<セッション名>: <触ったファイル>)" && git push
   ```

**注意**: 共通ファイルを触る**前**にボードで被り確認（逆方向ならユーザー判断）。本ステップは事後の宣言更新。

---

## フェーズ3.5: バックログ完了チェック（タスク完了記録の確実化）

> **設計意図**: 「あ、(別セッションで)終わってました」現象の構造的根絶。
> 生きタスクの正典は `00_SYSTEM/バックログ.md` 唯一（`[ ]`=未完了 / `[x]`=完了）。
> 本フェーズで「完了したのに `[x]` 忘れ」を記録フロー内で確実に回収する。

### 実行条件

**記録内容が「タスクの完了」を含む場合のみ**実行する（機能実装完了・バグ修正完了・作業クローズ等）。
- 途中メモ・調査記録・設計途中・単なる設定追記 等、完了を伴わない記録は**スキップ**（フェーズ4へ）。

### 手順

1. **バックログ `[ ]` 一覧を取得**:
   ```bash
   grep -n '^- \[ \]' ~/projects/obsidian-ssot/00_SYSTEM/バックログ.md
   ```

2. **LLM照合**: 記録内容（フェーズ0で収集した内容）と `[ ]` 一覧を照合し、今回完了した可能性のある行を**上位1〜3候補**として抽出する。タスク名の類似度・プロジェクト一致・日付の近さを総合。

3. **候補提示と承認ゲート**:
   ```
   ✅ バックログ完了チェック
   今回の記録「<記録サマリー>」に対応するバックログ候補:
     1. [ ] <候補1のタスク名>（P0/P1/P2）
     2. [ ] <候補2> ...
   どれを [x]（完了）にしますか？[番号 / 違う / なし]
   ```
   - **承認**: 指定された行を `[x]` 化（必要なら完了日付を追記）
   - **「違う」**: 手動で行番号を指定させる（フォールバック）
   - **「なし」**: バックログに該当タスクなし → 「バックログ未登録タスクです。追加しますか？[y/N]」（`y` なら `[x]` 済みとして該当P区分に新規追加）

4. **該当なし（候補0件）**: ステップ3の「なし」と同様に「バックログ未登録タスク。追加しますか？」を確認。

### 安全設計

- **LLM提案＋ユーザー承認のハイブリッド**: 誤判定は提示段階で人が修正可能なため安全。LLM単独で `[x]` 化しない。
- 既に `[x]` の行には触れない。
- 完了日付は既存行の慣習（`（M/D完了）` 等）に合わせる。

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

### 5-1. SSOT（必須）

```bash
cd /home/yn4416/projects/obsidian-ssot
git add -A
git commit -m "record: <内容の1行説明>"
git push
```

### 5-2. プロジェクトリポジトリ（フェーズ3-6で更新があった場合のみ）

フェーズ0.5で検出されたプロジェクトのリポジトリもコミット・pushする。

```bash
cd /home/yn4416/projects/<project>
git add -A
git commit -m "docs: <内容の1行説明>"
git push
```

### 5-3. ガイドリポジトリ（フェーズ4で更新があった場合のみ）

ガイドを更新した場合は別途ガイドリポジトリもコミット（フェーズ4で実施済みの場合はスキップ）。

---

## フェーズ6: 完了報告

```
✅ SSOT記録完了

📁 01_DECISIONS/claude-code/2026-05-31_<ファイル名>.md
📅 10_DAILY/2026-05-31.md（追記）  ← also_daily: false の場合は「日記追記: なし」
📦 プロジェクトdocs: docs/変更履歴.md 等（更新あり/なし）  ← フェーズ3-6で更新した場合
🏷️ タグ: #claude-code #バグ修正
📖 ガイド転記: なし（または「あり → <章名>」）
🔗 コミット: <hash>
```

---

## フェーズ7: セッション終了確認（オプション）

フェーズ6の完了報告の直後に、ユーザーへセッション終了可否を**1回だけ**確認する。Default は No（記録して作業継続）。

```
🔁 このままセッションを終了して新セッションへ引き継ぎますか？[y/N]
```

- **N（デフォルト）**: 何もしない。記録だけ完了・同一セッションで作業継続
- **y**: `new-session` スキルを呼び出す（引き継ぎサマリー生成 → handoff保存 → active-sessionsボード✅終了）

### 設計意図（統合ではなく確認ステップにした理由）
- `ssot-record`（タスク毎・高頻度）と `new-session`（セッション区切り・低頻度）は**粒度が違う**。自動統合すると全タスク切り替えでセッションが切れる事故になる
- だから**確認ステップのみ**。ユーザーが「この記録でセッション終わり」と判断した時だけ new-session に繋ぐ
- 確認は1回・Default No・自動終了しない（N でも記録は残る）

### 注意
- new-session 呼び出し後は本スキルの役割終了。引き継ぎ処理は new-session 側で完結する
- 共通ファイルを触った場合のボード✅終了処理は、y で new-session を呼ぶとそちらで実施される（二重処理に注意）

---

## 制約・禁止事項

- APIキー・シークレットの値は絶対に書かない（キー名はOK）
- 日記に詳細を直書きしない（サマリー + リンクのみ）
- _INDEX.md に【要更新】マーカーを残さない
- ガイド転記はフェーズ2の yes 承認をもって承認済みとみなす（追加確認は不要）
- 1トピック = 1ファイル（複数の無関係な作業は別々のファイルに）
- `also_daily: false` の時は 10_DAILY に何も書かない
- タグマッピング設定は `obsidian-ssot/00_SYSTEM/タグマッピング.md` で管理（スキル内にハードコードしない）

---

## このスキルのトリガーワード

以下のいずれかでトリガー（`/ssot-record` コマンドでも可）:
- 記録して / 書き留めて / 保存して / メモして
- 残しておいて / 忘れないようにして
- SSOTに入れて / SSOTに書いて
- ガイドに追加して / ガイドに書いて / ガイドに入れて
- 書いておいて / 記しておいて

`record-decision` スキルの上位互換。`/record-decision` が呼ばれた場合もこのスキルで処理する。

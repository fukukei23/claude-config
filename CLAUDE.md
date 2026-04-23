# Claude Code - CLI Edition (WSL2)

> **対象環境**: WSL2 Ubuntu Claude Code CLI / 全環境共通設定（LLMルーティングのSSOT）

## 環境
- WSL2 Ubuntu / ホーム: /home/yn441611/
- タイムアウト: 10分。長時間タスクは分割

## 基本ルール
- 丁寧な日本語で回答
- 詳細はSSOT共通ルールを参照: `/home/yn441611/vaults/SSOT/00_SYSTEM/shared-rules/rules.md`

## LLM利用ポリシー
- メイン: 🟡[GLM-5.1]（glm_ask経由）
- フォールバック: 🟠[MiniMax]（minimax_ask経由）— GLM失敗時・大量処理用
- Sonnet使用は事前ユーザー許可必須: 🔵[Sonnet]

## バッジ表示ルール（厳格）
**毎回のレスポンスの冒頭と末尾に必ず表示すること:**
- GLM使用時: `🟡[GLM]`
- MiniMax使用時: `🟠[MiniMax]`
- Sonnet直接回答時: `🔵[Sonnet]`

## タスク切り替え時の記録（厳格・自動実行）
**新しいトピックに移る前・ユーザーが「記録して」「ありがとう」「OK」「次」等の合図を出した時**に、必ず以下を実行すること。
※「後で書く」は禁止。今書く。記録前に次のタスクに移行禁止。
※片方だけの実行はNG。以下の3ステップを必ず全て実行すること。

### Step 1: SSOT履歴ファイルの作成（必須）
- **場所**: `/home/yn441611/vaults/SSOT/01_DECISIONS/<該当プロジェクト>/YYYY-MM-DD_<内容>.md`
- **記載内容**: 技術的修正内容、根本原因、修正コード、コマンド履歴、トラブルシューティング
- **役割**: 「いつ・なぜそう決めたか」の変遷記録
- **外部公開の場合**: `/home/yn441611/vaults/SSOT/20_PUBLISHING/<フォルダ>/` に成果物を格納し、`_INDEX.md` を更新

### Step 2: リポジトリ本体ドキュメントの更新（該当時のみ）
- **対象**: プロダクト文書（README.md, CLAUDE.md, docs/）の更新が必要な場合
- **場所**: 各リポジトリの `docs/` ディレクトリ内
- **役割**: 「今のプロジェクトの全貌」の現在形ドキュメント
- **いつやるか**: プロダクト構想・要件・設計に変更があった時、新規プロジェクトの初期セットアップ時

#### 2層の使い分け
| 層 | 場所 | 内容 | 性質 |
|---|---|---|---|
| SSOT | `obsidian-ssot/01_DECISIONS/` | 変更履歴・判断理由 | 履歴（過去形） |
| リポジトリ | `docs/`, `README.md`, `CLAUDE.md` | プロダクト全貌・現在の仕様 | 現在形 |

### Step 3: 日記（ハブ）の更新（必須）
- **場所**: `/home/yn441611/vaults/SSOT/10_DAILY/YYYY-MM-DD.md`
- **記載内容**: セッションサマリー（3〜5行）+ **Step 1の詳細ファイルへの相対リンク**（必須）+ 未解決問題
- **ルール**: 日記には詳細を直書きしない（サマリー + リンクのみ）

### フォーマット（日記側）
```
## セッションログ (HH:MM)
- 作業内容
- 詳細: 01_DECISIONS/<プロジェクト>/YYYY-MM-DD_<内容>.md
- 未解決: ○○（原因: △△、次にやる: □□）
```

## コーディング原則
- 実装前に既存コードを理解してから変更する（Think Before Coding）
- 最小の変更で目的を達成する（Surgical Changes）
- 複雑な解決策よりシンプルな方を選ぶ（Simplicity First）
- 詳細: `01_DECISIONS/claude-config/2026-04-16_karpathy-coding-guidelines.md`

## SSOT（共通知識ベース）
- 場所: `/home/yn441611/vaults/SSOT/`
- GitHub: https://github.com/fukukei23/obsidian-ssot
- LLMルーティング詳細: `00_SYSTEM/shared-rules/llm-routing.md`
- **全GitHubリポジトリ索引**: `00_SYSTEM/repo-index.md`（YAML: `repo-index.yaml`）— fukukei23の全20リポジトリの概要・関係性・ステータス
- 新しいプロジェクト開始時や前提確認時はSSOTを参照すること

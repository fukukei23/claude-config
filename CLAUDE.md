# グローバル開発設定

WSL2 Ubuntu環境でのAIファースト開発。GLM-5をメインLLMとし、コスト効率と品質のバランスを重視。

---

## 言語設定
- **常に日本語で回答・出力すること**
- タスク名、ファイル名の提案、コメント等も日本語を優先
- コード内のコメントも日本語で記述

---

## 環境
- OS: Windows 11 + WSL2 Ubuntu
- エディタ: VSCode
- ファイルパス形式: `\\wsl.localhost\Ubuntu\home\yn441611\` または `/home/yn441611/`
- シェル: bash (WSL2内)

---

## LLM使用ポリシー（重要）

### デフォルトのLLM振り分けルール
Proプランのトークンは限られているため、**GLMをデフォルト**として以下のルールに厳密に従うこと：

| 用途 | 使用LLM | MCPツール |
|-----|---------|---------|
| **普通の会話・質問・調査・説明・雑談** | 🟡 **GLM-5.1**（デフォルト） | `glm_ask` |
| コード生成・ドキュメント作成・GitHub・Obsidian更新 | 🟡 **GLM-5.1** | `glm_generate_code` / `glm_write_document` / `glm_ask` |
| ファイル要約・翻訳・大量変換・バッチ処理 | 🟠 **MiniMax**（軽量処理） | `minimax_summarize_file` / `minimax_batch_process` / `minimax_ask` |
| Tier1（セキュリティ・認証・本番デプロイ）・複雑なアーキ設計・GLMが失敗した場合 | 🔵 **Sonnet**（最終手段） | （直接回答） |

### 会話フロー（重要）
1. ユーザーからメッセージを受け取る
2. **まず `glm_ask` を呼び出してGLMに回答させる**
3. GLMの回答をそのままユーザーに返す（加工不要）
4. Sonnet直接回答は上記表の「最終手段」ケースのみ

### レスポンスへのバッジ表示ルール
**毎回のレスポンスの冒頭に必ず以下のバッジを付けること：**
- GLMツールを使った場合: `🟡[GLM]`
- MiniMaxツールを使った場合: `🟠[MiniMax]`
- Sonnet（自分）が直接回答する場合: `🔵[Sonnet]`

### IMPORTANT
- **普通の会話でも必ずglm_askを経由すること。Sonnetで直接回答しない**
- Sonnet直接回答は「Tier1・複雑なアーキ設計・GLM失敗時」のみ
- ユーザーがどのLLMが動いているか常に把握できるようにバッジを省略しないこと
- **🔴 Sonnetを直接使う前に必ずユーザーに許可を取ること（例：「Sonnetを使ってよいですか？」）**
- ブラウザ自動操作・ファイル操作・ツール実行の結果報告もGLM経由でユーザーに返す

---

## LLM統合

### デスクトップアプリ（チャット・Cowork・Codeタブ全て）
- **バックエンド: Anthropic Claude Sonnet 4.6**
- 認証: `C:\Users\USER\.claude\.credentials.json` のOAuth（Pro購読）
- 重要: OAuthが存在する限り settings.json のenvセクションは無効
- Pro制限: 週次リセット・追加課金あり（追加$5/月上限）

### CursorアプリのClaude Code CLI（WSL2内）
- **バックエンド: Z.AI / GLM-5.1**
- 認証: `~/.claude/settings.json` の `ANTHROPIC_AUTH_TOKEN`（GLMキー）
- エンドポイント: `https://api.z.ai/api/anthropic`
- フォールバック: GLM失敗時は `~/.claude/scripts/claude-fallback` でMiniMaxへ退避

### 重要な仕組み（2026-03-31検証済み）
- デスクトップアプリ: `.credentials.json` OAuth > settings.json env（OAuthが必ず勝つ）
- Cursor CLI: `settings.json` env > `.credentials.json`（envが優先）
- 2つの環境は独立して動作する

### タスク複雑度による自動選択
- Simple (0.0-0.35): Haiku相当
- Medium (0.35-0.65): Sonnet相当
- Complex (0.65-1.0): Opus相当（品質優先時）

---

## 🔴 厳格禁止（絶対に実行しないで）

### 以下のコマンドは使用禁止
- `rm -rf` で `*` や `/` を含むもの
- `del *.*`、`Remove-Item -Recurse *` などの全削除
- `git reset --hard`、`git push --force`
- `DROP`、`TRUNCATE`、`DELETE *` を含むSQL
- `sudo`、`shutdown`、`reboot`、`format`

### 以下のファイル/ディレクトリへの操作禁止
- `C:\Windows`、`C:\Program Files`
- `/etc`、`/bin`、`/usr/bin`（WSL）
- `.git/` ディレクトリ
- `.env`、`.env.production` の削除/変更

---

## 開発フロー

### ブランチ命名規則
```
feat/機能名     # 新機能
fix/バグ名       # バグ修正
docs/内容       # ドキュメント
refactor/対象   # リファクタリング
test/対象       # テスト追加
chore/内容      # その他（依存関係更新等）
```

### コミットメッセージ（Conventional Commits）
```
feat: 機能の説明
fix: バグ修正の説明
docs: ドキュメント変更の説明
refactor: リファクタリング内容
test: テスト追加内容
chore: その他の変更
```

### Git運用
- ローカルコミット: 自動実行OK
- git push: 必ず確認（askモード）
- force push: 禁止

---

## Tier 1品質管理（超軽量版）

以下のキーワードを含むタスクのみ実装前に簡易仕様確認必須:

| カテゴリ | キーワード |
|---------|-----------|
| **金銭** | 決済、課金、返金、料金計算、サブスクリプション |
| **認証** | パスワード、トークン、OAuth、JWT |
| **データ破壊** | データ削除、テーブル削除、カラム削除、マイグレーション |
| **本番環境** | 本番デプロイ、プロダクション、本番リリース |
| **セキュリティ** | 暗号化、SQLインジェクション、XSS、CSRF |

それ以外のタスク（API追加、UI変更、テスト追加等）は即座に実装開始。

### 簡易仕様確認（3項目）
1. 何を作るか（1-2文）
2. 主要な制約（3つまで）
3. 影響範囲（新規/既存、対象ファイル）

IMPORTANT: Tier 1以外でも、Claudeが判断に迷う場合は質問してOK。

---

## 自動化方針

### 🟢 自動実行OK（確認不要）
- ファイル作成・編集・読み取り
- テスト実行
- 非破壊的bashコマンド（ls, cat, grep, find等）
- ローカルブランチ作成・コミット
- Docker操作（起動・停止・ビルド）
- パッケージインストール（npm, pip等）
- 開発サーバー起動

### 🟡 確認必須（AskUserQuestionを使用）
- ファイル削除（rm）
- git push
- Tier 1タスクの実装開始
- 本番環境への操作

### 作業方針
- 最初にタスク全体を設計・計画
- 不明点は可能な限りLLMで解決
- **人間にしか判断できない重要事項のみ質問**
- それ以外は全自動で進行

---

## プロジェクト管理

### /initコマンド運用
1. 新規プロジェクトで`/init`実行
2. 生成されたCLAUDE.mdを叩き台として使用
3. Claude自身に精査・削減させる（自明な情報、冗長な記述を削除）
4. 「この行を削除したら、Claudeが間違いを犯すか？」テストを適用

### Progressive Disclosure
プロジェクトのCLAUDE.mdが500行を超えた場合:
1. Layer 1（CLAUDE.md）: 30-50行に削減
2. Layer 2（.claude/rules/*.md）: 詳細ルールを分離
3. Layer 3（.claude/skills/）: 専門知識を分離

約500行以内に収めることが推奨されるが、短いほど効果的。

---

## Desktop Commander MCP

以下の操作が利用可能:
- ファイル読み書き編集
- ディレクトリ操作
- プロセス起動（サーバー起動等）
- bashコマンド実行（破壊的操作以外）

---

## 注意事項
- ユーザーはコードを読めないため、安全第一で行動
- バイパスモードが有効になっている
- 不安な操作は必ず確認する
- WSL2環境: Windowsパスと Linux パスの混在に注意
- APIタイムアウト: 3分設定。長時間タスクは分割実行
- GLM-5優先: コスト効率重視だが、品質が必要な場合は上位モデル使用OK
- IMPORTANT: コードは全てLLMが書く。人間はレビューと意思決定に専念

## ワークスペース管理

### 構造
- 作業の起点: `C:\Users\User\workspace\`
- プロジェクト状態の索引: `workspace\_INDEX.md`（タスク開始前に必ず参照）
- `active\` = 作業対象。読み書き自由
- `archive\` = 読み取り専用。移動・削除は確認必須
- `handover\` = LLM引き継ぎ文書の置き場。ルート直置き禁止

### ファイル命名規則
- 日付入りファイル: `YYYY-MM-DD_名前.ext`
- バックアップファイル: `元ファイル名_bak_YYYY-MM-DD.ext`
- 引継ぎ文書: `handover\YYYY-MM-DD_プロジェクト名_handover.md`

### AIが自動更新するもの
- `_INDEX.md`（新規プロジェクト追加・完了時）
- `handover\` 内の引き継ぎ文書（タスク完了時）

### 注意
- `tools\atelier-kyo-manager` に `.env` あり。移動時はパス依存設定を確認すること
- `docker-compose.yml`（ルート）は帰属プロジェクト未特定。触れないこと

# Claude Code Configuration & Operations

fukukei23/claude-config — Private Repository

## 概要

Claude Codeの全環境設定を一元管理するリポジトリです。

- **2環境構成**: Desktop（Windows OAuth Pro）+ CLI（WSL2 Z.AI）
- **コスト最適化**: GLM・MiniMax活用によるトークンコスト制御
- **運用記録**: 設定変更・意思決定・トラブルシューティングの完全記録

## 2環境アーキテクチャ

| 環境 | ベースモデル | 認証方式 | 設定場所 |
|------|------------|---------|---------|
| Windows Desktop App | Anthropic Sonnet 4.6（OAuth固定） | `.credentials.json` OAuth Pro | `C:\Users\USER\.claude\` |
| WSL2 CLI | GLM-5.1（Z.AI） | `settings.json` env | `~/.claude/settings.json` |

**Desktop環境**
- Sonnet固定でモデル変更不可
- 外部LLM（GLM/MiniMax）はMCP経由のみ利用可能

**CLI環境**
- GLM-5.1がメインモデル
- フォールバック設定によりMiniMaxへ自動退避（429/500系エラー時）

## LLMコスト構造

> **重要**: Claude Codeは常にバックグラウンドで動作しています。

Claude Codeのセッション本体（オーケストレーター）は常にAnthropicのClaudeが実行し、トークンを消費しています。
GLM・MiniMaxはMCPツールとして呼び出されますが、**無料ではありません（安いだけ）**。

### コスト体系

| 項目 | Desktop | CLI |
|------|---------|-----|
| ベース | Sonnet OAuth Pro（週次リセット） | GLM-5.1（Z.AI） |
| MCP呼び出し | MiniMax/GLM API料金 | MiniMax（フォールバック時） |
| 月額ベース | Anthropic Proプラン $20/月 | Z.AI APIコスト |

### コスト内訳

- **Anthropic Proプラン**: $20/月（ベース料金）
- **GLM API**: Z.AI従量課金
- **MiniMax API**: 従量課金（GLMより安価）

### よくある誤解

| 誤解 | 事実 |
|------|------|
| 「GLM/MiniMaxは無料」 | 無料ではない。Claude Codeより安いだけ |
| 「Desktopでモデルを変更できる」 | OAuth ProではSonnet固定。変更不可 |
| 「CLIの設定をDesktopに適用できる」 | 2環境は完全に独立したアーキテクチャ |
| 「401/403エラーでもフォールバックする」 | 認証エラーはフォールバック対象外。429/500系のみ |

## ディレクトリ構成

```
claude-config/
├── CLAUDE.md              # グローバル開発設定（LLMルーティング・禁止操作等）
├── ROUTING.md             # LLMルーティング正式仕様（Desktop/CLI両対応）
├── ARCHITECTURE.md        # SSOT・2環境アーキテクチャ図
├── TROUBLESHOOTING.md     # 2環境トラブルシューティング
├── agents/                # Specialized Agents
│   ├── code-reviewer.md       # コード品質レビュー
│   ├── decision-recorder.md   # 意思決定記録
│   └── tier1-validator.md     # 高リスク操作の事前検証
├── core/                  # Computer Useスクリプト群（.sh/.ps1）
├── docs/                  # 詳細ドキュメント
│   ├── CLAUDE_FALLBACK.md     # フォールバック構成詳細
│   ├── COMPUTER-USE.md        # Computer Use機能の設定と使い方
│   ├── CONFIG-STRATEGY.md     # 設定戦略・環境別設定方針
│   ├── DEVELOPMENT.md         # 開発ガイドライン
│   ├── REPO-USAGE-GUIDE.md    # リポジトリ利用ガイド
│   ├── TROUBLESHOOTING.md     # 詳細トラブルシューティング
│   ├── decisions/             # 意思決定記録（ADR）
│   └── archive/               # 旧ドキュメント保管庫
├── lib/                   # フォールバックライブラリ（JS）
├── obsidian-logging/      # Obsidian自動ログ（hooks/templates）
├── plugins/               # Claude Code プラグイン設定
├── scripts/               # 自動化スクリプト
├── shared-rules/          # SSOTへのポインタ
├── workflows/             # 開発フロー定義
├── fallback-config.json   # CLI版フォールバック設定
├── settings.example.json  # CLI設定テンプレート
└── .env.example           # 環境変数テンプレート
```

## LLMルーティング

Desktop/CLI共通のルーティングポリシーです。詳細は [ROUTING.md](ROUTING.md) を参照。

| 優先度 | バッジ | モデル | 用途 |
|--------|--------|--------|------|
| 第一優先 | 🟡 | GLM-5.1 | 日常作業・分析・要約・翻訳 |
| 第二優先 | 🟠 | MiniMax | GLM失敗時・大量処理 |
| 最終手段 | 🔵 | Sonnet | Tier1・複雑設計（事前許可制） |

### バッジ凡例

- 🟡 **GLM** — 第一優先。コード生成能力が高く日常タスクに最適
- 🟠 **MiniMax** — 第二優先。GLM失敗時のフォールバック・大量処理用
- 🔵 **Sonnet** — 最終手段。高精度だがコスト高。事前許可制

## 品質管理

### Tier分類

| Tier | リスクレベル | 対象操作 | アクション |
|------|------------|---------|-----------|
| Tier1 | 高リスク | 認証・決済・データ移行・本番デプロイ | Tier1 Validator Agentが事前検証 |
| Tier2 | 通常 | 通常の開発作業 | 即時実装 |

### Specialized Agents

| Agent | 役割 | ファイル |
|-------|------|---------|
| Tier1 Validator | 高リスク操作の事前検証・承認 | `agents/tier1-validator.md` |
| Code Reviewer | コード品質の自動レビュー | `agents/code-reviewer.md` |
| Decision Recorder | 意思決定の記録・追跡 | `agents/decision-recorder.md` |

## セッション管理・記憶

3層構造でセッション間のコンテキストを維持:

| 層 | 場所 | 目的 |
|----|------|------|
| セッション記憶 | `~/.claude/projects/<project>/memory/` | セッション間で継続する重要情報 |
| SSOT日記 | `SSOT/10_DAILY/YYYY-MM-DD.md` | 日次作業ログ・決定事項 |
| Obsidianログ | hooks自動記録 | セッション開始/終了のタイムスタンプ |

## 関連リポジトリ

| リポジトリ | 役割 | URL |
|-----------|------|-----|
| obsidian-ssot | SSOT（共通知識ベース） | https://github.com/fukukei23/obsidian-ssot |

**知識ベース**: `obsidian-ssot/01_DECISIONS/claude-code/`

## ドキュメント一覧

| ファイル | 概要 |
|---------|------|
| `CLAUDE.md` | グローバル開発設定。LLMルーティングルール・禁止操作・コーディング規約 |
| `ROUTING.md` | LLMルーティング正式仕様。Desktop/CLI両対応のルーティング定義 |
| `ARCHITECTURE.md` | SSOT・2環境アーキテクチャ図。システム全体構成 |
| `TROUBLESHOOTING.md` | 2環境トラブルシューティング。よくある問題と解決策 |
| `docs/CLAUDE_FALLBACK.md` | フォールバック設定の詳細仕様 |
| `docs/COMPUTER-USE.md` | Computer Use機能の設定と使い方 |
| `docs/CONFIG-STRATEGY.md` | 設定戦略・環境別設定方針 |
| `docs/DEVELOPMENT.md` | 開発ガイドライン・ワークフロー |
| `docs/REPO-USAGE-GUIDE.md` | リポジトリ利用ガイド |

---

> Private Repository — fukukei23/claude-config

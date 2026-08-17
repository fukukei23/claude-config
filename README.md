# Claude Code Configuration & Operations

> Centralized configuration and operations management for Claude Code across all environments (Windows Desktop + WSL2 CLI). Includes LLM routing policies, MCP-based cost optimization, and multi-tier quality management.

fukukei23/claude-config — Claude Code 全環境の設定・運用を一元管理するリポジトリ

---

## Claude Code とは

Claude Code は Anthropic が提供するAIコーディングアシスタントで、**2つの異なる動作形態**がある。

| 形態 | 起動方法 | 主な使い方 |
|------|---------|-----------|
| **CLI版** | ターミナルで `claude` コマンド | WSL / Linux / macOS での開発作業 |
| **Desktopアプリ版** | Windows / Mac のGUIアプリ | デスクトップ上での会話・コード支援 |

この2形態は**認証方式・使用モデル・コスト構造がすべて異なる**。混同しないことが重要。

---

## 認証方式とモデルの違い

### CLI版（WSL2 / Linux）

```
認証: APIキー（.env / settings.json に直書き）
モデル: 自由に選択可能（GLM-5.3 など外部LLMも直接設定できる）
課金: APIキーに紐づく従量課金
```

- `settings.json` の `env` セクションで `ANTHROPIC_API_KEY` を GLM の APIキーに設定することで、**Claude Code CLI 自体を GLM で動かす**ことができる。
- フォールバック設定で複数モデルを自動切り替えすることも可能。

### Desktopアプリ版（Windows / Mac）

```
認証: OAuth Pro（Anthropic アカウントでログイン）
モデル: Sonnet 固定（変更不可）
課金: Anthropic Pro プラン $20/月（週次リセット制）
```

- OAuth認証のため、**APIキーを差し替えてモデルを変えることができない**。
- 会話・コード生成はすべて Sonnet が処理する。

---

## Desktop版のコスト対策 → MCP経由で安価LLMを使う

Desktopアプリ版はモデルを変更できないが、**MCP（Model Context Protocol）サーバーを自作して登録する**ことで、GLMやMiniMaxなどの安価なLLMをツールとして呼び出せる。

```
Claude Desktop（Sonnet）
    └── MCP ツール呼び出し
            ├── glm_ask  → Z.AI GLM-5.3（安価）
            └── minimax_ask → MiniMax（安価）
```

Sonnetがオーケストレーターとして動作し、コード生成・文書作成などの重い処理を安価LLMに委譲することでコストを大幅に削減できる。

設定の本体は `%APPDATA%\Claude\claude_desktop_config.json` の **1ファイル**。
PC移行もこのファイルをコピーするだけで復元できる。

### 👉 [Desktop × MCP で安価LLMを使う完全ガイド](mcp-cheap-llm/README.md)

セットアップ手順 / APIキー一元管理 / ハマりポイント（`set -a` 問題）/ PC移行手順 / セキュリティをすべて網羅。

---

## CLI版のコスト対策 → glm-rate-proxy（ローカルプロキシ）

CLI版では `glm-rate-proxy` というローカルリバースプロキシを挟むことで、429エラー・ピーク時間帯のコスト爆発を自動防止する。

```
Claude Code CLI
    └── http://127.0.0.1:8787（ローカルプロキシ）
            ├── 正常時 → Z.AI GLM-5.3
            ├── 使用率80%↑ → GLM-4.7
            ├── 使用率95%↑ → GLM-4.7-Flash（無料）
            ├── ピーク時間帯(15-19時) → MiniMax M2.7
            ├── 429エラー → GLM-4.7 → MiniMax M2.7
            └── その他エラー → MiniMax M2.7
```

### フォールバックチェーン（2026-05-29 現在）

| # | 状況 | 動作 |
|---|---|---|
| ① | 正常時 | ZAI（GLM-5.3）使用 |
| ② | 使用率 80-95% | GLM-4.7 にダウングレード |
| ③ | 使用率 >95% | GLM-4.7-Flash（無料枠）使用 |
| ④ | ピーク時間帯（JST 15-19時） | MiniMax M2.7 に強制ルーティング |
| ⑤ | 429エラー | GLM-4.7 → MiniMax M2.7 |
| ⑥ | その他エラー（500/502/タイムアウト等） | MiniMax M2.7 に自動フォールバック |
| ⑦ | MiniMaxもエラー | 503返す |

### 主要ファイル

| ファイル | 用途 |
|---|---|
| `~/.claude/scripts/glm-rate-proxy/` | プロキシ本体（Python/aiohttp） |
| `~/.claude/scripts/start-glm-proxy.sh` | SessionStart hook で自動起動 |
| `~/.config/glm-rate-proxy/config.json` | ピーク時間・使用率閾値の設定 |

### ステータス確認

```bash
# プロキシのルーティング状態
curl -s http://127.0.0.1:8787/proxy/status | python3 -m json.tool

# ANTHROPIC_BASE_URL がプロキシ向きか確認
echo $ANTHROPIC_BASE_URL
# → http://127.0.0.1:8787 ならプロキシ経由
# → https://api.z.ai/... ならZAI直結（プロキシバイパス）
```

---

## このリポジトリの構成

| 環境 | ベースモデル | 認証 | 主な設定ファイル |
|------|------------|------|----------------|
| Windows Desktop App | Sonnet（OAuth固定） | OAuth Pro | `claude_desktop_config.json` + `mcp-cheap-llm/` |
| WSL2 CLI | GLM-5.3（Z.AI） | APIキー | `~/.claude/settings.json` |

```
claude-config/
├── mcp-cheap-llm/         ⭐ Desktop × MCP 安価LLM完全ガイド
│   └── README.md
├── CLAUDE.md              # グローバル開発設定（LLMルーティング・禁止操作等）
├── ルーティング.md             # LLMルーティング正式仕様（Desktop/CLI両対応）
├── アーキテクチャ.md        # 2環境アーキテクチャ図
├── トラブルシューティング.md     # トラブルシューティング
├── agents/                # Specialized Agents
│   ├── コードレビュー.md
│   ├── 判断記録.md
│   └── tier1バリデーター.md
├── core/                  # Computer Useスクリプト群
├── docs/                  # 詳細ドキュメント群
├── lib/                   # フォールバックライブラリ（JS）
├── obsidian-logging/      # Obsidian自動ログ
├── plugins/               # Claude Code プラグイン設定
├── scripts/               # 自動化スクリプト
└── workflows/             # 開発フロー定義
```

---

## LLMルーティングポリシー

Desktop / CLI 共通のルーティング方針。詳細は [ルーティング.md](ルーティング.md) を参照。

| 優先度 | バッジ | モデル | 用途 |
|--------|--------|--------|------|
| 第一優先 | 🟡 | GLM-5.3 | 日常作業・コード生成・要約・翻訳 |
| 第二優先 | 🟠 | MiniMax | GLM失敗時・大量処理・ピーク時間帯 |
| 最終手段 | 🔵 | Sonnet | Tier1・複雑設計（事前許可制） |

> **Sonnet は最終手段。** 事前許可なしに Sonnet を直接使うことは禁止。

### CLI版: 自動ルーティング（glm-rate-proxy経由）

CLI版では `glm-rate-proxy` が自動でルーティングを制御。ユーザー操作不要。

```
正常時 → ピーク時間帯(15-19時)はMiniMax / 通常はGLM-5.3
エラー時 → 429/500/502/タイムアウト → 自動でMiniMaxにフォールバック
```

---

## 品質管理

### Tier分類

| Tier | リスクレベル | 対象操作 |
|------|------------|---------|
| Tier1 | 高リスク | 認証・決済・データ移行・本番デプロイ |
| Tier2 | 通常 | 通常の開発作業 |

Tier1 操作は `agents/tier1バリデーター.md` の Agent が事前検証する。

---

## コスト構造と注意点

| 項目 | Desktop | CLI |
|------|---------|-----|
| ベース | Sonnet OAuth Pro（週次リセット） | GLM-5.3（Z.AI 従量課金） |
| MCP経由呼び出し | GLM / MiniMax API料金 | MiniMax（フォールバック時） |
| 月額目安 | Anthropic Pro $20/月 + MCP API料金 | Z.AI 従量課金のみ |

**よくある誤解**

| 誤解 | 事実 |
|------|------|
| 「GLM/MiniMaxは無料」 | 無料ではない。Sonnetより安いだけ |
| 「Desktopでモデルを変更できる」 | OAuth ProではSonnet固定。変更不可 |
| 「CLIの設定をDesktopに適用できる」 | 2環境は完全に独立したアーキテクチャ |

---

## セッション管理・記憶（3層構造）

| 層 | 場所 | 目的 |
|----|------|------|
| セッション記憶 | `~/.claude/projects/<project>/memory/` | セッション間で継続する重要情報 |
| SSOT日記 | `SSOT/10_DAILY/YYYY-MM-DD.md` | 日次作業ログ・決定事項 |
| Obsidianログ | hooks自動記録 | セッション開始/終了のタイムスタンプ |

---

## ドキュメント一覧

| ファイル | 概要 |
|---------|------|
| `docs/Claude-Code完全ガイド.md` | **Claude Code 全機能ガイド（コマンド・スキル・MCP・フック・メモリ・エージェント）** |
| `mcp-cheap-llm/README.md` | **⭐ Desktop × MCP 安価LLM完全ガイド** |
| `CLAUDE.md` | グローバル開発設定。LLMルーティングルール・禁止操作 |
| `ルーティング.md` | LLMルーティング正式仕様 |
| `アーキテクチャ.md` | 2環境アーキテクチャ図 |
| `トラブルシューティング.md` | よくある問題と解決策 |
| `docs/Claudeフォールバック.md` | フォールバック設定の詳細仕様 |
| `docs/コンピュータ使用.md` | Computer Use機能の設定と使い方 |
| `docs/設定戦略.md` | 設定戦略・環境別設定方针 |
| `docs/開発ガイド.md` | 開発ガイドライン・ワークフロー |

---

## Claude Code フルカスタマイズ実績

非IT公務員からAI駆動開発に転身し、Claude Code CLIを以下のようにフルカスタマイズして運用しています。

### Hooks（5種類のライフサイクル自動化）

| タイミング | スクリプト | 役割 |
|-----------|-----------|------|
| PreToolUse | `guard-destructive-commands.sh` | 19種の破壊的コマンド（rm -rf /, git push --force 等）を自動ブロック |
| PostToolUse | `track-tool-usage.sh` | 全ツール呼び出しを日次CSVに自動記録 |
| SessionStart | `check-version.sh` + `load-handoff.sh` + `startup-banner.sh` | バージョンチェック・前回引き継ぎ・今日の状況表示 |
| Stop | `notify-discord-on-error.sh` + `generate-handoff.sh` | エラー時Discord通知・ハンドオフ文書自動生成 |
| CronCreate | 自律開発ループ | 毎時自動でコード品質チェック・テスト実行 |

### MCP Servers（10+サーバー常時稼働）

| サーバー | 用途 |
|---------|------|
| brave-search | Web検索・ニュース・画像・動画 |
| context7 | ライブラリドキュメント検索 |
| exa | 高精度Web検索・ページ取得 |
| plugin:discord | Discord経由でAIエージェント操作 |
| plugin:github | Issues/PR/コード検索・CI状況確認 |
| plugin:playwright | ブラウザ自動操作・E2Eテスト |
| web-reader | URL→Markdown変換 |
| mermaid | アーキテクチャ図・フローチャート生成 |
| 4_5v_mcp | 画像解析（マルチモーダル） |

### Skills（自作スキル3種）

| スキル | 用途 |
|-------|------|
| delegate-to-minimax | 大量処理タスクをMiniMaxに自動委譲 |
| ssot-record | SSOTへの記録・振り分けを自動化（record-decision統合済） |
| zenn-article-pipeline | Zenn技術記事の下書き→公開パイプライン |

### Memory（永続的記憶システム）

セッションを跨いで文脈を維持する4層構造：
- **user**: ユーザーのロール・志向・制約
- **feedback**: 過去の修正指示・確認済み方針
- **project**: 進行中のタスク・デッドライン
- **reference**: 外部リソースのポインタ

### glm-rate-proxy（7層フォールバックチェーン）

```
正常時 → ZAI（GLM-5.3）
使用率 80-95% → GLM-4.7 にダウングレード
使用率 >95% → GLM-4.7-Flash（無料枠）
ピーク時間帯（JST 15-19時）→ MiniMax M2.7 に強制ルーティング
429エラー → GLM-4.7 → MiniMax M2.7
その他エラー（500/502/タイムアウト）→ MiniMax M2.7 に自動フォールバック
MiniMaxもエラー → 503返す
```

月額コスト $180 に最適化（GLM 85% / MiniMax 14% / Sonnet <1%）。

### Subagent（4並列同時実行）

調査・実装・テスト・レビューを4エージェント並列で実行し、開発速度を最大化。

---

## 関連リポジトリ

| リポジトリ | 役割 |
|-----------|------|
| [obsidian-ssot](https://github.com/fukukei23/obsidian-ssot) | SSOT（共通知識ベース・意思決定記録） |

---

> fukukei23/claude-config — Claude Code 全環境の設定・運用を一元管理

# claude-config

Claude Code CLI のコスト最適化を実装し、実際に運用している設定リポジトリです。
Sonnet 比 約90%のコスト削減を達成済みの構成を公開しています。

## 概要

Claude Code CLI を日常的に利用するなかで、API利用料金の増大が課題となっていました。
本リポジトリは、その課題に対して実際に導入・運用しているコスト最適化の設定一式です。

主な取り組みとして以下を実施しています。

- ANTHROPIC_BASE_URL を Z.AI（GLM-5.1）に向け、Sonnet 比で約90%のコスト削減を実現
- Claude Sonnet をオーケストレーターとし、MCP 経由で GLM / MiniMax を呼び出す構成を導入
- Windows Desktop（OAuth Sonnet）と WSL2 CLI（GLM-5.1）の 2環境で認証方式の違いを実測で把握・運用中
- GLM 呼び出し失敗時に MiniMax へ自動フォールバックする仕組みをスクリプトで実装

すべて実際の開発環境で稼働しており、継続して運用・改善しています。

## 実装内容

### コスト削減構成

Sonnet API の代替として Z.AI（GLM-5.1）を利用する構成です。
環境変数 ANTHROPIC_BASE_URL の変更のみで導入でき、既存の Claude Code CLI の使い方を大きく変えることなくコストを抑えられます。
実際に本構成で約90%のコスト削減を確認し、現在も運用しています。

### 自動フォールバックスクリプト

GLM の呼び出しに失敗した場合、MiniMax へ自動でフォールバックするスクリプトを実装・公開しています。

- [scripts/claude_fallback.py](scripts/claude_fallback.py) — フォールバックスクリプト本体

設定テンプレートも公開しています。実際の値はサニタイズ済みです。

- [settings.example.json](settings.example.json) — 設定テンプレート

### LLMルーティング

Claude Sonnet をオーケストレーターとして機能させ、タスクに応じて GLM や MiniMax を MCP 経由で呼び出すルーティング設定です。
詳細は以下のドキュメントを参照してください。

- [ROUTING.md](ROUTING.md)

## ドキュメント

各構成の詳細な説明はドキュメントディレクトリにまとめています。

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — アーキテクチャ概要
- [docs/CLAUDE_FALLBACK.md](docs/CLAUDE_FALLBACK.md) — フォールバック構成の詳細説明

## お問い合わせ

本リポジトリの構成に関するご質問は、GitHub Discussions にて受け付けています。

また、Claude Code CLI のコスト最適化設定の代行も承ります。ご相談は GitHub Discussions からご連絡ください。

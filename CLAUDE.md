# Claude Code CLI 設定・スクリプト集

このリポジトリは、Claude Code CLI の設定ファイル・スクリプト・ワークフローを一元管理する「ソースリポジトリ」です。

## ディレクトリ構造

| ディレクトリ | 内容 |
|---|---|
| `agents/` | エージェント定義・プロンプト |
| `cache/` | キャッシュ管理 |
| `claude-mem/` | Claude用メモリ・コンテキスト管理 |
| `docs/` | ドキュメント |
| `lib/` | 共通ライブラリ |
| `mcp-cheap-llm/` | 低コストLLM用MCPサーバー |
| `obsidian-logging/` | Obsidian連携ログ |
| `plugins/` | プラグイン |
| `scheduled-tasks/` | 定期実行タスク |
| `scripts/` | 各種スクリプト（hookスクリプト等） |
| `scripts/glm-rate-proxy/` | GLMレートリミット対応プロキシ（Pythonパッケージ） |
| `skills/` | スキル定義 |
| `shared-rules/` | 共有ルール |
| `workflows/` | ワークフロー定義 |

| ファイル | 内容 |
|---|---|
| `settings.example.json` | Claude Code CLI 設定テンプレート（サニタイズ済み） |
| `settings.local.example.json` | ローカル設定テンプレート |
| `fallback-config.json` | フォールバック条件・閾値設定テンプレート |

## ⚠️ 実際の設定ファイルの場所

このリポジトリは設定の「ソース」です。Claude Code CLI が実際に読み込むのは **WSL 側の ~/.claude/ ディレクトリ** にあるファイルです。

- **グローバルCLAUDE.md**: `//wsl.localhost/Ubuntu/home/yn4416/.claude/CLAUDE.md`
- **グローバルsettings.json**: `//wsl.localhost/Ubuntu/home/yn4416/.claude/settings.json`
- **スクリプト確認**: `ls /home/yn4416/.claude/scripts/`

## 運用ルール

- LLMルーティング・バッジ表示・SSOT記録などのグローバルルールは `~/.claude/CLAUDE.md` を参照
- このリポジトリの変更を反映する際は `~/.claude/` に手動でコピーまたはシンボリックリンクを設定する
- APIキー等の機密情報は `settings.example.json` に含めない（サニタイズ済みテンプレートのみ管理）

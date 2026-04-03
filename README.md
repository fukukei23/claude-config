# claude-config

Claude Code専用設定リポジトリ。CLAUDE.md、settings.json、hooks、plugins等を管理。

共通ルール（他AI用）は `shared-rules/` に配置し、Obsidian + GitHubで管理。

## 構成

```
claude-config/
├── CLAUDE.md              ← リポ直下のClaude Code設定（CLAUDE.mdとして使う場合はシンボリックリンク）
├── shared-rules/          ← 全AI共通ルール（Obsidian管理・GitHub公開）
│   ├── rules.md           ← 禁止操作・Tier1判定
│   ├── locations.md       ← Obsidian・プロジェクト場所
│   ├── llm-routing.md     ← LLMルーティング
│   ├── session-log-format.md
│   └── ai-setup/          ← 各AI設定テンプレート
├── projects/              ← プロジェクト別情報
├── plugins/               ← Claude Codeプラグイン
├── scheduled-tasks/       ← 定期実行タスク
├── core/                  ← 削除禁止: フォールバック等
├── docs/                  ← ドキュメント
└── workflows/             ← ワークフロー定義
```

## 運用方針

- **実体**: ローカルObsidianで管理
- **バックアップ**: GitHub（このリポ）
- **他AIへの共有**: `shared-rules/` の内容を各AIの設定ファイルにコピペ

## 2環境構成

| 項目 | Windows Desktop | WSL2 CLI |
|------|----------------|----------|
| 設定フォルダ | `C:\Users\USER\.claude\` | `/home/yn441611/.claude/` |
| バックエンド | OAuth Sonnet (Pro) | GLM-5.1 (Z.AI) |
| 認証 | `.credentials.json` OAuth | `settings.json` env |

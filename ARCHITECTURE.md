# Claude Code Configuration Architecture

2環境（WSL2 CLI / Windows Desktop）の構成と、SSOTへの集約状況。

## 構成図

```
┌─────────────────────────────────────────────────┐
│                  SSOT (共通知識ベース)              │
│         /home/yn441611/vaults/SSOT/              │
│         GitHub: fukukei23/obsidian-ssot          │
│                                                   │
│  00_SYSTEM/shared-rules/                         │
│  ├── rules.md          ← 禁止操作・Tier1・確認必須   │
│  ├── llm-routing.md    ← LLM振り分け・バッジ表示    │
│  ├── session-log-format.md ← ログフォーマット       │
│  ├── locations.md      ← パス情報                  │
│  └── ai-setup/         ← AI別セットアップ           │
│                                                   │
│  01_DECISIONS/          ← 意思決定記録              │
│  10_DAILY/              ← セッションログ             │
│  projects/              ← プロジェクト別情報         │
│  99_ARCHIVE/            ← 旧ファイル                │
└────────────────────┬────────────────────────────┘
                     │ 参照
         ┌───────────┴───────────┐
         ▼                       ▼
┌─────────────────┐    ┌──────────────────┐
│  WSL2 CLI       │    │  Windows Desktop   │
│ ~/.claude/      │    │ C:\Users\USER\     │
│                 │    │   .claude\         │
│ CLAUDE.md (31行)│    │ CLAUDE.md (32行)   │
│ FALLBACK.md     │    │ agents/            │
│ fallback-config │    │ core/              │
│ scripts/        │    │ docs/              │
│  ├── glm-mcp    │    │ lib/               │
│  ├── minimax-mcp│    │ rules/workspace.md │
│  ├── save-log   │    │ scheduled-tasks/   │
│  └── load-log   │    │ tools/             │
│ skills/         │    │ workflows/         │
│ settings.json   │    │ settings.json      │
│ settings.local  │    │ settings.local.json│
│ .env            │    │ .claude-wrapper    │
│ scheduled_tasks │    │ .env               │
│                 │    │                    │
│ [claude-mem]    │    │ [claude-mem]       │
│ ~/.claude-mem/  │    │ C:\~\.claude-mem\  │
│ v12.1.0 GLM/Z.ai│   │ v12.1.0 Sonnet OAuth│
└─────────────────┘    └──────────────────────┘
```

## claude-mem（永続メモリプラグイン）

両環境にインストール済み。操作ログを自動記録し、次回セッション冒頭に注入。

| 項目 | WSL2 CLI | Windows Desktop |
|------|----------|-----------------|
| バージョン | v12.1.0 | v12.1.0 |
| 要約API | Z.ai経由（GLMトークン消費） | Claude OAuth（サブスク枠内） |
| データ場所 | `~/.claude-mem/` | `C:\Users\USER\.claude-mem\` |
| 推奨モデル | デフォルト（Sonnet） | Haiku（コスト最適化推奨） |
| Web Viewer | `http://localhost:37777` | `http://localhost:37777` |

3層メモリ設計の第1層（自動操作ログ）を担当。詳細は `claude-mem/README.md` 参照。

## ファイル分類

### 共通（SSOTに集約済み）
以下はCLAUDE.md/rulesから削除済み。SSOTが単一ソース。

| 内容 | SSOTの場所 |
|---|---|
| 禁止操作 | `00_SYSTEM/shared-rules/rules.md` |
| Tier1キーワード | `00_SYSTEM/shared-rules/rules.md` |
| 確認必須操作 | `00_SYSTEM/shared-rules/rules.md` |
| LLMルーティング | `00_SYSTEM/shared-rules/llm-routing.md` |
| バッジ表示ルール | `00_SYSTEM/shared-rules/llm-routing.md` |
| セッションログフォーマット | `00_SYSTEM/shared-rules/session-log-format.md` |
| 開発フロー | `00_SYSTEM/shared-rules/rules.md` |

### 環境固有（各.claude/に残す）

#### WSL2 CLI固有
| ファイル | 用途 |
|---|---|
| `FALLBACK.md` | GLM→MiniMaxフォールバック手順 |
| `fallback-config.json` | フォールバック設定 |
| `scripts/claude_fallback.py` | フォールバック実装 |
| `scripts/glm-mcp-server.py` | GLM MCPサーバー（18ツール） |
| `scripts/minimax-mcp-server.py` | MiniMax MCPサーバー（17ツール） |
| `scripts/llm-status.sh` | ステータスライン表示 |
| `scripts/save-session-log.sh` | セッション終了時ログ保存 |
| `scripts/load-obsidian-log.sh` | セッション開始時ログ読込 |
| `skills/gas-autopilot/` | GAS自動開発スキル |
| `scheduled_tasks.json` | 定期タスク定義 |
| `.env` | APIキー（秘匿） |
| `settings.json` | メイン設定 |
| `settings.local.json` | 権限設定 |

#### Windows Desktop固有
| ファイル | 用途 |
|---|---|
| `agents/code-reviewer.md` | コードレビューエージェント |
| `agents/decision-recorder.md` | 意思決定記録エージェント |
| `agents/tier1-validator.md` | Tier1検証エージェント |
| `core/` | Windows自動化スクリプト群 |
| `lib/` | JS wrapper/LLM pool管理 |
| `docs/COMPUTER-USE.md` | Windows自動操作ガイド |
| `docs/FALLBACK.md` | フォールバック手順 |
| `docs/TROUBLESHOOTING.md` | 2環境分離ドキュメント |
| `docs/decisions/` | 意思決定記録 |
| `rules/workspace.md` | ワークスペース管理 |
| `scheduled-tasks/daily-handover/` | 日次引き継ぎ自動化 |
| `scheduled-tasks/glm-cost-tracker/` | GLMコスト追跡 |
| `tools/` | ユーティリティツール |
| `.claude-wrapper.json` | LLMプール設定 |
| `create-obsidian-vault.md` | Obsidian構築ガイド |

### 削除済み（重複）
2026-04-04に重複排除で削除:

| ファイル | 理由 |
|---|---|
| WSL `rules.md` | SSOT rules.mdに統合 |
| WSL `rules/automation.md` | SSOT rules.md + CHARTERに統合 |
| WSL `rules/quality.md` | SSOT rules.mdに統合 |
| Windows `rules.md` | SSOT rules.mdに統合 |
| Windows `rules/llm-routing.md` | SSOT llm-routing.mdに統合 |
| Windows `rules/dev-workflow.md` | SSOT rules.mdに統合 |
| Windows `workflows/development-flow.md` | SSOT rules.mdに統合 |

## 削除・移動禁止ディレクトリ

`core/`, `lib/`, `tools/`, `docs/`, `agents/`, `scheduled-tasks/` は削除・移動禁止。
クリーンアップは提案のみ。自動実行しない。

## 注意事項

- 2環境は完全に独立（認証方法も異なる）
- Desktop: Anthropic OAuth（Sonnet）
- CLI: settings.json env override（GLM-5.1）
- `.env` にはAPIキーが平文 → GitHubにpushしない
- 共通ルールの変更はSSOTで行うこと

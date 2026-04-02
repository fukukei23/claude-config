# claude-config

Claude Code（デスクトップアプリ）用のグローバル設定、運用スクリプト、および自動化ツール群を管理する個人用リポジトリです。

## 環境

- **OS:** Windows 11 + WSL2 (Ubuntu)
- **Claude Code:** デスクトップアプリ（Sonnetバックエンド）
- **LLMルーティング:**
  - デフォルト: Z.AI / GLM-5.1（コスト効率重視）
  - フォールバック: MiniMax（GLM失敗時に自動切り替え）

## ディレクトリ構成

```
~/.claude/
├── CLAUDE.md              # Claude Code用グローバル設定（LLMルーティング・禁止ルール等）
├── rules.md               # Claude Code動作時の追加ルール
│
├── core/                  # ⚠️ 削除禁止：重要スクリプト群
│   ├── claude-fallback    # GLM→MiniMaxフォールバック実行ファイル
│   ├── claude_fallback.py # フォールバック処理本体（Python）
│   ├── fallback-config.json # フォールバック設定
│   ├── notify.sh/.ps1     # Windows通知
│   ├── hotkey.sh/.ps1     # ホットキー操作
│   ├── click.sh/.ps1      # マウスクリック
│   └── take-screenshot.sh/.ps1 # スクリーンショット取得
│
├── lib/                   # JavaScriptライブラリ（LLMプール管理等）
├── tools/
│   └── obsidian-sync/     # Obsidian連携ツール
│
├── docs/                  # ドキュメント
│   ├── FALLBACK.md        # フォールバック運用手順
│   ├── TROUBLESHOOTING.md
│   └── COMPUTER-USE.md
│
├── agents/                # Claude Codeエージェント定義
├── scheduled-tasks/       # スケジュールタスク（定期自動実行）
│   ├── daily-handover/    # 日次引き継ぎ
│   └── glm-cost-tracker/  # GLM APIコスト試算・Notion記録
│
└── plugins/               # Claude Codeプラグイン
```

## 各ディレクトリの役割

| ディレクトリ | 役割 |
|------------|------|
| `core/` | フォールバックスクリプトやWindows操作スクリプト等、システムの中核。**削除禁止** |
| `lib/` | LLMプール管理などの汎用JSライブラリ |
| `tools/` | Obsidian連携など特定アプリ向けの補助ツール群 |
| `docs/` | 運用マニュアル・トラブルシューティング |
| `agents/` | Claude Codeエージェント定義ファイル |
| `scheduled-tasks/` | 日次レポート・コスト管理など定期自動実行タスク |
| `plugins/` | Claude Code拡張プラグイン |

## 2環境構成（重要）

このリポジトリは **Windows Desktop側の設定** を管理しています。
WSL2側（krokod）は独立した設定を持ち、2環境は完全に独立して動作します。

| 項目 | Windows Desktop（本リポジトリ） | WSL2 CLI（krokod） |
|------|-------------------------------|-------------------|
| 設定フォルダ | `C:\Users\USER\.claude\` | `/home/yn441611/.claude/` |
| CLAUDE.md | Desktop Edition | CLI Edition |
| settings.json | プラグイン・UI設定のみ | GLM/MCP/hooks/権限の本体 |
| バックエンドLLM | OAuth Sonnet（Pro） | GLM-5.1（Z.AI） |
| MCPサーバー | Desktopアプリのコネクタ経由 | settings.jsonで直接定義 |
| hooks | なし | SessionStart/Stop あり |

**注意事項:**
- OAuthが存在する限り、Windows Desktop側のenv設定は無効（OAuthが必ず勝つ）
- 2つの設定ファイルは共有していない。片方を変更しても他方に影響しない
- WSL2側の設定は [krokod-setup](https://github.com/fukukei23/krokod-setup) を参照

# Claude Code 完全ガイド — 早見表 + 機能解説

> Claude Code CLI / Desktop App / IDE拡張の全機能を体系的に解説（2026年5月版）

---

## Claude Code とは

Anthropic が提供する AI コーディングアシスタント。3つの形態で利用可能。

| 形態 | 説明 | 使い方 |
|---|---|---|
| **CLI** | ターミナル上で動作。最も高機能 | `claude` コマンドで起動 |
| **Desktop App** | Windows/Mac用デスクトップアプリ | スタンドアロンで起動 |
| **IDE拡張** | VS Code・JetBrains用プラグイン | IDE内パネルで操作 |

---

## 1. ビルトインコマンド

`/` で始まるCLI組み込みコマンド。

### セッション管理

| コマンド | 説明 |
|---|---|
| `/clear` | 会話履歴を完全リセット（システムプロンプト・MCP・メモリは残る） |
| `/compact` | 古い会話を要約して圧縮（手動実行版） |
| `/reset` | セッションを初期状態に戻す |
| `/exit` | Claude Codeを終了 |

### 情報確認

| コマンド | 説明 |
|---|---|
| `/context` | コンテキスト使用量の内訳を表示（システム・MCP・メモリ・メッセージ別） |
| `/help` | ヘルプを表示 |
| `/model` | 現在のモデルを表示・切替（Opus/Sonnet/Haiku） |
| `/cost` | セッションのコスト概算を表示 |

### 設定

| コマンド | 説明 |
|---|---|
| `/config` | 設定メニューを開く（モデル・テーマ・権限等） |
| `/permissions` | 権限設定を管理（allow/deny/確認） |
| `/mcp` | MCPサーバーの状態を表示 |

### 機能

| コマンド | 説明 |
|---|---|
| `/fast` | 高速モード切替（Opus高速出力、モデル変更なし） |
| `/review` | コードレビューを実行 |
| `/init` | プロジェクトにCLAUDE.mdを自動生成 |
| `/memory` | メモリを管理（確認・追加・削除） |
| `/agents` | カスタムエージェントを管理 |
| `/skills` | スキル一覧を表示 |

---

## 2. コマンド vs スキル vs MCP

| 種類 | 例 | 来源 | 実装 |
|---|---|---|---|
| ビルトインコマンド | `/clear`, `/context` | Claude Code本体 | プログラム的 |
| スキル | `/brainstorming`, `/code-review` | プラグイン or 自作 | プロンプト（Markdown） |
| MCPツール | `brave_web_search`, `browser_click` | MCPサーバー | 外部API呼び出し |

---

## 3. スキルシステム

スキルは **プロンプトテンプレートのライブラリ**。`/コマンド名` で呼び出すと、対応する指示書が読み込まれる。

### 3つの来源

| 来源 | 説明 | 例 |
|---|---|---|
| **ビルトイン** | Claude Code本体に内蔵 | `init`, `review`, `simplify`, `loop` |
| **プラグイン** | プラグインインストールで追加 | `brainstorming`, `code-review`, `feature-dev` |
| **カスタム** | ユーザーが自作 | `skill-creator`で作成 |

### 代表的なプラグイン

| プラグイン | 主なスキル | 用途 |
|---|---|---|
| **superpowers** | `brainstorming`, `writing-plans`, `executing-plans`, `systematic-debugging`, `test-driven-development`, `verification-before-completion` | 開発ワークフロー |
| **pr-review-toolkit** | `review-pr` | PR包括レビュー |
| **code-review** | `code-review` | コードレビュー |
| **feature-dev** | `feature-dev` | 機能開発ガイド |

### 代表的なビルトインスキル

| スキル | 用途 |
|---|---|
| `claude-api` | Anthropic SDK関連作業 |
| `update-config` | settings.jsonの変更（権限・環境変数・フック） |
| `simplify` | コード簡素化 |
| `loop` | 定期実行タスクの設定 |
| `security-review` | セキュリティレビュー |
| `fewer-permission-prompts` | 権限プロンプト削減 |

---

## 4. MCPサーバー

**MCP（Model Context Protocol）** で外部ツールをClaude Codeから利用する。

### 代表的なMCPサーバー

| サーバー | ツール数 | 用途 |
|---|---|---|
| **github** | 41 | PR・Issue・ファイル・コード検索・リポジトリ操作 |
| **playwright** | 25 | ブラウザ自動操作（ナビ・クリック・スクショ・フォーム） |
| **brave-search** | 6 | Web検索（画像・動画・ニュース・ローカル・要約） |
| **context7** | 2 | ライブラリ公式ドキュメント検索 |
| **discord** | 5 | Discord連携（メッセージ送受信・添付・リアクション） |
| **mermaid** | 4 | 図表生成（フローチャート・シーケンス図等） |

### 管理

```bash
claude mcp add <サーバー名> -- <コマンド>    # 追加
claude mcp remove <サーバー名>               # 削除
claude mcp list                              # 一覧
```

**注意**: 各MCPツールはコンテキストを消費する。不要なサーバーは削除してトークンを節約。

---

## 5. フック（Hooks）

特定のイベント発生時に自動実行されるシェルスクリプト。

| イベント | タイミング | 代表用途 |
|---|---|---|
| `SessionStart` | セッション開始時 | 環境変数読み込み・初期化 |
| `PreToolUse` | ツール実行前 | セキュリティチェック・ブロック |
| `PostToolUse` | ツール実行後 | ログ記録・後処理 |
| `SessionEnd` | セッション終了時 | クリーンアップ・記録保存 |

### 設定例（settings.json）

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "python3 check-safety.py" }]
      }
    ]
  }
}
```

- `matcher` でツール名をフィルタ（空文字 = 全ツール）
- スクリプトがエラーを返すとツール実行が**ブロック**される

---

## 6. メモリシステム

セッションを超えて記憶を保持する仕組み。

| 種類 | 場所 | 自動保存 | スコープ |
|---|---|---|---|
| **Auto Memory** | `~/.claude/projects/<path>/memory/` | Yes | プロジェクト単位 |
| **User Memory** | `~/.claude/CLAUDE.md` | 手動 | 全プロジェクト共通 |
| **Project Memory** | `<repo>/CLAUDE.md` | 手動 | プロジェクト固有 |
| **MEMORY.md** | `memory/MEMORY.md` | 自動（インデックス） | プロジェクト単位 |

### Auto Memoryの4タイプ

| タイプ | 記録内容 |
|---|---|
| `user` | ユーザーの役割・目標・知識レベル |
| `feedback` | 「こうして」「これはやめて」等の指導 |
| `project` | プロジェクトの状況・決定事項 |
| `reference` | 外部システムへのポインタ |

---

## 7. エージェント（サブエージェント）

Agent ツールで別のAIインスタンスを起動し、独立したコンテキストでタスクを実行。

### 実行モード

| モード | 説明 | 使いどころ |
|---|---|---|
| フォアグラウンド | 結果を待つ | 調査・分析（結果が必要） |
| バックグラウンド | 結果を待たない | 独立した並列作業 |
| Worktree分離 | 別worktreeで作業 | コード変更の隔離 |

### 代表的な特殊エージェント

| エージェント | 用途 |
|---|---|
| `pr-review-toolkit:code-reviewer` | スタイル・ベストプラクティス確認 |
| `pr-review-toolkit:silent-failure-hunter` | エラー処理の穴発見 |
| `feature-dev:code-architect` | 機能設計のブループリント作成 |
| `feature-dev:code-explorer` | コードベースの深い分析 |

---

## 8. 設定ファイル

### CLAUDE.md（3層構造）

| 層 | 場所 | スコープ |
|---|---|---|
| Layer 1（グローバル） | `~/.claude/CLAUDE.md` | 全プロジェクト共通 |
| Layer 2（プロジェクト） | `<repo>/CLAUDE.md` | プロジェクト固有 |
| Layer 3（ディレクトリ） | `<repo>/<dir>/CLAUDE.md` | ディレクトリ固有 |

### settings.json

| 設定項目 | 説明 |
|---|---|
| `permissions` | ツール実行の許可・拒否ルール |
| `hooks` | フック定義 |
| `mcpServers` | MCPサーバー定義 |
| `env` | 環境変数（APIキー等は直書き禁止） |

**注意**: `~/.claude.json` と `~/.claude/settings.json` の両方が存在し、マージされる（2ファイル問題）。削除時は両方から削除すること。

---

## 9. その他の機能

| 機能 | 説明 |
|---|---|
| **Git Worktree** | メインブランチを汚さずに独立した作業環境を作成 |
| **IDE連携** | VS Code・JetBrains拡張でネイティブdiff・サイドバー操作 |
| **リモートモード** | ヘッドレス実行（CI/CDパイプラインで利用可能） |
| **Plan Mode** | コードを書かずに計画だけを立てるモード（承認後に実装） |
| **自動コンパクション** | コンテキスト上限時に古い会話を自動要約・圧縮 |

---

## 10. 用語早見

| 用語 | 説明 |
|---|---|
| **コンテキスト** | 一度に処理できる情報の総量（最大200kトークン） |
| **トークン** | テキストの最小単位（日本語1字 ≒ 1〜2トークン） |
| **オートコンパクション** | コンテキスト上限時の自動要約 |
| **MCP** | 外部ツール統合プロトコル |
| **スキル** | プロンプトテンプレートのライブラリ |
| **フック** | イベント駆動の自動実行スクリプト |
| **エージェント** | 独立コンテキストで動作するサブAIインスタンス |
| **CLAUDE.md** | Claude Codeへの指示書（3層構造） |
| **Worktree** | Git機能による独立作業環境 |

---

## 公式リンク

- [Claude Code 公式ドキュメント](https://docs.anthropic.com/en/docs/claude-code)
- [Claude Code GitHub](https://github.com/anthropics/claude-code)
- [MCP ドキュメント](https://modelcontextprotocol.io/)
- [Anthropic API](https://docs.anthropic.com/en/api)

---

> Based on [obsidian-ssot/00_SYSTEM/claude-code-guide/](https://github.com/fukukei23/obsidian-ssot)（非公開完全版）

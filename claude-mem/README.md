# claude-mem 設定

Claude Code用の永続メモリプラグイン [claude-mem](https://github.com/thedotmack/claude-mem) の設定ファイルです。

## 概要

セッションを跨いだ自動記憶機能をClaude Codeに追加します。

- **セッション操作を自動記録** → SQLite + ChromaベクトルDBに保存
- **次回セッション冒頭に自動注入** → 前回の作業文脈を即座に復元
- **追加APIコストゼロ** → CLI認証でClaude Codeサブスク課金のみ

## インストール

```bash
# 1. Bun をインストール（未インストールの場合）
npm install -g bun

# 2. claude-mem をインストール
npx claude-mem install

# もし失敗した場合（claudeがPATHにない環境）:
# known_marketplaces.json に thedotmack エントリを手動追加してから:
# claude.exe plugin install claude-mem@thedotmack

# 3. 設定ファイルを配置
cp settings.json ~/.claude-mem/settings.json

# 4. Worker 起動確認
curl http://localhost:37777/api/health
```

## 設定内容（settings.json）

| キー | 値 | 説明 |
|------|-----|------|
| `CLAUDE_MEM_PROVIDER` | `claude` | Claude Code CLIを使用 |
| `CLAUDE_MEM_CLAUDE_AUTH_METHOD` | `cli` | サブスク課金（追加費用ゼロ） |
| `CLAUDE_MEM_MODEL` | `claude-haiku-4-5` | 最安モデルを使用 |
| `CLAUDE_MEM_TIER_SIMPLE_MODEL` | `haiku` | 簡単な観察はHaiku |
| `CLAUDE_MEM_TIER_SUMMARY_MODEL` | `haiku` | サマリーもHaiku |
| `CLAUDE_MEM_CHROMA_ENABLED` | `true` | ベクトル検索を有効化 |
| `CLAUDE_MEM_WORKER_PORT` | `37777` | Webビューアーポート |

## 既存システムとの役割分担

| システム | 担当 |
|---------|------|
| **claude-mem**（本設定） | 操作ログ層 — 何をしたか（自動） |
| **Auto Memory** | 判断・設定層 — どう扱うか（半自動） |
| **SSOT / Obsidian** | 知識・決定層 — なぜそうしたか（手動） |

## Webビューアー

インストール後は http://localhost:37777 でリアルタイム確認できます。

## 注意事項

- GLM APIへの直接接続は非対応（プロバイダー未実装）
- `cli`認証はClaude Code（Max等）サブスク加入が前提
- uv は Claude Code バンドル版を流用可能:
  `C:\Users\USER\AppData\Roaming\Claude\uv-runtime\uv-0.9.7-win32-x64\`

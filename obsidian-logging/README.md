# Claude Code → Obsidian 自動ログ

Claude Codeでの作業をObsidianに自動保存する仕組み。

## 機能

- セッション終了時に自動でタイムスタンプ追加
- 日次/プロジェクト/セッション単位でログ管理
- Obsidianで見やすいMarkdown形式

## セットアップ

### 1. Obsidian vault内にディレクトリ作成

```bash
# Obsidian vaultのパスに合わせて変更
OBSIDIAN_PATH="$HOME/your-obsidian-vault/ClaudeLog"

mkdir -p "$OBSIDIAN_PATH"/{daily,projects,sessions,templates}
```

### 2. テンプレートをコピー

```bash
cp -r templates/* "$OBSIDIAN_PATH/templates/"
```

### 3. スクリプトのパスを設定

```bash
# スクリプトをClaude設定ディレクトリにコピー
cp scripts/save-session-log.sh ~/.claude/scripts/
chmod +x ~/.claude/scripts/save-session-log.sh

# スクリプト内のOBSIDIAN_PATHを自分の環境に合わせて編集
```

### 4. settings.json にフック追加

`~/.claude/settings.json` に以下を追加:

```json
{
  "hooks": {
    "Stop": [
      {
        "command": "/home/YOUR_USERNAME/.claude/scripts/save-session-log.sh",
        "timeout": 5000
      }
    ]
  }
}
```

## 使い方

### 自動保存
セッション終了時に自動でタイムスタンプが追加される。

### 手動保存
```
「今日の作業をObsidianに保存して」
「このプロジェクトの進捗をログに書いて」
```

## ディレクトリ構成

```
ClaudeLog/
├── daily/           # 日次ログ (YYYY-MM-DD.md)
├── projects/        # プロジェクト別ログ
│   └── MOC.md       # プロジェクト一覧 (Map of Content)
├── sessions/        # セッション詳細
└── templates/       # テンプレート
    ├── daily.md
    ├── project.md
    └── session.md
```

## 運用のコツ

1. **日次ログ**: 毎日の作業をざっくり記録
2. **プロジェクトログ**: 重要なプロジェクトは別途ページ作成
3. **セッションログ**: 詳細な作業内容が必要な場合
4. **定期的に振り返り**: Obsidianのグラフビューで全体像を確認

## Claude Memory との違い

| 項目 | Claude Memory | Obsidian Log |
|------|---------------|--------------|
| 目的 | Claudeが参照する長期記憶 | 人間が見る作業ログ |
| 保存先 | `~/.claude/projects/` | Obsidian vault |
| 自動更新 | 一部（feedback等） | フックで自動 |
| 見やすさ | 機械向け | 人間向け |

## ライセンス

MIT

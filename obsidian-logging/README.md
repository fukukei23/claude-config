# Claude Code → Obsidian 自動ログ

**Claude Codeでの作業を自動的にObsidianに記録する仕組み**

複数の場所・プロジェクトでClaude Codeを使っていて、「あれ、どこまでやったっけ？」とならないように、作業ログを自動保存します。

## 特徴

- ✅ **セッション開始時に前回ログ表示** - SessionStartフックで自動実行
- ✅ **セッション終了時に自動保存** - Stopフックで自動実行
- ✅ **日次/プロジェクト/セッション単位で整理** - あとで見返しやすい
- ✅ **Obsidianで即座に確認** - グラフビュー、検索、タグ活用
- ✅ **ハイブリッド運用** - 自動 + 手動のベストプラクティス

## クイックスタート

### 1. ディレクトリ作成

```bash
# Obsidian vault内にClaudeLogディレクトリを作成
OBSIDIAN_PATH="$HOME/your-obsidian-vault/ClaudeLog"
mkdir -p "$OBSIDIAN_PATH"/{daily,projects,sessions,templates}
```

### 2. テンプレート配置

```bash
# テンプレートをコピー
cp templates/*.md "$OBSIDIAN_PATH/templates/"
```

### 3. フックスクリプト設定

```bash
# スクリプトをClaude設定ディレクトリに配置
mkdir -p ~/.claude/scripts
cp scripts/save-session-log.sh scripts/load-obsidian-log.sh ~/.claude/scripts/
chmod +x ~/.claude/scripts/*.sh

# スクリプト内の OBSIDIAN_PATH を自分の環境に変更
sed -i "s|/home/yn441611/openclaw-workspace/obsidian|$HOME/your-obsidian-vault|g" ~/.claude/scripts/*.sh
```

### 4. settings.json にフック追加

`~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "command": "/home/YOUR_USERNAME/.claude/scripts/load-obsidian-log.sh",
        "timeout": 5000
      }
    ],
    "Stop": [
      {
        "command": "/home/YOUR_USERNAME/.claude/scripts/save-session-log.sh",
        "timeout": 5000
      }
    ]
  }
}
```

完了！次回のセッション終了時から自動でログが保存されます。

## 使い方

### 自動（セッション終了時）

セッション終了時にタイムスタンプが自動追加されます。

### 手動（任意のタイミング）

以下のトリガーワードで即座に保存：

```
「記憶しといて」
「記録しといて」
「覚えといて」
「保存しといて」
「ログに書いといて」
「メモしといて」
「今日の作業をObsidianに保存して」
```

Claudeがこれらの言葉を検出したら、その時点での作業内容をObsidianに保存します。

## ディレクトリ構成

```
ClaudeLog/
├── daily/              # 日次ログ
│   ├── 2026-03-27.md
│   └── 2026-03-28.md
├── projects/           # プロジェクト別
│   ├── MOC.md          # プロジェクト一覧
│   ├── NexusCore.md
│   └── openclaw.md
├── sessions/           # セッション詳細
│   └── 2026-03-27-setup-logging.md
└── templates/          # テンプレート
    ├── daily.md
    ├── project.md
    └── session.md
```

## ログの例

### 日次ログ (daily/2026-03-27.md)

```markdown
# 2026-03-27 Claude作業ログ

## 今日やったこと
- Claude Codeの長期記憶システムを構築
- Obsidian自動ログの仕組みをセットアップ

## 完了したタスク
- [x] ClaudeLogディレクトリ構造作成
- [x] Stopフック設定

## 進行中のタスク
- [ ] 他プロジェクトへの展開

## 次回やること
- 定期的にセッションサマリーを保存

---
セッション終了: 15:45
```

## 運用のコツ

| タイミング | やること |
|------------|----------|
| セッション開始時 | 前回のログを確認 |
| 作業中 | 重要な判断は「保存して」で記録 |
| セッション終了時 | 自動でタイムスタンプ追加 |
| 週次 | 週レビューでMOC更新 |

## Claude Memory との関係

| | Claude Memory | Obsidian Log |
|---|---------------|--------------|
| **目的** | Claudeが参照 | 人間が確認 |
| **保存先** | `~/.claude/projects/` | Obsidian vault |
| **内容** | ユーザー属性、フィードバック | 作業履歴、進捗 |
| **自動更新** | 一部 | フックで自動 |

**両方使うのがベストプラクティス**

## トラブルシューティング

### ログが保存されない

1. スクリプトに実行権限があるか確認
   ```bash
   ls -la ~/.claude/scripts/save-session-log.sh
   ```
2. settings.jsonのパスが正しいか確認
3. OBSIDIAN_PATHが正しいか確認

### Obsidianで表示されない

- Obsidianを再読み込み（Ctrl+R）
- ファイルが実際に作成されているか確認

## カスタマイズ

### テンプレート編集

`templates/` 内のMarkdownファイルを自由にカスタマイズできます。

### 保存タイミング変更

`PreToolUse` フックを使うことで、ツール実行前にログ保存も可能です。

## ライセンス

MIT

---

**Contributing**: 改善案はIssue/PRで歓迎します

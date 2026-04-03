# Claude Code 用設定テンプレート

## 配置場所

| 稡境別 | パス |
|------|------|
| Windows Desktop | `C:\Users\USER\.claude\CLAUDE.md` |
| WSL2 CLI | `/home/yn441611/.claude/CLAUDE.md` |

## CLAUDE.md に必須含める内容

```markdown
# [AI名] - [環境名]

## 基本原則
- 常に日本語で回答
- 環境: [環境情報]

- クイリアウスト先: [Claude Code固有設定へのポインタ]

## 共通ルール
<!-- rules.md をコピペして埋め込む -->
- 籿止操作（厳格): rm -rf *, git push --force, DROP/DELETE *
- 禁止ディレクトリ: core/, lib/, tools/, docs/, agents/, scheduled-tasks/
- 確認必須: rm, git push, Tier1タスク, 本番環境操作

- Tier1キーワード: 決済, 課金, パスワード, OAuth, JWT, データ削除, 本番デプロイ, 暗号化, XSS, CSRF

## LLMルーティング
- デフォルト: GLM-5.1
- フォールバック: MiniMax
- Sonnet: 使用前に必ずユーザー許可

- バッジ: 🟡[GLM] / 🟠[MiniMax] / 🔵[Sonnet]

## セッションログ
<!-- session-log-format.md を参照 -->
- ログ場所: [Obsidianパス]

- セッション終了時に必ずログ記録
## 謽️各AI環境の情報
## 苡ュこのファイル: https://github.com/fukukei23/claude-config/blob/main/ai-setup/claude-code.md

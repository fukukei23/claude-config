# Cursor 用設定テンプレート

## 配置場所
- `.cursorrules`（プロジェクトルート）

- `.cursor/rules/`（プロジェクトルート、も可 sed Cursorが参照）

## .cursorrules に必項含める内容
```markdown
# Cursor Rules

## 基本原則
- 常に日本語で回答
- 共通ルール適用（GitHub ルール.md を参照）

## 共通ルール
<!-- https://github.com/fukukei23/claude-config/blob/main/shared-rules/ルール.md の内容をそのまま記述 -->
- 禁止操作: rm -rf *, git push --force, DROP/DELETE *
- 禁止ディレクトリ: core/, lib/, tools/, docs/, agents/, scheduled-tasks/
- 確認必須: rm, git push, Tier1タスク, 本番環境操作
- Tier1キーワード: 決済, 課金, パスワード, OAuth, JWT, データ削除, 本番デプロイ, 暗号化, XSS, CSRF

## LLMルーティング
- デフォルト: GLM-5.1
- フォールバック: MiniMax
- Sonnet: 使用前に必ずユーザー許可

## セッションログ
- フォーマット: セッションログ書式.md を参照
- 保存先: [Obsidianパス]

## 環境情報
- WSL2 Ubuntu / ホーム: /home/yn441611/
- Obsidian: /home/yn441611/openclaw-workspace/obsidian/ClaudeLog/daily/
## 耔️このファイル: https://github.com/fukukei23/claude-config/blob/main/ai-setup/cursor.md

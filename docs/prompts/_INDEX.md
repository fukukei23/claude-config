# Claude Code プロンプト集

Claude Codeで再利用可能なプロンプトテンプレート集。

## カテゴリ別一覧

### 分析系
| ファイル | 用途 | 対象 |
|----------|------|------|
| [repo-deep-analysis.md](repo-deep-analysis.md) | GitHubリポジトリの深層分析 | 任意のリポジトリ |
| [repo-value-extraction.md](repo-value-extraction.md) | リポジトリから再利用可能コンポーネントの発見・評価 | 任意のリポジトリ |

### レビュー系
（今後追加）

### 生成系
（今後追加）

## 使い方

1. 対象プロンプトのMarkdownをコピー
2. `{{REPO_URL}}` 等のプレースホルダーを実際の値に置換
3. Claude Codeのチャットに貼り付けて実行

## 追加ルール

- プロンプトは **Claude Codeのツール（Bash, Glob, Grep, Read, Agent）を活用するよう指示** すること
- 推測ではなく **実際のコードを読んだ事実のみ** を出力させること
- 構造化Markdown形式で出力させること

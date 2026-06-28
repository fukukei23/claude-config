---
name: ssot-search
description: obsidian-ssot（個人知識ベース）を横断検索するスキル。ユーザーが「SSOTから探して」「SSOT検索」「SSOTで検索」「ナレッジベースを検索」「過去の決定を探して」と言った時、または /ssot-search を呼んだ時にトリガー。
---

# スキル: SSOTから探して（SSOT検索）

## トリガーワード
- 「SSOTから探して」
- 「SSOT検索」
- 「SSOTで検索」
- 「ナレッジベースを検索」
- 「過去の決定を探して」
- `/ssot-search`

## 概要
obsidian-ssot（個人知識ベース）を横断検索するスキル。
ripgrep で全文検索し、sentence-transformers で意味的に rerank して上位5件を返す軽量 RAG。

## 使い方（ユーザーへの案内）
```
SSOTから探して: glm-rate-proxy の設定
SSOTから探して: MiniMaxのAPIエラー対処法
SSOTから探して: openclaw-stack の設計方針
```

## 実行手順（Claude Code が行うこと）

1. ユーザーのメッセージからクエリを抽出する
2. 以下のBashコマンドを実行する：

```bash
python3 ~/.claude/scripts/ssot/search.py "<クエリ>" --top 5
```

3. 出力結果をそのままユーザーに提示する
4. ヒットしたファイルの内容が必要な場合は Read ツールで該当ファイルを開いて要約する

## 補足オプション
- 件数を増やしたい場合: `--top 10`
- 特定ディレクトリに絞りたい場合: `--ssot-dir ~/projects/obsidian-ssot/01_DECISIONS`

## スクリプト場所
`~/.claude/scripts/ssot/search.py`（シンボリックリンク元: `~/projects/claude-config/scripts/ssot/search.py`）

## 依存
- `ripgrep`（`sudo apt install ripgrep`）
- `sentence-transformers`（`pip3 install sentence-transformers`）
- モデル: `all-MiniLM-L6-v2`（初回実行時に自動ダウンロード ~80MB）

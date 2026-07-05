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
- カバレッジ表示を消す（pipe用途）: `--no-coverage`
- カバレッジ3情報をJSONでstderr出力（計測/監査）: `--log-coverage`

## カバレッジ出力の読み方（False Negative 対策・spec v3）

検索結果の末尾に、探した範囲と除外された範囲を明示するカバレッジ情報が出力されます。これは「ちゃんと探せているか」の不安を構造的に除去するためのものです。

```
📊 カバレッジ: SSOT全体 2,482 .mdファイル中、ripgrep で19ファイル抽出 → 意味rerankで上位5件表示
📌 次点候補: 6位〜10位にあと5件（表示を増やすなら --top 10）
🚨 2,463ファイルはキーワード非マッチのため未確認（語彙違いの類縁判断が含まれている可能性があります）
```

- **母数・フィルタ結果・除外量**: 「N件ヒット＝全部だ」でなく「N件ヒット・でも未確認領域が残る」と気づける
- **次点候補**: 「なぜN位で切れたか」への回答・`--top` 増量の判断材料
- **⚠️/🚨 未確認**: ripgrep 第1段でキーワード非マッチのファイルは**意味的に近くても絶対に出てこない**（語彙違いの類縁判断が含まれている可能性）。抽出率5%未満は 🚨 強化
- **0ヒット時**: 「母数中0ファイル抽出」とヒント表示。クエリの語彙違いを見直す合図

> 「気づける + 動ける + 計測できる」が目的。検索の再現率自体を上げるものではありません（アルゴリズム変更なし）。詳細: `docs/superpowers/specs/2026-07-05-ssot-search-coverage-design.md`

## スクリプト場所
`~/.claude/scripts/ssot/search.py`（シンボリックリンク元: `~/projects/claude-config/scripts/ssot/search.py`）

## 依存
- `ripgrep`（`sudo apt install ripgrep`）
- `sentence-transformers`（`pip3 install sentence-transformers`）
- モデル: `all-MiniLM-L6-v2`（初回実行時に自動ダウンロード ~80MB）

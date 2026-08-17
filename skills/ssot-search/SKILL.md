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
**主経路 = v2（ベクトル意味検索・ruri-v3-130m + ChromaDB）**。日本語意味検索が効き、語彙が違ってもヒットする（2026-08-17ベンチ: 自然文39問中29問ヒット vs 旧v1は3問・Recall@5=0.744 vs 0.026）。
v1（ripgrep+rerank）は**ピンポイント字句検索**（型番・ファイル名・エラー文の正確コピー等）のサブ経路として残存。

## 使い方（ユーザーへの案内）
```
SSOTから探して: glm-rate-proxy の設定
SSOTから探して: MiniMaxのAPIエラー対処法
SSOTから探して: 過去に並行セッションの事故を防いだ判断
```

## 実行手順（Claude Code が行うこと）

1. ユーザーのメッセージからクエリを抽出する
2. **主経路（v2・意味検索）** を実行:

```bash
cd /home/yn4416/projects/ssot-search-v2 && .venv/bin/python3 cli.py "<クエリ>" --top 5
```

3. 出力結果をそのままユーザーに提示する（索引鮮度表示付き・🚨48h超なら差分更新の異常を報告）
4. ヒットしたファイルの内容が必要な場合は Read ツールで該当ファイルを開いて要約する
5. **クエリが型番・ファイル名・エラー文言の正確コピー系**（例: `ISSUE-106`・`PriceIntegrityError`）は v1 が強い:

```bash
python3 ~/.claude/scripts/ssot/search.py "<クエリ>" --top 5
```

## 経路使い分け（2026-08-17ベンチ実測に基づく）

| クエリ型 | 経路 | 理由 |
|---|---|---|
| 自然文・概念・語彙が不定（「〜を防いだ判断」等） | **v2** | 意味検索が語彙違いを吸収（R@5=0.744） |
| 型番・固有名・エラー文の正確コピー | v1（またはv2併用） | 字句一致が最短 |
| 字句+意味の両方を広く拾いたい | v2の `--mode hybrid` | RRF統合（R@10はv2と同率・順位はやや下がる実測） |

## 補足オプション（v2 cli.py）
- 件数: `--top 10`
- RRF統合: `--mode hybrid`
- JSON出力（機械処理用）: `--json`

## v1の補足オプション
- `--top 10` / `--ssot-dir <dir>` / `--no-coverage` / `--log-coverage`（カバレッジ3情報をJSONでstderr出力）

## 索引の保守（v2）
- **差分更新が*/30で自動稼働**（auto-sync連動・`~/bin/update_rag_index.sh`）
- 確認: `tail -2 ~/.local/share/ssot-search-v2/update.log`・48h更新なしがCLI表示で🚨警告
- 全再構築・モデル差替手順: `~/projects/ssot-search-v2/README.md`

## スクリプト場所
- v2: `~/projects/ssot-search-v2/cli.py`（実装repo・ローカルcommit）
- v1: `~/.claude/scripts/ssot/search.py`（シンボリックリンク元: `~/projects/claude-config/scripts/ssot/search.py`）

## 依存
- v2: repoの `.venv`（chromadb・sentence-transformers）・ruri-v3-130m モデル
- v1: `ripgrep` / `sentence-transformers` / `all-MiniLM-L6-v2`

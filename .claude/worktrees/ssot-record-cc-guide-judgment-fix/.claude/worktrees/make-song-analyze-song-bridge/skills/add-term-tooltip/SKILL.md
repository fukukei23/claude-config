---
name: add-term-tooltip
description: HTMLページの専門用語にホバー（マウスオーバー）で解説が出るツールチップを追加するスキル。python-reading-guide で使う .term/.term-popup パターンを使用。ユーザーが「ツールチップ追加して」「用語に解説つけて」「ホバー説明を」と言った時、または /add-term-tooltip を呼んだ時にトリガー。
---

# スキル: add-term-tooltip

## トリガー
- 「ツールチップ追加して」「用語に解説つけて」「ホバー説明を」と言ったとき
- HTMLページの専門用語に初見の読者向けの補足説明を追加したいとき

## 概要
HTMLページの専門用語に、ホバー（マウスオーバー）で解説が出るツールチップを追加するスキル。
python-reading-guide で使われている .term / .term-popup パターンを使う。

---

## 実装パターン

### 1. HTML マークアップ


### 2. CSS（</style> 直前に挿入）


### 3. JS（</body> 直前に挿入）


---

## 手順

1. 対象ファイル・用語を特定: grep -n 用語 ファイル
2. CSS未追加なら挿入（term-tooltip で grep して確認）
3. JS未追加なら挿入（同上）
4. 用語を .term + .term-popup パターンに置換
5. git add / commit / push

## tooltip文章ルール
- 30〜60字程度
- 「〇〇製の〜。〜できる」形式
- 専門用語を専門用語で説明しない（対象読者：非IT・初学者）

## 既存実装サイト
- ~/projects/python-reading-guide/ — 全ページに実装済み（参考実装）
- ~/projects/tech-glossary/index.html — 実装済み（PyTorch, LangChain, FastAPI, 高トラフィックAPI, 組み込みシステム）

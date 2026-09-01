---
name: story
description: 作業の物語（専門用語なし版+技術解説版ペア）を cc-stories-guide へ1話追加するスキル。新しい仕組みを作った/事故を解決した/繰り返す課題を潰した等、物語に値する作業の後や「物語書いて」「あれを物語にして」と言った時に発動。4段承認ゲート（マスク候補提示→生成→denylist再走査→全文確認）で公開品質を担保。
---

# story — 作業物語を1話追加

## 前提
- サイトリポジトリ: `~/projects/cc-stories-guide/`（source/NNN_<slug>.md → convert.py → docs/ → GitHub Pages）
- 公開チェッカー: `check_story_public.py <file> --denylist security-denylist.yaml`（0=通過/2=ヒット）
- 設計正典: obsidian-ssot `docs/superpowers/specs/2026-09-01_作業物語ガイド-design.md`

## 手順（4段ゲート・省略禁止）

### 1. 判定と記録
- 素材をセッション記録から特定・種別（新仕様/事故解決/反復解消）と成立理由1行・confidence(高/中/低)を判定
- `~/projects/cc-stories-guide/judgment-log.yaml` に1行追記（`- date: YYYY-MM-DD / type: / reason: / confidence: / episode: NNN`・yamlリスト形式を維持）
- 上限: **1日10話**（暴走止め・超過時は提案せず翌日に持ち越し）

### 2. 第1ゲート: マスク候補提示（書く前に）
- セッション記録に出た固有名詞（鍵名・ベンダー名・クライアント名・内部パス・個人情報）を表で提示し処置（マスク表記/一般化/実名）をふくけいに提案 → **承認を得てから原稿を書く**

### 3. 原稿生成
- 物語本文 合計400〜800字（`## 困ったこと`/`## どう解決したか`/`## 何が変わったか` のH2各100〜250字・専門用語なし・比喩使用）
- `<details><summary>▶ 技術的にどう作ったか</summary>` に技術解説。SSOT記録は**要約のコピー+所在情報のみ・原文URL禁止**（公開サイトからの内部到達経路遮断）
- 先頭に `<!-- published: YYYY-MM-DD / 種別: ... -->` コメント

### 4. 第2ゲート: 自動再走査
- `python3 check_story_public.py source/NNN_<slug>.md --denylist security-denylist.yaml` が **EXIT=0必須**（ヒット時はマスクして再実行）
- 加えて「ゼロ件/見つからない」等の断定をした場合は固定プロトコル再検索（`grep -rln --include={py,sh,md,ts,js,json,yaml} <語> <root>` head無し）で裏取り

### 5. 第3ゲート: 全文確認
- 原稿**全文**をふくけいに提示 → 承認で `python3 convert.py && git add <files> && git commit && git push`（ファイル指定add・`git add -A`禁止）

### 6. 公開確認
- `curl -s -o /dev/null -w "%{http_code}" https://fukukei23.github.io/cc-stories-guide/chapters/<slug>.html` が200になることを確認（反映に数分かかることがある）

## 注意
- ファイル命名: `NNN_<タイトル>.md`（NNNは次の話番号・ゼロ埋め3桁）
- 判定ログは1話ごとに必ず記録（週次で偏りレビューするため）

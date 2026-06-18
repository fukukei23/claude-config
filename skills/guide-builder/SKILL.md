---
name: guide-builder
description: >
  Markdownソース → モバイル対応GitHub Pagesガイドサイトを構築・更新するスキル。
  新規リポジトリの立ち上げ（new モード）と、既存サイトへの章追加（add モード）の2モードを持つ。
  「ガイド作って」「ガイドサイト作って」「ガイド立ち上げて」「章追加して」「教科書作って」「教科書を書いて」「/guide-builder」でトリガー。
  GitHub Pagesでガイドを公開したい、convert.pyでMarkdownをHTMLに変換したい時に使う。
user-invocable: true
---

# guide-builder — ガイドサイト構築・章追加スキル

## トリガーワード

**新規作成系（どれでもOK）:**
- 「ガイド作って」「ガイドサイト作って」「ガイド立ち上げて」
- 「ガイドサイトを作って」「新しいガイドを立ち上げて」「ガイドリポジトリを作りたい」
- 「○○のガイドを作りたい」「○○ガイドサイトを作って」
- 「教科書作って」「教科書を書いて」「○○の教科書を作りたい」「○○教科書を作って」
- 「GitHub Pagesでガイドを公開したい」

**章追加系（どれでもOK）:**
- 「章追加して」「章を追加して」「新しい章を作って」「ガイドに章を足して」
- 「○○についての章を追加して」「○○章を追加して」

**コマンド:**
- `/guide-builder` — モード自動判定
- `/guide-builder new` — 新規モード強制
- `/guide-builder add` — 章追加モード強制

---

## アーキテクチャ概要

このスキルが扱うガイドサイトの構造:

```
<repo>/
├── source/          ← Markdownソース（1ファイル = 1章）
├── docs/            ← GitHub Pages公開ディレクトリ
│   ├── index.html   ← トップページ（自動生成）
│   ├── chapters/    ← 章ページ（自動生成）
│   └── assets/
│       ├── style.css
│       └── script.js
├── convert.py       ← ビルドスクリプト
├── test_convert.py  ← テストスイート
└── VERSION          ← ビルド番号（自動インクリメント）
```

**参照リポジトリ（テンプレート）:**
- `~/projects/claude-code-guide/` — Claude Codeガイド（先行実装）
- `~/projects/ssot-guide/` — SSOTガイド（2番目の実装）

---

## STEP 0: モード判定

ユーザーの発言から自動判定する:

| 状況 | モード |
|---|---|
| 既存リポジトリが見当たらない / 「新規」「立ち上げ」 | **new** |
| 既存リポジトリがある / 「章を追加」「追記」 | **add** |

不明な場合はユーザーに確認:
```
どちらのモードで進めますか？
A) new — 新しいガイドサイトを1から作る
B) add — 既存のガイドに章を追加する
```

---

## ─── NEW モード: 新規ガイドサイト立ち上げ ───

### STEP N1: 情報収集

以下をユーザーに確認する（不足分のみ、1項目ずつ）:

- **リポジトリ名**: 例 `ssot-guide`、`python-guide`
- **サイトタイトル**: 例 `SSOT 知識管理ガイド`
- **サブタイトル（ヒーロー）**: 例 `AIと人間が協働するための設計・運用ガイド`
- **アクセントカラー**: デフォルト `#5b4cf5`（紫）でよいか
- **章一覧（仮）**: タイトルとアイコンのリスト（後で変更可）
- **GitHubユーザー名**: 例 `fukukei23`

### STEP N2: GitHubリポジトリ作成

```bash
cd ~/projects
gh repo create <repo-name> --public --description "<サイトタイトル>"
git clone https://github.com/<username>/<repo-name>.git
cd <repo-name>
```

### STEP N3: ディレクトリ構造作成

```bash
mkdir -p source docs/chapters docs/assets
```

### STEP N4: テンプレートファイルをコピー・カスタマイズ

**convert.py のコピー元:** `~/projects/ssot-guide/convert.py`

以下の箇所をカスタマイズ:
```python
# CHAPTER_MAP を新サイトの章構成に書き換え
CHAPTER_MAP = {
    "00_概要.md": {"slug": "00-overview", "title": "概要", "icon": "📖", "desc": "..."},
    # ... 各章を追加
}

# テンプレート内のサイト名・URL・説明を書き換え
# 検索: "ssot-guide" → 新リポジトリ名
# 検索: "SSOT 知識管理ガイド" → 新サイトタイトル
# 検索: "fukukei23/ssot-guide" → "fukukei23/<repo-name>"
```

**style.css のコピー元:** `~/projects/ssot-guide/docs/assets/style.css`

アクセントカラーが異なる場合は `:root` の `--accent` 等を変更:
```css
:root {
    --accent: <新しいカラー>;
    --grad-1: <グラデ1>;
    --grad-2: <グラデ2>;
}
```

**script.js のコピー元:** `~/projects/ssot-guide/docs/assets/script.js`
→ そのままコピー（カスタマイズ不要）

### STEP N5: VERSIONファイル作成

```bash
echo "1.0" > VERSION
```

### STEP N6: ソースMarkdownを作成

各章のMarkdownを `source/` に作成する。最低限の構造:

```markdown
# NN <タイトル> — <サブタイトル>

> <章の一言説明>

---

## はじめに

<本文>
```

**命名規則:** `NN_タイトル.md`（NN は 00 から始まる2桁の連番）

### STEP N7: テストスイート作成

`test_convert.py` のコピー元: `~/projects/ssot-guide/test_convert.py`

以下を新サイト用に書き換え:
```python
# PERSONAL_PATTERNS は不要なら空にする
# CHAPTER_MAP のキーはそのまま（importするため変更不要）
# テスト内のスラッグ名・タイトルを新サイト用に更新
```

### STEP N8: ビルド・テスト

```bash
# テスト実行
python3 -m pytest test_convert.py -q

# ビルド
python3 convert.py
```

**全テスト通過を確認してから次へ。**

### STEP N9: GitHub Pages 設定

1. `git add -A && git commit -m "feat: 初期リリース — <サイトタイトル>（N章）"`
2. `git push origin main`
3. GitHub Web UI で Settings → Pages → Source: `main` / `docs` に設定

または CLI で:
```bash
gh api repos/<username>/<repo>/pages \
  --method POST \
  -f source='{"branch":"main","path":"/docs"}'
```

### STEP N10: 公開確認

```bash
# 数分後にアクセス可能になる
# URL: https://<username>.github.io/<repo-name>/
```

WebFetch で `https://<username>.github.io/<repo-name>/` を取得して確認。

### STEP N11: 完了報告

```
✅ ガイドサイト構築完了

🌐 URL: https://<username>.github.io/<repo-name>/
📁 リポジトリ: github.com/<username>/<repo-name>
📖 章数: N章
🔖 バージョン: v1.1

次のステップ:
- source/ の各章Markdownを充実させる
- python3 convert.py → git push で随時更新
```

---

## ─── ADD モード: 既存ガイドへの章追加 ───

### STEP A1: 情報収集

以下をユーザーに確認する（不足分のみ）:

- **対象リポジトリ**: 例 `~/projects/ssot-guide/`
- **章番号**: 例 `10`（既存の最大番号 + 1 を提案）
- **章タイトル**: 例 `セキュリティ設計`
- **章アイコン**: 例 `🔒`
- **章の概要（カードに表示）**: 1〜2行
- **内容の骨子**: 見出し一覧か、書きたいことのメモ

### STEP A2: 既存の章構成を確認

```bash
ls <repo>/source/
```

既存の最大章番号を確認し、次の番号を提案する。

### STEP A3: Markdownソース作成

`<repo>/source/NN_<タイトル>.md` を作成:

```markdown
# NN <タイトル> — <サブタイトル>

> <章の一言説明（blockquoteはcalloutに変換される）>

---

## <見出し1>

<本文>

## <見出し2>

<本文>
```

**Markdownのルール:**
- `> テキスト` — callout-info（青）に変換
- `> ⚠ テキスト` / `> 注意` — callout-warn（黄）に変換
- `> 重要` — callout-danger（赤）に変換
- `> 💡` / `> Tip` — callout-tip（緑）に変換
- テーブルは自動でスクロールラッパーに包まれる

### STEP A4: CHAPTER_MAPに追加（手動定義している場合）

`<repo>/convert.py` の `CHAPTER_MAP` を確認:
- **自動スキャン対応**（`build_chapter_map()` が未登録ファイルを検出）なら追加不要
- 手動定義のみの場合は追記:

```python
"NN_<タイトル>.md": {
    "slug": "NN-<slug>",
    "title": "<タイトル>",
    "icon": "<アイコン>",
    "desc": "<カード説明>",
},
```

### STEP A5: テスト実行

```bash
cd <repo>
python3 -m pytest test_convert.py -q
```

**失敗時:** エラーメッセージを確認して原因を修正してから次へ。

### STEP A6: ビルド

```bash
python3 convert.py
```

出力に `OK: NN-<slug>.html` が含まれることを確認。

### STEP A7: コミット＆プッシュ

```bash
git add source/ docs/ convert.py VERSION
git commit -m "feat: 第NN章「<タイトル>」追加 — <概要>"
git push origin main
```

### STEP A8: 公開確認（任意）

WebFetch で章ページ `https://<username>.github.io/<repo>/chapters/NN-<slug>.html` を確認。

### STEP A9: 完了報告

```
✅ 章追加完了

📄 新章: 第NN章「<タイトル>」
🔖 バージョン: v<新バージョン> · <日付>
🌐 URL: https://<username>.github.io/<repo>/chapters/NN-<slug>.html
```

---

## CSS変数ルール（重要）

**必ずCSS変数を使うこと。ハードコード色は禁止。**

```css
/* ✅ 正しい */
color: var(--text);
background: var(--bg-card);
border: 1px solid var(--border);

/* ❌ 禁止 */
color: #1e293b;
background: #ffffff;
```

**新しい変数を追加する場合は `:root` と `[data-theme="dark"]` 両方に追加必須:**

```css
:root {
    --my-new-color: #abcdef;
}
[data-theme="dark"] {
    --my-new-color: #fedcba;
}
```

callout系は必ず4色セットで定義する（片方だけ定義するとダークモードで視認不能になる）。

---

## よくある問題と対処

| 問題 | 原因 | 対処 |
|---|---|---|
| ダークモードで背景が見えない | CSS変数の `[data-theme="dark"]` 側が未定義 | 両方に定義を追加 |
| `.md` リンクが残っている | `rewrite_links()` がマッチしない | `CHAPTER_MAP` にファイル名を追加 |
| テストでバージョンが上がる | `get_build_info()` がテスト時に呼ばれた | `_build` fixture で `patch.object(convert, "get_build_info", return_value=("TEST", "2026.01.01"))` |
| 章が表示されない | `CHAPTER_MAP` 未登録 + 自動スキャン無効 | `CHAPTER_MAP` に追加するか `build_chapter_map()` を確認 |
| GitHub Pages が 404 | Pages設定が未完了 | Settings → Pages → Source を `main/docs` に設定 |

---

## チェックリスト（コミット前）

**新規サイト:**
- [ ] `python3 -m pytest test_convert.py -q` 全通過
- [ ] `python3 convert.py` 全章 OK
- [ ] `docs/index.html` にフッターのバージョン表示あり
- [ ] 全章ページにサイドバー・prev/nextナビあり
- [ ] GitHub Pages の Source が `main/docs` に設定済み
- [ ] **ガイド一覧 `~/projects/guides/index.html`** に新ガイドの `guide-card` を追記 → commit & push（51個のカードを手動羅列のHTML。既存カードをコピーして書き換え。GitHub Pagesの一覧に反映される）
- [ ] **全体マップ `~/projects/obsidian-ssot/00_SYSTEM/全体マップ_MOC.md`** の「ガイドサイト（N冊 + 外部3サイト）」の **N を +1**（カウント基準=index.html掲載数。`check-guide-count.sh` が次回SessionStartで整合チェック＝ズレると警告）

**章追加:**
- [ ] `python3 -m pytest test_convert.py -q` 全通過
- [ ] 新章HTMLに `.md` リンクが残っていない
- [ ] calloutのCSS変数がダーク/ライト両方に定義済み

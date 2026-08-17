---
name: html-guide
description: ガイドサイト（claude-code-guide / loop-engineering-guide 等、convert.py経由・手書きHTML問わず全ガイドrepo）に新しいHTMLページを追加する際のルール（CSS変数・ダーク/ライトモード対応・視認性チェック・CIテスト通過）を自動適用するスキル。ユーザーが「新しいHTMLページを作って」「インタラクティブな章を追加したい」「HTML章を追加して」と言った時、または /html-guide を呼んだ時にトリガー。
---

> ⚠️ 画像確認時は `00_SYSTEM/共通ルール/画像読込運用規約.md` 準拠（Read base64廃止・browser_snapshot/ビューポート分割/別窓1枚）

# スキル: html-guide — ガイドサイト用インタラクティブHTMLページ作成

## トリガーワード
- 「新しいHTMLページを作って」
- 「インタラクティブな章を追加したい」
- 「HTML章を追加して」
- `/html-guide`

## 概要
ガイドサイト（claude-code-guide / loop-engineering-guide 等）に新しいHTMLページを追加する際のルールを自動適用するスキル。
CSS変数・ダーク/ライトモード対応・視認性チェック・CIテスト通過を保証する。

> **適用範囲**: convert.py パイプラインを持つ repo（claude-code-guide: `docs/chapters/`）と、
> 手書きHTMLの repo（loop-engineering-guide: ルート `*.html`）の**両方**に対応する。
> 各 repo の構造差は Step 2 と Step 5 で吸収する。

---

## 実行手順（Claude Code が行うこと）

### Step 1: 要件確認
ユーザーに以下を確認する:
- 章番号・タイトル・概要
- インタラクティブ要素の有無（クリック・アニメーション等）
- 特殊なレイアウト要件

### Step 2: HTMLファイル作成

以下のテンプレートをベースに作成する。**配置場所は repo により異なる**:

```
# claude-code-guide（convert.py パイプライン型）: source Markdown → 変換で生成
~/projects/claude-code-guide/docs/src/XX_タイトル.md   # source

# loop-engineering-guide（手書きHTML型）: ルートに直接HTML
~/projects/loop-engineering-guide/XX-slug.html
```

**必須チェックリスト（作成時に必ず守ること）:**

#### ✅ CSS変数ルール
```css
/* ✅ 正しい: CSS変数を使う */
color: var(--text, #1e293b);
background: var(--bg-card, #ffffff);

/* ❌ 禁止: ハードコード色 */
color: #1e293b;
background: white;
```

**使用すべきCSS変数一覧:**
| 変数 | ライトモード | ダークモード | 用途 |
|---|---|---|---|
| `--text` | `#1e293b` | `#e2e8f0` | 本文テキスト |
| `--text-secondary` | `#64748b` | `#94a3b8` | 補助テキスト・見出し小 |
| `--bg` | `#f0f4ff` | `#0c1222` | ページ背景 |
| `--bg-card` | `#ffffff` | `#162032` | カード・パネル背景 |
| `--bg-secondary` | `#e8edf5` | `#1a2744` | コード背景・サブカード |
| `--accent` | `#6366f1` | `#818cf8` | アクセントカラー |
| `--accent-bg` | `#eef2ff` | `#1e1b4b` | アクセント薄背景 |
| `--accent-dark` | `#4f46e5` | `#a5b4fc` | アクセント文字色 |
| `--border` | `#cbd5e1` | `#334155` | ボーダー |

#### ✅ CSS変数の使用前検証（重要・文字消失バグの直接防止）

**上記一覧にない変数を使う場合、必ず定義を確認してから使う。** 一覧表は「よく使う変数」の掲示にすぎず、
未定義変数（例: `--fg`, `--bg-raised`）を書いても作成時には気づけない。これがダークモードで文字が消える主原因。

```
ルール:
1. var(--xxx) を使うなら、xxx が assets/style.css の :root か [data-theme="..."] に
   定義されているか grep で確認（インライン <style> に定義する場合も可）。
2. 新しい変数が必要なら、assets/style.css の :root（ライト）と [data-theme="dark"]（ダーク）
   の【両方】に定義を追加してから使う。片方だけだとモード切替で文字が消える。
3. fallback を付ければ文字消失は起きない（var(--xxx, #fff)）が、未定義変数の使用自体は
   CI（test_convert.py / test_css.py）で fail する。基本は定義してから使う。
```

```bash
# 使おうとしている変数が定義済か確認（claude-code-guide の例）
grep -E '^\s*--fg' ~/projects/claude-code-guide/assets/style.css
# 何も出なければ未定義 → 変数名を確認 または 定義を追加
```

#### ✅ コマンドバッジのルール
```css
/* ✅ コマンドバッジ（/init のような表示）*/
.cmd-badge {
    background: var(--accent-bg, #eef2ff);
    color: var(--accent-dark, #4f46e5);
    font-family: monospace;
    font-weight: 700;
    padding: 0.25rem 0.6rem;
    border-radius: 6px;
}
/* ❌ code-bg は濃い紺色なので文字が消える */
background: var(--code-bg);  /* 禁止 */
```

#### ✅ インラインコードのルール
```css
/* ✅ インラインコード */
code {
    background: var(--bg-secondary, #e8edf5);
    color: var(--text, #1e293b);
    padding: 0.1rem 0.35rem;
    border-radius: 4px;
}
```

#### ✅ ダーク/ライト両モード対応
カスタムスタイルに `[data-theme="dark"]` セレクタが必要な場合:
```css
.my-element { background: #e8f5e9; color: #2e7d32; }
[data-theme="dark"] .my-element { background: #1b3d1e; color: #a5d6a7; }
```

#### ✅ 禁止文字列（テストで検出される）
HTMLに以下の文字列を含めない:
- `yn4416`（Linuxユーザー名）
- `fukukei`（GitHubアカウント名、公開URLを除く）
- `GLM-5.3`, `GLM-5.1`, `GLM-4.7`, `GLM-4.5-Air`（モデル名）
- `00_SYSTEM/`（SSOTの内部パス）
- `glm_ask`, `minimax_ask`（MCPツール名）

### Step 3: index.html に章を追加

```bash
# Python で安全に挿入
python3 -c "
with open('docs/index.html', 'r') as f: content = f.read()
old = '        </section>'  # 最後の </section> の直前
new = '''            <a href=\"chapters/XX-slug.html\" class=\"chapter-card\">
                <div class=\"card-icon\">🎯</div>
                <div class=\"card-number\">第XX章</div>
                <h2 class=\"card-title\">タイトル</h2>
                <p class=\"card-desc\">説明</p>
            </a>

        </section>'''
# 最後の出現のみ置換
idx = content.rfind(old)
content = content[:idx] + new + content[idx+len(old):]
with open('docs/index.html', 'w') as f: f.write(content)
print('OK')
"
```

### Step 4: 前後章のナビゲーションリンクを更新

作成したHTMLの章ナビ（`chapter-nav-bottom`）と、前の章のHTMLの「次の章→」リンクを更新する。

### Step 5: テスト実行（CIでデプロイをガード）

repo ごとのテストファイルを実行する。**両 repo とも「未定義CSS変数検出（文字消失防止）」と
「禁止文字列検出（個人情報）」をCI（static.yml）で実行し、fail するとデプロイが阻止される。**

```bash
# claude-code-guide（convert.py パイプライン型）
cd ~/projects/claude-code-guide
python3 -m pytest test_convert.py -q

# loop-engineering-guide（手書きHTML型）
cd ~/projects/loop-engineering-guide
python3 -m pytest test_css.py -q
```

**テストが未定義CSS変数で fail した場合**: 変数名が正しいか / 定義を追加すべきか見直す（Step 2「CSS変数の使用前検証」参照）。絶対にテストを無効化しない。

全テストが通ることを確認してからコミットする。

### Step 6: コミット＆プッシュ

```bash
git add -f docs/chapters/XX-slug.html docs/index.html
git commit -m "feat: 第XX章「タイトル」追加 ..."
git push origin main
```

**注意**: `docs/` は `.gitignore` に含まれているため `git add -f` が必要。

---

## よくある問題と対処

| 問題 | 原因 | 対処 |
|---|---|---|
| コマンドバッジが黒塗り | `var(--code-bg)`使用 | `var(--accent-bg)`に変更 |
| ダークモードで文字消え | `color`未指定 **or 未定義変数（`--fg`等）を使用** | `color: var(--text)`を明示 / 変数が `style.css` に定義済か確認（Step 2「使用前検証」） |
| CIテストfailure | 禁止文字列 または **未定義CSS変数(fallbackなし)** が含まれる | 上記禁止リスト / 変数定義を確認 |
| 404エラー | CIが失敗してデプロイされていない | GitHub Actionsのログを確認 |
| `git add`できない | `.gitignore`の影響 | `git add -f docs/` を使う |

---

## ファイル場所

**claude-code-guide（convert.py パイプライン型）:**
- ソースMarkdown: `~/projects/claude-code-guide/docs/src/`
- 生成HTML: `~/projects/claude-code-guide/docs/chapters/`
- インデックス: `~/projects/claude-code-guide/docs/index.html`
- スタイル変数の参照: `~/projects/claude-code-guide/assets/style.css`
- テスト: `~/projects/claude-code-guide/test_convert.py`（未定義変数検出 + 禁止文字列 + XSS/構造）

**loop-engineering-guide（手書きHTML型）:**
- HTML（手書き）: `~/projects/loop-engineering-guide/*.html`
- スタイル変数の参照: `~/projects/loop-engineering-guide/assets/style.css`
- テスト: `~/projects/loop-engineering-guide/test_css.py`（未定義変数検出）

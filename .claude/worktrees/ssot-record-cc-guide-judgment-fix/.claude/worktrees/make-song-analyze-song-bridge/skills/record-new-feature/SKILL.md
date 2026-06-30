---
name: record-new-feature
description: Claude Code新バージョンのリリースノートを調査し、SSOTとガイドに追記するスキル。SessionStart hookで新バージョンを検知した後に発動する。
---

# record-new-feature スキル

## 発動タイミング

- SessionStart hook が新バージョンを検知した後、ユーザーが「新機能記録」または「新バージョンの新機能を追記して」と指示した時
- ユーザーが明示的に指示した時のみ発動（自動発動しない）

## 前提条件

- 現在の Claude Code バージョン（`claude --version`）
- 最新バージョン（`npm show @anthropic-ai/claude-code version`）
- SSOTファイル: `~/projects/obsidian-ssot/01_DECISIONS/claude-code/` 内の最新の新機能まとめファイル
- ガイドファイル: `~/projects/guides/claude-code-whats-new/index.html`

## 実行手順

### Step 1: バージョン確認

```
CURRENT=$(claude --version | grep -oP '\d+\.\d+\.\d+' | head -1)
LATEST=$(npm show @anthropic-ai/claude-code version)
```

現在バージョンと最新が同じなら「既に最新です」と返して終了。

### Step 2: リリースノート取得

GitHub API から現在→最新の間の全バージョンのリリースノートを取得:

```
curl -sf "https://api.github.com/repos/anthropics/claude-code/releases?per_page=30"
```

### Step 3: 各機能のGLM（CLI環境）対応を評価

各新機能について以下を判定:

| GLM（CLI環境）対応 | 判定基準 |
|---|---|
| ✅ 完全対応 | Anthropic API不要で動作する機能（CLI機能、設定変更、スキル関連等） |
| ⚠️ 部分的 | 一部機能は使えるが、Anthropic API依存部分は不可 |
| ❌ 利用不可 | Anthropic API（Sonnet/Opus）が必須の機能（Dynamic Workflows等） |

### Step 4: SSOTファイルに追記

SSOT内の最新の新機能まとめファイル（`2026-MM-DD_Claude-Code新機能*.md`）の末尾（`## 関連`セクションの前）に、以下テンプレートを埋めて追記:

```markdown
## vX.X.XXX — YYYY-MM-DD

| 項目 | 内容 |
|---|---|
| **GLM（CLI環境）対応** | ✅ 完全対応 / ⚠️ 部分的 / ❌ 利用不可 |
| **メリット** | （1〜2行で） |
| **デメリット** | （1〜2行で。なければ「なし」） |
| **自分の使い道** | （この環境での具体的な使い方。なければ「当面なし」） |
| **有効化方法** | （コマンドや設定変更） |

### 機能一覧

| 機能 | 説明 |
|---|---|
| **機能名** | 簡潔な説明 |

### 詳細

（重要な機能の詳しい説明。必要に応じて）
```

### Step 5: サマリー表を更新

SSOTファイル内の「まとめ: GLM（CLI環境）ユーザーとして覚えること」テーブルに新機能の行を追加。

### Step 6: ガイドファイル更新

`~/projects/guides/claude-code-whats-new/index.html` に新しいバージョンのカード（`<div class="card">`）を既存カードの上（サマリーボックスの下）に挿入。

フォーマット:
```html
<div class="card">
  <h2>📦 v2.1.XXX — YYYY-MM-DD（機能名）</h2>
  <p><span class="badge badge-ok/warn/no">GLM対応</span> 判定理由</p>
  <h3>機能一覧</h3>
  <table>
    <tr><th>機能</th><th>説明</th></tr>
    <tr><td><code>機能名</code></td><td>説明</td></tr>
  </table>
  <h3>自分の使い道</h3>
  <div class="tip">具体的な使い方</div>
</div>
```

サマリーボックス（`summary-box`）のテーブルにも行を追加。

### Step 7: _INDEX.md 更新

`01_DECISIONS/claude-code/_INDEX.md` の新規セクションに、もし新しくファイルを作成した場合は追記。既存ファイルに追記した場合は不要。

### Step 8: 日記に記録

`10_DAILY/YYYY-MM-DD.md` にセッションログとして記録:
```
- record-new-feature スキル発動: v2.1.XXX の新機能をSSOT・ガイドに追記
  - 新機能N個（GLM対応: ✅X個 / ❌Y個）
```

## 出力フォーマット

作業完了時にユーザーへ以下を報告:

1. 追記したバージョン番号
2. 新機能数とGLM（CLI環境）対応状況のサマリー
3. 「自分の使い道」のハイライト（あれば）

## 注意事項

- GitHub APIが空の場合は「リリースノート取得失敗」としてユーザーに報告し、手動でWeb検索するよう提案
- SSOTファイルは追記のみ。既存の内容は削除・変更しない
- ガイドのHTML構造を壊さないよう注意
- コミット・pushはユーザーの指示があった場合のみ実行

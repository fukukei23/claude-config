---
name: zenn-article-pipeline
description: Zenn記事の作成から公開前チェックまでを6ステップで実行するパイプライン。ドラフト作成→セキュリティスキャン→品質チェック→Mermaid図追加→相互リンク→タグ最適化。ユーザーが「記事を書いて」「Zenn記事」「記事の品質チェック」等と言った時に起動。
disable-model-invocation: true
user-invocable: true
---

# Zenn Article Pipeline

Zenn記事をプロ品質に仕上げる6ステップパイプライン。

## 入力

ユーザーから以下のいずれかを受け取って開始:
- 記事のテーマ・タイトル
- 既存ドラフトのパス（レビューのみの場合）
- 「記事の品質チェックして」等の指示

## Step 1: ドラフト作成

### frontmatterテンプレート

```yaml
---
title: "タイトル"
emoji: "絵文字1文字"
type: "tech"
topics: ["tag1", "tag2", "tag3"]
published: false
---
```

### 作成ルール

1. **結論ファースト**: はじめにで結論を3行以内で書く
2. **コードブロックは必ず動くコード**: 疑似コードにしない
3. **見出しは3層まで**（h3まで）。h4以上は使わない
4. **1記事3000〜8000字程度**を目安
5. **「この記事はClaude Code（GLM-5.2）と一緒に書きました。」** を末尾の `---` の後に付ける
6. **専門用語は初出時に1行説明**

### ファイル配置

- パス: `<zenn-repo>/articles/<slug>.md`
- スラッグはケバブケース（例: `openclaw-24h-owl-butler-3months`）

## Step 2: セキュリティスキャン

全記事に対して以下をgrepで検査:

```bash
# 個人情報・機密情報のパターン
grep -rn "162\.43\|flopenclaw\|yn4416\|fukukei\|sk-\|MTQ\|BSA\|192\.168\." <articles-dir>/
```

### 検査項目

| パターン | 対応 |
|---------|------|
| IPアドレス（VPS等） | `XXX.XXX.XXX.XXX` にマスキング |
| 独自ドメイン | `your-xxx.example.com` に置換 |
| ユーザー名（SSH等） | `your_username` に置換 |
| APIキー（sk-等） | `sk-xxxxx` のサンプル値以外は即削除 |
| 個人GitHubユーザー名 | 公開済みリポジトリのリンクはOK、設定ファイル内の名前は要確認 |

### 修正ルール

- サンプル値（`sk-abc123...`等）はOK（実在しないため）
- 既に公開済みの情報（リポジトリURL、Zennリンク）はOK
- 修正後は再度スキャンして0件を確認

## Step 3: 品質チェック

### チェックリスト

- [ ] frontmatterの必須フィールドが全てある（title, emoji, type, topics, published）
- [ ] `type` が `tech` または `idea` になっている
- [ ] topicsが2〜5個
- [ ] 見出し構造が論理的（h1→h2→h3の順）
- [ ] コードブロックに言語指定がある（```python 等）
- [ ] リンクが相対パスまたは正しい絶対URL
- [ ] テーブルが正しくフォーマットされている
- [ ] 誤字脱字がない
- [ ] 専門用語に初出時説明がある
- [ ] 重要な設計判断（技術選定理由等）に :::message 記法を使用している
- [ ] 外部ライブラリ依存（CryptoJS等）に環境固有の注意書きがある
- [ ] セキュリティに関わる実装（認証・認可）に制限・注意が明記されている
- [ ] 「〜が必要」「〜に注意」で終わらず、具体的な解決策が添えられている

### 複数記事の一括チェック

4エージェント並列で高速処理:
- Agent 1: Sランク記事
- Agent 2: Aランク記事
- Agent 3: Bランク記事
- Agent 4: Cランク記事

## Step 4: Mermaid図追加

### 図の選び方

詳しくは `mermaid-guide.md` を参照。

| 状況 | 図の種類 | 例 |
|------|---------|-----|
| アーキテクチャ・構成 | `flowchart LR` または `flowchart TD` | Internet→Caddy→Gateway→LLM |
| 処理フロー・判断 | `flowchart TD` | リクエスト→判定→分岐 |
| 時系列のやり取り | `sequenceDiagram` | API呼び出し→応答→フォールバック |
| 状態遷移 | `stateDiagram-v2` | pending→in_progress→completed |
| 分類・グループ分け | `flowchart TD` with subgraph | カテゴリ分類 |

### 追加ルール

1. Zennは `` ```mermaid `` ブロックに対応
2. 日本語ラベルを使用
3. ノード数は5〜12個程度（多すぎると見にくい）
4. 既存のASCII図がある場合はMermaid版を追加（ASCIIは残してもOK）
5. テーブルや箇条書きで十分な箇所には無理に入れない

## Step 5: 相互リンク

### リンク追加のルール

1. 各記事の末尾（`---` の直前）に `## 関連記事` セクションを追加
2. リンク形式: `- [タイトル](./slug) — 一言説明`
3. 同シリーズの記事は完全相互リンク（全ての記事が他の記事にリンク）
4. 各記事に2〜5本のリンク
5. `---` の後の「この記事はClaude Code...」の直前に配置

### シリーズ判定基準

| シリーズ | 判定条件 |
|---------|---------|
| 同一ツール | 同じツール名（openclaw, claude, mcp等）を含む |
| 同一技術スタック | 同じ言語・フレームワーク（flask, playwright等）を含む |
| 同一テーマ | 同じトピック（security, testing, cost等）を含む |

## Step 6: タグ最適化

### Zenn人気タグ（検索流入が多い）

詳しくは `popular-tags.md` を参照。

### 最適化ルール

1. topicsは3〜5個（Zenn最大5個）
2. 人気タグを優先（`claude` > `claudecode`, `linux` > `vps`）
3. 固有名詞は維持（`openclaw`, `mcp`, `obsidian`, `playwright`）
4. 初心者向け記事に `beginners` を追加
5. ニッチタグは広いタグに置換（`glm` → `llm`, `cost` → `automation`）

## プレビュー確認（オプション）

```bash
cd <zenn-repo>
npx zenn preview --port 8000 --host 0.0.0.0
```

- Windows/WSL2環境では `localhost` アクセスが不通の場合あり
- 代替手段: Playwright MCPブラウザで `http://127.0.0.1:8000` にアクセス
- Mermaid図のレンダリング確認

## 最後に

全ステップ完了後:
1. `git add -A && git commit && git push`
2. SSOTに記録（ssot-record スキルを起動）
3. `published: true` で公開した場合は、ユーザーに「Xの投稿文も作りますか？」と一声かけ、YESなら `x-post-draft` スキルを起動して投稿文案を生成する

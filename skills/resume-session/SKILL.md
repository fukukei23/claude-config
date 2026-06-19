---
name: resume-session
description: セッション再開時に最新5件のhandoffを読み込み文脈を復元するスキル。「おはよう」「こんにちは」「こんばんは」「再開」「restart」または /resume-session を呼んだ時にトリガーする。new-session の対（読込側）。
user-invocable: true
---

# resume-session — セッション再開・handoff読込

ユーザーが「おはよう」「こんにちは」「こんばんは」「再開」「restart」等を言った時、
または `/resume-session` を呼んだ時に、**最新5件のhandoffを読み込んで文脈を復元**する。

`new-session`（書き出し側）の対となる読込側スキル。

---

## トリガーワード

- おはよう / おはようございます
- こんにちは / こんばんは
- 再開 / レジューム / restart / リスタート
- `/resume-session`

---

## Step 1: 最新5件のhandoffを取得（Bash）🟡[GLM]

```bash
ls -t ~/projects/obsidian-ssot/00_SYSTEM/handoff/*.md 2>/dev/null | head -5
```

取得したファイルパス一覧を控える。

**並行セッション競合確認**: handoff取得と一緒に active-sessions ボードも読み込む（自分が触る共通ファイルを別セッションが触っていないか確認）。

```bash
# active-sessions ボード読込（並行セッション競合確認）
cat ~/projects/obsidian-ssot/00_SYSTEM/active-sessions.md 2>/dev/null | head -40
```

**フォールバック**: 一覧が空の場合は `~/.claude/state/handoff.md`（最新1件）を代わりに使う。

---

## Step 2: 5件をReadして文脈を復元 🟡[GLM]

Readツールで各ファイルの全文を取得し、以下を把握：

- **環境**（WSL2 / LLMルーティング / プロキシ）— 重複する固定情報は1回だけ統合
- **前回セッションの完了内容**（5件から時系列で統合・新しい順）
- **次のタスク**（最重要・最新ファイルを最優先）
- **未解決問題**

---

## Step 3: 復元サマリーを出力 🟡[GLM]

以下の形式で出力する。冗長にせず「今何をすべきか」が1読で分かること。

```markdown
🟡[GLM] セッション再開 — 最新5件のhandoffを読み込みました。

## 直近の作業（新しい順）
- [HHMM] ○○（1行）
- [HHMM] ○○
- ...（3〜5行）

## 次のタスク
[具体的に何をするか。spec/詳細ファイルがあればパス明記]

## 未解決
[あれば。なければ「なし」]

どこから再開しますか？（A: ○○ / B: ○○ / C: 提案して）
```

### 出力ルール

- **最新ファイルを最優先**: 次タスク・未解決は最新handoffの記述を正とする
- **重複統合**: 環境情報等の固定項目は5件に渡って繰り返さず1回にまとめる
- **即断即決**: 最後に「どこから再開するか」の選択肢を提示し、ユーザーがすぐ動けるようにする
- **バッジ**: 冒頭と末尾に 🟡[GLM]（LLMルーティング準拠）

---

## Step 4: active-sessions ボードに自分のエントリを追加 🟡[GLM]

復元サマリーを出力した後、現在のセッションをボードに宣言する。

手順:
1. ユーザーが「どこから再開するか」を選んだ後、そのトピックでエントリを追加
2. `obsidian-ssot/00_SYSTEM/active-sessions.md` の「アクティブセッション」テーブルの**先頭行**に挿入:
   - セッション: 環境(WSL-CLI/Win)+トピック短縮名
   - 触る共通ファイル: 当該トピックで触りそうな共通ファイル（無ければ「—」）
   - 方針: 1行で（「調査」「修正方向」「削除検討」等）
   - 開始: HH:MM
   - 状態: 🟢進行
3. **即commit+push**（ラグ回避）:
   ```bash
   cd ~/projects/obsidian-ssot && git add 00_SYSTEM/active-sessions.md && git commit -m "chore: active-sessions にエントリ追加(<セッション名>)" && git push
   ```

**注意**: 開始時にボードを読み、**自分が触ろうとする共通ファイルを別セッションが既に触っている場合は、作業前にユーザーに相談**（逆方向なら特に）。

---

## 補足: スキルが呼ばれるタイミング

- セッション開始直後の最初の挨拶（「おはよう」等）
- SessionStart hook（load-handoff.sh）が自動で5件読み込むが、それに加えて明示的に再読込したい時
- hook が失敗した・文脈が足りないと感じた時のフォールバック
- 会話途中で「やっぱり前の文脈を思い出して」と言われた時

## LLM割り当て

| ステップ | LLM | 理由 |
|---|---|---|
| Step 1 (ファイル取得) | Bash直実行 | LLM不要 |
| Step 2 (Read) | Readツール | LLM不要 |
| Step 3 (復元サマリー生成) | 🟡[GLM] | テキスト生成 |
| Step 4 (ボードエントリ追加) | 🟡[GLM] | 宣言更新・即push |

## 関連

- `new-session` スキル — 書き出し側（引き継ぎ生成＋SSOT保存）
- `~/projects/obsidian-ssot/00_SYSTEM/handoff使い方.md` — 運用マニュアル
- `~/projects/claude-config/docs/resume-session-spec.md` — 本スキルの設計spec

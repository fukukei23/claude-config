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

**生きタスクの正典を取得（バックログ.md）**: 次タスクのソースは handoff の「次タスク候補」ではなく**バックログ.md 唯一**（spec 2026-06-26・コピペ連鎖で完了済みタスクが残り続けるのを防ぐ）。

```bash
# バックログ.md の未完了 [ ] 一覧（生きタスクの正典・優先度区分付き）
grep -nE '^- \[ \]' ~/projects/obsidian-ssot/00_SYSTEM/バックログ.md
# active-sessions セッション状態表の🟢行（他セッションの占有確認・開始時刻で放置判断）
grep '| 🟢 |' ~/projects/obsidian-ssot/00_SYSTEM/active-sessions.md
```

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

## 今やるべきタスク（from バックログ.md）
🟢 占有中: <active-sessions.md セッション状態表の🟢行・他セッションが占有中（着手前にsoft警告・開始時刻で放置も判断）>
🔴 P0: <バックログ.md の P0 の [ ] 一覧>
🔁 前回継続: <直近handoffの「前回占有タスク（継続可・参考）」欄・未完了のもののみ>
ℹ️ 他候補: バックログ.md 参照（P1: N件 / P2: M件）

> ⚠️ 候補は handoff ではなく**バックログ.md が正典**。handoffの「次タスク候補」は廃止済み（完了済みが混入するため）。

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

## Step 4: active-sessions ボード宣言 + タスク占有 🟡[GLM]

復元サマリーを出力した後、ユーザーが「どこから再開するか」を選んだら、
**共通ファイル競合回避** と **タスク占有** の2つを宣言する。

### 4a. 「続きやる？」確認（前回占有タスクの継続判定）

最新handoffの「前回占有タスク（継続可）」参考欄があれば:
> 「前回『<タスク名>』をやっていました。続きをやりますか？ それとも別タスクに進みますか？」

- 続ける → そのタスクを占有
- 別タスク → 占有せず（前回タスクはバックログに残置）

### 4b. セッション状態表に🟢行を追加（単一表・タスク占有）

`obsidian-ssot/00_SYSTEM/active-sessions.md` の「## セッション状態」テーブルの**先頭行**（ヘッダ直後）に挿入:
- セッション: 環境(WSL-CLI/Win)+トピック短縮名（**＝タスク名で統一・照合キー**）
- 触る共通ファイル: 当該トピックで触りそうな共通ファイル（無ければ「—」）
- 方針: 1行で（「調査」「修正方向」「削除検討」等）
- 開始: HH:MM
- 状態: 🟢

```markdown
| <環境-トピック(=タスク名)> | <触る共通ファイル> | <1行の方針> | <HH:MM> | 🟢 |
```

**重複確認（soft警告）**: 追加前に同表に状態🟢の同名セッションがあれば:
> ⚠️「<セッション名>」は <HH:MM>〜進行中です。重複着手しますか？（ユーザー判断・ブロックしない）

※ 🟢表は廃止済（2026-07-02 単一表化）。占有宣言はこの1行のみ。

### 4c. ✅行の定期GC（10件超で古い順削除）

セッション状態表の✅行が **10件超** の場合、**古い順（表の下＝時系列で古い）に削除**して10件に抑える:

```bash
# ✅行数カウント
grep -c '| ✅' ~/projects/obsidian-ssot/00_SYSTEM/active-sessions.md
```

handoff（`00_SYSTEM/handoff/`）が履歴SSOTなので✅行の削除は情報ロスなし。アーカイブファイルは作らない。

### 4d. 即commit+push（ラグ回避）

```bash
cd ~/projects/obsidian-ssot && git add 00_SYSTEM/active-sessions.md && git commit -m "chore: active-sessions に🟢行追加(<セッション名>)" && git push
```

**注意**: 開始時にボードを読み、**自分が触ろうとする共通ファイルを別セッションが既に触っている場合**、および**着手セッションが🟢行に既にある場合**は、作業前にユーザーに相談（逆方向なら特に）。

---

## 補足: スキルが呼ばれるタイミング

- セッション開始直後の最初の挨拶（「おはよう」等）
- SessionStart hook（load-handoff.sh）が自動で5件読み込むが、それに加えて明示的に再読込したい時
- hook が失敗した・文脈が足りないと感じた時のフォールバック
- 会話途中で「やっぱり前の文脈を思い出して」と言われた時

## 補足: Windows Desktop版での実行に関する注意

handoffファイルはWSL CLI版が`~/projects/...`形式のWSLパスで書くため、Windows Desktop版がこのスキルでhandoffを読み込む際、かつてはパス解決やGitHub認証で問題が起きていた（Windows DesktopとWSL2は別ホームディレクトリを持つ別OSであるため）。

2026-06-30時点でこの2点は解決済み:
- パス変換: PreToolUseフック（`path-rewrite.py`）が`~/projects/`・`~/.claude/`等を自動でUNCパスに変換 → [05_フック](../../../obsidian-ssot/00_SYSTEM/Claude-Codeガイド/05_フック.md)
- GitHub認証: HTTPS + GitHub CLI方式で`git push`が動作 → [08_設定ファイル](../../../obsidian-ssot/00_SYSTEM/Claude-Codeガイド/08_設定ファイル.md)

詳細: [01_基礎概念「Windows Desktop版とWSL2版は別のホームディレクトリ」](../../../obsidian-ssot/00_SYSTEM/Claude-Codeガイド/01_基礎概念.md)

## LLM割り当て

| ステップ | LLM | 理由 |
|---|---|---|
| Step 1 (ファイル取得) | Bash直実行 | LLM不要 |
| Step 2 (Read) | Readツール | LLM不要 |
| Step 3 (復元サマリー生成) | 🟡[GLM] | テキスト生成 |
| Step 4 (ボード宣言+タスク占有) | 🟡[GLM] | 🟢行追加(単一表)・続きやる？・✅行GC・即push |

## 関連

- `new-session` スキル — 書き出し側（引き継ぎ生成＋SSOT保存）
- `~/projects/obsidian-ssot/00_SYSTEM/handoff使い方.md` — 運用マニュアル
- `~/projects/claude-config/docs/resume-session-spec.md` — 本スキルの設計spec

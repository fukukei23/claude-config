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

**セッション開始時の初期化（ssot-recordカウンタクリア）**:
```bash
# カウンタファイル名決定（セッションID分離・未設定時フォールバック）
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-}"
if [ -n "$SESSION_ID" ]; then
  COUNTER_FILE="$HOME/.claude/state/ssot-record-session-count-${SESSION_ID}.txt"
else
  COUNTER_FILE="$HOME/.claude/state/ssot-record-session-count.txt"
fi
rm -f "$COUNTER_FILE"
```
> **不変条件**: セッションのカウンタファイルの行数は、同一セッション内のssot-record呼び出し回数と一致しなければならない。new-session（終了時）と本ステップ（開始時）の両方でクリアすることで、異常終了でnew-sessionが未実行だった場合の残存を防ぐ（二重防御）。**2026-07-06 改修**: カウンタはセッションID別ファイル（`ssot-record-session-count-${CLAUDE_CODE_SESSION_ID}.txt`）に分離し、並行セッション汚染を構造的に防止。未設定時は旧単一ファイル名にフォールバック（spec: 2026-07-06-ssot-record-counter-session-scoped.md）。

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
# 📝WIP構想メモ一覧（未spec化の構想・バックログ.md該当タスク直下・C層機械スキャン）
grep -nE '^[[:space:]]*- 📝 構想' ~/projects/obsidian-ssot/00_SYSTEM/バックログ.md
# WT4取得（自セッション識別子・spec 2026-07-09 セッション識別子改善・2026-07-30フォールバック追加）
# WT_SESSIONはWSL CLI版のみ払い出される変数。Windows Desktopアプリ版では常にunknownになるため、
# その場合はCLAUDE_CODE_SESSION_ID（両環境で必ず取得できる）にフォールバックする。
WT_SESSION="${WT_SESSION:-unknown}"; SESSION_ID="${CLAUDE_CODE_SESSION_ID:-unknown}"
EFFECTIVE_WT="$WT_SESSION"; [ "$WT_SESSION" = "unknown" ] && EFFECTIVE_WT="$SESSION_ID"
WT4=${EFFECTIVE_WT:0:4}
# 自分の🟢行（wt4でピンポイント特定・/clear跨ぎ残存行も拾う）
grep "| $WT4 |" ~/projects/obsidian-ssot/00_SYSTEM/active-sessions.md 2>/dev/null
# 他セッションの🟢行（soft警告用・自分行除外）
grep '| 🟢 |' ~/projects/obsidian-ssot/00_SYSTEM/active-sessions.md 2>/dev/null | grep -v "| $WT4 |"
# 🎯要望(Why)層の一覧（W1,W2...=動機の束・タスク選択の軸・各タスク行末の←Wx逆参照と突合）
grep -nE '^- W[0-9]' ~/projects/obsidian-ssot/00_SYSTEM/バックログ.md
# 週次リフレクション検知（Phase2・spec 2026-08-16 §5・完了週ベース）
# RFL_ / RFL_PENDING / RFL_STALE: で始まる出力を Step3 の「📝 リフレクション検知」に反映。
RFL_INDEX=~/projects/obsidian-ssot/40_CAREER/リフレクション/_INDEX.md
RFL_STOPPED=$(grep -c '^reflection_stopped: true' "$RFL_INDEX" 2>/dev/null); RFL_STOPPED=${RFL_STOPPED:-0}
if [ "$RFL_STOPPED" -ge 1 ]; then
  echo "RFL: 停止宣言済み（再開は「リフレクション再開」）"
else
  REF_DATE=$(TZ=Asia/Tokyo date -d "last sunday" +%F)
  W0=$(TZ=Asia/Tokyo date -d "$REF_DATE" +%G-W%V)
  W1=$(TZ=Asia/Tokyo date -d "$REF_DATE -7 days" +%G-W%V)
  W2=$(TZ=Asia/Tokyo date -d "$REF_DATE -14 days" +%G-W%V)
  W4=$(TZ=Asia/Tokyo date -d "$REF_DATE -28 days" +%G-W%V)
  ELAPSED=$(( ($(TZ=Asia/Tokyo date +%s) - $(TZ=Asia/Tokyo date -d "$REF_DATE" +%s)) / 86400 ))
  WD=~/projects/obsidian-ssot/40_CAREER/リフレクション/weekly
  M0=$([ -f "$WD/$W0.md" ] && echo 0 || echo 1)
  M1=$([ -f "$WD/$W1.md" ] && echo 0 || echo 1)
  M2=$([ -f "$WD/$W2.md" ] && echo 0 || echo 1)
  PENDING=$(grep -oP '^pending_top3: \K[0-9]{4}-W[0-9]{2}' "$RFL_INDEX" 2>/dev/null)
  TOP3_U=$(grep -oP '^top3_last_updated: \K[0-9]{4}-W[0-9]{2}' "$RFL_INDEX" 2>/dev/null)
  # 未承認Top3があれば最優先
  if [ -n "$PENDING" ]; then
    echo "RFL_PENDING: 📌 Top3未承認($PENDING) — 承認(y/修正/見送り)を最優先で依頼すること"
  fi
  # 鮮度⚠️（top3_last_updatedが4週前より古い）
  if [ -n "$TOP3_U" ] && [ "$TOP3_U" \< "$W4" ]; then
    echo "RFL_STALE: ⚠️ 気づきTop3が4週超未更新($TOP3_U) — Top3セクション直前に⚠️表示"
  fi
  if [ "$M0" -eq 1 ]; then
    if [ "$M1" -eq 1 ] && [ "$M2" -eq 1 ]; then
      echo "RFL_ESC3: 🚨 週次リフレクション3週超未生成(未生成: $W2 $W1 $W0) — 「今すぐ生成(古い週から1週)/運用停止を宣言/このまま」の3択を強制提示"
    elif [ "$ELAPSED" -ge 8 ]; then
      echo "RFL_ESC2: ⚠️ 週次リフレクション未生成($W0・経過${ELAPSED}日) — サマリー冒頭で再提示"
    elif [ "$ELAPSED" -ge 4 ]; then
      echo "RFL_ESC1: 週次リフレクション未生成($W0・経過${ELAPSED}日) — 再開候補の選択肢先頭に提示"
    else
      echo "RFL_OK_NEW: 週次リフレクション未生成($W0) — サマリーに1行提案"
    fi
  fi
fi
# 自己駆動ループ状態（Step 4a-2で使用・2026-08-31追加）
python3 -c "
import json
s = json.load(open('/home/yn4416/.claude/scripts/auto-dev/state.json'))
print('LOOP: active=%s mode=%s running=%s pending=%d current=%s blocked=%d completed=%d' % (
    s.get('active'), s.get('mode'), s.get('running'), len(s.get('pending', [])),
    bool(s.get('current')), len(s.get('blocked', [])), len(s.get('completed', []))))"
TODAY_TASKS="$HOME/.claude/state/today-tasks.md"
if [ -f "$TODAY_TASKS" ]; then
  GEN=$(grep -oP '^<!-- generated_at: \K[^\s>]+' "$TODAY_TASKS" | head -1)
  CNT=$(grep -cE '^[0-9]+\. \*\*' "$TODAY_TASKS")
  echo "TRIAGE: today-tasks あり（生成: ${GEN:-不明}・候補${CNT}件）"
else
  echo "TRIAGE: today-tasks なし（Daily Triage未実行・bash ~/.claude/scripts/auto-dev/daily-triage.sh で生成可）"
fi
# Claude Code changelog 日本語サマリ（Step 3 で挨拶に混ぜる・2026-09-03 追加）
CHANGELOG_JA="$HOME/projects/obsidian-ssot/00_SYSTEM/claude-code/claude-code-changelog-ja.md"
if [ -f "$CHANGELOG_JA" ]; then
  # grep パターンは frontmatter インデント揺れ許容のため緩めに（2026-09-03 multi-llm-review #2 反映）
  LAST_FETCHED=$(grep -oE 'last_fetched: *[0-9]{4}-[0-9]{2}-[0-9]{2}' "$CHANGELOG_JA" 2>/dev/null | head -1 | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}')
  # DAYS_OLD 計算:GNU date → macOS date → Python フォールバック（mac対応・2026-09-03 mini-llm-review #2 反映）
  if [ -n "$LAST_FETCHED" ]; then
    if date -d "$LAST_FETCHED" +%s >/dev/null 2>&1; then
      # GNU date (Linux)
      DAYS_OLD=$(( ($(date +%s) - $(date -d "$LAST_FETCHED" +%s)) / 86400 ))
    elif date -j -f "%Y-%m-%d" "$LAST_FETCHED" +%s >/dev/null 2>&1; then
      # macOS date (BSD)
      DAYS_OLD=$(( ($(date +%s) - $(date -j -f "%Y-%m-%d" "$LAST_FETCHED" +%s)) / 86400 ))
    else
      # Python フォールバック（確実に動く）
      DAYS_OLD=$(python3 -c "from datetime import date; print((date.today()-date.fromisoformat('$LAST_FETCHED')).days)" 2>/dev/null)
    fi
  fi
  echo "CHANGELOG_JA: あり（最終取得: ${LAST_FETCHED:-不明}・経過${DAYS_OLD:-?}日）" >&2
  # changelog-ja の begin/end マーカー間を抽出（マーカー行は除外・2026-09-03 multi-llm-review r2 #1 反映）
  # awk 範囲指定は両端を含むため flag 変数方式で BEGIN/END 行をスキップ
  CHANGELOG_SUMMARY=$(awk '
    /<!-- BEGIN: resume-summarable -->/ { flag=1; next }
    /<!-- END: resume-summarable -->/   { flag=0 }
    flag { print }
  ' "$CHANGELOG_JA" 2>/dev/null)
  if [ -z "$CHANGELOG_SUMMARY" ]; then
    echo "CHANGELOG_SUMMARY: 抽出失敗（begin/end マーカーが見つかりません・フォーマット確認推奨）" >&2
  else
    echo "CHANGELOG_SUMMARY: 抽出成功（${#CHANGELOG_SUMMARY} chars）" >&2
  fi
else
  echo "CHANGELOG_JA: なし（ファイル未作成・changelog 和訳未着手）"
fi
```

---

## Step 2: 5件をReadして文脈を復元 🟡[GLM]

Readツールで各ファイルの全文を取得し、以下を把握：

- **🎯要望(W1〜W4)**（バックログ.md先頭の🎯要望セクション・タスク選択の軸・各タスク行末の ←Wx 逆参照と突合）
- **メタ情報**（先頭 `## メタ情報` ブロック・spec 2026-07-06）— 各 handoff の `session_id` / `wt_session` / `セッション名` / `開始` / `終了` を抽出。**同じ `wt_session` = 同タブの継続作業**・**異なる `wt_session` = 別タブの並列**。メタ情報ブロック無し（旧 handoff）・`wt_session: unknown` は「メタ情報なし」グループへ（後方互換）
- **環境**（WSL2 / LLMルーティング / プロキシ）— 重複する固定情報は1回だけ統合
- **前回セッションの完了内容**（5件から時系列で統合・新しい順）
- **次のタスク**（最重要・最新ファイルを最優先）
- **未解決問題**

---

## Step 3: 復元サマリーを出力 🟡[GLM]

以下の形式で出力する。冗長にせず「今何をすべきか」が1読で分かること。

```markdown
🟡[GLM] セッション再開 — 最新5件のhandoffを読み込みました。

## 🤖 Claude Code 最新情報（changelog 日本語サマリ・2026-09-03 追加）

> Step1 の `CHANGELOG_JA:` 出力が「あり」の場合のみ表示。挨拶の最初に混ぜ、ふくけいが CC の現状を即座に把握できるようにする。
>
> **出典**: `~/projects/obsidian-ssot/00_SYSTEM/claude-code/claude-code-changelog-ja.md` の `<!-- BEGIN: resume-summarable -->` 〜 `<!-- END: resume-summarable -->` ブロック（2026-09-03 multi-llm-review #6 反映）。
> 毎回同じ場所から読み込むので、サマリが古く感じたら changelog-ja.md を更新する（更新手順は同ファイル「🔁 更新運用」セクション参照）。
>
> **古い和訳の警告（2026-09-03 multi-llm-review #5 反映）**: `DAYS_OLD` が **14 日超**の場合はサマリ表示ではなく警告に切り替える（古い和訳を『最新』として嘘をつかれるリスクを防止）。30 日超は表示スキップ推奨。

### A. 通常（DAYS_OLD ≤ 14）

```
🤖 Claude Code 直近アップデート（最終取得: <last_fetched>・経過<DAYS_OLD>日）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<Step1 で抽出した CHANGELOG_SUMMARY の中身をここに展開>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### B. 警告（14 < DAYS_OLD ≤ 30）

```
⚠️ Claude Code changelog 日本語サマリが <DAYS_OLD> 日古いです（最終取得: <last_fetched>）。
新しいバージョン情報に追随できていない可能性があります。
更新手順: ~/projects/obsidian-ssot/00_SYSTEM/claude-code/claude-code-changelog-ja.md の「🔁 更新運用」参照
または `code.claude.com/docs/en/changelog` を直接確認してください。
```

### C. 部分的スキップ（DAYS_OLD > 30・2026-09-03 multi-llm-review r2 #7 反映）

挨拶の骨格は維持・changelog 和訳部分のみ差し替え:

```
⚠️ changelog 日本語サマリが <DAYS_OLD> 日古いため、和訳表示をスキップしました。
resume の本来の挨拶（直近作業・バックログ等）は通常通り続行します。
和訳を更新: ~/projects/obsidian-ssot/00_SYSTEM/claude-code/claude-code-changelog-ja.md の「🔁 更新運用」参照
```

💡 実装メモ: 挨拶ブロックへの実際の注入は **awk -v テンプレート方式**でプレースホルダ展開（2026-09-03 multi-llm-review r2 #2 反映）:

```bash
# Step1 で抽出した CHANGELOG_SUMMARY を Step3 テンプレに展開
awk -v lf="$LAST_FETCHED" -v elapsed="$DAYS_OLD" -v cs="$CHANGELOG_SUMMARY" 'BEGIN{
  printf "🤖 Claude Code 直近アップデート（最終取得: %s・経過%s日）\n", lf, elapsed
  print "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  print cs
  print "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}'
```

※ `sed` での置換は CHANGELOG_SUMMARY 内の改行で `unterminated 's' command` になるため不適（**2026-09-03 検証で確認**）。
※ 変数名 `do` は awk 予約語なので使えない（**gawk: fatal: cannot use gawk builtin 'do' as variable name**・2026-09-03 検証で確認）→ `elapsed` 等の非予約語を使う。
※ `-v` 経由でなく、シェル変数の **直接展開**（`'"$CHANGELOG_SUMMARY"'` のシングルクォート内の式展開）も可。

💡 かみ砕くと: これが現状の CC のリビジョン。新しければ「新機能はこれだけ」、古ければ「そろそろ和訳を更新してね」の警告に切り替え。

## 直近の作業（wt_session でグループ化・spec 2026-07-06）

> 同じ `wt_session` = 同タブの継続作業 / 異なる `wt_session` = 別タブの並列。
> メタ情報なし（旧 handoff）・`wt_session: unknown` は「⬜ メタ情報なし」グループへ。

### 🟦 タブA（wt_session: <先頭8桁> / セッション名: <値>）
- [HHMM] ○○
- [HHMM] ○○（同タブ継続）

### 🟩 タブB（wt_session: <別ID> / セッション名: <別タスク>）
- [HHMM] ○○（別タブ並列）

### ⬜ メタ情報なし（旧 handoff・後方互換）
- [HHMM] ○○

※ グループが1つ（全件同タブ or 全件メタ情報なし）なら見出し分けせずフラット列出でも可

## 今やるべきタスク（from バックログ.md）
🎯 **要望(Why) — タスク選択の軸**: W1: <要望文> / W2: ... / W3: ... / W4: ...
> 各タスク行末の ←Wx で要望↔タスクを紐付け。タスク選択時は「どの要望に効くか」を優先度判断の基準に。
🟢 占有中: <active-sessions.md セッション状態表の🟢行・他セッションが占有中（着手前にsoft警告・開始時刻で放置も判断）>
🔴 P0: <バックログ.md の P0 の [ ] 一覧>
🔁 前回継続: <直近handoffの「前回占有タスク（継続可・参考）」欄・未完了のもののみ>
ℹ️ 他候補: バックログ.md 参照（P1: N件 / P2: M件）
📝 WIP構想: <直近handoffの「WIP構想一覧」欄・バックログ.md実体と突合>
📝 リフレクション検知: <Step1 の RFL_PENDING / RFL_STALE / RFL_ESC1〜3 / RFL_OK_NEW 出力に応じて表示: RFL_PENDING=最優先で承認要求・RFL_ESC3=3択強制提示・RFL_ESC2=サマリー冒頭で再提示・RFL_ESC1=選択肢先頭・RFL_OK_NEW=1行提案・出力なしゲート通過時は表示しない（alert fatigue回避）・RFL:停止宣言済みなら「リフレクション再開」選択肢のみ>
🔁 自己駆動ループ: <Step1 の LOOP/TRIAGE 出力を1行で表示（例: 「待機中（active=False）・今日のTriage候補5件」）。**active=True で稼働中の場合はサマリー冒頭に目立たせて表示**（「⚠️ 自己駆動ループ稼働中・current=<タスク名>」）・TRIAGE なしなら「Daily Triage未実行（生成可）」>

> ⚠️ 候補は handoff ではなく**バックログ.md が正典**。handoffの「次タスク候補」は廃止済み（完了済みが混入するため）。

**【C層・構想欠損検出（機械スキャン）】** Step1の 📝WIPメモ grep 結果と直近handoffの「WIP構想一覧」を突合:
- バックログに 📝WIPメモがあるが handoff に載っていない → 構造化確認「⚠️ このタスクの構想文脈が handoff に見つかりません。バックログ該当タスク直下の📝WIPメモを確認するか、詳細を教えてください」
- handoff の WIP構想がバックログに見つからない → 「⚠️ handoff 記載の構想がバックログ.md に見つかりません。記録漏れまたはタスク破棄の可能性」
- 一致 → 正常（📝WIPメモから文脈復元して継続）

> 設計根拠: 能動検知・キーワード検知は廃止（誤検知/アラート疲労・resume時は履歴なく発動しない脆さ）。機械スキャンのみ（`@rules/_shared/記録.md` 準拠）。

## 未解決
[あれば。なければ「なし」]

どこから再開しますか？（A: ○○ / B: ○○ / C: 提案して）
```

### 出力ルール

- **最新ファイルを最優先**: 次タスク・未解決は最新handoffの記述を正とする
- **重複統合**: 環境情報等の固定項目は5件に渡って繰り返さず1回にまとめる
- **即断即決**: 最後に「どこから再開するか」の選択肢を提示し、ユーザーがすぐ動けるようにする。**各候補に ←Wx を付与**（「A: ○○ ←W1 / B: ○○ ←W2」）し、どの要望に効くかを明示（形骸化防止）
- **バッジ**: 冒頭と末尾に 🟡[GLM]（LLMルーティング準拠）
- **平易な解説併記**: サマリー末尾に「💡一言でいうと」で今日何をすべきかを素人言葉で1行併記する（CLAUDE.md平易解説ルール）

---

## Step 4: active-sessions ボード宣言 + タスク占有 🟡[GLM]

復元サマリーを出力した後、ユーザーが「どこから再開するか」を選んだら、
**共通ファイル競合回避** と **タスク占有** の2つを宣言する。

### 4a. 「続きやる？」確認（前回占有タスクの継続判定）

最新handoffの「前回占有タスク（継続可）」参考欄があれば:
> 「前回『<タスク名>』をやっていました。続きをやりますか？ それとも別タスクに進みますか？」

- 続ける → そのタスクを占有
- 別タスク → 占有せず（前回タスクはバックログに残置）

### 4a-2. 自己駆動ループの起動確認（2026-08-31 追加・auto連続既定）

Step1で取得した `LOOP:` / `TRIAGE:` 出力を使い、タスク選択の流れの中で**1回だけ**確認する。
「毎朝の Daily Triage が Discord 通知だけで終わる」問題の解消導線（Triage→承認→自動実行までを朝の挨拶で完結させる）。

**表示**:
> 🔁 自己駆動ループ: 今日のTriage候補（N件）から自動実行するタスクをキューに入れられます
> （実装→**別コンテキスト検証**→次タスク自動起動・**最大3件で自動停止**）。回しますか？
> - **番号指定**（例: `1,3`）でキュー投入
> - **スキップ**（既定・何もしない）

**yes の場合の実行手順（全て必須・省略しない）**:

1. **稼働中チェック**: Step1の LOOP 出力で `running=True` または `current=True` なら**起動せず中止して報告**する
   （根拠: `approve.py` の `_init_state` は state.json を**無条件再構築**するため・稼働中の再承認は実行中タスクを破壊する）
2. **鮮度チェック**: TRIAGE の生成日が**当日**でなければ「today-tasks が古い（<日付> 生成）」と警告し、
   `bash ~/.claude/scripts/auto-dev/daily-triage.sh` の再実行を提案してから承認を取る
3. **テスト方針ドラフト（CCがドラフト・2026-08-31ふくけい決定）**: 指定番号の各タスクについて方針をドラフトして一括提示する
   （`1=テスト追加 / 2=既存テストで網羅 / 3=該当なし+理由20字以上`・ドキュメント/設定/調査系は「3=該当なし: <理由>」を提案）。ふくけいが修正可・**空白は起票不可**（F層）
4. **非対話実行**: 番号と方針を stdin で渡して起動する。（手動）タスク・repo実在なしは approve.py が自動除外する旨も伝える:
   ```bash
   printf '<番号,区切り>\n<方針1>\n<方針2>\n' | python3 ~/.claude/scripts/auto-dev/approve.py
   ```
   ⚠️ **パイプで繋がない**（`approve.py | tail` 等・2026-08-31実測でハング: setsid切り離し子がstdoutパイプを握りtailがEOF待ち・2分タイムアウト）。出力を絞りたい場合はリダイレクトで
5. **連続実行への切替（既定auto・2026-08-31ふくけい決定）**: approve.py 単体は mode=manual で**1件だけ**起動する
   （`next_issue.py` の Stop hook 連鎖は mode=auto でしか働かない・next_issue.py:121/130/193）。
   **キュー全体を自動消化するには起動直後に必ず実行**:
   ```bash
   bash ~/.claude/scripts/auto-dev/set-mode.sh auto
   ```
   ⚠️ 1件ずつ人間承認したい場合のみ mode=manual のままにする
6. **完了監視ワンショットcronの発行（必須・2026-08-31追加）**: 「終わったらまた話しかけてね」を禁止し、CCが自分で確認しに行く予約を仕掛ける。
   - **発行タイミング**: 手順5の直後（報告を出す前に発行まで完了させる）
   - **発火時刻**: 投入タスクの想定コスト目安 + 余白（S=15分後・M=30分後・L=60分後・:00/:30回避）
   - **prompt必須5要素（冪等に書く）**: ①状態確認コマンド（`state.json` の running/completed/blocked + `loop.log` 末尾 + `ps -p <run-task PID>`）②判定基準（running=False=完了 / True=待機継続）③達成時の次アクション（成果物実測→state整合確認→バックログ反映提案→ssot-record）④背景1行 ⑤正典リンク（loop.log・TASK_DIR）
   - **待機継続時**: 進捗ログ1行を確認してふくけいに簡報告→**同様のワンショットcronを再発行**（延長はmax 3回・以降はDiscord完了通知頼み）
   - **限界の明示**: 発行するcronは session-only（セッションを閉じると消える）。ふくけいに1行伝える:「本セッションを閉じると監視予約は消える（ループ完了のDiscord通知は別途飛ぶ）」
7. **停止方法の常時表示**: 報告に1行添える —
   「止める: `bash ~/.claude/scripts/auto-dev/set-mode.sh manual`（実行中タスクは完了待ち・max 3件/キュー空で自動停止）」

**安全装置（実測根拠つき・省略禁止）**:
- `approve.py` `_init_state` は pending/completed/blocked を**全て初期化** → 手順1の稼働中チェックは省略禁止
- `max_tasks_per_session: 3`（auto-loop-config.yaml）で自動停止・検証NGは blocked 停止＝無限ループ構造なし
- TDDゲート（tdd_gate）は `test_gate_repos`（NexusCore/atelier）のみ有効・他repoは run-task.sh の別コンテキスト検証のみ
- 実行先repoが他セッション🟢行と重なる場合、着手前に active-sessions.md で soft 警告（通常のタスク占有ルール準拠）

### 4b-0. stale🟢警告の確認（SessionStart hook 経由・2026-07-25 L98）

**hook**: `check-stale-sessions.sh` が SessionStart で自動発火。死亡🟢行があれば警告が出る。

- 警告は**人間が✅化するまで消えない**（自動✅化しない＝生セッション誤殺防止）
- 警告対象ID=WT4は自分行・他行の区別無く列挙される。**他タブの古い🟢はsoft警告**（ブロックしない・ユーザー判断）
- 警告理由: `heartbeat_timeout`(12h超無活動)/ `handoff_timeout`(handoff mtimeが古い・heartbeat無)/ `no_trace`(6d3f型=証跡ゼロ)/ `[長時間]`マーカー付き行は72h閾値で別判定
- 対処: `active-sessions.md` で該当行の `🟢` を `✅` に書き換え + 必要なら `new-session` で handoff 生成

**heartbeat 機構（参考）**: `track-tool-usage.sh` (PostToolUse) が毎ツール使用で `~/.claude/state/heartbeat/$WT4` を touch。stale検知の一次情報源（より詳しくは `/home/yn4416/.claude/scripts/obsidian/check-stale-sessions.sh --help`）。

### 4b. セッション状態表に🟢行を追加（単一表・タスク占有・ID=wt4）

`obsidian-ssot/00_SYSTEM/active-sessions.md` の「## セッション状態」テーブルの**先頭行**（ヘッダ直後）に挿入:
- **ID: `WT4`（WT_SESSION先頭4桁・spec 2026-07-09 セッション識別子改善）** — /clear跨ぎでも同一・handoffファイル名と統一・自分行特定の照合キー
- セッション: 環境(WSL-CLI/Win)+トピック短縮名（**＝タスク名で統一**）
- 触る共通ファイル: 当該トピックで触りそうな共通ファイル（無ければ「—」）・**実パスは `~/.claude/state/active-sessions-paths.json` に書き、🟢行には件数+「→paths.json」のみ記載（層2b・2026-08-11・フルパス直書き避ける・循環参照回避）**
- 方針: 1行で（「調査」「修正方向」「削除検討」等）
- 開始: `MM-DD HH:MM`（日付必須・GC判定と24hチェックの基準）
- 状態: 🟢

```bash
# WT4取得（Step1と同一・🟢行のID列に記載・2026-07-30フォールバック追加）
WT_SESSION="${WT_SESSION:-unknown}"; SESSION_ID="${CLAUDE_CODE_SESSION_ID:-unknown}"
EFFECTIVE_WT="$WT_SESSION"; [ "$WT_SESSION" = "unknown" ] && EFFECTIVE_WT="$SESSION_ID"
WT4=${EFFECTIVE_WT:0:4}; echo "WT4=$WT4"
```

```markdown
| <WT4> | <環境-トピック(=タスク名)> | <触る共通ファイル> | <1行の方針> | <MM-DD HH:MM> | 🟢 |
```

### 4b-2. paths.json に宣言path書込（層2b・spec §2.1・ID照合ガード §4.4）

🟢行追加後、触るファイル実パスを `~/.claude/state/active-sessions-paths.json` に書込。auto-sync（*/30 cron）がこのpathを**除外宣言**として参照し、🟢活動中ファイルの巻き込みを防ぐ（post-push監査層 `audit-auto-sync-commits.py` もこのpathで🟢宣言を把握）。

```bash
# ID照合ガード: 現セッションWT4 = 🟢行ID 確認（不一致は書込拒否・spec §4.4）
WT4=${EFFECTIVE_WT:0:4}
# paths.json に WT4 エントリ追記（v3・ヘルパー書込・rename原子性+世代backup+ID_COLLISION/DEGRADED対応）
# 既存entries保持・git pathspec互換・並列5本でも破損ゼロ検証済(revised_proposal_v3_final.md Case21)
paths-json-update.py "$WT4" "<触るファイル実パス1>" "<触るファイル実パス2>"  # ~/.claude/scripts/session/paths-json-update.py
```

⚠️ **ID照合ガード（spec §4.4）**: `$WT4` が🟢行IDと一致すること必須（不一致は paths.json 書込拒否）。**🟢行→paths.json の順で必ず両方書く**（paths.jsonだけ書いて🟢行が無いと、監査が🟢宣言を拾えず誤検出になる）。

**重複確認（soft警告）**: 追加前に同表に状態🟢の同名セッションがあれば:
> ⚠️「<セッション名>」は <HH:MM>〜進行中です。重複着手しますか？（ユーザー判断・ブロックしない）

※ 🟢表は廃止済（2026-07-02 単一表化）。占有宣言はこの1行のみ。

### 4c. ✅行の定期GC（開始日から30日経過で削除）

セッション状態表の✅行で **開始日（MM-DD）から30日経過したものを削除**:

```bash
# 当日の月日と✅行の開始日を表示し目視判定（30日超が削除候補）
date +%m-%d
grep '| ✅' ~/projects/obsidian-ssot/00_SYSTEM/active-sessions.md
```

- **過去行（HH:MMのみ・日付なし）は残す**（段階的移行・日付付きの古いものから削除）
- handoff（`00_SYSTEM/handoff/`）が履歴SSOTなので✅行の削除は情報ロスなし。アーカイブファイルは作らない

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
| Step 4a-2 (自己駆動ループ起動確認) | 🟡[GLM] | LOOP/TRIAGE表示・稼働中チェック→鮮度チェック→方針ドラフト→approve.py非対話実行→set-mode.sh auto・停止法表示（2026-08-31追加） |

## 関連

- `new-session` スキル — 書き出し側（引き継ぎ生成＋SSOT保存）
- `~/projects/obsidian-ssot/00_SYSTEM/handoff使い方.md` — 運用マニュアル
- `~/projects/claude-config/docs/resume-session-spec.md` — 本スキルの設計spec

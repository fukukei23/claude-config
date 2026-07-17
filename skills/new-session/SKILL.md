---
name: new-session
description: コンテキストが溜まったセッションを捨てて新セッションに移行するための引き継ぎプロンプトを生成するスキル。「新セッション」「コンテキスト圧縮」「引き継ぎ」「セッション切り替え」または /new-session を呼び出した時にトリガーする。
user-invocable: true
---

# new-session — 新セッション引き継ぎプロンプト生成

ユーザーが `/new-session` を呼び出したら、以下を順番に実行して
**コピペ用の引き継ぎプロンプト**を生成・出力する。

---

## Step 1: 現在の状態を収集 🟡[GLM]

以下を読み込む（全てBashで取得）:

```bash
# 1. 今日の日付
TODAY=$(date +%Y-%m-%d)

# 2. 今日の日記
cat ~/projects/obsidian-ssot/10_DAILY/${TODAY}.md 2>/dev/null | tail -60

# 3. 直近のDECISIONSファイル（全プロジェクト横断・新しい順5件・特定プロジェクト決め打ち廃止）
ls -t ~/projects/obsidian-ssot/01_DECISIONS/*/*.md 2>/dev/null | \
  grep -v '_INDEX\|README\|参考資料' | head -5 | xargs -r head -30

# 3b. 40_CAREER 配下の最近更新ファイル（新しい順3件・career関連セッションの見落とし対策）
ls -t ~/projects/obsidian-ssot/40_CAREER/01_ドキュメント/*.md 2>/dev/null | \
  grep -v '_INDEX' | head -3 | xargs -r head -20

# 3c. 00_SYSTEM 配下の最近更新ファイル（新しい順5件・バックログ/active-sessions/handoffは別枠で読むためここでは除外）
find ~/projects/obsidian-ssot/00_SYSTEM -name '*.md' 2>/dev/null | \
  grep -v 'active-sessions.md\|バックログ.md\|/handoff/\|_INDEX' | \
  xargs -r ls -t 2>/dev/null | head -5 | xargs -r head -20

# 3d. その他SSOTフォルダの最近更新ファイル（新しい順3件ずつ・99_ARCHIVEは定義上振り返り対象外のため除外）
for dir in 20_PUBLISHING 30_RESEARCH 50_PROJECTS 70_PROMPTS; do
  echo "=== $dir ==="
  find ~/projects/obsidian-ssot/$dir -name '*.md' 2>/dev/null | \
    grep -v '_INDEX' | xargs -r ls -t 2>/dev/null | head -3 | xargs -r head -20
done

# 4. 主要リポジトリのgit状態（自セッション成果にフィルタ・spec 2026-07-09 並行汚染対策）
SINCE=$(date -d '6 hours ago' '+%Y-%m-%d %H:%M')  # セッション開始推定時刻
for repo in claude-config claude-code-guide guides obsidian-ssot; do
  echo "=== $repo ==="
  cd ~/projects/$repo && git status --short | head -5
  # --author --since で自セッション成果に絞る（並行セッション成果を除外・フィルタで切る設計）
  git log --author="$(git config user.name)" --since="$SINCE" --oneline -10 2>/dev/null || git log --oneline -2
done

# 5. 未完了specファイル
find ~/projects/claude-config/docs/ -name '*spec*.md' -newer ~/projects/claude-code-guide/docs/chapters/08-config.html 2>/dev/null

# 6. .update-queue.md があれば読む
cat ~/projects/claude-code-guide/.update-queue.md 2>/dev/null | head -20

# 7. セッション識別子（## メタ情報 ブロック用・spec 2026-07-06）
# 注: 開始時刻（START_TS）は廃止（2026-07-06 修正）。JSONL ctime は PreCompact で新規作成され
# 「最終活動時刻 or 圧縮後作成時刻」になり真のセッション開始時刻を取れないため。
# グループ化（wt_session=同タブ判定）は session_id/WT_SESSION で機能・開始時刻は不要。
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-unknown}"
WT_SESSION="${WT_SESSION:-unknown}"
END_TS=$(date '+%Y-%m-%d %H:%M')
echo "SESSION_ID=$SESSION_ID"
echo "WT_SESSION=$WT_SESSION"
echo "END_TS=$END_TS"

# WT4取得（自セッション識別子・spec 2026-07-09 セッション識別子改善）
WT_SESSION="${WT_SESSION:-unknown}"; WT4=${WT_SESSION:0:4}; echo "WT4=$WT4"
# 8. active-sessions.md の自分の🟢行（wt4でピンポイント・Step5で✅化する前）
# /clear跨ぎ残存行も同一wt4で拾う・他セッション🟢行はsoft警告参照用に別途grep
grep "| $WT4 |" ~/projects/obsidian-ssot/00_SYSTEM/active-sessions.md 2>/dev/null
echo "--- 他セッションの🟢行（soft警告用）---"
grep '| 🟢 |' ~/projects/obsidian-ssot/00_SYSTEM/active-sessions.md 2>/dev/null | grep -v "| $WT4 |"
```

---

## Step 1.5: バックログ `[x]` 忘れ点検（副次防波堤）🟡[GLM]

> **設計意図**: タスク完了 → `ssot-record`（フェーズ3.5）で `[x]` 化するのが主軸。
> だが抜け漏れは起きる。handoff 生成直前に**1回だけ**フェイルセーフ確認を入れる。

handoff を生成する**直前**に、以下をユーザーへ1問だけ確認する:

```
🔁 バックログ点検: このセッションで完了したのに [x] にし忘れたタスクはありませんか？
（あれば番号を指定 → [x] 化してから引き継ぎ生成します）
```

### 手順

1. **バックログの `[ ]` 一覧を表示**（候補を絞りやすくするため）:
   ```bash
   grep -n '^- \[ \]' ~/projects/obsidian-ssot/00_SYSTEM/バックログ.md
   ```

2. **ユーザー回答の処理**:
   - **「ない」/ スキップ**: そのまま Step 2 へ（Default）
   - **番号指定あり**: 該当行を `[x]` 化（完了日付を追記）→ バックログ.md を commit+push（`*/30` auto-sync でも可）→ Step 2 へ

### 制約

- **任意ステップ**（必須ではない）。ユーザーが「いいよ」と言えば即スキップ。
- `ssot-record` で確定済みの完了は重複確認しない（形骸化防止）。
- 本ステップで `[x]` 化しても handoff の「前回占有タスク」欄には書かない（完了した占有タスクは解放扱い）。

---

## Step 2: 稼働中のLLMに引き継ぎプロンプトを生成させる 🟡[GLM]

収集した情報を稼働中のLLM（WSL CLI版=GLM / Windows デスクトップアプリ版=Sonnet）に渡し、以下のフォーマットで引き継ぎプロンプトを生成させる。

### LLMへの指示

```
以下の情報を元に、新セッションで渡す引き継ぎプロンプトを日本語で生成してください。

条件:
- コピペしてすぐ使えること
- 新セッションのClaudeが「何をすべきか」が1読で分かること
- 背景の説明は最小限、「次のアクション」を明確に
- 読むべきファイルパスを具体的に列挙
- 現在の環境状態（シンボリックリンク、secrets等）を要約
- **自動化機構（auto-sync/auto-push等）の記述は `00_SYSTEM/自動化.md` の記述を正典とし、憶測で修飾（「常駐」「常時」等）しないこと**。実態: claude-config の push は SessionStop hook 発火時のみ（常駐ではない）・obsidian-ssot は `*/30` cron。不明なら書かず「`00_SYSTEM/自動化.md` 参照」とすること
- **「次のタスク」には候補を列挙せず、バックログ.md への参照のみを記載すること**（コピペ連鎖で完了済みタスクが残り続けるのを防ぐため・spec 2026-06-26）。現セッションの占有タスクは「前回占有タスク（継続可・参考）」欄に記載すること
- **`## メタ情報` ブロックは必ず先頭（`# 引き継ぎ` の直後・`## 環境` の前）に配置すること**（spec 2026-07-06・resume-session が wt_session でグループ化するため必須）。Step1 の #7 で取得した SESSION_ID / WT_SESSION / END_TS と #8 の🟢行セッション名をそのまま埋める（推測・省略しない）。環境変数が unknown でも `unknown` のまま書く（空欄禁止・resume-session のグループ化判定に使うため）。**開始時刻は記録しない**（spec 2026-07-06 修正・JSONL ctime が真の開始時刻を取れないため廃止）

フォーマット:
====== 新セッション用プロンプト（ここからコピー）======
# 引き継ぎ

## メタ情報
- session_id: <SESSION_ID（CLAUDE_CODE_SESSION_ID・CLI版で取得・unknownならフォールバック）>
- wt_session: <WT_SESSION（ターミナルタブ単位・CLI版で取得・unknownならフォールバック）>
- セッション名: <active-sessions.md の自分の🟢行の「セッション」列と同じ値（🟢行が無ければ「unknown」）>
- 終了: <END_TS>

## 環境
[WSL2/Windowsデスクトップ、LLMルーティング等の固定情報]

## 前回セッションまでの状態
[完了した変更・決定事項を箇条書き3〜5行]

## 前回占有タスク（継続可・参考）
[現セッションがセッション状態表で🟢進行中だったタスク。未完了ならここに記載。次回resume-sessionで「続きやる？」確認される]

## WIP構想一覧（未spec化の構想）
[`バックログ.md` を走査し、該当タスク直下の 📝WIPメモから title/方針を**そのまま転記**（要約加工しない・真実はバックログが持つ・DRY）。📝WIPメモが1件もなければ `None` と明示（空欄禁止・次回 resume-session で機械スキャンにより欠損検出されるため）]

## 次のタスク
**バックログ.md を参照のこと**（生きタスクの唯一の正典）。本handoffには候補を列挙しない（コピペ連鎖で完了済みタスクが残り続けるのを防ぐ）。resume-session がバックログ.md を優先度（P0 / 前回継続 / 他候補）でフィルタ表示する。

## 必ず読むファイル
[パスのリスト]

## 注意事項
[忘れると困る制約・ルール]
====== ここまで ======

[収集した情報]
{Step1の内容}
```

---

## Step 3: 出力 & SSOT永続保存

生成されたプロンプトをそのまま出力する。

次に、以下のPythonで SSOT の handoff ディレクトリに永続保存する:

```python
import os, datetime
save_dir = '/home/yn4416/projects/obsidian-ssot/00_SYSTEM/handoff'
os.makedirs(save_dir, exist_ok=True)
wt = os.environ.get('WT_SESSION', 'unknown')
wt4 = wt[:4] if wt and wt != 'unknown' else 'unknown'
filename = datetime.datetime.now().strftime('%Y-%m-%d_%H%M') + f'_{wt4}.md'
save_path = os.path.join(save_dir, filename)
with open(save_path, 'w') as f:
    f.write(generated_prompt)  # 生成したプロンプト内容
print(f'保存完了: {save_path}')
```

**即commit+push（auto-sync任せず・spec 2026-07-09 Step3明示commit）**:
```bash
HANDOFF_FILE=$(basename "$(ls -t ~/projects/obsidian-ssot/00_SYSTEM/handoff/*.md | head -1)")
cd ~/projects/obsidian-ssot && git add "00_SYSTEM/handoff/$HANDOFF_FILE" \
  && git commit -m "chore: handoff 追加(<セッション名>)" && git push
# push失敗時: Step4サマリーに⚠警告追記（次セッションはローカルhandoffのみで起動せざるを得ない旨明記）
```

出力後に一言添える:
```
このプロンプトをコピーして新セッションの最初のメッセージに貼り付けてください。
SSOT 永続保存済み: ~/projects/obsidian-ssot/00_SYSTEM/handoff/YYYY-MM-DD_HHMM_<wt4>.md
（ls ~/projects/obsidian-ssot/00_SYSTEM/handoff/ で履歴を確認可能）
```

---

## Step 4: 【必須・最後】3行のコピペ用サマリーを出力 🟡[GLM]

ユーザーが毎回プロンプト全文をコピペするのは大変。**SSOT に保存済み**であることを明示し、
**新セッションに貼る1行だけ**を案内する。**この3行だけ毎回必ず出力すること。**

```markdown
---

✅ 引き継ぎをSSOTに保存しました: `~/projects/obsidian-ssot/00_SYSTEM/handoff/YYYY-MM-DD_HHMM.md`

📝 要約: [このセッションで完了した内容を1行で]

🔜 新セッションで貼る1行:
\`\`\`
~/projects/obsidian-ssot/00_SYSTEM/handoff/YYYY-MM-DD_HHMM.md を読んで再スタートして
\`\`\`
```

**運用ルール:**
- YYYY-MM-DD_HHMM は Step 3 で保存した実ファイル名と一致させる
- 要約は冗長にせず「何を終えて・次は何か」が伝わる1行（30〜60字目安）
- 新セッションの Claude はそのファイルを読んで全文脈を取得するので、ユーザーは全文を読む必要なし
- 詳細: `~/projects/obsidian-ssot/00_SYSTEM/handoff使い方.md`

---

## Step 5: active-sessions 自分エントリを ✅終了 にする（状態変更のみ・行は残す）🟡[GLM]

セッションを新セッションに移行する＝現セッション終了。ボードの自分エントリを処理する。

手順:
1. WT4取得: `WT_SESSION="${WT_SESSION:-unknown}"; WT4=${WT_SESSION:0:4}`
2. active-sessions.md で **wt4 を含む🟢行を特定し状態列を `🟢` → `✅` に変更**（自分行・/clear跨ぎ残存行も同一wt4で拾う・spec 2026-07-09・行は残す・行移動しない）
   `grep "| $WT4 |" ~/projects/obsidian-ssot/00_SYSTEM/active-sessions.md | grep '| 🟢 |'`
   ※ 複数ヒット時（同タブ残存行）は全て✅化で占有解放
   - Edit ツールで該当行の状態列セルのみ置換（行全体を再描画しない）
   - ※ 🟢表は廃止済（2026-07-02 単一表化）。旧「2b 🟢表から削除」は不要・状態列変更だけで占有解放
   - ※継続する意思がある場合は🟢のまま残す（前回占有タスクとしてhandoffに記載される）
3. **✅行の定期GC**: **開始日（MM-DD）から30日経過した✅行を削除**（handoffが履歴SSOT・アーカイブ不要）。過去行（HH:MMのみ・日付なし）は残す（段階的移行）
4. **即commit+push**:
   ```bash
   cd ~/projects/obsidian-ssot && git add 00_SYSTEM/active-sessions.md && git commit -m "chore: active-sessions 終了処理(<セッション名>)" && git push
   ```
5. 併せて **24h超・状態不明のstale🟢行**があれば警告（resume-session の次回開始時にも検出）

---

## Step 6: ssot-recordセッションカウンタのクリア 🟡[GLM]

> **不変条件**: セッションのカウンタファイルの行数は、同一セッション内のssot-record呼び出し回数と一致しなければならない。session開始（resume-session）およびsession終了（本ステップ）の両方で必ずクリアされる（二重防御）。**2026-07-06 改修**: カウンタはセッションID別ファイル（`ssot-record-session-count-${CLAUDE_CODE_SESSION_ID}.txt`）に分離し、並行セッション汚染を構造的に防止。未設定時は旧単一ファイル名にフォールバック（spec: 2026-07-06-ssot-record-counter-session-scoped.md）。

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

- このファイルはssot-recordフェーズ7.5（セッション横断総括）の発火判定に使う外部カウンタ。クリアせず放置すると無期限に行数が増え続け、「同一セッション内で2回以上」という判定が壊れる
- 2026-07-06 改修前は単一ファイルをWSL CLI版・Windows Desktop版で共有していたため、真の並行セッションで他セッションの記録が混入する汚染が発生。セッションID別ファイル化で物理分離し根本解決（CLAUDE_CODE_SESSION_ID は両環境で安定取得確認済・未設定時フォールバックで後方互換）
- 本ステップに加えresume-session側（開始時）でもクリアすることで、異常終了（new-session未実行のままセッション終了）時の残存を防止（二重防御）
- `rm -f` のため、ファイルが存在しなくてもエラーにならない

---

## 補足: スキルが呼ばれるタイミング

- ユーザーが「コンテキスト85%超えた」「新セッションにしたい」と言った時
- コンテキスト使用量が多くなってきた時（自発的に提案してもよい）
- 長時間セッションで複数の別トピックが混在している時

## LLM割り当て

| ステップ | LLM | 理由 |
|---|---|---|
| Step 1 (情報収集) | Bash直実行 | LLM不要 |
| Step 2 (要約・生成) | 🟡[GLM] | テキスト生成 |
| Step 5 (ボード終了処理) | 🟡[GLM] | 状態列🟢→✅変更(行残す)・✅行GC・即push |
| Step 6 (カウンタクリア) | Bash直実行 | LLM不要・rm -fのみ |

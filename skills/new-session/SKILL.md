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

# 3. 直近のDECISIONSファイル（claude-code関連、新しい順3件）
ls -t ~/projects/obsidian-ssot/01_DECISIONS/claude-code/*.md 2>/dev/null | \
  grep -v '_INDEX\|README\|参考資料' | head -3 | xargs head -30

# 4. 主要リポジトリのgit状態
for repo in claude-config claude-code-guide guides obsidian-ssot; do
  echo "=== $repo ==="
  cd ~/projects/$repo && git status --short | head -5
  git log --oneline -2
done

# 5. 未完了specファイル
find ~/projects/claude-config/docs/ -name '*spec*.md' -newer ~/projects/claude-code-guide/docs/chapters/08-config.html 2>/dev/null

# 6. .update-queue.md があれば読む
cat ~/projects/claude-code-guide/.update-queue.md 2>/dev/null | head -20
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

## Step 2: GLMに引き継ぎプロンプトを生成させる 🟡[GLM]

収集した情報をGLMに渡し、以下のフォーマットで引き継ぎプロンプトを生成させる。

### GLMへの指示

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

フォーマット:
====== 新セッション用プロンプト（ここからコピー）======
# 引き継ぎ

## 環境
[WSL2/Windowsデスクトップ、LLMルーティング等の固定情報]

## 前回セッションまでの状態
[完了した変更・決定事項を箇条書き3〜5行]

## 前回占有タスク（継続可・参考）
[現セッションが🟢進行中タスク表に入れていたタスク。未完了ならここに記載。次回resume-sessionで「続きやる？」確認される]

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
filename = datetime.datetime.now().strftime('%Y-%m-%d_%H%M') + '.md'
save_path = os.path.join(save_dir, filename)
with open(save_path, 'w') as f:
    f.write(generated_prompt)  # 生成したプロンプト内容
print(f'保存完了: {save_path}')
```

出力後に一言添える:
```
このプロンプトをコピーして新セッションの最初のメッセージに貼り付けてください。
SSOT 永続保存済み: ~/projects/obsidian-ssot/00_SYSTEM/handoff/YYYY-MM-DD_HHMM.md
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

## Step 5: active-sessions ボードの自分エントリを ✅終了 にする 🟡[GLM]

セッションを新セッションに移行する＝現セッション終了。ボードの自分のエントリを処理する。

手順:
1. `obsidian-ssot/00_SYSTEM/active-sessions.md` を読み、自分のセッション(環境+トピック)のエントリを特定
2. 該当エントリの「状態」を `✅終了` に変更（または行を削除）
   - 削除基準: 完全に終わった・他セッションの参照不要 → 行削除
   - 終了マーク基準: 成果参照の可能性 → `✅終了` を残す
2b. **🟢進行中タスク表から自分のタスクを削除（占有解放）**:
    - 「## 🟢 現在進行中タスク」テーブルから自分の環境+トピックの行を削除
    - これでタスクはバックログに戻り、他セッションが候補として拾えるようになる
    - ※継続する意思がある場合は削除せず残す（前回占有タスクとしてhandoffに記載される）
3. **即commit+push**:
   ```bash
   cd ~/projects/obsidian-ssot && git add 00_SYSTEM/active-sessions.md && git commit -m "chore: active-sessions 終了処理(<セッション名>)" && git push
   ```
4. 併せて **24h超・状態不明のstaleエントリ**があれば掃除（確認の上削除）

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
| Step 5 (ボード終了処理) | 🟡[GLM] | 宣言更新・即push |

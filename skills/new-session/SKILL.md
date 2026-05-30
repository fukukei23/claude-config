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

フォーマット:
====== 新セッション用プロンプト（ここからコピー）======
# 引き継ぎ

## 環境
[WSL2/Windowsデスクトップ、LLMルーティング等の固定情報]

## 前回セッションまでの状態
[完了した変更・決定事項を箇条書き3〜5行]

## 次のタスク
[具体的に何をするか。仕様書があればパスを明記]

## 必ず読むファイル
[パスのリスト]

## 注意事項
[忘れると困る制約・ルール]
====== ここまで ======

[収集した情報]
{Step1の内容}
```

---

## Step 3: 出力

生成されたプロンプトをそのまま出力する。

出力後に一言添える:
```
このプロンプトをコピーして新セッションの最初のメッセージに貼り付けてください。
（ファイルに保存済みにする場合: /tmp/new-session-prompt.md にも書き出します）
```

`/tmp/new-session-prompt.md` にも同内容を書き出す（次のセッションで `cat` して読める）。

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

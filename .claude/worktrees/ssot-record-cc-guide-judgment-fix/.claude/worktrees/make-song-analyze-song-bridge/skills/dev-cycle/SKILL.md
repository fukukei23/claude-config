---
name: dev-cycle
description: コード品質改善の全サイクルを実行するスキル。品質スイープ→コードレビュー→Issue化→自律実装ループ→完了通知の5フェーズ。ユーザーが「dev-cycle」「開発サイクル」「品質改善」「自律ループ」などと言った時、または /dev-cycle を呼び出した時にトリガーする。
user-invocable: true
---

# dev-cycle — コード品質改善サイクル

ユーザーが `/dev-cycle` を呼び出したら、まず以下を確認する:

```
どのフェーズから始めますか？
  [1] 品質スイープ（全ファイル走査・問題列挙）
  [2] コードレビュー v3（重要ファイルを深く評価）
  [3] Issue化（レビュー結果をGitHub Issueに登録）
  [4] 自律実装ループ（Issueを順番に自動実装）
  [all] 全フェーズ通し実行
  
対象プロジェクト: ?
```

小規模（変更ファイル少）→ フェーズ2から推奨
大規模（50件超の改善）→ フェーズ1から推奨

---

## フェーズ1: 品質スイープ 🟡[GLM]

**目的**: 全ファイルを機械的に走査し High/Medium/Low リストを作る（読み取り専用）

```
実行方法: CronCreate（20分間隔）または今すぐ実行
テンプレート: 00_SYSTEM/共通ルール/コード品質スイープ.md を参照
出力先: 01_DECISIONS/<project>/YYYY-MM-DD_リファクタリング調査_<area>.md
```

**LLM**: 🟡[GLM]（パターン検出・列挙）

---

## フェーズ2: コードレビュー v3 🟡[GLM] / 🔵[Sonnet]（許可時）

**目的**: 重要ファイルを深く読み、★スコア + P1/P2 改善提案を出力

```
手順:
1. python score-files.py <project_path> --top 20 --json
2. wc -l で行数実測（スコアと照合）
3. Read ツールで実際に読む
4. 🟡[GLM] または 🔵[Sonnet] で評価
5. 出力: 40_CAREER/キャリア分析/02_コード品質/YYYY-MM-DD_<内容>/_REPORT.md

テンプレート: 00_SYSTEM/プロンプト集/コードレビュー/code-review-v3.md を参照
```

**LLM**: 🟡[GLM]（主観的評価・深い読解が必要なため MiniMax は使わない）

---

## フェーズ3: Issue化 🟡[GLM]

**目的**: P1/P2 リストを GitHub Issues に自動登録

```python
# GitHub API で Issue 一括作成
import yaml, json, urllib.request
hosts = yaml.safe_load(open('/home/yn4416/.config/gh/hosts.yml'))
token = hosts['github.com']['oauth_token']

issues_to_create = [
    # レビュー結果の P1/P2 からここを埋める
    {"title": "test: [A] ...", "body": "...", "labels": ["type:test","priority:low"]},
    {"title": "fix: [B] ...",  "body": "...", "labels": ["type:test","priority:medium"]},
]

for issue in issues_to_create:
    data = json.dumps(issue).encode()
    req = urllib.request.Request(
        f'https://api.github.com/repos/fukukei23/<REPO>/issues',
        data=data,
        headers={'Authorization': f'token {token}', 'Content-Type': 'application/json'}
    )
    res = json.load(urllib.request.urlopen(req))
    print(f"Created #{res['number']}: {res['title']}")
```

**タイトル形式**:
- `[A]` = priority:low（1h以下）
- `[B][C]` = priority:medium（2-3h）
- `[D]` = priority:high（4h以上）

**ラベル**: `type:test` / `type:fix` / `priority:high|medium|low`

---

## フェーズ4: 自律実装ループ

**目的**: GitHub Issues を高→中→低の順に自動実装

### 今すぐ実行（Stop Hook 連鎖方式）

```bash
# Issue番号を指定
bash ~/.claude/scripts/auto-dev/start.sh 76 77

# GitHubから自動取得（--auto）
bash ~/.claude/scripts/auto-dev/start.sh --auto <repo>
# 例: bash ~/.claude/scripts/auto-dev/start.sh --auto atelier-kyo-manager
```

### 夜間・放置実行（CronCreate 方式）

```
CronCreate:
  schedule: "7 * * * *"    # 毎時:07
  durable: true
  prompt: <repo>/docs/autonomous-loop-prompt.md の内容
```

### 実装中のLLM割り当て

| タスク | LLM |
|---|---|
| コード生成・大量処理 | 🟠[MiniMax] |
| テスト実行・CI確認 | Claude 直接 |

### 完了後の自動処理（自動実行される）

1. `pytest` 全件パス確認
2. `git commit && git push`
3. `gh run watch` で CI 確認
4. Issue close（GitHub API）
5. 次の Issue へ（Stop Hook 連鎖）
6. **全完了時 → Discord 通知**

### 緊急停止

```bash
python3 -c "
import json; p='/home/yn4416/.claude/scripts/auto-dev/state.json'
s=json.load(open(p)); s['active']=False; json.dump(s,open(p,'w'),indent=2)
print('停止:', s)
"
```

### 状態確認

```bash
cat ~/.claude/scripts/auto-dev/state.json
tail -f ~/.claude/scripts/auto-dev/loop.log
```

---

## フェーズ5: 完了通知（自動）

`~/.claude/scripts/auto-dev/next-issue.py` が `pending=[]` を検知して自動実行。
Discord Webhook に完了メッセージを送信する。

---

## 関連ファイル

| ファイル | 役割 |
|---|---|
| `~/.claude/scripts/auto-dev/start.sh` | ループ手動起動 |
| `~/.claude/scripts/auto-dev/next-issue.py` | Stop Hook 本体 |
| `~/.claude/scripts/auto-dev/state.json` | キュー状態 |
| `~/.claude/scripts/auto-dev/run-issue.sh` | Issue実行wrapper |
| `00_SYSTEM/共通ルール/コード品質スイープ.md` | フェーズ1詳細 |
| `00_SYSTEM/プロンプト集/コードレビュー/code-review-v3.md` | フェーズ2詳細 |
| `00_SYSTEM/共通ルール/自律開発ループ.md` | フェーズ4詳細 |
| `01_DECISIONS/claude-code/2026-05-30_dev-cycleスキル登録.md` | 実装記録 |

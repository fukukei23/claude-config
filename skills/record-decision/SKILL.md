---
name: record-decision
description: >
  【非推奨 → record-ssot を使うこと】
  record-ssot に統合済み。/record-decision が呼ばれた場合は record-ssot スキルに処理を委譲する。
  トリガーワード「記録して」「書き留めて」「保存して」は record-ssot が優先的に処理する。
disable-model-invocation: true
user-invocable: true
---

> ⚠️ このスキルは **record-ssot** に統合されました。
> `/record-ssot` または「記録して」を使ってください。
> 以下の処理は record-ssot スキルに委譲します。

# Record Decision to SSOT

Automate the 3-step SSOT recording from CLAUDE.md. The user invoked this by saying "記録して" or `/record-decision`.

## Before Writing

Ask the user for these 3 pieces of information (keep it brief, 1 line each):

1. **プロジェクト名** — which project (e.g. `claude-code`, `atelier-kyo-manager`, `obsidian-ssot`)
2. **作業内容** — what was done in this session/topic (2-3 sentences)
3. **未解決問題** — anything left unfinished, or "なし"

If the user already provided context in the conversation, skip asking and confirm what you understood.

## Step 1: SSOT Decision File

Create a decision file at:
```
/home/yn4416/projects/obsidian-ssot/01_DECISIONS/<project>/YYYY-MM-DD_<content>.md
```

**File naming convention**: `YYYY-MM-DD_<kebab-case-summary>.md`
- Use today's date
- Summary in Japanese kebab-case (e.g. `スクリプト再編成` → `スクリプト再編成` → use English: `2026-05-15_scripts-reorganization.md`)

**Content format**:
```markdown
# <作業内容の簡潔なタイトル>

## 概要
<2-3行で何をしたか>

## 詳細
<技術的詳細・コマンド・トラブルシューティング等>

## コミット
- `<commit-hash>` <1行説明>  ← あれば

## 未解決
- <残タスク> ← なければ「なし」
```

## Step 2: Repo Docs Update (only if needed)

Check if any repo documentation needs updating:
- `README.md`, `CLAUDE.md`, `docs/` in the project repo
- Only update if there were **spec/requirement/architecture changes**
- Skip for bug fixes, refactors, or routine changes

## Step 3: Daily Log Update

Append to today's daily log:
```
/home/yn4416/projects/obsidian-ssot/10_DAILY/YYYY-MM-DD.md
```

**Append format** (match existing style exactly):
```markdown
## セッションログ (HH:MM)
- <作業サマリー 3-5行>
- 詳細: 01_DECISIONS/<project>/<filename>.md
- 未解決: <あれば> ← なければ省略
```

Rules:
- Use current time for HH:MM
- Daily log should be a **summary with a link** — never write full details here
- If the file doesn't exist, create it with the header:
  ```
  # YYYY-MM-DD

  ---
  ```

## After Writing

1. Confirm to the user: what was written and where
2. Git commit & push the obsidian-ssot changes
3. If Step 2 updated repo docs, commit those separately in the project repo

## Constraints

- Never write API keys, secrets, or sensitive values
- Keep decision files factual — what was decided and why, not speculation
- Use Japanese for all content except code/commands/file paths
- One decision file per topic, not per session (if the user worked on 2 unrelated things, create 2 files)

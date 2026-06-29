# resume-session スキル + handoff自動読込 設計

> 作成日: 2026-06-17
> 関連: `new-session` スキル（書き出し側）、`handoff使い方.md`（運用マニュアル）

---

## 1. 背景と目的

### 現状の課題
セッション再開時の文脈復元が手動運用に依存している：

- **SessionStart hook (`load-handoff.sh`)** は `~/.claude/state/handoff.md`（最新1件・要約）のみ表示。Claude は handoff 全文を Read していないため、文脈が浅い。
- **`handoff使い方.md`** の運用ではユーザーが手動で「ファイルパスを読んで再スタート」と貼る必要がある。
- 直近の複数セッション（同日内に何度も `/new-session` を実行した場合等）の文脈を横断的に復元する手段がない。

### 目的
「おはよう」の1発（またはセッション開始の自動）で、**最新5件の handoff 全文**を読み込み、セッションを即座に再開可能な状態にする。

---

## 2. handoff の2系統（前提知識）

| 系統 | 場所 | 件数 | 生成タイミング |
|---|---|---|---|
| **state** | `~/.claude/state/handoff.md` | 常に最新1件（上書き） | Stop hook が毎セッション自動生成 |
| **履歴** | `~/projects/obsidian-ssot/00_SYSTEM/handoff/*.md` | 66件（増加） | `/new-session` 実行時のみ保存 |

- **「最新5件」** = 履歴系（`00_SYSTEM/handoff/`）の `ls -t | head -5`
- **state** は `/new-session` 未実行セッションの唯一の記録 → 完全廃止せず**フォールバック**として温存

### サイズ実測（2026-06-17 時点）
- 1ファイル: 37〜81行 / 3〜5KB
- 5件合計: 約5,800トークン（GLM-5.2 1M窓で 0.6%未満 → 消費無視可）

---

## 3. 設計

### 3.1 全体構成

2経路で同じ「最新5件全文」を読み込む：

```
┌─ 自動 ─────────────────────────────────┐
│ SessionStart hook (load-handoff.sh)    │
│  → セッション開始時に自動で5件全文 cat   │
└────────────────────────────────────────┘

┌─ 明示 ─────────────────────────────────┐
│ resume-session スキル                  │
│  → 「おはよう」等で発動、5件 Read+復元  │
└────────────────────────────────────────┘
```

hook は「無意識に文脈が入っている状態」、スキルは「任意タイミングでの再読込・フォールバック」を担う。

### 3.2 hook拡張: `load-handoff.sh`

**現状**（`~/.claude/scripts/session/load-handoff.sh`）:
```bash
HANDOFF_FILE="$HOME/.claude/state/handoff.md"
cat "$HANDOFF_FILE"  # 最新1件
```

**変更後**:
```bash
HISTORY_DIR="$HOME/projects/obsidian-ssot/00_SYSTEM/handoff"
STATE_FILE="$HOME/.claude/state/handoff.md"

files=$(ls -t "$HISTORY_DIR"/*.md 2>/dev/null | head -5)

if [[ -n "$files" ]]; then
  # 履歴の最新5件を全文 cat
  echo "--- Handoff (最新5件) ---"
  for f in $files; do echo "### $(basename "$f")"; cat "$f"; echo; done
  echo "--- /Handoff ---"
elif [[ -f "$STATE_FILE" ]]; then
  # フォールバック: 履歴が空なら state（1件）
  echo "--- Handoff ---"; cat "$STATE_FILE"; echo "--- /Handoff ---"
else
  echo "(handoff: なし)"
fi
```

- `/dev/tty` のバナー1行表示は既存ロジックを維持（最新1件のタイトルのみ）
- 出力フォーマット `--- Handoff ---` は維持（既存の認識を壊さない）

### 3.3 新規スキル: `resume-session`

**場所**: `~/.claude/skills/resume-session/SKILL.md`
**user-invocable**: true
**対**: `new-session`（書き出し）↔ `resume-session`（読込）

**frontmatter**:
```yaml
---
name: resume-session
description: セッション再開時に最新5件のhandoffを読み込み文脈を復元するスキル。「おはよう」「こんにちは」「こんばんは」「再開」「restart」または /resume-session を呼んだ時にトリガーする。new-session の対（読込側）。
user-invocable: true
---
```

**動作フロー**:

1. **最新5件取得**（Bash）:
   ```bash
   ls -t ~/projects/obsidian-ssot/00_SYSTEM/handoff/*.md | head -5
   ```
2. **5件を Read**（Readツール）— 各ファイルの全文を取得
3. **復元サマリーを出力**:
   - 環境（WSL2 / LLMルーティング / プロキシ）— 重複する固定情報は1回だけ
   - 前回セッションの完了内容（5件から時系列統合）
   - **次のタスク**（最重要・最新ファイル優先）
   - 未解決問題
4. **再開提案を1行出力**: 「どこから再開するか」を提示し、ユーザーが即断即決できるようにする

**出力イメージ**:
```markdown
🟡[GLM] セッション再開 — 最新5件のhandoffを読み込みました。

## 直近の作業（新しい順）
- [1959] Phase2 api 脆弱性監査 完了（HIGH 2件）
- [1951] ...

## 次のタスク
 NexusCore /execute 修正（C案）→ テスト → PR

## 未解決
修正合意待ち

どこから再開しますか？（A: 修正実装 / B: 別作業 / C: 提案して）
```

**トリガーワード**（スキルファイル内「トリガーワード」欄 + CLAUDE.md）:
- おはよう / こんにちは / こんばんは
- 再開 / restart / レジューム
- `/resume-session`

### 3.4 CLAUDE.md スキルトリガー追記

グローバル `~/.claude/CLAUDE.md` の「スキルトリガー（厳格）」セクションに追記：

```markdown
- resume-session: 「おはよう」「こんにちは」「こんばんは」「再開」「restart」で発動
```

### 3.5 設定同期（必須・既存ルール準拠）

hook・CLAUDE.md 変更に伴い、以下を同時更新：
- `~/projects/obsidian-ssot/01_DECISIONS/claude-code/設定ファイル/` 配下の該当コピー
- `~/projects/claude-config/` 配下（skills/ に resume-session 配置、docs/ に本spec）
- ※ PostToolUse/Stop hook が自動同期する設定もあるが、新規スキル作成は手動配置が確実

---

## 4. 実装ステップ

1. `load-handoff.sh` を修正（3.2）
2. `~/.claude/skills/resume-session/SKILL.md` を作成（3.3）
3. グローバル `~/.claude/CLAUDE.md` のスキルトリガー欄に追記（3.4）
4. 設定同期（3.5）— SSOT設定ファイルコピー更新
5. 動作検証:
   - 新セッションを開き、hook が5件全文を読むか確認
   - 「おはよう」発言で resume-session が発動するか確認
6. **スキル完成後の必須フロー**（既存ルール）:
   - SSOT詳細: `01_DECISIONS/claude-code/2026-06-17_resume-session-skill-作成.md`
   - 日記追記: `10_DAILY/2026-06-17.md`
   - `SKILL_CATALOG.md`（SessionStart hook が自動生成）
   - 関連ガイド追記（handoff使い方.md に resume-session への言及）

---

## 5. テスト方針

- **hook**: `bash load-handoff.sh` を単体実行し、5件分の出力が出るか確認
- **スキル**: 新セッションで「おはよう」→ resume-session 発動 → 復元サマリーが出るか
- **フォールバック**: 履歴ディレクトリが空の想定ケースで state が読まれるか（手動確認）

---

## 6. スコープ外（YAGNI）

- 読込件数の可変指定（「おはよう 3」等）→ 固定5件（ユーザー決定）
- トピック別フィルタ（「make-song関連だけ」等）→ 必要になったら別スキル
- handoff使い方.md の全面改訂 → 最小追記のみ

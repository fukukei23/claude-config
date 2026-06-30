# claude-code-guide 自動更新システム 実装仕様

> このファイルは新セッションで実装を再開するための引き継ぎ仕様書。
> 実装完了後に削除してよい。

---

## 目的

`~/projects/claude-code-guide/` (GitHub Pages) を、
`~/projects/claude-config/scripts/` や `~/.claude/settings.json` の変更に
自動追従させる仕組みを作る。

---

## 3段階構成

### 段階1: Stop hook でキュー記録

**ファイル**: `scripts/session/queue-guide-updates.sh`  
**トリガー**: セッション終了時（Stop hook）  
**動作**: claude-config の直近コミットを見て「どの章が古くなったか」を記録

**出力先**: `~/projects/claude-code-guide/.update-queue.md`

```
| 2026-05-31 | scripts/hooks/ 変更 | 05-hooks.html |
| 2026-05-31 | settings.json hooks変更 | 05-hooks.html, 08-config.html |
```

**マッピングテーブル（変更ファイル → 更新すべき章）**:
```
scripts/hooks/        → 05-hooks.html
scripts/session/      → 05-hooks.html, 08-config.html
scripts/config/       → 08-config.html
scripts/mcp/          → 04-mcp.html
scripts/llm/          → 08-config.html
scripts/security/     → 08-config.html
scripts/auto-dev/     → 12-dev-cycle.html
settings.json(hooks)  → 05-hooks.html
settings.json(mcp)    → 04-mcp.html
~/.claude/CLAUDE.md   → 01-basics.html, 08-config.html
skills/               → 03-skills.html
```

重複は排除。同じ章が複数回キューに入らない。

---

### 段階2: /update-guide スキル（手動トリガー）

**ファイル**: `~/.claude/skills/update-guide/SKILL.md`  
**トリガー**: ユーザーが `/update-guide` を実行  
**動作**:

1. `.update-queue.md` を読む（対象章を特定）
2. 対象章の現HTMLを読む
3. 変更されたスクリプト・設定ファイルを読む
4. GLM に「PROTECTED以外を最新状態に合わせて更新」させる
5. HTMLバリデーション（`python3 -c "from html.parser import HTMLParser; ..."`)
   - 失敗 → 中断・エラー表示
6. diff を表示して確認
7. commit → push → `.update-queue.md` から処理済み行を削除

**オプション**:
- `/update-guide --dry-run` : 差分確認のみ、変更しない
- `/update-guide --apply`   : 確認なしで適用

---

### 段階3: Cron 自動実行（月・木 6:00）

**Cronスケジュール**: `0 6 * * 1,4`（月曜・木曜 6:00）

**ファイル**: `scripts/auto-dev/update-guide-cron.sh`

**動作フロー**:
```
① .update-queue.md が空なら終了
② ブランチ作成: guide-update-YYYY-MM-DD
③ GLMで対象章を更新
④ HTMLバリデーション
   - 失敗 → ブランチ削除・Discord通知「バリデーション失敗」で終了
⑤ PR自動作成
⑥ Discord通知:
   「🤖 ガイド自動更新
    章: XX.html
    変更: （要約3行）
    PR: https://github.com/.../pull/NN
    ⏱ 24時間後に自動マージします
    問題があれば↑のリンクからPRを閉じてください」
⑦ 24時間スリープ（scheduled-tasks で翌日実行）
⑧ PRがまだオープンなら自動マージ → Discord通知「マージしました」
   PRが閉じられていたら → Discord通知「スキップしました」
```

---

## 保護マーカー（PROTECTED）

HTML章ファイル内に以下のコメントで保護範囲を指定できる。
GLMはPROTECTEDセクションを読み飛ばして変更しない。

```html
<!-- GUIDE:PROTECTED -->
<h2>概念の説明（確定・変更不要）</h2>
<p>ここは触らない。</p>
<!-- /GUIDE:PROTECTED -->

<!-- GUIDE:AUTO-UPDATE -->
<h2>現在の設定一覧（実環境と連動）</h2>
<p>GLMが自動更新してOK。</p>
<!-- /GUIDE:AUTO-UPDATE -->
```

マーカーなしのセクションはデフォルトで `AUTO-UPDATE` 扱い。

---

## settings.json への hook 追加（段階1・3）

### Stop hook（段階1）
```json
{
  "type": "command",
  "command": "/home/yn4416/.claude/scripts/session/queue-guide-updates.sh",
  "timeout": 5000
}
```

### Cron（段階3）
```
CronCreate: "0 6 * * 1,4"
command: bash /home/yn4416/.claude/scripts/auto-dev/update-guide-cron.sh
durable: true
```

---

## 完了後にすること

1. 各章の `PROTECTED` セクションをマークしていく（任意・後回し可）
2. 動作確認: 何かスクリプトを編集 → Stop hook でキューに記録されるか確認
3. 初回 `/update-guide --dry-run` で差分確認

---

## 関連ファイル

- claude-code-guide: `~/projects/claude-code-guide/`
- 更新キュー: `~/projects/claude-code-guide/.update-queue.md`（自動生成）
- 既存の auto-dev: `~/projects/claude-code-guide/scripts/auto-dev/`
- 既存 dev-cycle スキル: `~/.claude/skills/dev-cycle/`（構造を参考にする）

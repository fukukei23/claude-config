---
name: cron-setup
description: 定期実行（durable cron・system cron）を新規作成する時の規定路線。排他設計（flock+当日スタンプ / stamp-lock）+実行ログ+renew-crons.sh正典追記+apply-crons reconcile+同日skip実測までを強制する。「定期実行作って」「cron新設」「cron登録して」「毎日/毎週XXを自動実行して」「/cron-setup」等で発動。durable cronは並行セッション全てに発火するため排他なしの定期実行は作らない（2026-09-02 ふくけい指示・openrouter当日スタンプ事案の規定路線化）。
---

# cron-setup — 定期実行新設の規定路線

## 背景（なぜ排他が必須か）

durable cronは発火時**並行セッション全てに同じpromptが配信され、各セッションが順次（時間差で）実行する**。flock guardは「同時実行」しか防御できず、時間差発火は全セッションが実行してしまう（2026-09-02 openrouter-refresh実測・当日に複数回実行を確認）。

> 正典: `01_DECISIONS/claude-code/2026-09-02_openrouter-refresh当日スタンプ排他実装.md`・排他化系列は [[2026-08-28_durable-cron残6件の排他化①ssot-check-auto実行ロックと②使用量集計flockラッパー]]・③stamp-lock汎用化

## 手順（省略禁止・順番固定）

### Step 0: 既存横断確認（車輪の再発明防止）

```bash
grep -n '<抽象キーワード>' ~/projects/obsidian-ssot/00_SYSTEM/自動化.md ~/bin/renew-crons.sh
```

同目的の定期実行が既にあれば新設せず既存への追加/統合を提案する。

### Step 1: 実行形態の判定（排他方式の選定・必須）

| 形態 | 条件 | 排他方式 |
|---|---|---|
| **A: スクリプト1本完結** | シェル/Pythonのみで終了・LLMセッション不要 | **flock（同時排他）＋当日成功スタンプ（時間差冪等化）＋実行ログ** |
| **B: LLMセッションが介在** | cron promptでCCが複数ステップ実行 | **stamp-lock**（`bash ~/.claude/scripts/obsidian/stamp-lock.sh <name> acquire` → BUSY(exit 1)ならskip報告で終了 → release必須・失敗時も） |

### Step 2: スクリプト実装（形態A・見本は既存2本）

- **flock+当日スタンプの見本**: `~/bin/ai-repo-watch.sh`（シェル版）・`~/bin/openrouter-pick/orp.py` の `cmd_refresh`（Python版）
- **実装要素（必須）**:
  1. 非ブロッキングflock（`LOCK_EX|LOCK_NB`・取得失敗=同時実行→exit 3 skip）
  2. 当日成功スタンプ（開始時に当日日付が書かれていればskip・**成功時のみ**スタンプ書込=失敗翌日は再試行可能）
  3. 実行ログ（専用jsonl 1行/回・**既存の消費者とファイルを混ぜない** — 2026-09-02実測: pick.jsonlに混ぜたら `d["model"]` キー前提の昇格判定がKeyError落ち）
  4. `--force` / `--offline` オプション（手動再実行・dry-runの出口）
- **ログが無いと「多重発火しているか」の計測自体が不能になる**（観測穴の教訓）

### Step 3: renew-crons.sh 正典へ追記

```
# @cron id=<既存最大+1> name="<日本語名>" schedule="<cron式>" health="<形式>"
#   <実行プロンプト（1文で明確に）・prompt末尾に [cron-id:N] マーカー必須（id突合に使用）>
```

- 編集後に実体パス存在確認: `grep -oE '(bash|python3?) ~/[^ ]+' ~/bin/renew-crons.sh | awk '{print $2}' | sort -u | while read p; do pp="${p/#\~/$HOME}"; [ -e "$pp" ] || echo "MISSING: $p"; done`
- system cronへ移行すべき案件（LLM不要・深夜等）は durable でなく WSL crontab 直登録も選択肢（判断基準は自動化.md）

### Step 4: 登録（AIのCronCreate直接は廃止済み）

```bash
bash ~/bin/apply-crons.sh check       # 整合確認
bash ~/bin/apply-crons.sh reconcile   # 冪等同期・[RESULT]=done/skip 確認
```

### Step 5: 実測検証（生exit code添付・省略禁止）

1. dry-run実行（書込なし確認）
2. 本番1回目 → `EXIT=0` ＋ スタンプ/ログ作成確認
3. **同日2回目 → skip確認**（`EXIT=3` かつ skipメッセージ / stamp-lockなら BUSY exit 1）← ここが本機構のfail条件
4. fail条件: 「同日2回目がskipにならず実行される」・定義↔実体乖離・ログ不在のいずれか

### Step 6: 自動化.md cron表へ1行追記

`| <スケジュール> | <スクリプト> | active | <説明+排他方式+ログ先> |` 形式・排他方式と実行ログ先を必ず明記。

### Step 7: 記録

`ssot-record` スキルで記録（排他設計の判断・テスト実測証跡を含める）。

## fail条件（このスキルが機能しなかったと判定する事例）

- 排他なしで定期実行を新設した事例が1件出る
- 同日skip検証（Step 5-3）を省略して「実装済み」と報告した事例が1件出る

## 関連

- cron永続化の正典: `00_SYSTEM/自動化.md`「Cron永続化（apply-crons.sh）」節
- stamp-lock本体: `~/projects/claude-config/scripts/obsidian/stamp-lock.sh`（`~/.claude/scripts/obsidian/` 経由）

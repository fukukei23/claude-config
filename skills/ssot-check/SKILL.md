---
name: ssot-check
description: >
  SSOT（Single Source of Truth）と実際のファイル/設定の整合性をチェックし、乖離があれば修正するスキル。
  「SSOTチェックして」「SSOT整合性チェックして」「SSOT整理して」「SSOTのズレを直して」
  「00_SYSTEM更新して」「乖離を修正して」と言った時にトリガーする。
  /ssot-check でも呼び出せる。
user-invocable: true
---

# ssot-check スキル

## 概要

SSOT（`~/projects/obsidian-ssot/`）内のファイルと実態（設定ファイル・フォルダ構成・Cron等）を照合し、乖離があれば提案・修正する。

---

## 無人モード（auto）

`/ssot-check auto` または引数に `auto` が含まれる場合、**ユーザー承認をスキップ**して無人実行する。Cron定期実行専用。呼び出し時にモードを判定し、以降の各フェーズで auto の挙動を適用すること。

### auto 時の挙動
- **フェーズ2**: 承認確認なし。乖離一覧は内部保持のみでユーザーに問わない。
- **フェーズ3（修正）**: **重要度「高」のみ自動修正**。「中」「低」は自動修正せず**「修正は要確認（承認後に実施）」として報告・記録する**（報告文面の表記ルール・2026-08-30 ふくけい指摘:「検知のみ」「修正しない」等の受け身表現は後続アクションが見えず紛らわしいため禁止）。
- **フェーズ4**: **commit のみ自動実行**（push は ssot-auto-sync `*/30` に委譲・git競合の窓口を減らす）。メッセージ: `chore: SSOT整合性チェック[auto]（高重要度N件修正）`
- **記録**: 修正した「高」と「修正は要確認」とした「中・低」の**全件**を `10_DAILY/YYYY-MM-DD.md` に追記。ヘッダーは `## SSOT整合性チェック[auto] (HH:MM)` 形式（セッションログではない）。**Edit ツールではなく bash の `>>` heredoc で追記**（複数プロセス・並行セッションによる `File has been modified since read` 競合を回避。**security-guard にブロックされた場合は Edit 経路へ切替可・2026-08-30 実績**）。

### auto 時のstate更新（2段階・重複発火抑制）
state は2ファイルに分離（2026-06-26 の 04:39/41/42/43 の4連鎖発火事故対策）:
- `ssot-check-triggered`: **SessionStart hook（check-ssot-check-staleness.sh）が発火指示時に先行マーク**する。本スキルでは触らない。後続セッションの同時発火を弾く。
- `ssot-check-last-run`: **本スキルが auto 実行完了時に更新**する（実行成功日・翌日以降の参照用）。

```bash
# auto 実行の完了時（高0件で commit なしの場合でも必ず実行）:
date +%Y-%m-%d > ~/.claude/state/ssot-check-last-run
```
**高0件で commit をスキップした場合でも last-run は更新すること**（更新忘れが state 古残り→翌セッション再発火の無限ループの原因。04:39実行の再発原因）。

### auto 実行ロック（2026-08-28 追加・並行セッション同時実行の封止）
durable cron は各並行セッションが独立発火する（2026-08-28 07:27+07:33 並行発火で
MCPガイド再是正ロールバック3回の実害）。**auto 開始直後（フェーズ1の前）に acquire、
終了時（last-run 更新と同時）に release** すること（LLM駆動のため flock でなく
stamp+年齢方式・汎用 `scripts/obsidian/stamp-lock.sh`・停滞30分で次回が強制取得）:

```bash
# auto 開始直後:
if ! bash ~/.claude/scripts/obsidian/stamp-lock.sh ssot-check-auto acquire; then
  # BUSY = 他セッションが実行中 → 日記に1行だけ残して即終了（調査もしない）
  cat >> ~/projects/obsidian-ssot/10_DAILY/$(date +%F).md << 'EOF'

## SSOT整合性チェック[auto] (HH:MM)
- ⏭️ 他セッションが ssot-check auto 実行中のためスキップ（実行ロック BUSY）
EOF
  exit 0
fi
# auto 終了時（last-run 更新と同時に・異常終了時も release 必須）:
bash ~/.claude/scripts/obsidian/stamp-lock.sh ssot-check-auto release
```

### 安全装置（auto 時の厳格な制限）
- 「高」でも**削除系**（リポ消失・フォルダ消失等の記述削除）は自動修正せず検知のみ。誤削除防止。
- commit 前に `git diff --stat` で変更範囲を確認。**5ファイル超 または 100行超**の大規模変更時は commit 中止 → 日記に「要手動確認: 変更規模が想定外」と記録して終了。
- `git push --force` は auto・対話ともに**絶対禁止**。
- 調査で `gh` コマンドが失敗（認証切れ等）した場合、その対象はスキップし日記に「要確認」記録。

---

## チェック対象

### 1. 自動化.md
- **settings.json hooks**: 全Hookコマンドが `自動化.md` のテーブルに載っているか
- **Cron**: `~/.claude/scheduled_tasks.json` のCronが `自動化.md` のCronテーブルに載っているか
- **スクリプト**: `~/bin/` と `~/.claude/scripts/` のスクリプトが一覧に載っているか
- **ssot-auto-sync.sh**: 実際のスケジュール（`*/5` or `*/30`）を確認

### 2. repo-index.yaml / リポジトリ索引.md
- **last_updated**: 古くなっていないか（1週間以上前なら更新）
- **total_repos**: GitHubの実リポ数と合っているか
- ** visibilidade**: public/private が実際のものか
- **不足リポ**: GitHubにあるのにYAMLに載っていないリポはないか

### 3. MCPツール使い分けガイド.md
- **有効サーバー数**: settings.json の mcpServers と合っているか
- **無効化済みリスト**: 実際に無効化したサーバーが載っているか

### 4. 全体マップ_MOC.md
- **リポジトリ数**: `全XXリポジトリ` の表示が正しいか
- **プロジェクト一覧**: 01_DECISIONS/ の最新フォルダ構成と合っているか

### 5. チャーター.md
- **禁止操作**: `guard-destructive-commands.sh` と一致しているか
- **Tier1参照**: `共通ルール/ルール.md` への参照があるか

### 6. ssot-search v1/v2 取り違え防止（2026-08-23 L21 追加）
- **検出対象**: v1 パス（`scripts/ssot/search.py`）が **「v1 字句完全一致用」等の明示なし** に手順書/ガイドに記載されていないか
- **真因**: 2026-08-22 「RAG を実測した」と誤報告した事故（実際は v1=ripgrep+rerank）・v2 は意味検索で Recall@5=0.744・v1 は 0.026
- **除外**: 01_DECISIONS/, handoff/, マルチLLMレビュー/, docs/ は経緯記録のため除外
- **実行**: `bash ~/projects/claude-config/scripts/obsidian/check-ssot-search-v1-hardcoded.sh`
- **exit 0 = 検出なし（または全ファイル明示済）**, **exit 1 = 検出あり**
- **auto 時**: 高重要度（手順書/ガイド）として自動修正提案。中（記録引用）は提案のみ

---

## フェーズ1: 調査

各対象ファイルを実際に読み込んで乖離を検出する:

```bash
# 1. 自動化.md の乖離チェック
#    ※ cat は security-guard hook でブロックされるため python 直接読込（auto定期実行で停止防止）
python3 -c "
import json
d = json.load(open('/home/yn4416/.claude/settings.json'))
for event, hooks in d.get('hooks', {}).items():
    for h in hooks:
        cmd = json.dumps(h, ensure_ascii=False)
        print(f'{event}: {cmd[:80]}')
"

# 2. GitHubリポ数確認（--limit 200 で取りこぼし防止・2026-08-24 教訓）
gh repo list fukukei23 --limit 200 --json name,visibility --jq '.[] | .name' | wc -l

# 3. 01_DECISIONS プロジェクト一覧
ls /home/yn4416/projects/obsidian-ssot/01_DECISIONS/

# 4. scheduled_tasks.json のCron
python3 -c "import json; print(len(json.load(open('/home/yn4416/.claude/scheduled_tasks.json'))['tasks']), '件')"

# 5. settings.json のmcpServers
python3 -c "import json; print(list(json.load(open('/home/yn4416/.claude/settings.json'))['mcpServers'].keys()))"

# 6. Cron整合の独立検視（reconcileの沈黙事故検知・2026-08-20追加）
bash ~/bin/apply-crons.sh check 2>&1 | tail -4
# →「整合: ✅」なら正常。「⚠️ create/ghost」またはコマンド自体が失敗する場合は
#   reconcileまたは定義が壊れている可能性→高重要度として記録（reconcileは*/6hで自己修復するが、
#   この検視はreconcile自体の死亡を検知する独立層）

# 7. repo-index.yaml repositories: 節カウント（relationship_groups: 節は数えない・2026-08-24 教訓）
# ⚠️ `^  - name:` 全体マッチは groups 定義を混入させる（誤って53件と数えた事例あり）。
#    repositories: 行から relationship_groups: 行の間のみを awk で抽出してカウントする。
awk '/^repositories:/{f=1;next}/^relationship_groups:/{f=0}f && /^  - name:/' /home/yn4416/projects/obsidian-ssot/00_SYSTEM/repo-index.yaml | wc -l
```

---

## フェーズ2: 乖離一覧提示

検出した乖離を以下の形式で提示:

```
📋 SSOT整合性チェック結果

【重要度: 高】← 実態と大きく異なる
- [ ] リポジトリ索引.md: 総リポ数 23→実際の28と不一致
- [ ] MCPガイド: 有効サーバー 12個→実際の4個と不一致

【重要度: 中】← 一部古い
- [ ] 全体マップ_MOC.md: 新規プロジェクト（ssot-guide等）未記載
- [ ] repo-index.yaml: last_updated が9日古い

【重要度: 低】← 軽微
- [ ] チャーター.md: 禁止操作リストが一部古い

修正しますか？ [yes/選択/却下]
```

### 重要度基準
- **高**: ユーザーが見た時に「嘘だろう」と感じるレベル（数・visibility・存在しないフォルダ記載等）
- **中**: 若干古い情報（1週間以上の日付違い、追加されたプロジェクト等）
- **低**: 説明文の微妙な言い回し変更等

---

## フェーズ3: 修正実行（ユーザー承認後）

### 修正対象별手順

#### repo-index.yaml
1. `last_updated` を現在日時に更新
2. `total_repos` を実際のGitHubリポ数に更新
3. visibility/privateの不一致を修正
4. 不足リポを追加（GitHubに 있는데YAMLにないもの）
5. YAML更新後、`リポジトリ索引.md` を再生成

#### MCPツール使い分けガイド.md
1. ヘッダーの「有効サーバー: X個」を actual 値に更新
2. 無効化済みセクションに実際に切ったサーバーを追記（再インストール可能な旨を記載）

#### 全体マップ_MOC.md
1. リポジトリ数の表示を更新
2. 01_DECISIONS/ の最新フォルダ構成を反映
3. 新規プロジェクトを追加

#### チャーター.md
1. 禁止操作リストが `guard-destructive-commands.sh` と一致しているか確認
2. 一致していなければ「詳細は `guard-destructive-commands.sh` を参照」と追記

#### 自動化.md
1. settings.json hooks の全コマンドが載っているか確認
2. ssot-auto-sync.sh の実際のスケジュールを確認（`*/5` or `*/30`）
3. 不足分を追記

---

## フェーズ4: git commit（push は auto-sync に委譲）

```bash
cd /home/yn4416/projects/obsidian-ssot
# auto 時は安全装置（5ファイル/100行超）で commit 中止判定を先に行うこと
git add -A
git commit -m "update: SSOT整合性チェック（修正対象: XXX）"
# ※ push は行わない。ssot-auto-sync.sh（*/30）が自動 push する（git競合窓口を減らす）
```

---

## 完了報告

```
✅ SSOT整合性チェック完了

【修正ファイル】
- repo-index.yaml（リポ数・last_updated・visibility 更新）
- リポジトリ索引.md（再生成）
- MCPツール使い分けガイド.md（有効4個に更新）
- 全体マップ_MOC.md（プロジェクト一覧更新）
- チャーター.md（禁止操作参照追加）

🔗 コミット: <hash>
```

---

## 制約

- 修正はユーザー承認後（デフォルト: 全件承認の `yes`、選択なら `[1,3]` 形式）
- 追加：新リポジトリを作ったら、このスキルで整合性を確認する習慣をつける
- 削除：リポジトリを削除した場合は `自動化.md` 等から手動削除（自動検知は困难）
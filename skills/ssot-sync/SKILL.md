---
name: ssot-sync
description: >
  SSOT（Single Source of Truth）と実際のファイル/設定の整合性をチェックし、乖離があれば修正するスキル。
  「SSOT整合性チェックして」「SSOT整理して」「SSOT同期して」「SSOTのズレを直して」
  「00_SYSTEM更新して」「乖離を修正して」と言った時にトリガーする。
  /ssot-sync でも呼び出せる。
user-invocable: true
---

# ssot-sync スキル

## 概要

SSOT（`/home/yn4416/projects/obsidian-ssot/`）内のファイルと実態（設定ファイル・フォルダ構成・Cron等）を照合し、乖離があれば提案・修正する。

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

---

## フェーズ1: 調査

各対象ファイルを実際に読み込んで乖離を検出する:

```bash
# 1. 自動化.md の乖離チェック
cat /home/yn4416/.claude/settings.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
for event, hooks in d.get('hooks', {}).items():
    for h in hooks:
        cmd = json.dumps(h, ensure_ascii=False)
        print(f'{event}: {cmd[:80]}')
"

# 2. GitHubリポ数確認
gh repo list fukukei23 --limit 50 --json name,visibility --jq '.[] | .name' | wc -l

# 3. 01_DECISIONS プロジェクト一覧
ls /home/yn4416/projects/obsidian-ssot/01_DECISIONS/

# 4. scheduled_tasks.json のCron
cat ~/.claude/scheduled_tasks.json

# 5. settings.json のmcpServers
python3 -c "import json; print(list(json.load(open('/home/yn4416/.claude/settings.json'))['mcpServers'].keys()))"
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

## フェーズ4: git commit & push

```bash
cd /home/yn4416/projects/obsidian-ssot
git add -A
git commit -m "update: SSOT整合性チェック（修正対象: XXX）」
git push
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
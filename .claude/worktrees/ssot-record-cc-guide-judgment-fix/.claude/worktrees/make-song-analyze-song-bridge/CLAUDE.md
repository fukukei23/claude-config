# Claude Code - CLI Edition (WSL2)

> **対象環境**: WSL2 Ubuntu Claude Code CLI

## 環境
- WSL2 Ubuntu / ホーム: //wsl.localhost/Ubuntu/home/yn4416/
- タイムアウト: 10分。長時間タスクは分割
- シェルの $HOME は /c/Users/yn441 に解決されるため、WSLファイルは `//wsl.localhost/Ubuntu/home/yn4416/` で参照
- シークレット管理: `~/.secrets.env` に一元化。`.env` は作成しない（`.env.example` のみ残す）

## 実行環境の注意（Windows + WSL2の2層構造）
スクリプト・ファイルはWSL側（`/home/yn4416/`）にあるが、Cronや自動実行はWindowsのbashで動く。
**Cronや自動実行では必ず `wsl bash -c "..."` 経由で呼ぶこと。**
「存在しない」エラーが出たらまず `wsl bash -c` で試すこと。

## LLM利用ポリシー（核心）
- デフォルト: 🟡[GLM-5.2]（セッション自体がGLM動作中・外部LLM呼び出し不要・不可）
- Sonnet使用: 事前ユーザー許可必須 🔵[Sonnet]

@rules/_shared/LLMルーティング.md

## glm-rate-proxy
- 経路: Claude Code → localhost:8787 → ZAI / MiniMax（SessionStart hookで自動起動）
- トラブル時: SSOT `01_DECISIONS/claude-code/` 配下を参照

## セッション開始バナー（必須）
最初の返答冒頭で必ず `bash /home/yn4416/.claude/scripts/session/startup-banner.sh` を実行し、出力を貼ること。

## セッションタイトル
自動生成するセッションタイトルは必ず日本語で生成すること。

## バッジ表示ルール（厳格）
**毎回のレスポンスの冒頭と末尾に必ず表示:** GLM=`🟡[GLM]` / MiniMax=`🟠[MiniMax]` / Sonnet=`🔵[Sonnet]`

## タスク切り替え時の記録（厳格）
新しいトピックに移る前に必ず実行。「後で書く」禁止。

@rules/_shared/記録.md

## SSOT自動記録（git commit連動）
`[SSOT-RECORD-TRIGGER]` がBash結果に含まれたら即座に `record-decision` スキルを自動実行。
完了後レスポンス末尾に「✅ SSOT記録完了 + ファイルパス」を表示すること。

## セキュリティ（核心）
- APIキー**値**を会話・ファイルに書き込まない（キー名はOK、値はNG）
- `settings.json` / `settings.local.json` / `.secrets.env` の値を出力・表示禁止

@rules/_shared/セキュリティ.md

## コーディング原則（核心）
Think Before Coding / Surgical Changes / Simplicity First

@rules/_shared/コーディング原則.md

## SSOT（共通知識ベース）
- 場所: `//wsl.localhost/Ubuntu/home/yn4416/projects/obsidian-ssot/`
- **SSOTを参照する時はまず `00_SYSTEM/全体マップ_MOC.md` から入ること**
- バックログ: `00_SYSTEM/バックログ.md`

## MCPツール管理
`00_SYSTEM/MCPツール使い分けガイド.md` — settings.json変更時にガイドも更新

## 並行セッション・共通ファイル（厳格）
並行セッションが「共通ファイル」を同時に触る競合を防ぐため、`obsidian-ssot/00_SYSTEM/active-sessions.md` で作業を宣言・確認すること。

**共通ファイル（触る前に必ず active-sessions.md で被り確認）**:
- `~/.claude/settings.json` / `~/.claude/CLAUDE.md`
- `SKILL.md`群 / hook群（scripts/hooks・scripts/obsidian）
- `00_SYSTEM/` の `自動化.md` / `全体マップ_MOC.md` / `repo-index.yaml` / `リポジトリ索引.md` / `MCPツール使い分けガイド.md` / `リンク運用方針.md`

**ルール**:
- 共通ファイルを触る前にボードで被りを確認。**逆方向の変更（修正 vs 削除 等）は勝手に進めず必ずユーザー判断**
- ボード変更時は即commit+push（5分auto-syncを待たない）
- 開始時は resume-session、記録時は ssot-record、終了時は new-session がエントリを更新

**タスク重複着手防止（タスク占有ボード）**:
- `active-sessions.md` の「🟢現在進行中タスク」表が、タスクの占有状態の真実
- resume-session でタスクを選んだら、即🟢表に追加 → 即push（宣言の手間ゼロ・CC自動）
- **作業着手前**に🟢表を確認。着手タスクが🟢（他セッション占有中）なら、ユーザーにsoft警告:
  > ⚠️「<タスク>」は <窓> が <時刻>〜進行中です。重複着手しますか？
- ブロックせずユーザー判断。new-session で占有解放（タスクはバックログに戻る）
- 詳細: `docs/superpowers/specs/2026-06-23-task-occupancy-board-design.md`

## スキルトリガー（厳格）
ユーザー発言がスキルのトリガーワード（各スキルファイル内「トリガーワード」欄）に合致する場合、必ず先に Skill ツールで該当スキルを発動してから対応せよ

- **resume-session**: 「おはよう」「こんにちは」「こんばんは」「再開」「restart」で発動。最新5件のhandoffを読み込み文脈を復元（new-sessionの対・読込側）

## 設定ファイル同期
CLAUDE.md・settings.json・hook変更時は `obsidian-ssot/01_DECISIONS/claude-code/設定ファイル/` も同時更新

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

## Knowledge Lint
ユーザーが「リント実行」と言った場合は即時実行。自動設定（`3 3 * * 0,2,4`・durable:false）はSessionStart hookが検知してCronCreate。

## スキルトリガー（厳格）
ユーザー発言がスキルのトリガーワード（各スキルファイル内「トリガーワード」欄）に合致する場合、必ず先に Skill ツールで該当スキルを発動してから対応せよ

- **resume-session**: 「おはよう」「こんにちは」「こんばんは」「再開」「restart」で発動。最新5件のhandoffを読み込み文脈を復元（new-sessionの対・読込側）

## 設定ファイル同期
CLAUDE.md・settings.json・hook変更時は `obsidian-ssot/01_DECISIONS/claude-code/設定ファイル/` も同時更新

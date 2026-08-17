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
- デフォルト: 🟡[GLM-5.3]（セッション自体がGLM動作中・外部LLM呼び出し不要・不可）
- Sonnet使用: 事前ユーザー許可必須 🔵[Sonnet]

@rules/_shared/LLMルーティング.md

## glm-rate-proxy
- 経路: Claude Code → localhost:8787 → ZAI / MiniMax（SessionStart hookで自動起動）
- トラブル時: SSOT `01_DECISIONS/claude-code/` 配下を参照
- **⚠️ プロキシ操作時の警告ゲート（厳格・2026-07-03事故対策）**:
  - プロキシの**再起動・kill・設定変更**は **全Claude Code CLIセッション（並行含む）を最大数秒〜数分停止**させる
  - 実行前に**必ずユーザーへ警告し承認を取得**すること:「これからプロキシを再起動します・全セッションがN秒停止します・よろしいですか？」
  - 切替は `switch-backend.sh zai` で自救可能だが、**事故を起こさないのが先決**
  - systemd登録済みのため kill→5秒自動再起動（層1）・設定変更時も事前警告（層2）

## セッション開始バナー（必須）
最初の返答冒頭で必ず `bash /home/yn4416/.claude/scripts/session/startup-banner.sh` を実行し、出力を貼ること。

## セッションタイトル
自動生成するセッションタイトルは必ず日本語で生成すること。

## バッジ表示ルール（厳格）
**毎回のレスポンスの冒頭と末尾に必ず表示:** GLM=`🟡[GLM]` / MiniMax=`🟠[MiniMax]` / Sonnet=`🔵[Sonnet]`

## 外向き文面の実績数値は正典から（厳格）
外向き文面（応募文・経歴書・ポートフォリオ等）に実績数値を書く時は必ず `obsidian-ssot/40_CAREER/01_ドキュメント/ポートフォリオ数値マスター.md` をその場で確認（memory・記憶の概数は禁止・2026-08-15）。

## 説明・報告時の平易な解説併記（厳格・2026-07-23 memory昇格）
報告・要約・完了通知・設計判断の提示・選択肢提示・リスク説明など「ユーザーが理解して判断・承認する必要がある場面」では、専門的な説明に**加えて**、素人でもわかる平易な解説を**必ず併記**すること。専門用語を羅列した「要約」は情報の羅列でしかなく、**理解できないまま承認・判断させる危険**がある。

- **並び順**: 専門説明 → その後に平易な解説（見出し例: `💡 一言でいうと` / `📖 かみ砕くと`）
- **専門用語を日常言葉に翻訳**: 「セッション」→「タブ」、「cron」→「定期実行の予約」、「物理分離」→「別々のファイルに分ける」等・比喩・一般例を積極使用
- **専門説明は残す**（学習・成長のため・削らない）・**長くなることを許容**（簡潔さより伝わることを優先）
- **対象外**: 単発のコマンド実行・短い応答・純粋な事実確認（冗長回避）
- **確認ゲートは設けない**: 平易な解説を「出す」だけでOK・「理解できましたか？」等は押し付けがましいので聞かない（成果報告→次へ）

## タスク切り替え時の記録（厳格）
新しいトピックに移る前に必ず実行。「後で書く」禁止。
**必ず `ssot-record` スキルを Skill ツールで発動すること（手動 Write 絶対禁止・PreToolUse hook がブロックします）**。

@rules/_shared/記録.md

## SSOT記録は ssot-record スキル経由のみ（手動Write禁止・厳格）
タスク完了・トピック区切りで記録すべき内容が生じたら、**自発的・自動的に `ssot-record` スキルを発動**（ユーザーが「記録して」と言わなくても・`[SSOT-RECORD-TRIGGER]` 等のトリガー也不要）。
- ❌ **手動 Write/Edit での `01_DECISIONS/` 作成は PreToolUse hook(`enforce-ssot-record.sh`)がブロック**（`/tmp/ssot-record-active` フラグ時のみ許可＝スキル経由のみ通る）
- ✅ ssot-record スキルが frontmatter・`_INDEX.md`・`自動化.md`・日記・CCガイド の連携更新を機械的に担保（手動だと抜け漏れが出る）
- `[SSOT-RECORD-TRIGGER]` + record-decision 機構は**廃止**（ssot-record スキルに一本化・2026-07-03）

## セキュリティ（核心）
- APIキー**値**を会話・ファイルに書き込まない（キー名はOK、値はNG）
- `settings.json` / `settings.local.json` / `.secrets.env` の値を出力・表示禁止

@rules/_shared/セキュリティ.md

## コーディング原則（核心）
Think Before Coding / Surgical Changes / Simplicity First

@rules/_shared/コーディング原則.md

## LLMサボりバイアス防止（核心・厳格・2026-07-26 Phase0）
LLM（ホスト自身含む）のサボり（省略/楽観/迎合/検証回避）を構造化出力と機械的検証で封じる。語彙検知・自己申告は無効。

@rules/_shared/LLMサボりバイアス防止.md

## SSOT（共通知識ベース）
- 場所: `//wsl.localhost/Ubuntu/home/yn4416/projects/obsidian-ssot/`
- **SSOTを参照する時はまず `00_SYSTEM/全体マップ_MOC.md` から入ること**
- バックログ: `00_SYSTEM/バックログ.md`
- **memory過信禁止・SSOT正典優先**: 記録前に自問→「能力・方針・構造か?」→`00_SYSTEM` / 「なぜそう決めたか理由あるか?」→`01_DECISIONS` / 「私的失敗の直し方か?」→memory。memoryは毎回読まれるが個人FB専用・永久保存版は00_SYSTEM正典へ。ユーザー指摘を待たず自ら判定（2026-07-24 e36d引継ぎ・Gemini+MiniMaxレビュー反映）。

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
- **commit前は必ず pre-commit hook の stage 内容出力を見る**（並行セッションの他タブ作業ファイル巻き込み検知・2026-07-25 導入）。`git add -A`/`git add .` は原則使わず**特定ファイル指定**。配備済み: claude-config/NexusCore/reserve-optimizer は `.githooks/pre-commit`・obsidian-ssot は `.pre-commit-config.yaml`(local hook)。10件超で警告。**他タブ🟢セッションがある時は特に注意**
- 開始時は resume-session、記録時は ssot-record、終了時は new-session がエントリを更新

**タスク重複着手防止（タスク占有ボード）**:
- `active-sessions.md` の「セッション状態」表（状態列🟢/✅・単一表）が、タスクの占有状態の真実
- resume-session でタスクを選んだら、即セッション状態表に🟢行追加 → 即push（宣言の手間ゼロ・CC自動）
- **作業着手前**に🟢行を確認。着手タスクが🟢（他セッション占有中）なら、ユーザーにsoft警告:
  > ⚠️「<タスク>」は <窓> が <時刻>〜進行中です。重複着手しますか？
- ブロックせずユーザー判断。new-session で占有解放（タスクはバックログに戻る）
- 詳細: `docs/superpowers/specs/2026-06-23-task-occupancy-board-design.md`

## スキルトリガー（厳格）
ユーザー発言がスキルのトリガーワード（各スキルファイル内「トリガーワード」欄）に合致する場合、必ず先に Skill ツールで該当スキルを発動してから対応せよ

- **resume-session**: 「おはよう」「こんにちは」「こんばんは」「再開」「restart」で発動。最新5件のhandoffを読み込み文脈を復元（new-sessionの対・読込側）

## 設定ファイル同期
CLAUDE.md・settings.json・hook変更時は `obsidian-ssot/01_DECISIONS/claude-code/設定ファイル/` も同時更新

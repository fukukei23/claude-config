# Claude Code - CLI Edition (WSL2)

> **対象環境**: WSL2 Ubuntu Claude Code CLI / 全環境共通設定（LLMルーティングのSSOT）

## 環境
- WSL2 Ubuntu / ホーム: //wsl.localhost/Ubuntu/home/yn4416/
- タイムアウト: 10分。長時間タスクは分割
- **注意**: シェルの $HOME は /c/Users/yn441 に解決されるため、WSLファイルへのアクセスは必ず `//wsl.localhost/Ubuntu/home/yn4416/` プレフィックスを使うこと
- **シークレット管理**: `~/.secrets.env` に一元化。プロジェクトごとの `.env` は作成しない（`.env.example` のみ残す）

## 基本ルール
- 丁寧な日本語で回答
- 詳細はSSOT共通ルールを参照: `00_SYSTEM/共通ルール/ルール.md`

## LLM利用ポリシー
- メイン: 🟡[GLM-5.1]（glm_ask経由）
- フォールバック: 🟠[MiniMax]（minimax_ask経由）— GLM失敗時・大量処理用
- Sonnet使用は事前ユーザー許可必須: 🔵[Sonnet]
- **MiniMax自動委譲**: 大量処理タスクはdelegate-to-minimax skillに従いMiniMaxに自動委譲
- 詳細: `00_SYSTEM/共通ルール/LLMルーティング.md`

## glm-rate-proxy（ローカルプロキシ）
- **場所**: `~/.claude/scripts/glm-rate-proxy/`（SessionStart hook で自動起動）
- **経路**: Claude Code → localhost:8787 → ZAI / MiniMax
- **ピーク時間帯(15-19時)**: MiniMaxに強制ルーティング（GLM消費3倍防止）
- **エラー時**: 429/500/502/タイムアウト → 自動でMiniMaxにフォールバック
- **ステータス確認**: `curl -s http://127.0.0.1:8787/proxy/status | python3 -m json.tool`
- **トラブル時**: Memory `glm-rate-proxy.md` 参照

## セッション開始バナー（必須）
最初の返答冒頭で必ず `wsl bash -c "bash /home/yn4416/.claude/scripts/session/startup-banner.sh"` を実行し、その出力をそのまま貼ること。

## セッションタイトル
自動生成するセッションタイトルは必ず日本語で生成すること。

## バッジ表示ルール（厳格）
**毎回のレスポンスの冒頭と末尾に必ず表示:** GLM=`🟡[GLM]` / MiniMax=`🟠[MiniMax]` / Sonnet=`🔵[Sonnet]`

## タスク切り替え時の記録（厳格）
- **手順詳細**: `00_SYSTEM/共通ルール/記録手順.md` — Steps 1-7の完全な手順
- **概要**: 新しいトピックに移る前に必ず実行（SSOT履歴→日記→MOC→リンク）
- 「後で書く」禁止。記録前に次のタスクに移行禁止

## SSOT自動記録（git commit連動）
**Bashツール実行結果に `[SSOT-RECORD-TRIGGER]` が含まれていたら、必ず以下を即座に実行すること:**
1. `record-decision` スキルを自動実行（ユーザーが「記録して」と言わなくてよい）
2. コミットメッセージとプロジェクト名からSSOT決定ファイル・日記を自動作成
3. レスポンスの**末尾**に必ず以下を表示:
   ```
   ✅ SSOT記録完了
   - 決定ファイル: 01_DECISIONS/<project>/YYYY-MM-DD_<内容>.md
   - 日記: 10_DAILY/YYYY-MM-DD.md
   ```
4. これはユーザーへの「記録しました」報告であり、省略厳禁

## セキュリティ
- APIキー値を会話・ファイルに書き込まない（キー名はOK、値はNG）
- 詳細ポリシー: `01_DECISIONS/claude-code/参考資料/シークレット管理ポリシー.md`

## コーディング原則
- Think Before Coding / Surgical Changes / Simplicity First
- 詳細: `01_DECISIONS/claude-code/参考資料/Karpathy-コーディングガイドライン.md`

## ブランチ運用
- **常にmainに直接コミット・push**。featureブランチ禁止（CI用一時ブランチのみ例外）

## 設定ファイル同期
- `~/.claude/CLAUDE.md` や `settings.json` 変更時は `obsidian-ssot/01_DECISIONS/claude-code/設定ファイル/` の対応コピーも同時更新

## SSOT（共通知識ベース）
- 場所: `//wsl.localhost/Ubuntu/home/yn4416/projects/obsidian-ssot/`
- **全体マップ（MOC）**: `00_SYSTEM/全体マップ_MOC.md` — 全トピックへの入口
- **バックログ**: `00_SYSTEM/バックログ.md` — 未完了タスク（SessionStartで自動読み込み）

## ユーザープロファイル
- 40代中盤、非IT公務員、Python/TS中心に20+プロジェクトGitHub公開
- コードは読めない素人。専門用語は初出時に説明。結論ファースト
- 詳細: `00_SYSTEM/プロフィール/自己紹介.md`
- **⚠️ obsidian-ssotはパブリック化禁止**

## MCPツール管理
- **ガイド**: `00_SYSTEM/MCPツール使い分けガイド.md` — settings.json変更時にガイドも更新

## Knowledge Lint
- 詳細: `01_DECISIONS/claude-code/2026-05-26_ナレッジリント自動化システム.md`
- SessionStart hookが未設定を検知 → CronCreateで自動設定（durable:false, `3 3 * * 0,2,4`）
- ユーザーが「リント実行」と言った場合は即時実行

## 完了通知
- 詳細: `01_DECISIONS/claude-code/2026-05-26_完了通知設定.md`

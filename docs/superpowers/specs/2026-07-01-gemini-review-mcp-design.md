# Gemini Review MCP Server — 設計

- date: 2026-07-01
- status: approved (brainstorming + MiniMax review reflected)
- author: WSL-CLI session (GLM)
- review: MiniMax M3 (2026-07-01) — 8項反映・1項反証（モデル名実在）

## 背景・目的

- GLM/MiniMax（格安系LLM）だけで責任の重いレビュー/デバッグを任せることに不安がある
- 別ベンダーの高品質LLM を第2オピニオンとして自律ループに組み込みたい
- WSL CLI（GLM動作中）から MCP 経由で Gemini を呼び出し、レビュー/デバッグ時だけ担当させる
- 「逆MCP」: GLM が Gemini を"道具"として呼ぶ構成（既存 `glm-mcp-server.py` / `minimax-mcp-server.py` と同じパターン）

## 決定事項

| 項目 | 決定 |
|---|---|
| 第2LLM | **Gemini**（完全無料・Google AI Studio） |
| API key | `GEMINI_API_KEY` 所持済み・**ローテーション必須（実装前完了・会話露出のため）**・`.secrets.env` 追加登録・chmod 600 確認 |
| デフォルトモデル | `gemini-2.5-pro`（安定版・無料枠寬大） |
| モデル切替 | `model` 引数で `gemini-3.1-pro-preview` / `gemini-3.5-flash` 等に切替可（**preview は許可ゲート後述**） |
| 発動タイミング | **手動のみ先行**（dev-cycle フェーズ2 自動連携はバックログ） |
| ポリシー | 「無料＝無制限」撤回・**「重大度×採用率」基準**（後述ポリシー節） |

### LLM 選定の根拠（調査済み）

- Gemini vs DeepSeek V4（2026-07）: コード品質は DeepSeek が上（SWE-bench 80.6% vs Gemini 3.1 Pro 69-70%）だが、**完全無料（チャージ不要・1,500 RPD）**で安定なのは Gemini のみ
- 第2オピニオン多様性: ベース GLM（中国系）に対し Gemini（米国・Google）は異質で真の第2の目（DeepSeek は GLM と同系統で盲点共有リスク）
- **利用可能モデルを実機確認**（`v1beta/models`・2026-07-01）: `gemini-2.5-pro`(stable), `gemini-3.1-pro-preview`, `gemini-3.5-flash` 等すべて `generateContent` 対応 ※MiniMaxレビューで「実在しない」と指摘されたが実機取得で実在確認・反証

## アーキテクチャ

```
Claude Code CLI (🟡GLM動作中)
   ↓ MCP tool call: review_with_gemini(code, focus, model?)
gemini-mcp-server.py  [新設・glm-mcp-server.py 構造踏襲 + Gemini固有制約]
   ↓ urllib REST (generativelanguage.googleapis.com/v1beta)
Gemini API (gemini-2.5-pro)
   ↓ レビュー結果（構造化テキスト）
CLI に返却 → GLM が指摘を統合して判断（衝突時はユーザーエスカレ）
```

## コンポーネント

### 1. `scripts/mcp/gemini-mcp-server.py`（新規）

`glm-mcp-server.py` の**構造**（`_load_key`・`call_*` 関数・ステータス記録）を踏襲しつつ、**Gemini 固有の制約**（REST形式・safety filter・トークン上限）を正面扱い:

- `_load_key()`: 環境変数 `GEMINI_API_KEY` → `~/.secrets.env` フォールバック（glm-mcp と同じ2段階・env優先）
- `call_gemini(prompt, model="gemini-2.5-pro", max_tokens=4000)`:
  - REST `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
  - ペイロード: `{contents:[{role:user,parts:[{text:prompt}]}], generationConfig:{maxOutputTokens}}`
  - **入力長上限**: code 引数が上限（目安: トークン換算 8k相当・文字数で約24k）超過時は切り詰め＋警告
  - **safety filter ハンドリング**: `promptFeedback.blockReason` / `candidates[0].finishReason=SAFETY` 検出時は「safety block」エラー返却（GLM が代替判断）
  - **atomic write**: `/tmp/llm-last-used.txt` はテンポラリファイル→rename で書出（並列競合回避）・`💚 Gemini-2.5-Pro` 記録（glm-mcp の `🟡 GLM-5.1` と同形式・ステータスライン連動）
- MCP サーバーループ（JSON-RPC over stdio）: `tools/list`・`tools/call` ハンドラ

### 2. MCP ツール `review_with_gemini`

```
入力:
  code (string, required)     — レビュー対象のコード/差分（上限あり・超過時切り詰め）
  focus (string, optional)    — "bug" / "security" / "performance" / "readability" / "all"(default)
  model (string, optional)    — default "gemini-2.5-pro"（preview 指定は許可ゲットリガー）

出力:
  Gemini が生成したレビュー（指摘リスト・重要度・修正提案の構造化テキスト）
  ※safety block / 429 / エラー時は構造化エラーメッセージ
```

プロンプトは「コードレビュー特化」のシステム指示を組み込み（観点別・重要度付き・日本語出力）。

### 3. `scripts/mcp/start-gemini-mcp.sh`（新規）

`start-glm-mcp.sh` と同形式の起動スクリプト。

### 4. `settings.json` の `mcpServers.gemini` 追加（★共通ファイル）

```json
"gemini": {
  "command": "bash",
  "args": ["-c", "~/.claude/scripts/mcp/start-gemini-mcp.sh"]
}
```
※変更前に **検証手順**（後述）を実施・`active-sessions.md` で被り確認（settings.json は共通ファイル9種の1番目）

## 第2オピニオン統合手順（MiniMax 3-2 指摘対応）

- **フィードバックプロンプトテンプレ**: Gemini 出力を GLM に渡す際の定型プロンプト（「以下は Gemini による第2オピニオンです。指摘を検証し、採用/却下を判断せよ。根拠を示せ」）
- **指摘衝突時のエスカレーション**: GLM と Gemini の指摘が重大点で矛盾する場合（例: 片方が「安全」・片方が「脆弱」）は **ユーザーにエスカレ**（自動採用しない）
- dev-cycle 連携時もこの統合手順を維持（バックログだが設計は共有）

## エラー処理（MiniMax 4-4 / 2-2 指摘対応）

| ケース | 挙動 |
|---|---|
| API key 未設定 | "Error: GEMINI_API_KEY が設定されていません"（glm-mcp 同様） |
| **safety filter ブロック** | `blockReason`/`finishReason=SAFETY` 検出時・「safety block（内容がセンシティブ判定）」エラー返却（GLM代替判断） |
| **429 rate limit** | **バックオフ再試行（1-2回・指数）**→だめならエラーメッセージ（GLM代替判断・無料枠超過示唆） |
| 入力長超過 | 切り詰め＋警告メッセージ |
| ネットワークタイムアウト | upstream_timeout・タイムアウトメッセージ |
| JSON パース失敗 | Gemini の生テキストをそのまま返却 |
| preview モデルの不安定 | default は stable(2.5-pro)・preview 利用は許可ゲート |

## ポリシー（MiniMax 3-1 / 2-3 指摘対応）

- **「無料＝無制限」撤回**: Sonnet 許可制の本質は「コスト」でなく「出力品質と責任範囲」
- **許可制判定基準 = 「重大度 × 採用率」**:
  - 軽微レビュー（読みやすさ・typo 等の参考意見）→ Gemini 自由呼出可
  - **重大バグの最終レビュー**（セキュリティ・認証・データ移行 等 Tier1 領域）→ **事前ユーザー許可必須**（Sonnet 許可制と同一閾値）
- **preview モデル利用**: preview（3.1-pro-preview 等）は重大用途で**許可ゲート**（安定性劣るため・stable 以外は人間承認）
- **第2オピニオンの位置づけ**: Gemini 指摘は「参考」・最終判断は GLM・衝突時はユーザーエスカレ（前述統合手順）

## settings.json 変更の検証手順（MiniMax 4-1 指摘対応）

実装時・`mcpServers.gemini` 追加前に以下を完了:

1. **バックアップ**: 既存 settings.json をコピー（`settings.json.bak-YYYYMMDD`）
2. **stdio 競合確認**: 既存 `glm` / `minimax` MCP と transport(stdio)・起動順序が衝突しないか確認
3. **env 解決順序テスト**: `GEMINI_API_KEY` の env / `.secrets.env` 解決が既存 `GLM_API_KEY` / `MINIMAX_API_KEY` と干渉しないか確認
4. **active-sessions 被り確認**: settings.json 触る他セッションがないか（現在: Win-ssot-record 11:32🟢 は SKILL.md 系・settings.json 非接触想定）

## テスト（TDD）

`scripts/mcp/test_gemini_mcp_server.py`:

- `_load_key()`: env 優先→`.secrets.env` フォールバック・**古い key 残留時の env 優先**ケース（MiniMax 4-2）
- `call_gemini()`: urllib モック・ペイロード検証・model 切替・**入力長上限・切り詰め**・**safety block 検出**
- MCP ツール定義: `tools/list` レスポンス形状
- `review_with_gemini`: focus/model パラメータのプロンプト反映・**preview 指定時の許可ゲート**
- エラーケース: key 未設定・safety block・429（バックオフ）・タイムアウト
- `/tmp` atomic write: 並列書き込み競合テスト
- **env 優先順位明示**（MiniMax 4-2）・実APIは `@pytest.mark.integration`（手動・CI対象外・失敗時通知先=日記）

## 受け入れ基準

- [ ] `gemini-mcp-server.py` が `glm-mcp-server.py` と同等の構造で Gemini 固有制約付きで動作
- [ ] `review_with_gemini` ツールが CLI から呼べる
- [ ] default 2.5-pro でレビューが返る・model 引数で切替可（preview は許可ゲート）
- [ ] `/tmp/llm-last-used.txt` に atomic write で `💚 Gemini` 記録（ステータスライン連動）
- [ ] エラー処理: key 未設定 / **safety block** / **429バックオフ** / 入力長超過 が適切
- [ ] 第2オピニオン統合手順（フィードバックテンプレ・衝突時エスカレ）が実装/文書化
- [ ] テストが PASS（モックベース・env優先/atomic write 含む）
- [ ] `GEMINI_API_KEY` ローテーション完了後・`.secrets.env` 登録（chmod 600）
- [ ] settings.json 追加前に検証手順（バックアップ/stdio競合/env解決）完了

## バックログ（後回し・明記）

- **dev-cycle フェーズ2 自動連携**: `dev-cycle/SKILL.md`（共通ファイル）のフェーズ2「コードレビュー v3」に Gemini 呼出を組み込む。ユーザー当初目的「自律ループに組み込み」の完遂。手動実装の動作確認後に別タスク化

## セキュリティ（MiniMax 2-1 指摘対応）

- brainstorming 中に `GEMINI_API_KEY` 値が会話露出（echo パターン誤り）。**実装前に必ずローテーション（再発行）完了**（「推奨」でなく「必須」）
- 新 key を `.secrets.env` に登録・**chmod 600 確認**・`.gitignore` 対象確認（`.secrets.env` は既に git 管理外のはず・実装時確認）
- キー確認は `[ -n "$GEMINI_API_KEY" ] && echo set` 形式のみ（値を出さない）
- **使用量モニタリング**: Google AI Studio console で異常使用量（流出 key の悪用）を定期確認

## MiniMax レビュー反映メモ（2026-07-01）

- 採用: 2-1(ローテ必須化) / 2-2(入力長上限・バックオフ) / 2-3(preview許可ゲート) / 3-1(許可制基準再定義) / 3-2(統合手順) / 4-1(settings.json検証) / 4-2(env優先テスト) / 4-3(atomic write) / 4-4(safety block) / 1-2(Gemini固有制約明示)
- 反証: 1-3(モデル名実在・実機確認済み) / 1-1(v1beta現行動作確認・SDK移行は将来留意)

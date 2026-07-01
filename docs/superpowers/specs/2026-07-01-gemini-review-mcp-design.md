# Gemini Review MCP Server — 設計

- date: 2026-07-01
- status: approved (brainstorming)
- author: WSL-CLI session (GLM)

## 背景・目的

- GLM/MiniMax（格安系LLM）だけで責任の重いレビュー/デバッグを任せることに不安がある
- 別ベンダーの高品質LLM を第2オピニオンとして自律ループに組み込みたい
- WSL CLI（GLM動作中）から MCP 経由で Gemini を呼び出し、レビュー/デバッグ時だけ担当させる
- いわゆる「逆MCP」: GLM が Gemini を"道具"として呼ぶ構成（既存の `glm-mcp-server.py` / `minimax-mcp-server.py` と同じパターン）

## 決定事項

| 項目 | 決定 |
|---|---|
| 第2LLM | **Gemini**（完全無料・Google AI Studio） |
| API key | `GEMINI_API_KEY` 所持済み（`.secrets.env` に追加登録必要・⚠️ローテーション推奨：brainstorming中に誤って会話露出） |
| デフォルトモデル | `gemini-2.5-pro`（安定版・無料枠寬大） |
| モデル切替 | `model` 引数で `gemini-3.1-pro-preview` / `gemini-3.5-flash` 等に切替可 |
| 発動タイミング | **手動のみ先行**（dev-cycle フェーズ2 自動連携はバックログ明記） |
| ポリシー | Gemini は無料・GLM/MiniMax と同格の外部LLM → 「Sonnet 使用＝事前許可必須」の対象外（自由呼出可） |

### LLM 選定の根拠（調査済み）

- Gemini vs DeepSeek V4（2026-07）: コード品質は DeepSeek が上（SWE-bench 80.6% vs Gemini 3.1 Pro 69-70%）だが、**完全無料（チャージ不要・1,500 RPD）** で安定なのは Gemini のみ
- 第2オピニオンとしての多様性: ベースが GLM（中国系）に対し Gemini（米国・Google）は異質で真の第2の目になりうる（DeepSeek は GLM と同系統で盲点を共有するリスク）
- 利用可能モデルを実機確認（`v1beta/models`）: `gemini-2.5-pro`(stable), `gemini-3.1-pro-preview`, `gemini-3.5-flash` 等すべて `generateContent` 対応

## アーキテクチャ

```
Claude Code CLI (🟡GLM動作中)
   ↓ MCP tool call: review_with_gemini(code, focus, model?)
gemini-mcp-server.py  [新設・glm-mcp-server.py 踏襲]
   ↓ urllib REST (generativelanguage.googleapis.com/v1beta)
Gemini API (gemini-2.5-pro)
   ↓ レビュー結果（構造化テキスト）
CLI に返却 → GLM が指摘を統合して判断
```

## コンポーネント

### 1. `scripts/mcp/gemini-mcp-server.py`（新規）

`glm-mcp-server.py` の構造を踏襲（urllib・外部SDK不要・統一性）:

- `_load_key()`: 環境変数 `GEMINI_API_KEY` → `~/.secrets.env` フォールバック（glm-mcp と同じ2段階）
- `call_gemini(prompt, model="gemini-2.5-pro", max_tokens=4000)`:
  - REST `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
  - ペイロード: `{contents: [{role:user, parts:[{text:prompt}]}], generationConfig:{max_output_tokens}}`
  - `/tmp/llm-last-used.txt` に `💚 Gemini-2.5-Pro` 記録（ステータスライン連動・glm-mcp の `🟡 GLM-5.1` と同形式）
- MCP サーバーループ（JSON-RPC over stdio）: `tools/list`・`tools/call` ハンドラ

### 2. MCP ツール `review_with_gemini`

```
入力:
  code (string, required)     — レビュー対象のコード/差分
  focus (string, optional)    — 観点: "bug" / "security" / "performance" / "readability" / "all"(default)
  model (string, optional)    — default "gemini-2.5-pro"

出力:
  Gemini が生成したレビュー（指摘リスト・重要度・修正提案を含む構造化テキスト）
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
※実装時に `active-sessions.md` で被り確認（settings.json は共通ファイル9種の1番目）

## データフロー

1. CLI(GLM) が `review_with_gemini` ツール呼出（コード+観点を渡す）
2. `gemini-mcp-server.py` が Gemini API にコード+観点+システム指示を送信
3. Gemini がレビュー生成（指摘・重要度・提案）
4. server が結果を CLI に返却
5. GLM が Gemini の指摘を統合し、最終判断・修正を担当

## エラー処理

| ケース | 挙動 |
|---|---|
| API key 未設定 | "Error: GEMINI_API_KEY が設定されていません"（glm-mcp 同様） |
| 429 rate limit | エラーメッセージ返却（GLM が代替判断・無料枠超過示唆） |
| ネットワークタイムアウト | upstream_timeout 設定・タイムアウトメッセージ |
| JSON パース失敗 | Gemini の生テキストをそのまま返却 |
| preview モデルの不安定 | default は stable(2.5-pro) で回避 |

## テスト（TDD）

`scripts/mcp/test_gemini_mcp_server.py`:

- `_load_key()`: 環境変数優先→`.secrets.env` フォールバック（glm-mcp テストがあれば踏襲）
- `call_gemini()`: urllib をモック・ペイロード検証・モデル切替確認
- MCP ツール定義: `tools/list` レスポンス形状
- `review_with_gemini`: focus/model パラメータのプロンプト反映
- エラーケース: key 未設定・429・タイムアウト
- 実API呼出は `@pytest.mark.integration`（手動・CI対象外）

## 受け入れ基準

- [ ] `gemini-mcp-server.py` が `glm-mcp-server.py` と同等の構造で動作する
- [ ] `review_with_gemini` ツールが CLI から呼べる
- [ ] default 2.5-pro でレビューが返る・model 引数で切替可
- [ ] `/tmp/llm-last-used.txt` に `💚 Gemini` が記録される（ステータスライン連動）
- [ ] エラー処理（key 未設定/429）が適切
- [ ] テストが PASS（モックベース）
- [ ] `GEMINI_API_KEY` が `.secrets.env` に登録される（ローテ後）
- [ ] settings.json に `mcpServers.gemini` 追加（被り確認済）

## ポリシー

- **Gemini は無料・GLM/MiniMax と同格の外部LLM** → 「Sonnet 使用＝事前許可必須」ルールの対象外。GLM が自律的にレビュー時呼出可能（dev-cycle 連携時も許可ゲート不要）
- **第2オピニオンの位置づけ**: Gemini の指摘は「参考意見」・最終判断は GLM（人間の承認ゲートは dev-cycle の既存仕組み維持）

## バックログ（後回し・明記）

- **dev-cycle フェーズ2 自動連携**: `dev-cycle/SKILL.md`（共通ファイル）のフェーズ2「コードレビュー v3」に Gemini 呼出を組み込む。ユーザー当初目的「自律ループに組み込み」の完遂。手動実装の動作確認後に別タスク化

## セキュリティ注意

- brainstorming 中に `GEMINI_API_KEY` 値が会話に露出した（echo パターン誤り）。**実装前に必ずローテーション（再発行）** し、新しい key を `.secrets.env` に登録
- 実装時のキー確認は `[ -n "$GEMINI_API_KEY" ] && echo set` 形式のみ（値を出さない）

# GLM -> MiniMax フォールバック運用

## 目的
- 通常は `GLM (Z.ai)` を使い、失敗時のみ `MiniMax` に自動退避します。

## 追加ファイル
- `~/.claude/fallback-config.json`: 失敗判定、モデル割り当て、ログ設定
- `~/.claude/scripts/claude_fallback.py`: フォールバック本体
- `~/.claude/scripts/claude-fallback`: 実行ラッパー

## MiniMax 側モデル割り当て
- opus: `MiniMax-M2.7`
- sonnet: `MiniMax-M2.7-highspeed`
- haiku: `MiniMax-M2.5-highspeed`

## フォールバック判定
- フォールバック対象:
  - HTTP: `429, 500, 502, 503, 504`
  - キーワード: `timeout`, `ECONNRESET`, `ENOTFOUND`, `temporary failure` など
- フォールバック対象外:
  - HTTP: `400, 401, 403, 404, 422`
  - キーワード: `invalid api key`, `authentication`, `invalid_request_error` など

## 実行方法
```bash
chmod +x ~/.claude/scripts/claude-fallback ~/.claude/scripts/claude_fallback.py
~/.claude/scripts/claude-fallback -p "接続確認。OKのみ返して"
```

## 事前条件
- `MINIMAX_API_KEY` が環境変数に存在すること
  - 例: `~/.claude/.env` に `export MINIMAX_API_KEY=...`
  - 実行前に `source ~/.claude/.env`

## ログ
- 保存先: `~/.claude/logs/claude-fallback-YYYY-MM-DD.jsonl`
- 主な項目:
  - `provider`: `glm` or `minimax`
  - `latency_ms`
  - `exit_code`
  - `error_class`
  - `fallback_triggered`

## 段階導入・受け入れテスト
1. **正常系**: GLMが通る状態で実行し、`provider=glm` のみ記録されること
2. **疑似障害**: `--simulate-primary-failure` を付けて実行し、`provider=minimax` が記録されること
3. **設定不備**: APIキー不正時に MiniMax へ誤フォールバックしないこと（`401/403` は対象外）

```bash
source ~/.claude/.env
~/.claude/scripts/claude-fallback --simulate-primary-failure -p "疑似障害テスト。OKのみ返して"
```

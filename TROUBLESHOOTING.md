# トラブルシューティング

Claude CodeデスクトップアプリとCLIでサードパーティLLMを使う際の調査記録と正しい知識。

> **最終更新: 2026-03-31（実機検証済み）**

---

## ⚠️ 重要: 2つの環境は完全に独立している

```
C:\Users\USER\.claude\           ← デスクトップアプリが読む（Windows側）
~/.claude/  (WSL2)               ← Claude Code CLI が読む（WSL2側）
```

この2つは**別々のディレクトリ**であり、設定は共有されない。

---

## デスクトップアプリの動作（チャット・Cowork・Codeタブ全て）

### 認証の仕組み
デスクトップアプリは `C:\Users\USER\.claude\.credentials.json` のAnthropicOAuthトークンを使う。
**OAuthが存在する限り、全タブがAnthropicのSonnetに向く。変更不可。**

```json
// C:\Users\USER\.claude\.credentials.json
{
  "claudeAiOauth": {
    "accessToken": "sk-ant-oat01-...",
    "subscriptionType": "pro"
  }
}
```

### settings.json のenvセクションについて
- OAuthが存在する場合、`C:\Users\USER\.claude\settings.json` の `env` セクションは**無効**
- envセクションにBASE_URLやAPIキーを書いても使われない

### ~/.bashrc に書いても意味がない
- `echo $ANTHROPIC_BASE_URL` でURLが変わって見えても、それはシェルの表示のみ
- デスクトップアプリのAPIコールには影響しない

### .credentials.json を削除するとどうなるか
- アプリ再起動時にOAuth再認証が走り、**自動的に再作成される**
- 削除では解決しない

### 結論
デスクトップアプリでサードパーティLLMを使う方法は現時点で存在しない。
Anthropic Proサブスクリプションを使い続けるのが現実的。

---

## Cursor Claude Code CLI の動作（WSL2内）

### 認証の仕組み
CursorでClaude Code CLIを起動した場合、WSL2の `~/.claude/settings.json` を読む。
**settings.jsonのenvセクションが有効で、.credentials.jsonより優先される。**

```json
// ~/.claude/settings.json (WSL2)
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
    "ANTHROPIC_AUTH_TOKEN": "GLMのAPIキー",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "GLM-5.1"
  }
}
```

これにより GLM-5.1 / Z.AI を使える（2026-03-31 Cursorで動作確認済み）。

---

## 2環境の対応表（2026-03-31時点の最終設定）

| 環境 | バックエンド | 設定ファイル | 認証 |
|------|------------|------------|------|
| デスクトップアプリ（全タブ） | Anthropic Sonnet 4.6 | `C:\Users\USER\.claude\.credentials.json` | OAuth（Pro） |
| Cursor Claude Code CLI | GLM-5.1 (Z.AI) | `~/.claude/settings.json` (WSL2) | GLM APIキー |

---

## 調査の経緯（ハマったポイント）

### 誤解1: 「settings.jsonのenvセクションは効かない」
→ **正確には「デスクトップアプリにOAuthがある場合は効かない」**
→ CursorのCLIではsettings.json envが有効

### 誤解2: 「~/.bashrcに書けばCodeタブに効く」
→ `echo $ANTHROPIC_BASE_URL` でURLが変わって見えるが、これはシェル環境変数の表示
→ デスクトップアプリのAPIルーティングには無関係

### 誤解3: 「.credentials.jsonを消せばサードパーティLLMが使える」
→ アプリが再起動時にOAuth再認証して自動再作成する
→ 消しても意味がない

---

## MiniMax APIキーのcurlテスト

デスクトップアプリとは別に、MiniMaxのAPIが使えるか直接確認する方法：

```bash
curl -s -X POST "https://api.minimax.io/anthropic/v1/messages" \
  -H "Content-Type: application/json" \
  -H "x-api-key: あなたのMiniMaxキー" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"MiniMax-M2.7","max_tokens":30,"messages":[{"role":"user","content":"hi"}]}'
```

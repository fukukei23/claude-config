# トラブルシューティング

Claude CodeデスクトップアプリでサードパーティLLM（MiniMax・GLM等）を使う際の既知の問題と解決策。

---

## 問題1: ANTHROPIC_BASE_URLが変わらず api.anthropic.com を向く

### 症状
`echo $ANTHROPIC_BASE_URL` を実行すると `https://api.anthropic.com` が返る。
settings.json に設定してあるのに反映されない。

### 原因
**Claude Codeデスクトップアプリは `settings.json` の `env` セクションを読まない。**
アプリは `~/.claude/.credentials.json` のAnthropicのOAuthトークンを優先し、
`ANTHROPIC_BASE_URL` のデフォルト値として `https://api.anthropic.com` をハードコードする。

また、Windowsのユーザー環境変数を設定してもWSL2には届かない。

### 解決策
WSL2の `~/.bashrc` に直接環境変数を書く：

```bash
echo 'export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"' >> ~/.bashrc
echo 'export ANTHROPIC_AUTH_TOKEN="あなたのトークン"' >> ~/.bashrc
echo 'export ANTHROPIC_API_KEY="あなたのトークン"' >> ~/.bashrc
source ~/.bashrc
```

その後、Claude Codeデスクトップアプリを**完全終了→再起動**する。

### 確認方法
```bash
echo $ANTHROPIC_BASE_URL
# → https://api.minimax.io/anthropic と表示されれば成功
```

---

## 問題2: MiniMaxトークンが認証エラーになる

### 確認方法（curlで直接テスト）
```bash
curl -s -X POST "https://api.minimax.io/anthropic/v1/messages" \
  -H "Content-Type: application/json" \
  -H "x-api-key: あなたのトークン" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"MiniMax-M2.7","max_tokens":30,"messages":[{"role":"user","content":"hi"}]}'
```

レスポンスに `"model":"MiniMax-M2.7"` が含まれれば正常。

---

## 問題3: アップデート後に元に戻る

`~/.bashrc` はアップデートで上書きされない。ただし `.credentials.json` がリセットされた場合は以下を確認：

```bash
cat ~/.bashrc | grep ANTHROPIC
```

設定が消えていたら問題1の解決策を再実行する。

---

## 各タブのバックエンド対応表

| タブ | バックエンド | ~/.bashrcの影響 |
|------|------------|---------------|
| チャット | Anthropic Sonnet 4.6 | 受けない |
| Cowork | Anthropic Sonnet 4.6 | 受けない |
| コード | ~/.bashrcのBASE_URL先 | **受ける** |

---

## 現在の設定（2026-03-31時点）

| 項目 | 値 |
|------|---|
| コードタブのバックエンド | MiniMax-M2.7 |
| BASE_URL | `https://api.minimax.io/anthropic` |
| 設定ファイル | `~/.bashrc`（WSL2） |
| トークン変数 | `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_API_KEY`（両方同じ値） |

---

## GLM-5.1に切り替えたい場合

```bash
# ~/.bashrcを編集
export ANTHROPIC_BASE_URL="https://api.z.ai/api/anthropic"
export ANTHROPIC_AUTH_TOKEN="Z.AIのAPIキー"
export ANTHROPIC_API_KEY="Z.AIのAPIキー"
```

Z.AIエンドポイント: `https://api.z.ai/api/anthropic`
モデル名: `GLM-5.1`（Opus/Sonnet相当）、`GLM-4.5-Air`（Haiku相当）

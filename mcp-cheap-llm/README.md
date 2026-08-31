# Claude Code Desktop × MCP 経由で安価LLMを利用する

## 概要

Claude Code Desktopアプリ版は、OAuth Pro認証により使用モデルがSonnetに固定されており変更不可である。しかし、MCP（Model Context Protocol）サーバーとして自作Pythonスクリプトを登録することで、GLMやMiniMaxなどの安価な外部LLMをツールとして呼び出すことが可能になる。

この構成では、Claude（Sonnet）がオーケストレーターとして動作し、コード生成やドキュメント作成などの重い処理を安価なLLMに委譲することで、API利用コストを大幅に削減できる。

## 設定ファイルの全体像（Windows）

> **ポイント**: Windows版Claude Code DesktopでカスタムMCPを使う際の「本体」はこの1ファイル。

```
C:\Users\<ユーザー名>\AppData\Roaming\Claude\
├── claude_desktop_config.json   ⭐ 本体。カスタムMCPサーバーの全定義がここにある
├── Claude Extensions\           公式コネクターのバイナリ本体（新PCでは再インストール推奨）
├── extensions-installations.json 公式コネクターのインストール記録
└── Cache\, logs\, GPUCache\ ...  キャッシュ・ログ（移行不要）
```

### `claude_desktop_config.json` が本体の理由

| 項目 | 内容 |
|---|---|
| **定義内容** | カスタムMCPサーバーの起動コマンド・引数・環境変数 |
| **影響範囲** | このファイルがないとカスタムMCP（minimax/glm等）は全て動かない |
| **PC移行時** | この1ファイルを新PCにコピーするだけでカスタムMCPの定義が復元する |
| **公式コネクター** | `Claude Extensions\`にバイナリがあるが、新PCではアプリから再インストールの方が確実 |

### 内容例

```json
{
  "mcpServers": {
    "glm": {
      "command": "wsl",
      "args": ["-d", "Ubuntu", "--", "bash", "/home/<user>/.claude/scripts/start-glm-mcp.sh"]
    },
    "minimax": {
      "command": "wsl",
      "args": ["-d", "Ubuntu", "--", "bash", "/home/<user>/.claude/scripts/start-minimax-mcp.sh"]
    }
  }
}
```

---

## アーキテクチャ

```
┌─────────────────────────────────────────────┐
│         Claude Code Desktop (Sonnet)         │
│              オーケストレーター                │
└──────────┬──────────────────┬────────────────┘
           │ MCP (stdio)      │ MCP (stdio)
           ▼                  ▼
   ┌──────────────┐   ┌──────────────┐
   │  GLM MCP     │   │  MiniMax MCP │
   │  Server      │   │  Server      │
   │  (Python)    │   │  (Python)    │
   └──────┬───────┘   └──────┬───────┘
          │ HTTP              │ HTTP
          ▼                   ▼
   ┌──────────────┐   ┌──────────────┐
   │  Z.AI API    │   │  MiniMax API │
   │  (Anthropic  │   │  (Anthropic  │
   │   互換)      │   │   互換)      │
   └──────────────┘   └──────────────┘
```

- **通信方式**: MCPはstdio形式のJSON-RPC
- **API互換性**: 各LLMサービスのAnthropic互換エンドポイントを使用（`x-api-key`ヘッダーで認証）
- **プロセス構成**: Claude DesktopがWSL（Ubuntu）上のBashスクリプトを起動し、Python MCPサーバーを実行

---

## セットアップ手順

### 1. スクリプト全体像（WSL側）

`~/.claude/scripts/` 以下に用途別のスクリプトが存在する。

```
~/.claude/
├── secrets.env                      # APIキー一元管理（要 chmod 600）
├── fallback-config.json             # CLIフォールバック設定
└── scripts/
    │
    ├── [MCP本体 — Desktop版専用]
    │   ├── start-glm-mcp.sh
    │   ├── start-minimax-mcp.sh
    │   ├── start-polygon-mcp.sh
    │   ├── glm-mcp-server.py
    │   └── minimax-mcp-server.py
    │
    ├── [外部LLM直接呼び出し]
    │   ├── ask-grok.py              # Grok (xAI)、X投稿検索付き
    │   （ask-perplexity.py は PERPLEXITY_API_KEY 401のまま引退・2026-09-01）
    │   ├── ask-minimax.py
    │   （Geminiは scripts/api/gemini.py へ統合移行・2026-06-17・YouTube真正解析）
    │
    ├── [Obsidian連携]
    │   ├── load-obsidian-log.sh     # セッション開始時にログ読み込み
    │   ├── save-session-log.sh      # セッション終了時にログ書き込み
    │   └── cleanup-obsidian-timestamps.sh
    │
    ├── [Computer Use — WSL↔Windows橋渡し]
    │   ├── click.sh / click.ps1
    │   ├── hotkey.sh / hotkey.ps1
    │   ├── notify.sh / notify.ps1
    │   ├── take-screenshot.sh / take-screenshot.ps1
    │   ├── type.sh / type.ps1
    │   ├── clip-save.sh             # Win+Shift+Sのクリップボード画像保存
    │   └── monitor-screen.sh
    │
    └── [その他]
        ├── llm-status.sh            # ステータスバー表示
        ├── claude_fallback.py       # GLM→MiniMax自動切り替え
        ├── tmux-restore-5pane.sh
        └── tmux-restore-6pane.sh
```

### 2. APIキーの一元管理（secrets.env）

`~/.claude/secrets.env` を作成し、APIキーをまとめて記述する。

```env
# MCP・CLIフォールバック用（必須）
GLM_API_KEY=your_glm_api_key_here
MINIMAX_API_KEY=your_minimax_api_key_here
MASSIVE_API_KEY=your_polygon_api_key_here

# 外部LLM直接呼び出し用（使う場合のみ）
XAI_API_KEY=your_xai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
PERPLEXITY_API_KEY=your_perplexity_api_key_here
```

パーミッションを制限する（必須）。

```bash
chmod 600 ~/.claude/secrets.env
```

> **設計方針**: APIキーをスクリプトに直書きせず、`secrets.env` に一元管理することで、
> スクリプト本体をGitで安全に管理できる。

### 3. 起動スクリプトの作成

#### start-glm-mcp.sh

```bash
#!/bin/bash
set -a                          # 以降の変数を自動export（子プロセスに渡す）
source ~/.claude/secrets.env    # APIキー一元管理ファイル
set +a
exec python3 -u ~/.claude/scripts/glm-mcp-server.py
```

#### start-minimax-mcp.sh

```bash
#!/bin/bash
set -a
source ~/.claude/secrets.env
set +a
exec python3 -u ~/.claude/scripts/minimax-mcp-server.py
```

実行権限を付与する。

```bash
chmod +x ~/.claude/scripts/*.sh
```

### 4. MCPサーバー本体の実装（Python）

stdio形式のJSON-RPCサーバーとして実装する。以下はGLMサーバーの最小構成例。

```python
import os, sys, json, urllib.request

API_KEY = os.environ.get('GLM_API_KEY', '')
API_URL = 'https://api.z.ai/api/anthropic/v1/messages'
MODEL   = 'GLM-5.1'

def call_glm(prompt, max_tokens=4000):
    if not API_KEY:
        return 'Error: GLM_API_KEY が設定されていません'
    data = json.dumps({
        'model': MODEL,
        'max_tokens': max_tokens,
        'messages': [{'role': 'user', 'content': prompt}]
    }).encode()
    req = urllib.request.Request(
        API_URL, data=data,
        headers={'x-api-key': API_KEY, 'anthropic-version': '2023-06-01',
                 'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=300) as res:
        r = json.loads(res.read())
    return next((b['text'] for b in r.get('content', []) if b['type'] == 'text'), '')

TOOLS = [
    {
        'name': 'glm_ask',
        'description': 'GLM-5.1に汎用的な作業を依頼する。ClaudeのAPIトークンを消費しない。',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'prompt': {'type': 'string', 'description': 'GLMへの指示'},
                'max_tokens': {'type': 'integer', 'default': 4000}
            },
            'required': ['prompt']
        }
    }
]

def handle(req):
    method, params, rid = req.get('method'), req.get('params', {}), req.get('id')
    if method == 'initialize':
        result = {'protocolVersion': '2024-11-05', 'capabilities': {'tools': {}},
                  'serverInfo': {'name': 'glm-mcp', 'version': '1.0.0'}}
    elif method in ('notifications/initialized', 'initialized'):
        return None
    elif method == 'tools/list':
        result = {'tools': TOOLS}
    elif method == 'tools/call':
        args = params.get('arguments', {})
        text = call_glm(args['prompt'], args.get('max_tokens', 4000))
        result = {'content': [{'type': 'text', 'text': text}]}
    else:
        result = None
    return {'jsonrpc': '2.0', 'id': rid, 'result': result} if rid and result else None

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        req = json.loads(line)
        res = handle(req)
        if res:
            sys.stdout.write(json.dumps(res) + '\n')
            sys.stdout.flush()
    except Exception as e:
        if req.get('id'):
            sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': req['id'],
                'error': {'code': -32603, 'message': str(e)}}) + '\n')
            sys.stdout.flush()
```

MiniMax版は API_KEY と API_URL を差し替えるだけでよい。

```python
API_KEY = os.environ.get('MINIMAX_API_KEY', '')
API_URL = 'https://api.minimax.io/anthropic/v1/messages'
MODEL   = 'MiniMax-M2.7'
```

### 5. claude_desktop_config.jsonの設定

`%APPDATA%\Claude\claude_desktop_config.json`（Windows）を編集する。
`<user>` は実際のWSLユーザー名に置き換えること。

```json
{
  "mcpServers": {
    "glm": {
      "command": "wsl",
      "args": ["-d", "Ubuntu", "--", "bash", "/home/<user>/.claude/scripts/start-glm-mcp.sh"]
    },
    "minimax": {
      "command": "wsl",
      "args": ["-d", "Ubuntu", "--", "bash", "/home/<user>/.claude/scripts/start-minimax-mcp.sh"]
    }
  }
}
```

設定後、Claude Desktopを再起動してMCPサーバーへの接続を確立する。

---

## PC移行時の対応

### コピーするものの分類

| 対象 | 要否 | 備考 |
|---|---|---|
| `claude_desktop_config.json` | ✅ 必須 | USBなどでコピーするだけでOK |
| `~/.claude/secrets.env` (WSL) | ✅ 必須 | 暗号化して安全に転送 |
| `~/.claude/scripts/` (WSL) | ✅ 必須 | 全37スクリプト（APIキーなし、Git管理可） |
| `~/.claude/fallback-config.json` (WSL) | ✅ 必須 | CLIフォールバック設定 |
| `Claude Extensions\` | ⚠️ 任意 | 新PCで再インストールの方が確実 |
| `Cache\` `logs\` 等 | ❌ 不要 | キャッシュ・ログ類 |

### 新PCでの復元手順

1. Claude Desktop をインストール・ログイン
2. `claude_desktop_config.json` を `%APPDATA%\Claude\` に上書きコピー
3. WSL2 + Ubuntu をセットアップ
4. `~/.claude/scripts/` と `secrets.env` と `fallback-config.json` を配置
5. `chmod 600 ~/.claude/secrets.env` と `chmod +x ~/.claude/scripts/*.sh` を実行
6. Claude Desktop を再起動
7. 公式コネクター（Desktop Commander・Context7等）をアプリのマーケットプレイスから再インストール

### パス書き換えチェックリスト

新PCでユーザー名が変わった場合のみ対応。

| ファイル | 書き換え箇所 | 変更内容 |
|---|---|---|
| `claude_desktop_config.json` | args内のWSLパス | `yn441611` → `<新WSLユーザー名>` |
| `settings.json` (hooks) | commandのパス | 同上 |
| `notify.sh` | SCRIPT_PATH | `/home/yn441611/` → `/home/<新ユーザー名>/` |
| `take-screenshot.sh` | OUTPUT_PATH デフォルト | 同上 |
| `tmux-restore-*.sh` | CLAUDE変数、作業ディレクトリ | npmパスとvaultsパスを修正 |
| `load-obsidian-log.sh` | OBSIDIAN_PATH | Vault移動時は新パスに変更 |
| `save-session-log.sh` | OBSIDIAN_PATH | 同上 |
| `start-polygon-mcp.sh` | PYTHONPATH / entrypoint | `Users/USER` → `Users/<新Winユーザー名>` |

---

## ハマりポイント

### `source` だけでは子プロセスに変数が渡らない

bashで `source` した変数はシェル変数のままで、`exec` した子プロセス（Python）の環境変数には渡らない。`set -a` で自動exportが必要。

```bash
# ❌ ダメな例 — Pythonで os.environ.get('GLM_API_KEY') が空になる
source ~/.claude/secrets.env
exec python3 -u glm-mcp-server.py

# ✅ 正しい例
set -a
source ~/.claude/secrets.env
set +a
exec python3 -u glm-mcp-server.py
```

### 設定変更後にMCPプロセスが更新されない

`claude_desktop_config.json` を変更しても、起動済みのMCPプロセスには反映されない。Claude Desktopの再起動が必要。

### 401エラーの原因切り分け

| エラーメッセージ | 原因 | 対処 |
|---|---|---|
| `GLM_API_KEY が設定されていません` | 環境変数のexport漏れ | `set -a` を追加 |
| `HTTP Error 401: Unauthorized` | APIキーが無効 / 期限切れ | 各サービスで新キーを発行 |

---

## セキュリティ

| 対象 | 施策 |
|---|---|
| `secrets.env` | `chmod 600` でアクセス制限 |
| Gitリポジトリ | `.gitignore` に `secrets.env` を追加 |
| スクリプト本体（.sh / .py） | Git管理可能（APIキーを含まないため） |
| バックアップ | パスワード付きZIPまたはパスワードマネージャーに保存 |

---

## 対応サービス一覧

| サービス | モデル | APIエンドポイント | 用途 |
|---|---|---|---|
| Z.AI | GLM-5.1 | `https://api.z.ai/api/anthropic/v1/messages` | MCP / CLI主力 |
| MiniMax | MiniMax-M2.7 | `https://api.minimax.io/anthropic/v1/messages` | MCP / CLIフォールバック |
| Polygon | — | Claude Extensions経由 | MCP（公式コネクター） |
| Grok (xAI) | grok-3 | `https://api.x.ai/v1/chat/completions` | X投稿検索・直接呼び出し |
| Google Gemini | gemini-2.0-flash | Google AI API | YouTube動画分析・直接呼び出し |
| Perplexity | sonar | `https://api.perplexity.ai/chat/completions` | Web検索＋引用・直接呼び出し |

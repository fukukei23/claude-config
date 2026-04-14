# claude-mem 設定

Claude Code用の永続メモリプラグイン [claude-mem](https://github.com/thedotmack/claude-mem) の設定ファイルです。

**両環境（CLI / Desktop）にインストール済み。**

## 概要

セッションを跨いだ自動記憶機能をClaude Codeに追加します。

- **セッション操作を自動記録** → SQLite + ChromaベクトルDBに保存
- **次回セッション冒頭に自動注入** → 前回の作業文脈を即座に復元
- **Webビューアー** → `http://localhost:37777` でリアルタイム確認

## 2環境のインストール状況

### WSL2 CLI版（GLM-5.1）

| 項目 | 内容 |
|------|------|
| **インストール日** | 2026-04-14（再インストール成功） |
| **インストール方法** | `npx claude-mem install`（v12.1.0） |
| **LLM** | GLM-5.1 via Z.ai proxy |
| **データ場所** | `/home/yn441611/.claude-mem/` |
| **要約API消費** | Z.ai経由でClaude APIトークン消費 |
| **Bun** | v1.3.11（事前導入済み） |
| **Hooks** | 6ライフサイクル自動登録済み |

#### CLI版のコスト影響
claude-memの要約処理は `CLAUDE_MEM_CLAUDE_AUTH_METHOD: "cli"` で動作。
Z.ai proxy経由のため、**Z.aiのトークン枠を消費**する。

### Windows Desktop版（Claude Sonnet OAuth）

| 項目 | 内容 |
|------|------|
| **インストール日** | 2026-04-13（初回）→ 2026-04-14（push） |
| **インストール方法** | `/plugin marketplace add thedotmack/claude-mem` |
| **LLM** | Claude Sonnet（Anthropic OAuth） |
| **データ場所** | `C:\Users\USER\.claude-mem\` |
| **要約API消費** | Claude Codeサブスク枠内（追加費用ゼロ） |

#### Desktop版の推奨設定変更（コスト最適化）
サブスク枠を節約するため、要約モデルをHaikuに変更:

```
CLAUDE_MEM_MODEL: "claude-haiku-4-5"       ← Sonnet→Haiku
CLAUDE_MEM_TIER_SIMPLE_MODEL: "haiku"       ← 簡単な観察
CLAUDE_MEM_TIER_SUMMARY_MODEL: "haiku"      ← サマリーもHaiku
```

## インストール手順

### WSL2 CLI版

```bash
# 1. Bun をインストール（未インストールの場合）
npm install -g bun

# 2. claude-mem をインストール
npx claude-mem install

# 3. 設定ファイルを配置
cp settings.json ~/.claude-mem/settings.json

# 4. Worker 起動確認
curl http://localhost:37777/api/health
```

### Windows Desktop版

```
# Claude Code内で実行:
/plugin marketplace add thedotmack/claude-mem
/plugin install claude-mem

# もし失敗した場合:
# claude.exe plugin install claude-mem@thedotmack
```

## 設定内容（settings.json）

| キー | 値 | 説明 |
|------|-----|------|
| `CLAUDE_MEM_PROVIDER` | `claude` | Claude Code CLIを使用 |
| `CLAUDE_MEM_CLAUDE_AUTH_METHOD` | `cli` | サブスク課金（追加費用ゼロ） |
| `CLAUDE_MEM_MODEL` | `claude-haiku-4-5` | 最安モデルを使用（コスト最適化） |
| `CLAUDE_MEM_TIER_SIMPLE_MODEL` | `haiku` | 簡単な観察はHaiku |
| `CLAUDE_MEM_TIER_SUMMARY_MODEL` | `haiku` | サマリーもHaiku |
| `CLAUDE_MEM_CHROMA_ENABLED` | `true` | ベクトル検索を有効化 |
| `CLAUDE_MEM_WORKER_PORT` | `37777` | Webビューアーポート |

## 3層メモリ設計（既存システムとの役割分担）

| 層 | システム | 担当 | 更新方法 |
|---|---------|------|---------|
| **第1層** | claude-mem | 操作ログ層 — **何をしたか** | 完全自動（フック駆動） |
| **第2層** | Auto Memory / MEMORY.md | 判断・設定層 — **どう扱うか** | 半自動（LLMが記録） |
| **第3層** | SSOT / Obsidian | 知識・決定層 — **なぜそうしたか** | 手動（構造化記録） |

### 禁止事項
- SSOTの内容をclaude-memに二重書き込みしない
- claude-memの検索結果をSSOTにそのまま転記しない
- 第2層と第3層の記録内容は重複させない

## 注意事項

- GLM APIへの直接接続は非対応（プロバイダー未実装）
- `cli`認証はClaude Code（Max等）サブスク加入が前提
- uv は Claude Code バンドル版を流用可能:
  `C:\Users\USER\AppData\Roaming\Claude\uv-runtime\uv-0.9.7-win32-x64\`
- 詳細な3層ルール: `.claude/rules/claude-mem.md`

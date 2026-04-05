# 🤖 LLM Routing & Architecture Specification

このドキュメントは、本リポジトリで管理されているClaude環境（Windowsデスクトップアプリ版およびWSL2 CLI版）における、**正確なアーキテクチャとLLMのルーティング仕組み**を定義するものです。

---

## 📋 目次
1. [システム全体のアーキテクチャ](#1-システム全体のアーキテクチャ)
2. [環境ごとの認証とベースモデル](#2-環境ごとの認証とベースモデル)
3. [MCPサーバーの役割と構成](#3-mcpサーバーの役割と構成)
4. [LLMルーティングポリシー](#4-llmルーティングポリシー)
5. [🚨 よくある誤解](#5-よくある誤解)

---

## 1. システム全体のアーキテクチャ

本システムは**「WSL2 CLI版」と「デスクトップ版」の2つの異なるアーキテクチャ**でルーティングを実行します。それぞれで設定ファイルやルーティングの仕組みが完全に異なります。

- **WSL2 CLI版**: `fallback-config.json` を読み込み、LLMプロバイダーのルーティングとフォールバックを直接制御
- **デスクトップ版**: MCPサーバー経由で `CLAUDE.md` に記述されたルールに基づきClaude自身がルーティングを判断・実行

---

## 2. 環境ごとの認証とベースモデル

### ⌨️ WSL2 CLI版
- **ベースモデル**: MiniMax（Anthropic互換API）→ GLMへ自動フォールバック
- **認証**: `~/.claude/.env`
  ```
  ANTHROPIC_AUTH_TOKEN=<GLM/Z.AIキー>
  ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic
  ```
- **フォールバック設定**: `C:\Users\USER\.claude\core\fallback-config.json`
  ```json
  {
    "fallback": {
      "primary_provider": "minimax-anthropic-compatible",
      "secondary_provider": "glm-zai",
      "fallback_on": { "http_status_codes": [429, 500, 502, 503, 504] },
      "do_not_fallback_on": { "http_status_codes": [400, 401, 403, 404, 422] }
    }
  }
  ```
  - タイムアウト・500系エラー → GLMへ自動フォールバック
  - 401/403等の認証エラー → フォールバックせずエラー返却（設定ミスとして扱う）

### 🖥️ デスクトップアプリ版（Windows）
- **ベースモデル**: Sonnet 4.6（Anthropic OAuth固定）
- **認証**: AnthropicのOAuth認証（Proプラン購読）
- **ルーティング**: `CLAUDE.md` の指示 + MCPツール呼び出し
- **主要設定ファイル**:
  - `C:\Users\USER\.claude\CLAUDE.md` ← ルーティングポリシー（AIへの指示）
  - `C:\Users\USER\AppData\Roaming\Claude\claude_desktop_config.json` ← MCPサーバー登録
- ⚠️ **`fallback-config.json` はデスクトップ版では使用されない**

---

## 3. MCPサーバーの役割と構成

デスクトップ版において、Sonnet 4.6からMiniMaxやGLMを利用するためにはMCPサーバー経由で**明示的にツールを呼び出す**必要があります。

| ツール名 | スクリプト | APIキー | 用途 |
| :--- | :--- | :--- | :--- |
| `minimax_ask` 他 | `~/.claude/scripts/minimax-mcp-server.py` | `MINIMAX_API_KEY` | MiniMaxへの問い合わせ |
| `glm_ask` 他 | `~/.claude/scripts/glm-mcp-server.py` | `GLM_API_KEY` | GLMへの問い合わせ |

**⚠️ 重要**: MCPツールは自動実行されません。`CLAUDE.md` のポリシーに従い、Claude自身が判断して呼び出します。

---

## 4. LLMルーティングポリシー

| 優先度 | モデル | 対象タスク |
| :---: | :--- | :--- |
| 🥇 第一優先 | 🟠 **MiniMax** | デフォルト。会話・調査・翻訳・要約・ドキュメント作成など |
| 🥈 第二優先 | 🟡 **GLM** | コード生成。またはMiniMaxが失敗した際のフォールバック |
| 🥉 最終手段 | 🔵 **Sonnet** | Tier1・複雑なアーキ設計・両方失敗時のみ |

> ルーティングポリシーを変更する場合:
> - **デスクトップ版**: `C:\Users\USER\.claude\CLAUDE.md` を編集
> - **WSL2 CLI版**: `C:\Users\USER\.claude\core\fallback-config.json` を編集

---

## 5. 🚨 よくある誤解

### ❌ 誤解1: CLI版の設定（fallback-config.json）をデスクトップ版に適用しようとする
- **事実**: 2つの環境は完全に独立したアーキテクチャです。`fallback-config.json` はWSL2 CLI版専用であり、デスクトップ版には無関係です。
- **正しい対応**: デスクトップ版のルーティング変更は `CLAUDE.md` を編集してください。

### ❌ 誤解2: デスクトップ版でベースモデルを変更できる
- **事実**: デスクトップ版はAnthropicのOAuth仕様上、**常にSonnet 4.6が固定**です。
- **正しい理解**: MCPツール（`minimax_ask`, `glm_ask`）を呼び出すことで処理を委譲するのみです。

### ❌ 誤解3: 401/403エラー時に別プロバイダーへフォールバックすれば解決する
- **事実**: 認証エラーはAPIキーの設定ミスを意味します。`fallback-config.json` も401/403ではフォールバックしない設計です。APIキーを確認してください。

### ⚠️ AI解析者への指示
設定を変更・提案する際は、**必ず実際にファイルシステムに存在するファイルのみを参照**してください。環境（CLI版/デスクトップ版）を混同した提案は誤動作の原因になります。

---

*最終更新: 2026-04-05*

# Claude Code LLM ルーティング戦略比較

**版: Desktop 1.0 | 作成: 2026-04-07 | 実装者: fukukei23**

---

## 概要

Claude Code Desktop（Windows）とWSL2版では、LLMルーティング戦略が異なります。この文書では、各環境での優先順位とその理由を説明します。

---

## Desktop版 LLM ルーティング（C:\Users\USER\.claude\CLAUDE.md）

### 優先順位

| 順位 | LLM | ツール | 用途 | 理由 |
|------|-----|--------|------|------|
| 🥇 第一優先 | **MiniMax** | `minimax_ask` | 会話・調査・翻訳・要約・ドキュメント・バッチ処理 | コスト効率と応答速度が最適 |
| 🥈 第二優先 | **GLM-5.1** | `glm_ask` | コード生成・MiniMaxが遅い/失敗した場合 | 高精度コード生成・フォールバック用 |
| 🥉 最終手段 | **Sonnet** | 直接呼び出し | Tier1タスク・複雑なアーキ設計・両方失敗時 | 最高精度・リソース集約的・事前許可必須 |

### 実装位置

- **設定ファイル**: `C:\Users\USER\.claude\CLAUDE.md`
  ```markdown
  ## LLM利用ポリシー
  - **第一優先（デフォルト）**: 🟠[MiniMax]（minimax_ask経由）
  - **第二優先**: 🟡[GLM-5.1]（glm_ask経由）
  - **最終手段**: 🔵[Sonnet]（Tier1・複雑なアーキ設計・両方失敗時のみ）
  ```

### 実行例

```bash
# 日常的なテキスト・調査
🟠[MiniMax] → minimax_ask で即座に回答

# コード生成が必要な場合（データ処理など）
🟡[GLM-5.1] → glm_ask で高精度コード生成

# 認証周り・複雑な設計が必要な場合（事前許可取得）
🔵[Sonnet] → 直接呼び出し
```

---

## WSL2版との主な相違点

### Desktop版が MiniMax 優先である理由

| 理由 | Desktop版での実装 | WSL2版での考慮 |
|------|-----------------|-------------|
| **応答速度** | MiniMax は平均 3-5秒で応答 | WSL2ではローカル実行パフォーマンスが異なる可能性 |
| **コスト効率** | API呼び出し最小化 | リソース豊富な開発環境 |
| **バッチ処理** | MiniMax は大量テキスト処理に最適 | ローカル処理の方が効率的な場合も |
| **ネットワーク依存** | インターネット接続に依存 | WSLではローカルツールチェーン優先 |

### Desert版で Sonnet を「事前許可制」にした理由

- **高コスト**: Sonnet API呼び出しはMiniMaxの3-5倍の費用
- **セッション管理**: Desktop版は毎回の許可確認で意図しない使用を防止
- **リソース管理**: "デフォルト自動実行"（`defaultMode: bypassPermissions`）との相乗効果を考慮

---

## 設定の継続性

### Desktop版（セッション内で持続）

- PAT（Personal Access Token）は `settings.local.json` に保存
- **セッション再開時**: 再設定不要（ファイル永続化）
- **LLMルーティング**: `CLAUDE.md` が全セッション適用

### WSL2版との差

| 項目 | Desktop | WSL2 |
|------|---------|------|
| 認証情報保存 | `settings.local.json`（Windows側） | `~/.claude/settings.local.json`（WSL側） |
| LLMルーティング | `CLAUDE.md`（グローバル） | `.claude/rules/` 配下（可能性） |
| 再設定頻度 | 不要 | 環境依存 |

---

## ベストプラクティス

### Desktop版での実装

```yaml
デフォルト動作:
  1. MiniMax で応答可能 → 即座に回答（バッジ: 🟠[MiniMax]）
  2. MiniMax が遅い/失敗 → GLM-5.1 にフォールバック（バッジ: 🟡[GLM]）
  3. Tier1 タスク発生 → ユーザー許可を得た上で Sonnet（バッジ: 🔵[Sonnet]）

許可制の効果:
  - Sonnet は「複雑設計・認証周り・両方失敗時」に限定
  - 無意識の高額API呼び出し防止
  - ユーザーがLLM選択に関与可能
```

### バッジ表示ルール（厳格）

毎レスポンスの**冒頭と末尾**に必ず表示：

```
🟠[MiniMax] ← 冒頭に表示
... 回答内容 ...
🟠[MiniMax] ← 末尾に表示
```

---

## まとめ

| 特性 | Desktop版 | 理由 |
|------|----------|------|
| **第一選択肢** | MiniMax | 速度・コスト最適化 |
| **自動実行** | `defaultMode: bypassPermissions` | 危険コマンド除外で安全性確保 |
| **Sonnet使用** | 事前許可制 | コスト管理・セッション安全性 |
| **設定永続化** | PAT自動復元 | `settings.local.json` の効果 |

このアーキテクチャは、**高速・低コスト・安全**のバランスを取る Desktop版独自の設計です。

---

参考リンク:
- [LLM優先ルール詳細](/home/yn441611/vaults/SSOT/00_SYSTEM/shared-rules/llm-routing.md)
- [GitHub リポジトリ設定](https://github.com/fukukei23/claude-config)
- [Workspace 管理ガイド](workspace.md)

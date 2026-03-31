---
name: LLMルーティングルール（GLM優先・Sonnet許可制）
description: 全ての応答はGLM経由が原則。Sonnetを直接使う場合はユーザーへの事前許可が必須。
type: feedback
---

全ての応答はGLM（`glm_ask` 等）を経由すること。Sonnetで直接回答してはいけない。

**Why:** ユーザーはProプランのトークンコストを意識しており、GLMをデフォルトにすることでコスト効率を保つ方針。過去にSonnetで直接回答したことを指摘された（2026-03-31）。

**How to apply:**
- 会話・説明・調査 → `glm_ask`
- コード生成 → `glm_generate_code`
- ファイル要約・翻訳 → `minimax_*`
- Sonnetを使いたい場合 → 「Sonnetを使ってよいですか？」とユーザーに許可を取る
- ツール実行結果の報告もGLM経由で返す
- バッジ（🟡/🟠/🔵）は毎回必ず冒頭に付ける

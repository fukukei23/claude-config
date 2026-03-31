---
name: スケジュールタスクの実行環境とSonnet/GLM役割分担
description: スケジュールタスクはSonnetバックエンドで動作。GLMはテキスト生成のみでBash/MCP実行不可。
type: project
---

スケジュールタスクはデスクトップアプリ（Sonnet OAuthバックエンド）で実行される。Cursor CLI（GLM-5.1）とは別環境。

**Why:** 2026-04-01に glm-cost-tracker がGLMを使わずSonnetで直接実行したことで判明。CLAUDE.mdのGLM優先ルールはSKILL.mdに明示しないと自動タスクに反映されない。

**How to apply:**
- 自動タスク（SKILL.md）には必ず「GLM委託ルール」セクションを追記する
- GLMにBash/ファイル/MCPを実行させることは不可能（テキスト受け渡しのみ）
- 正しい役割分担: Sonnet=実行ハブ（Bash/ファイル/MCP）、GLM=思考・報告文生成
- CLAUDE.mdのルールはインタラクティブ会話向けが主。スケジュールタスクへの適用は各SKILL.mdに明示が必要

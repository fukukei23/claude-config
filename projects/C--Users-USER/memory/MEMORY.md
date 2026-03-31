# Memory Index

- [LLMルーティングルール（GLM優先・Sonnet許可制）](feedback_llm_routing.md) — 全応答GLM経由。Sonnet直接使用は事前許可必須（2026-03-31指摘）
- [スケジュールタスクの実行環境とSonnet/GLM役割分担](project_scheduled_task_architecture.md) — タスクはSonnetバックエンド動作。GLMはテキスト生成のみ。SKILL.mdへの明示必須

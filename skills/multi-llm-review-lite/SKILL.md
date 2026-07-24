---
name: multi-llm-review-lite
description: 設計・方針・構想にOpenRouter経由のfree枠LLM（1〜2機）から独立にツッコミをもらい、ホストが重複排除＋重要度振り分け＋「押さえどころ」1行提言を返す軽量スキル。採用/却下はユーザー判断。会話内完結・ファイル出力なし。ユーザーが「各LLMでツッコミ」「LLMにツッコミさせて」「方針チェックして」「これで抜けないか各LLMに聞いて」と言った時、または /multi-llm-review-lite を呼んだ時にトリガー。
user-invocable: true
---

# multi-llm-review-lite（軽量マルチLLMレビュー）

設計・方針・構想を OpenRouter free 枠の LLM に独立ツッコミさせ、ホストが「重要度高/その他 + 押さえどころ1行」に整理。**採用/却下はユーザー**。本式 `multi-llm-review`（改訂案生成・268行）より軽い（箇条書き・会話内完結）。

## トリガーワード
「各LLMでツッコミ」「LLMにツッコミさせて」「方針チェックして」「これで抜けないか各LLMに聞いて」/ `/multi-llm-review-lite [--model <slug>] [--purpose code|design|general] [--mode dual]`

## フロー（4手順）

### 1. 受け取り＋機密確認
対象（設計/方針/構想）＋目的＋観点（未指定なら盲点・リスク・代替案）。機密確認1問: **「シークレット/社内情報/個人情報含みますか？」** → 含むならマスク/要約、または本式（機密フラグ扱い厚）へ誘導。

### 2. モデル選定（用途ベース自動・ユーザー指定が優先）
| purpose | モデル |
|---|---|
| `code` | `cohere/north-mini-code:free`（コード特化） |
| `design` | `openai/gpt-oss-20b:free`（汎用） |
| `general` | `nvidia/nemotron-3-super-120b-a12b:free`（大規模推論） |

`--model <slug>` 指定で上書き・文脈に「コード/実装」含めば自動で `code`・`--mode dual` で2機並列（コスト2倍）・**退役時は `/api/v1/models` で最新 slug 確認**。

### 3. OpenRouter curl 直叩き（モデル数分・並列）
```bash
set -a; source ~/.secrets.env; set +a   # 401対策
python3 -c "import json; open('/tmp/or_req.json','w').write(json.dumps({'model':'<slug>','messages':[{'role':'user','content':PROMPT}],'max_tokens':2000},ensure_ascii=False))"
curl -s --max-time 90 https://openrouter.ai/api/v1/chat/completions -H "Authorization: Bearer $OPENROUTER_API_KEY" -H "Content-Type: application/json" -d @/tmp/or_req.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['choices'][0]['message']['content'] if 'choices' in d else d)"
```

**プロンプト雛形**（目的ホールド・先頭1行）:
```
[前提] 対象はクラウドLLM APIで処理される（ローカル実行/GPUメモリ/ハードウェアの話は無関係）。
[目的] 以下が「<目的>」を達成するか、盲点・リスク・代替案でツッコミ。
[対象] <設計/方針>
[出力形式] 箇条書き（JSON不要・挨拶不要）:
- 【重要度高/その他】<指摘>（1行1指摘・具体的）
※ 目的外でも致命的欠陥があれば含めてください。
```

### 4. A′整理 → 会話内提示
```
【重要度高】
- <指摘>（<model_slug> / 共通）
【その他】
- <指摘>（<model_slug>）
📌 押さえどころ: <最低限これだけは・1行>
（採用/却下はあなたが判断してください）
```
ホストはジャッジしない（重要度振り分け＋重複排除のみ）。

## 失敗時
- **401**: `source ~/.secrets.env` 失敗 → 中断・手順案内
- **429**: 内容表示・時間待ち案内（自動リトライしない）
- **空応答/タイムアウト**: 「`<slug>` 失敗。別モデルか観点絞りで再実行を」
- **dual で 1/2 失敗**: 残りの指摘のみで A′（縮退）

## 棲み分け
実装前叩き=`doubt-driven-development` / A/B/C選び=`sentaku` L3 / **設計・方針ツッコミ（本スキル）** / 改訂案・コード全体・深統合=`multi-llm-review`（本式）

## YAGNI
採用/却下の自動判断・改訂案生成・コード全体レビュー・反復ラウンド・ファイル出力・Gemini curl直叩き

## 関連
spec: `obsidian-ssot/docs/superpowers/specs/2026-07-24-multi-llm-review-lite-design.md`（v2） / 本式: `~/.claude/skills/multi-llm-review/SKILL.md` / OpenRouter導入: `01_DECISIONS/claude-code/2026-07-24_OpenRouter導入完了とfree枠実態確認.md` / バックログ L432・L443

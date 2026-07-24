---
name: multi-llm-review-lite
description: 設計・方針・構想にOpenRouter経由のfree枠LLM（1〜2機）から独立にツッコミをもらい、ホストが重複排除＋重要度振り分け＋「押さえどころ」1行提言を返す軽量スキル。採用/却下はユーザー判断。会話内完結・ファイル出力なし・改訂案は作らない。ユーザーが「軽くツッコミ」「軽く他LLMでレビュー」「サクッと方針チェック」「これで抜けないか軽く聞いて」と言った時、または /multi-llm-review-lite を呼んだ時にトリガー。「軽く/サクッと」が入らないレビュー依頼（「各LLMにレビューして」「しっかり」「3機で」等・改訂案が欲しい）は multi-llm-review（本式）へ。
user-invocable: true
---

# multi-llm-review-lite（軽量マルチLLMレビュー）

設計・方針・構想を OpenRouter free 枠の LLM に独立ツッコミさせ、ホストが「重要度高/その他 + 押さえどころ1行」に整理。**採用/却下はユーザー**。本式 `multi-llm-review`（改訂案生成）より軽い（箇条書き・会話内完結・**改訂案は作らない**）。

> **前提**: WSL CLI環境（bash/python3/curl・`~/.secrets.env`）。Windows Desktop版は本式 `multi-llm-review` 推奨（MCP経由・機密フラグ厚）。

> **lite vs normal 切り分け（鉄則・ユーザー方針 2026-07-25）**:
> - 「**軽く**」「**サクッと**」が入った → **lite（本スキル）**：箇条書きツッコミ・改訂案なし・1〜2機（OpenRouter free）
> - 「軽く」が入らない（「各LLMにレビューして」「しっかり」「3機で」等）→ **normal（`multi-llm-review`）**：改訂案生成
> - **1機でも効果あり**（ホストと別のLLMの新鮮な視点で盲点洗い）。複数LLMの確度確認や改訂案が要る時だけ normal へ。

## トリガーワード
「軽くツッコミ」「軽く他LLMでレビュー」「サクッと方針チェック」「これで抜けないか軽く聞いて」 / `/multi-llm-review-lite [--model <slug>] [--purpose code|design|general] [--mode dual]`

> 「各LLMにレビューして」「複数LLMでレビュー」「3つのLLMで」は **normal（`multi-llm-review`）のトリガー**（改訂案が欲しい時）。本スキルは「軽く」が付いた時のみ。

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
set -a; source ~/.secrets.env 2>/dev/null; set +a   # 401対策（2>/dev/null=stderr抑制でキー値漏洩防止）
# PROMPT は環境変数経由で python3 に渡す（シェル展開しない＝引用符/インジェクション対策）
export PROMPT='[目的] ... [対象] <設計/方針> ...'   # 対象テキストをここに
export MAXTOKENS=2000   # 深い設計・長大specは 4000 に（思考モデルでないので 8000 不要）
python3 -c "import json,os; open('/tmp/or_req.json','w').write(json.dumps({'model':'<slug>','messages':[{'role':'user','content':os.environ['PROMPT']}],'max_tokens':int(os.environ.get('MAXTOKENS','2000'))},ensure_ascii=False))"
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
ホストはジャッジしない（重要度振り分け＋重複排除のみ）。**重複判定は文字列一致でなく意味で行う**（ホストがLLM所以・「APIキー漏洩」と「認証情報流出」は同じ意味でまとめる）。

## 失敗時
- **401**: `source ~/.secrets.env` 失敗 → 中断・手順案内
- **429**: 内容表示・時間待ち案内（自動リトライしない）
- **空応答/タイムアウト**: 「`<slug>` 失敗。別モデルか観点絞りで再実行を」
- **dual で 1/2 失敗**: 残りの指摘のみで A′（縮退）

## 棲み分け
実装前叩き=`doubt-driven-development` / A/B/C選び=`sentaku` L3 / **「軽く」ツッコミ・箇条書き・改訂案不要（本スキル）** / **改訂案が欲しい・しっかり・3機（triple）**＝`multi-llm-review`（本式・normal）

## YAGNI
採用/却下の自動判断・改訂案生成・コード全体レビュー・反復ラウンド・ファイル出力・Gemini curl直叩き

## 関連
spec: `obsidian-ssot/docs/superpowers/specs/2026-07-24-multi-llm-review-lite-design.md`（v2） / 本式: `~/.claude/skills/multi-llm-review/SKILL.md` / OpenRouter導入: `01_DECISIONS/claude-code/2026-07-24_OpenRouter導入完了とfree枠実態確認.md` / バックログ L432・L443

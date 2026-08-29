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

### 2. モデル選定（全用途 nemotron・2026-07-25 ベンチマーク反映）
| purpose | モデル |
|---|---|
| `code` / `design` / `general`（全用途同一） | `bash ~/bin/openrouter-free-pick.sh` のstdout（JSON契約 `{model, cost_tier, params}`）・`params`のみAPIペイロードへマージ。モデルslugはハードコード禁止（自動検知cronが日次更新・spec: `docs/superpowers/specs/2026-08-28-OpenRouter無料モデル自動検知-pick設計-design.md`） |

> **2026-07-25 改修（合成案A′）**: 用途別選定を廃止（旧 code=north-mini-code/design=gpt-oss-20b はベンチで否定・gpt-oss-20bは思考トークン汚染+3倍遅・north-mini-codeはセキュリティ検出率最低）。`--purpose` は将来の新型追加用にパラメータ残置（現状は全て同一モデルにフォールバック）。`--model <slug>` で上書き可・`--mode dual` で2機並列。2026-08-29: モデル選定はpick.sh契約へ移行（--purpose由来の選定は廃止）。実呼出失敗時は --exclude で次候補へ1回再試行し、log-resultで成否記録

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
※ 【サボりバイアス防止・必須（2026-07-25 C″追加）】"作らない/省略/後回し/既存で足りる"方向の指摘は、(1)省略デメリット1つ (2)代替シナリオ検討有無 (3)"新規〇〇ゼロ/検証済"が**測定範囲の偏り（未検証シナリオ）のアーティファクトでないか**、を**出力に言語化**（自問でなく出力義務・内部処理に埋没すると効果薄い）。
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

**【集団サボりバイアス検知（2026-07-25 C″追加・機械的）】** `--mode dual`(2機)等で複数LLMが「省略/作らない/後回し」方向に一致 **かつ** 根拠が「発生ゼロ/検証済/既存で足りる」等の**測定結果依存**の場合、A′整理の出力に以下を**機械付与**（ジャッジでなく機械検知なのでliteの「ジャッジしない」建前と両立・ホスト判断委ねない）:
> ⚠️ **集団サボりバイアス疑義**: 複数LLMが省略推奨で一致。未検証シナリオ「<ホストが1つ生成>」をユーザー再確認推奨。

（※本スキルは軽量版・反証シナリオ生成と警告付与のみ。深い検査・改訂案統合は本式 `multi-llm-review` Step6.5へ）

## 失敗時
- **401**: `source ~/.secrets.env` 失敗 → 中断・手順案内
- **429 / 空応答 / タイムアウト**: **`bash ~/bin/openrouter-free-pick.sh --exclude <失敗model>` で次候補へ切替し再実行**（同じ死んだモデルへ再試行しない・r3レビュー契約）。呼出後 `bash ~/bin/openrouter-free-pick.sh log-result <model> ok|fail <reason>` で成否記録。フォールバック先でも失敗なら「観点絞りで再実行」を案内
- **dual で 1/2 失敗**: 残りの指摘のみで A′（縮退）

## 棲み分け
実装前叩き=`doubt-driven-development` / A/B/C選び=`sentaku` L3 / **「軽く」ツッコミ・箇条書き・改訂案不要（本スキル）** / **改訂案が欲しい・しっかり・3機（triple）**＝`multi-llm-review`（本式・normal）

## YAGNI
採用/却下の自動判断・改訂案生成・コード全体レビュー・反復ラウンド・ファイル出力・Gemini curl直叩き

## 関連
spec: `obsidian-ssot/docs/superpowers/specs/2026-07-24-multi-llm-review-lite-design.md`（v2） / 本式: `~/.claude/skills/multi-llm-review/SKILL.md` / OpenRouter導入: `01_DECISIONS/claude-code/2026-07-24_OpenRouter導入完了とfree枠実態確認.md` / バックログ L432・L443

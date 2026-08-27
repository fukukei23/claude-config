---
name: multi-llm-review
description: 設計・コード・文章を複数の異なるLLMに並列独立レビューさせ、ホストLLMが当初目的を基準に取捨統合して改訂案を作る。デフォルト2機（WSL CLI版: MiniMax+Gemini）・triple指定で3機（MiniMax+Gemini+OpenRouter無料枠1機）。「各LLMに/でレビューして」は常にtriple（2026-08-27ユーザー指示）。ユーザーが「マルチLLMレビューして」「複数LLMでレビュー」「各LLMにレビューして」「3つのLLMで」「3機でしっかり」「panel review」「jury review」「クロスLLMレビュー」などと依頼した時に使う。改訂案が欲しい時は本スキル（ツッコミ箇条書きで良い時は multi-llm-review-lite）。
---

# multi-llm-review

## 概要

レビュー対象（設計/コード/文章）を複数の**異なるLLM**に並列独立レビューさせ、ホストLLM（現在動いているLLM）が**当初目的を唯一の基準**に取捨選択して元案へ統合し、よりよい改訂案を作る。

**核心価値: モデル多様性**。既存の `doubt-driven-development`（同LLM adversarial）/ `sentaku` L3（同LLM弁証）/ `superpowers:dispatching-parallel-agents`（同LLM並列）は全て **context 多様性**（同一LLM内での視点切り替え）。本スキルは **異なるLLMの死角を補完する** ことで直交する価値を提供する（**直交**＝観点パックは共通でも、異なるLLMが独立に発見する指摘の非重複度。3ラウンド実例で両LLMが同じ致命点を独立指摘した際に価値が実証される）。

## トリガーワード（自然言語・スラッシュコマンド両方可）

- 「マルチLLMレビューして」「複数LLMでレビュー」
- 「各LLMにレビューして」「各LLMでレビューして」「3つのLLMで」「3機でしっかり」「しっかりレビューして」→ **triple モード**（3機・後述・2026-08-27 ユーザー指示で「各LLM〜」は常に3機に昇格）
- 「panel review」「jury review」「クロスLLMレビュー」
- `/multi-llm-review` / `/multi-llm-review --triple`

> **lite（multi-llm-review-lite）との切り分け（鉄則）**: 「軽く」「サクッと」が入ったら lite（箇条書きツッコミ・改訂案なし）。「改訂案が欲しい」「しっかり」「3機で」は本スキル（normal）。曖昧なら確認。

## 既存スキルとの棲み分け（機械的振り分け表）

| 状況 | 起動スキル |
|---|---|
| 実装前・選択肢なし（単一案を叩く） | `doubt-driven-development` |
| 既存案 A/B/C から選ぶ | `sentaku` L3 |
| **ツッコミをサクッと（1〜2LLM・箇条書き・会話内完結・OpenRouter・改訂案なし）** 「軽く」「サクッと」 | `multi-llm-review-lite`（軽量版） |
| **改訂案が欲しい・既存案を改良（多LLM独立レビュー→統合・ファイル出力）** 「マルチLLMレビュー」「複数LLMでレビュー」 | **multi-llm-review（本）** |
| **3機でしっかり批評（MiniMax+Gemini+OpenRouter free）→ 改訂案** 「各LLMに/でレビュー」「3つのLLMで」「3機で」「しっかり」 | **multi-llm-review（本）`--triple`** |
| 「〜して」と作業依頼 | スキル不起動 |

曖昧な場合はユーザーに確認する。

---

## 環境前提（2層・ホスト以外の利用可能LLM全部を自動呼出）

| 環境 | ホストLLM（統合役） | レビュアーLLM（デフォルト） | triple 指定時（`--triple` / 「3機で」） |
|---|---|---|---|
| WSL CLI版 | GLM | MiniMax + Gemini（2） | MiniMax + Gemini + **OpenRouter無料枠1機**（3） |
| Windows デスクトップアプリ版 | Sonnet | GLM + MiniMax + Gemini（3） | （既に3機・triple指定は実質同じ） |

- ホスト自身はレビュアーに含めない（自己レビューは多様性ゼロ）
- ホスト以外の利用可能LLM全部を自動呼出（利用不能LLMは discover で検知してスキップ）
- **triple 時の OpenRouter 機選定**: purpose 別（`code`=cohere/north-mini-code:free / `design`=openai/gpt-oss-20b:free / `general`=nvidia/nemotron-3-super-120b-a12b:free・liteと共通）。退役時は `/api/v1/models` で最新 slug 確認

## 🔐 機密情報の取り扱い（必須・冒頭確認）

レビュー対象が**コード・社内文章・シークレット含む設計**の場合、外部LLM送信のリスクがある。**フロー開始前にユーザーへ「対象に機密が含まれるか」を必ず確認**する:

- **機密フラグ ON**: 外部LLM送信前に**リスク警告**→必要なら対象を**マスク/要約**して送信、または**限定モデルのみ**使用（ホスト=ローカル等）
- CLAUDE.md セキュリティルール（APIキー値の送信禁止等）に準拠。`~/.secrets.env` の値は絶対にレビュアープロンプトに含めない

## 全体フロー

1. **ユーザー**: トリガー + 対象（設計/コード/文章）+ 目的/観点
2. **ホスト**: 機密確認 → プロンプト組み立て（slot）
3. **discover / health check**: 各LLMの呼出可能性確認・失敗LLMはスキップ
4. **ホスト**: レビュアーLLMを並列独立呼出（2段階ファイル経由）
5. **各レビュー収集**（JSON抽出＝必須前提）
6. **統合ロジック**（8ステップ・Step6 が pre-flight 中断フェーズ）
7. **出力**: 改訂案 + review_log.md

**実行メカニズム**:
- **並列・独立**: 各LLMに互いの結果を見せず同一プロンプト（先入観なし・anchoring bias 回避）
- **1ラウンド固定**: 反復は廃止（深さが必要なら `sentaku` L3 / `doubt-driven` へ誘導）
- **当初目的ホールド**: 各統合ステップのプロンプト先頭に目的文を再注入（機械的ホールド）

---

## discover / health check（スキル冒頭で実行）

各LLMの呼出可能性を実行時検知する:

| 状況 | 処理 |
|---|---|
| **401**（APIキー無効/未設定） | 永続スキップ（以降のラウンドでも呼ばない） |
| **500 / ネットワークエラー / timeout** | 再試行1回（timeout=60s・累計上限180s）→それでも失敗ならスキップ |
| **429**（レート制限） | 順次化または2モデルに縮退（後述「コスト・レート制限」） |

**縮退判定**: 呼出成功LLM数 M ≥ 2 で続行。M < 2 は中止（多様性が保証できないため）。

### 自動フォールバック（lite から移植・2026-08-22）

これまで lite にしか無かった自動フォールバックを本スキルにも入れる（lite `SKILL.md` の「失敗時」節と同一挙動）:

| 状況 | 挙動 |
|---|---|
| **401** | 永続スキップ（鍵の問題なのでモデルを替えても直らない）。`source ~/.secrets.env` の失敗も疑う |
| **429 / 空応答 / タイムアウト** | **フォールバックモデルへ自動切替して1回だけ再実行**（OpenRouter は `cohere/north-mini-code:free`・別プロバイダを選び多様性も確保）。フォールバック先でも失敗したら観点を絞って再実行を案内 |
| **`content` が空で `finish_reason: length`** | 思考枠切れ（`thinking_overflow`）。`reasoning:{enabled:false}` の付け忘れをまず疑う。付けても再発するならプロンプト短縮 |

> **フォールバックを使った round は `round_id` の先頭に `fb-` を付ける**（例: `fb-20260822-031500`）。移植直後に異常が出た時、「フォールバックの実挙動」なのか「記録側のバグ」なのかを切り分けるための目印（spec §9）。
> attempt（llm単位の連番）は `mlr-log.sh annotate` が自動採番するので手で数えなくてよい。**モデルが替わってもリセットしない**（1回目=本命モデル / 2回目=フォールバック先）。

## 外部LLM呼出手段（経路分岐表）

| LLM | 通信方式 | 認証 | 備考 |
|---|---|---|---|
| MiniMax | `mcp__minimax__minimax_ask`（MCP） | MCP設定 | 同一メッセージで他curlと並列可能・JSON多指摘対策で `max_tokens=8000` 推奨 |
| Gemini | curl REST（`gemini-3.1-pro-preview`） | `$GEMINI_API_KEY` | `gemini.py` はYouTube専用で不使用・モデル名は現時点の最新版（退役時にホストが最新へ読み替え・ハードコードは例示）・**思考モデルのため `maxOutputTokens=8000` 必須**（3000では思考トークンが枠を消費して出力途中切れ=MAX_TOKENS・2ラウンド実例で実証） |
| OpenRouter（triple時の3機目） | curl REST（OpenRouter `/api/v1/chat/completions`） | `$OPENROUTER_API_KEY` | triple指定時のみ追加・free枠モデル（purpose別選定）・`max_tokens=2000`＋**`"reasoning": {"enabled": false}` 必須**（下記⚠️）・既存 lite のcurl手順を流用 |

> ⚠️ **OpenRouter には `"reasoning": {"enabled": false}` を必ず付ける（2026-08-21 実測・付けないと5連敗する）**
> free枠モデル（`cohere/north-mini-code:free` / `openai/gpt-oss-20b:free` 等）は**思考を `content` ではなく `reasoning` フィールドへ出力**し、思考が `max_tokens` を食い尽くして `content: null` / `finish_reason: length` のまま終わる。抽出コードが読む `message.content` は常に空になり、「200が返っているのに指摘0件」という**原因の見えない全滅**を起こす。
> かつて本表に「思考モデルでないので8000不要」と書いていたのは**誤り**（実測で否定済み）。
> 診断手順: `30_RESEARCH/LLMモデル/2026-08-21_思考出力の落とし穴-reasoning-thinkによる本文欠落.md`
| Windows版 GLM | glm-rate-proxy or MCP経由 | プロキシ設定 | WSL版ホスト=GLM自身は呼ばない |

## 実装手順（Claude Code環境・2段階ファイル経由・必須）

直接 curl はクォート/改行エスケープが破綻するため、**2段階ファイル経由**を標準手順とする:

1. **各LLMのAPIリクエストJSONペイロードを一時ファイルに書出**（Write ツール or python3）:
   - `/tmp/req_gemini.json`（Windows Desktop は環境に応じた一時パス）
   - triple時: `/tmp/req_or.json`（OpenRouter用）も生成
2. **並列送信**（同一メッセージでツール呼出・triple時は3ツール同時）:
   - MiniMax: `mcp__minimax__minimax_ask`（prompt に同一プロンプトを指定）
   - Gemini: Bash で `curl -s -H "Content-Type: application/json" -d @/tmp/req_gemini.json "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-pro-preview:generateContent?key=$GEMINI_API_KEY"`
   - OpenRouter（triple時のみ）: Bash で `set -a; source ~/.secrets.env 2>/dev/null; set +a; curl -s --max-time 90 https://openrouter.ai/api/v1/chat/completions -H "Authorization: Bearer $OPENROUTER_API_KEY" -H "Content-Type: application/json" -d @/tmp/req_or.json`（プロンプトはPROMPT環境変数経由でpython3に渡してペイロード生成・liteと同一手順）
     - **ペイロードに `"reasoning": {"enabled": false}` を必ず含める**（上記⚠️・欠落すると `content: null` で全モデル全滅する）:
       `{"model": <slug>, "messages": [...], "max_tokens": 2000, "reasoning": {"enabled": false}}`
3. **JSON抽出**: 結果から**文字種ステートマシン**でJSON配列を再構成（下記「JSON抽出」参照）

> python3 でペイロード生成する例:
> `python3 -c "import json; open('/tmp/req_gemini.json','w').write(json.dumps({'contents':[{'parts':[{'text':PROMPT}]}],'generationConfig':{'temperature':0.4,'maxOutputTokens':8000}},ensure_ascii=False))"`

### Gemini 空応答時のリトライ（思考モデルの罠・2026-07-05 実証）

Gemini 思考モデル（2.5 Pro / 3.1 Pro 等）は `maxOutputTokens=8000` 設定でも、**長大コード＋長focus** の組合せで思考トークンが枠を消費して**空応答**を返すことがある（`finishReason: MAX_TOKENS`・本文空）。

**検知**: レスポンス本文が空、または `candidates[0].content.parts[0].text` が空文字列。

**対策（空応答時のリトライ戦略・順に実施）**:

1. **focus 短縮**: `"all"` / `"readability"` → `"bug"` 等の**1観点1単語**に短縮（思考負荷を下げる）
2. **コード圧縮**: コメント・docstring・空行を削除し**核心ロジック・差分のみ**に圧縮（入力トークン削減で思考の余裕生成）
3. **再送信**: 上記2点を適用した圧縮ペイロードで再実行

**実証例（2026-07-05・daily_triage.py レビュー）**:
- 1回目（focus=readability・コード全文）: **空応答**
- 2回目（focus=bug・コード圧縮・背景1行追加）: **具体的指摘2件**（状態列動的特定・ヘルパー化）を獲得

> **MCP直接呼出 `mcp__gemini__review_with_gemini` は `maxOutputTokens` 指定不可**（スキル外で直接呼ぶ場合）で特に空応答しやすい。`multi-llm-review` スキル経由の curl REST（8000指定）でも長大コードでは発生するため、本リトリア戦略を標準手順に組み込む。

---

## レビュアープロンプト雛形（全LLM共通・slot化・順序固定）

ホストは以下テンプレの `{...}` を埋めて、全レビュアーに**同一プロンプト**を送る（先入観なし・同条件）:

```
[ロール] あなたは {security reviewer / consistency reviewer / simplicity advocate / ...} です。
[目的] 以下の元案が「当初目的: {目的}」を達成するか、観点「{観点}」でレビューしてください。

[元案]
{対象}

[出力形式] JSON配列のみで返答してください（挨拶・markdownコードブロック不要）:
[{"issue": "...", "severity": "critical/high/med/low", "quote": "元案からのコピペ抜粋", "suggestion": "改善案"}]
※ quote 内の `}` は必ずエスケープすること（例: `}` → `\}`）。文字種ステートマシンで解析するため壊れます。
※ 目的外でも致命的欠陥があれば含めてください（メタ指摘歓迎）。
※ 【サボりバイアス防止・必須（2026-07-25 C″追加）】"作らない/省略/後回し/既存で足りる/実装不要"方向の指摘をする場合、以下3点を**必ず出力に言語化**すること（"自問せよ"でなく出力義務・内部処理に埋没すると効果薄い）:
    (1) 省略した場合のデメリット・事故リスクを最低1つ明示
    (2) 既存ファイル/既存実装以外の代替シナリオを検討したか明示
    (3) "新規〇〇発生ゼロ/検証済"等の根拠が**測定方法のアーティファクト**（測定範囲の偏り・未検証シナリオ）でないことの証明
   ※ 検証範囲の偏りに依存する"作らない"推奨は**LLM集団サボりバイアス（実装コスト回避）**の典型（2026-07-25 承認スキーマPhase2事象で実証）。
※ 【サボりバイアス防止・Phase0拡張（2026-07-26）】省略方向だけでなく**全レビュー共通**で以下も出力義務（個別LLMの単独サボりも形式で捕捉・ホスト単独レビューでも有効）:
    (4) **反証シナリオ1つ**: 元案を支える前提が崩れるケース（確証バイアス対策）
    (5) **最悪ケース1つ**: "問題ない"とする場合の最悪の影響（楽観バイアス対策）
   ※ 詳細: `@rules/_shared/LLMサボりバイアス防止.md`（13類型カタログ）
```

### デフォルト観点パック（観点未指定時・全採用／指定時は指定観点のみ）

| 対象 | 観点 |
|---|---|
| 設計 | 目的整合 / 要件網羅 / 代替案検討 / リスク / スケーラビリティ / 実現性 / **サボりバイアス（省略推奨の妥当性・2026-07-25追加）** / **反証1つ＋最悪ケース（Phase0・2026-07-26）** |
| コード | 正確性 / 可読性 / 性能 / セキュリティ / テスタビリティ / 既存規約整合 |
| 文章 | 論理構造 / 明瞭性 / 読者適合 / 誤字脱字 / 出典・事実性 |

`[ロール]` の例: `security reviewer` / `consistency reviewer` / `simplicity advocate` / `performance reviewer` / `clarity reviewer`

---

## JSON抽出（文字種ステートマシン・必須前提）

### 前処理: 各LLM応答から本文を抽出（必須・2026-07-28追記）

curl/MCP の生レスポンスは **API用JSONで包まれている**（Gemini/OpenRouter）。文字種ステートマシンに渡す **前** に、各LLMの応答構造から本文（レビューJSON配列が入った `text`/`content`）を抽出すること。生レスポンスをそのまま食わせると外側JSONの `[` `]` に誤ヒットして **指摘が1件しか取れない事故** が起きる（2026-07-28 実証: Gemini 5件中1件のみ抽出 → 本文抽出後5件全取得）。

| LLM | 応答構造 | 本文の取り出し方 |
|---|---|---|
| **Gemini**（curl REST） | `{"candidates":[{"content":{"parts":[{"text":"..."}]}}], "usageMetadata":{...}}` | `resp['candidates'][0]['content']['parts'][0]['text']` |
| **OpenRouter**（curl REST） | `{"choices":[{"message":{"content":"..."}}]}` | `resp['choices'][0]['message']['content']` |
| **MiniMax MCP**（`mcp__minimax__minimax_ask`） | 直接テキスト（封筒なし） | そのまま（前処理不要・MCPが本文を返す） |

抽出例（python3）:
```python
import json
resp = json.load(open('/tmp/res_gemini.txt'))
text = resp['candidates'][0]['content']['parts'][0]['text']
open('/tmp/gemini_text.txt','w').write(text)
# → /tmp/gemini_text.txt を extract.py の stdin に渡す
```

> ※ lite スキルの OpenRouter 実装（`d['choices'][0]['message']['content']`）と同じ前処理。本スキルにも明示化（2026-07-28・これまで抜けていた）。
> ※ 「封筒（API用JSON）に入った届く」→「封筒を開けて中身（本文）を取り出す」→「本文からJSON配列を抽出（文字種ステートマシン）」の3ステップ。

LLMにはJSON配列のみを返すよう指示するが、markdownブロックや挨拶文を混入する。**本文抽出後**のテキストから **文字種ステートマシン** でJSON配列を抽出する:

- 文字列リテラル（`"` で囲まれた範囲）内の `}` は**無視**して split する（`{"quote":"if(x){}"}` 破綻回避）
- 抽出した要素のうち **必須key（`issue`/`severity`/`quote`/`suggestion`）が全て揃った指摘が ≥50%** なら成功・未満ならテキスト扱いで統合（Step1の閾値）

python3 抽出実装例（スクリプトを `/tmp/extract.py` に保存し `python3 /tmp/extract.py < /tmp/res_<llm>.txt` でパイプ入力・結果をファイルへもリダイレクト可能）:

```python
import json, sys

def extract_issues(text):
    """文字種ステートマシン: [ と ] の中身だけ走査し、
    文字列リテラル内の } を無視して各 {...} オブジェクトを切り出す。"""
    s, e = text.find('['), text.rfind(']')
    if s == -1 or e == -1 or e < s:
        return []
    body = text[s+1:e]  # 外括弧 [ ] は除外（中身のみ）
    items, buf, in_str, esc = [], '', False, False
    depth = 0
    for ch in body:
        if esc:                       # 直前が \（文字列内のエスケープ）
            esc = False
            if depth > 0: buf += ch
            continue
        if ch == '\\':
            esc = True
            if depth > 0: buf += ch
            continue
        if ch == '"':
            in_str = not in_str
            if depth > 0: buf += ch
            continue
        if in_str:                    # 文字列内は } { を無視
            if depth > 0: buf += ch
            continue
        # 以下 in_str == False
        if ch == '{':
            if depth == 0:
                buf = '{'             # 新オブジェクト開始（手前の [,カンマ,空白は捨てる）
            else:
                buf += ch
            depth += 1
        elif ch == '}':
            depth -= 1
            buf += ch
            if depth == 0:
                try:
                    items.append(json.loads(buf.strip()))
                except Exception:
                    pass
                buf = ''
        else:
            if depth > 0: buf += ch
    return items

text = sys.stdin.read()
res = extract_issues(text)
print(json.dumps(res, ensure_ascii=False, indent=2))
```

## severity 正規化マップ

各LLMの severity を `{critical, high, med, low}` に正規化する:

| LLM出力 | 正規化後 |
|---|---|
| blocker / critical / P0 / 致命的 | critical |
| major / high / P1 / 重大 | high |
| med / P2 / 中 | med |
| minor / low / nit / P3 / 低 | low |

---

## 統合ロジック（ホストLLM・8ステップ・Step6が中断フェーズ・当初目的ホールド）

**各ステップのプロンプト先頭に「当初目的: {目的}」を再注入する（機械的ホールド）。**

1. **JSON抽出**（上記・文字種ステートマシン）
2. **severity 正規化**: 上記マップで各指摘を `{critical, high, med, low}` に正規化
3. **Fact Check**: 各指摘の `quote` が元案に**部分一致**するか（トークン Jaccard ≥ 0.7・正規化後）→ 不存在は即却下（ハルシネーション除外）
   - **※要約渡し時（対象サイズ大）は Fact Check をスキップ**（要約ベースでは quote が元案と一致せず全却下される矛盾を回避）。**判定基準**: ホストが Step2 のプロンプト組み立て時に「全文渡し or 要約渡し」のフラグを保持し、要約渡し時は本ステップをスキップ（コスト・レート制限の要約渡しとも整合）
4. **ペルソナ切替（著者バイアス対策・ホストの認知ステップ）**: 「あなたは元案の作者ではない。冷徹な品質管理責任者として外部指摘を客観的に裁定せよ」＋盲点カタログ（著者が見落としがちな観点を列挙）＋devil's advocate（自分がこの指摘を出した側ならどう反論するか）。**※これは統合側のホスト認知であり、追加のLLM呼出は行わない**（独立性命題を維持。Step4でレビューアーを再呼びしない）
5. **当初目的 3tier 分類**:
   - **直接**（目的関連）→ 採否判断（必須）
   - **メタ**（目的自体への疑義・致命的欠陥）→ Step 6 でユーザー確認
   - **完全目的外** → 切る（理由1行記載）
6. **【pre-flight・中断フェーズ】** メタ指摘があれば統合前にユーザー確認:
   - JSONは保持・LLMセッション有効期間内のみ再開（再呼出＝コスト2倍を回避）
   - メタ却下後は**当初目的維持・tier判定は変更なし**（暴走防止）
   - メタ指摘がなければ Step 7 へ直行
7. **競合調停**: 相反指摘（A「削除」vs B「詳細化」等）は当初目的基準でトレードオフ評価・採用理由を明記
8. **統合**: 採用指摘を**元案の構造を保持し指摘箇所のみ置換/追記**→改訂案。末尾に「**却下サマリ（リスト・各1行理由）**」＋「当初目的: X / 改訂案が満たす根拠: Y」を強制記載

> ※Step6（pre-flight）は統合内の**中断フェーズ**。メタ指摘がなければ Step5 → Step7 へ直行する（spec v3 整合）。

### Step 6.5: 集団サボりバイアス検知（機械的・2026-07-25 C″追加）

複数レビュアーが「作らない/省略/後回し/既存で足りる/実装不要」方向に一致した場合、**LLM集団サボりバイアス（実装コスト回避）**の疑義を検知する。

**判定条件（両方満たす・ホストは"サボりか否か"の判断を生成せず機械的に適用）**:
1. **方向一致**: 複数レビュアー（≥2機、または全機）が省略方向の推奨で一致
2. **根拠の構造的条件**: 推奨の根拠が「新規X発生ゼロ/検証済/既存でカバー」等の**測定結果**に依存している（単なる方向一致では誤検知・M1指摘）

**成立時のアクション（ホストは判断を生成せず機械的に実行・G1+M6指摘）**:
- **反証シナリオ生成**: 「この『ゼロ/十分』は測定範囲の偏り（未検証シナリオ）のアーティファクトでないか？」→ 未検証シナリオを1つ明示生成（M3指摘・ユーザー丸投げ回避）
- **行動可能警告を付与**: 改訂案/review_log の冒頭に以下を機械挿入（G3+M4指摘・術語は内部ログ）:
  > ⚠️ **集団サボりバイアス疑義**: 両レビュアーが省略（実装不要）推奨で一致。この結論が特定の検証条件（例: 既存データの再利用のみ）に依存したアーティファクトでないか、**未検証シナリオ「<生成した反証>」をユーザーが再確認推奨**。

**設計根拠（Bの完全却下を訂正・M6指摘）**: ホストもLLMで盲点共有リスクがあるため、ホストに「サボりかどうか」の判断を委ねず**条件成立→機械的にフラグ+反証生成**。これでホストの判断バイアスを排除しつつ、ユーザーへの行動可能な警告を実現する。

**scope（M5指摘・MVP明記）**: 本ステップは「省略方向のサボり」限定。過剰同意バイアス・権威バイアス・均質化バイアス等の他の集団バイアスは将来拡張ロードマップ。

---

## 出力（2ファイル・デフォルトパス）

- **報告時の平易な解説併記（必須）**: 統合結果をユーザーに提示する時は、専門説明の後に素人にもわかる一言（💡一言でいうと）を必ず併記する（CLAUDE.md平易解説ルール）
- **デフォルト出力先**: `./multi-llm-review_<timestamp>/`
- **改訂案**（`revised_proposal.md`）: 本文（元案構造保持）＋**却下サマリ**＋「根拠 Y」。Step6.5成立時は冒頭に**集団サボりバイアス疑義の行動可能警告**（反証シナリオ+再確認推奨）を機械挿入
- **review_log.md**: 全指摘の `{LLM, issue, severity(正規化), quote, decision(採用/却下/保留), reason}`（重要度順・上位Nを本体・残りは折りたたみ/参照リンク）。**decision 行のフォーマット例**: `decision: 採用 / reason: [当初目的:X]の要件R3を満たすため・quote Yが該当`（判断が目的から演繹であることを追跡可能に・spec尊重却下も理由1行で明記）

### 実測証跡と計測frontmatter（2026-08-17追加・判断収束ループ計測用）

revised_proposal.md には frontmatter で以下の3数値を記載する（判断収束ループ「3回計測」の自動蓄積・レビュー経緯は `00_SYSTEM/マルチLLMレビュー/2026-08-17_判断収束ループ計測自動化-設計レビュー/revised_proposal.md`）:

```yaml
findings_total: <指摘総数>
converted_to_cmd: <検証コマンドに変換できた数>
overturned_by_measurement: <実測で覆した数>
```

- **「実測で覆した」の定義（境界3規則つき）**: LLMの指摘・主張が検証コマンド（grep/wc/curl/gh等）の実行結果と矛盾し、**採用撤回・却下・設計変更に至った件**。(a) 部分覆は二値丸め（0.5件扱いなし）(b) 表記修正レベルは除外（構造・事実判断のみ）(c) コマンド実行失敗（エラー）は不採用 (d) 文言裁定・合議のみは不可算
- **「## 実測証跡」セクション必須**: 覆した件ごとに `### 証跡N`（検証コマンド1行+出力抜粋）を列記。**frontmatter の `overturned_by_measurement` は `0 < overturned ≤ 証跡項目数` を満たすこと**（証跡には「確認系」も含まれるため一致は不要・2026-08-18実測で1<3・1<5の正当な不一致を確認し「一致」から修正）→ LLMによる数値の盛り・架空証跡を機械的に封じる
- **引用制約**: 実行していないコマンド・ユーザーが提供していない実行結果の引用は禁止
- **集約（判断収束台帳）**: 本frontmatterは `claude-config/scripts/obsidian/aggregate_judgment_ledger.py` により `00_SYSTEM/判断収束台帳_計測.md` に自動集約される（手書き追記禁止・`0 < overturned ≤ 証跡数` のクロス検証付き・違反行は「要修正」表示・2026-08-18実装）

## 失敗ログ（呼び出せなかったLLMを残す・2026-08-22実装）

`review_log.md` は「採用/却下した指摘」の記録であって「**呼び出せなかったLLM**」の記録ではない。失敗が どこにも残らないため、2026-08-18 と 2026-08-21 に**同じ OpenRouter 障害を別タスクとして2回バックログ起票**した。これを防ぐ機構。

**記録先**: `~/.claude/state/multi-llm-review.jsonl`（1行1レコード）

| 誰が | 何を | どうやって |
|---|---|---|
| **hook（自動）** | 呼出事実・llm・model・生の成否 | `log-mlr-calls.sh`（PostToolUse）が1行 append。ホストが忘れても必ず残る |
| **ホスト（あなた）** | `round_id`・`topic`・`attempt`・`findings` | **round終了時に `mlr-log.sh annotate` を1回**だけ実行 |

### ① round 終了時に1回だけ実行する（必須・これだけ）

```bash
~/bin/mlr-log.sh annotate <round_id> "<topic>" [--findings <llm>=<件数>,...]
```

- `round_id` は `YYYYMMDD-HHMMSS`（フォールバックを使った round は `fb-` prefix）
- `--findings` は任意（指標A/Bの算出には不要）。付けるなら各LLMの指摘件数
- 直近6時間の `status=raw` 行がまとめて `annotated` になる。**attempt は自動採番**なので数えなくてよい
- 対象0件なら警告して非0で終わる（無言で握り潰さない）。**レビュー本体は続行してよい**——ログ書込の失敗でレビューを人質にしない

> `status=raw` のまま残った行が「補記し忘れ」の可視化そのもの。件数は `~/bin/mlr-log.sh --self-test` で分かる。

### ② 失敗をバックログに起票する前に必ず引く（二重起票の防止）

**検索キーは `reason` × `model` の2軸に固定する**（軸がバラバラだと互いに「新規」と誤判定して同じ失敗を何度も起票する）:

```bash
grep '"model": "<対象モデル>"' ~/.claude/state/multi-llm-review.jsonl | grep '"reason": "<対象reason>"'
```

- `backlogged: true` の行があれば**起票済み**。新規に起票しない（既存タスクに追記する）
- 新規に起票したら、その行の `backlogged` を true にする

`reason` の値: `thinking_overflow`（思考が枠を食い尽くし本文が空）/ `empty_body_keepalive_only`（200だが本文空）/ `truncated` / `no_parseable_findings` / `timeout` / `auth_401` / `rate_limited_429` / `payment_required_402` / `partial_rescued`（一部救出＝ok側）/ `other`

### ③ 慢性的に失敗しているモデルの見分け方

| 指標 | 定義 | 答える問い |
|---|---|---|
| **A: 初回成功率** | `attempt=1` の ok件数 ÷ `attempt=1` の全件数 | 「素で呼んで通るか？」 |
| **B: 機体確保率** | okが1件以上出た round数 ÷ そのllmを呼んだ round数 | 「実際に多様性を確保できたか？」 |

- 指標Aを `attempt=1` に限るのは、「毎回初回timeout・再試行で必ず成功」と「初回から半分成功」を同値にしないため
- 集計対象は `status=annotated` の行のみ（`raw` は補記漏れなので分母に入れない）
- **フォールバック運用下で `attempt=1` のモデルが低いのは設計通り**であって慢性故障ではない

> spec: `obsidian-ssot/docs/superpowers/specs/2026-08-21-multi-llm-review-failure-log-design.md`
> 撤退基準（§10）: 導入1週間後に `status=raw` 残存が減らなければホスト補記は機能していないと判定し、curl系のラッパー化（D案）へ移行する。

## コスト・レート制限

- 各LLMの RPM/TPM 制限を考慮。3並列で制限抵触時（HTTP 429 受信等）は**順次化または2モデルに縮退**
- 対象サイズが大きい場合は**要約を渡す**（元案全文でなく観点に関連する部分）→ **要約時は Fact Check スキップ**（Step3 参照）

## WSL（GLMホスト時）の統合スキップ

- **指摘件数 > 50** または **統合入力 > 100K トークン（推定）** の場合、「統合スキップ・並列出力を束ねるだけ」をユーザーに提案（統合負荷がホストに集中するため）
- review_log.md は LLM別グルーピングで出力

## impact モード（影響範囲分析）

> 自動起動はしない（手動発動・例外: 静的危険操作カタログ一致時のみ層aが限定自動発動を推奨）。
> LLMの「想像力の欠如」（変更の副作用を未来投影で想像できない）を、複数LLMペルソナで補完する。

### トリガー
- 「impact」「影響範囲分析」「未来の副作用」「取りこぼしチェック」

### 層a（自動・PostToolUse）
- `git diff --unified=0` 走査 → trigger_keywords 正規化マッチ → category enum 判定
- additionalContext に 3択（「起動 / 無視 / 何もしない」）を軽量注入
- 検知失敗は silent skip + 検知失敗カウンタ（spec §5.1）

### 層b（手動発動・本モードの本体）
- 入力: 変更内容（git diff）+ antipatterns.md 抜粋 + dangerous-ops 一致情報
- ペルソナ分割（spec §3.2）: 2機時 = P1+P2 / triple時 = P1+P2+P3
  - P1 ドメイン専門家 / P2 破壊的変更検知 / P3 時系列変化
- 暫定コスト上限: P1=8k/30s/$0.10・P2=6k/20s/$0.08・P3=4k/15s/$0.05・合算$0.30/60s
- Future Logic Check（再設計）: シナリオ現実性を相互検証（正典照合でなく）
- 統合: 指摘LLM数 × severity マトリクスで並び替え

### 静的危険操作カタログ（M7=A'）
- ファイル変更で副作用が起きる系のみ（DBマイグレーション/本番シークレット変更/BLACKLIST追加/閾値変更/権限スコープ）
- 一致時: 層aが「限定自動発動候補」を追加注入
- コマンド実行系（`git push --force`等）は Phase2 送り

### ゴールデンセット（精度評価用）
- #7 BLACKLIST副作用 / #8 キーワードトリガー早合点 / #9 未来シナリオ想像の欠如
- 想定2件（実装時に合成データ追加）

### 既存 multi-llm-review との関係
- 層bは既存の「8ステップ統合ロジック」（§266 以降）を再利用して impact モードで起動
- ペルソナ以外の Step1〜8 は変更なし（破壊的変更は最小化）
- 既存 opt-out フラグ `--no-impact` で layer-b 影響を回避可能

### 詳細参照
- spec: `docs/superpowers/specs/2026-07-30-multi-llm-review-impact-mode-design.md` v0.2
- antipatterns: `00_SYSTEM/impact-antipatterns.md`
- dangerous-ops: `00_SYSTEM/dangerous-ops.yaml`

## YAGNI（切り捨て）

- 反復ラウンド（1ラウンド固定）・第4のパーティ判定役・採用率の数値ルール・自動LLM選択（利用可能LLM全部を呼ぶ）・自発発動（手動のみ）

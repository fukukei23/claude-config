---
name: multi-llm-review
description: 設計・コード・文章を複数の異なるLLMに並列独立レビューさせ、ホストLLMが当初目的を基準に取捨統合して改訂案を作る。手動発動のみ。ユーザーが「マルチLLMレビューして」「複数LLMでレビュー」「panel review」「jury review」「クロスLLMレビュー」などと依頼した時に使う。
disable-model-invocation: true
---

# multi-llm-review

## 概要

レビュー対象（設計/コード/文章）を複数の**異なるLLM**に並列独立レビューさせ、ホストLLM（現在動いているLLM）が**当初目的を唯一の基準**に取捨選択して元案へ統合し、よりよい改訂案を作る。

**核心価値: モデル多様性**。既存の `doubt-driven-development`（同LLM adversarial）/ `sentaku` L3（同LLM弁証）/ `superpowers:dispatching-parallel-agents`（同LLM並列）は全て **context 多様性**。本スキルは **異なるLLMの死角を補完する** ことで直交する価値を提供する。

## トリガーワード（手動発動のみ）

- 「マルチLLMレビューして」「複数LLMでレビュー」
- 「panel review」「jury review」「クロスLLMレビュー」
- `/multi-llm-review`

## 既存スキルとの棲み分け（機械的振り分け表）

| 状況 | 起動スキル |
|---|---|
| 実装前・選択肢なし（単一案を叩く） | `doubt-driven-development` |
| 既存案 A/B/C から選ぶ | `sentaku` L3 |
| 既存案を改良したい（多LLM独立レビュー→統合） | **multi-llm-review（本）** |
| 「〜して」と作業依頼 | スキル不起動 |

曖昧な場合はユーザーに確認する。

---

## 環境前提（2層・ホスト以外の利用可能LLM全部を自動呼出）

| 環境 | ホストLLM（統合役） | レビュアーLLM（自動呼出） |
|---|---|---|
| WSL CLI版 | GLM | MiniMax + Gemini（2） |
| Windows デスクトップアプリ版 | Sonnet | GLM + MiniMax + Gemini（3） |

- ホスト自身はレビュアーに含めない（自己レビューは多様性ゼロ）
- ホスト以外の利用可能LLM全部を自動呼出（利用不能LLMは discover で検知してスキップ）

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

## 外部LLM呼出手段（経路分岐表）

| LLM | 通信方式 | 認証 | 備考 |
|---|---|---|---|
| MiniMax | `mcp__minimax__minimax_ask`（MCP） | MCP設定 | 同一メッセージで他curlと並列可能・JSON多指摘対策で `max_tokens=8000` 推奨 |
| Gemini | curl REST（`gemini-3.1-pro-preview`） | `$GEMINI_API_KEY` | `gemini.py` はYouTube専用で不使用 |
| Windows版 GLM | glm-rate-proxy or MCP経由 | プロキシ設定 | WSL版ホスト=GLM自身は呼ばない |

## 実装手順（Claude Code環境・2段階ファイル経由・必須）

直接 curl はクォート/改行エスケープが破綻するため、**2段階ファイル経由**を標準手順とする:

1. **各LLMのAPIリクエストJSONペイロードを一時ファイルに書出**（Write ツール or python3）:
   - `/tmp/req_gemini.json`（Windows Desktop は環境に応じた一時パス）
2. **並列送信**（同一メッセージで2ツール呼出）:
   - MiniMax: `mcp__minimax__minimax_ask`（prompt に同一プロンプトを指定）
   - Gemini: Bash で `curl -s -H "Content-Type: application/json" -d @/tmp/req_gemini.json "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-pro-preview:generateContent?key=$GEMINI_API_KEY"`
3. **JSON抽出**: 結果から**文字種ステートマシン**でJSON配列を再構成（下記「JSON抽出」参照）

> python3 でペイロード生成する例:
> `python3 -c "import json; open('/tmp/req_gemini.json','w').write(json.dumps({'contents':[{'parts':[{'text':PROMPT}]}],'generationConfig':{'temperature':0.4,'maxOutputTokens':3000}},ensure_ascii=False))"`

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
```

### デフォルト観点パック（観点未指定時・全採用／指定時は指定観点のみ）

| 対象 | 観点 |
|---|---|
| 設計 | 目的整合 / 要件網羅 / 代替案検討 / リスク / スケーラビリティ / 実現性 |
| コード | 正確性 / 可読性 / 性能 / セキュリティ / テスタビリティ / 既存規約整合 |
| 文章 | 論理構造 / 明瞭性 / 読者適合 / 誤字脱字 / 出典・事実性 |

`[ロール]` の例: `security reviewer` / `consistency reviewer` / `simplicity advocate` / `performance reviewer` / `clarity reviewer`

---

## JSON抽出（文字種ステートマシン・必須前提）

LLMにはJSON配列のみを返すよう指示するが、markdownブロックや挨拶文を混入する。結果から **文字種ステートマシン** でJSON配列を抽出する:

- 文字列リテラル（`"` で囲まれた範囲）内の `}` は**無視**して split する（`{"quote":"if(x){}"}` 破綻回避）
- 抽出した要素のうち **必須key（`issue`/`severity`/`quote`/`suggestion`）が全て揃った指摘が ≥50%** なら成功・未満ならテキスト扱いで統合（Step1の閾値）

python3 抽出実装例（実行時にホストLLMが `python3 -c` で構築・使用）:

```python
import json, sys
def extract_issues(text):
    # [{ ... }, { ... }] を取り出す最初の [ から最後の ] まで
    s = text.find('[')
    e = text.rfind(']')
    if s == -1 or e == -1 or e < s:
        return []
    body = text[s+1:e+1]  # [ ... ] 全体
    # 文字種ステートマシンで文字列内を無視しつつ } で要素分割
    items, buf, in_str, esc = [], '', False, False
    depth = 0
    for ch in body:
        buf += ch
        if esc:
            esc = False; continue
        if ch == '\\':
            esc = True; continue
        if ch == '"':
            in_str = not in_str; continue
        if in_str:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    items.append(json.loads(buf.strip()))
                except Exception:
                    pass
                buf = ''
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
   - **※要約渡し時（対象サイズ大）は Fact Check をスキップ**（要約ベースでは quote が元案と一致せず全却下される矛盾を回避）
4. **ペルソナ切替（著者バイアス対策）**: 「あなたは元案の作者ではない。冷徹な品質管理責任者として外部指摘を客観的に裁定せよ」＋盲点カタログ（著者が見落としがちな観点を列挙）＋devil's advocate（自分がこの指摘を出した側ならどう反論するか）
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

---

## 出力（2ファイル・デフォルトパス）

- **デフォルト出力先**: `./multi-llm-review_<timestamp>/`
- **改訂案**（`revised_proposal.md`）: 本文（元案構造保持）＋**却下サマリ**＋「根拠 Y」
- **review_log.md**: 全指摘の `{LLM, issue, severity(正規化), quote, decision(採用/却下/保留), reason}`（重要度順・上位Nを本体・残りは折りたたみ/参照リンク）

## コスト・レート制限

- 各LLMの RPM/TPM 制限を考慮。3並列で制限抵触時（HTTP 429 受信等）は**順次化または2モデルに縮退**
- 対象サイズが大きい場合は**要約を渡す**（元案全文でなく観点に関連する部分）→ **要約時は Fact Check スキップ**（Step3 参照）

## WSL（GLMホスト時）の統合スキップ

- **指摘件数 > 50** または **統合入力 > 100K トークン（推定）** の場合、「統合スキップ・並列出力を束ねるだけ」をユーザーに提案（統合負荷がホストに集中するため）
- review_log.md は LLM別グルーピングで出力

## YAGNI（切り捨て）

- 反復ラウンド（1ラウンド固定）・第4のパーティ判定役・採用率の数値ルール・自動LLM選択（利用可能LLM全部を呼ぶ）・自発発動（手動のみ）

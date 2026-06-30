---
name: proxy-doctor
description: |
  glm-rate-proxy（localhost:8787）の診断・修復スキル。
  Claude Code CLI のバックエンドとして GLM / MiniMax を使うためのローカルプロキシが
  止まっている・エラーが出る・MiniMax フォールバックが失敗するなどの問題を素早く診断し、
  対処法を案内する。

  以下のキーワードで必ずトリガーすること：
  - /proxy-doctor
  - プロキシが壊れた / プロキシがおかしい / プロキシ直して / proxy直して
  - GLMが使えない / MiniMaxに切り替わらない / フォールバックが失敗した
  - 400エラーが出る / 401エラー / 429が頻発 / proxy止まってる / プロキシを診断して
  - Claude Code CLIが動かない（LLMエラー系）
---

# proxy-doctor — glm-rate-proxy 診断スキル

glm-rate-proxy は Claude Code CLI が GLM (ZAI) / MiniMax へ接続するためのローカルプロキシ
（localhost:8787）。このスキルは「止まる・遅い・エラーが出る」を素早く診断し、
具体的な対処コマンドを提示する。

**スコープ**: 診断 + 案内のみ。ソースコードの自動書き換えはしない。
修正が必要な場合はコマンドを提示し、ユーザー確認後に実行する。

---

## 重要: プロキシが止まっても Claude Code は動く

```
Claude Code 起動時の .bashrc claude() 関数の判定フロー:
  → プロキシ (localhost:8787) に接続できる → プロキシ経由（フォールバックあり）
  → 接続できない → ZAI 直結（フォールバックなし・安定）
```

**ユーザーが何かする必要はない。新しいターミナルを開けば自動でZAI直結で動く。**
プロキシ停止 = 詰む、ではなく、プロキシ停止 = MiniMaxフォールバックだけ失う、が正しい理解。

緊急時に「今すぐプロキシをやめてZAI直結に戻す」コマンド:
```bash
pkill -f glm_rate_proxy
# 次に新しいターミナルで claude を起動すれば自動でZAI直結になる
```

---

## Phase 1: 情報収集（必ず4つ全部実行）

```bash
# 1. プロセス確認（ブラケット技で自分自身を除外・複数起動も検出）
ps -eo pid,cmd | grep "[g]lm_rate_proxy"

# 2. 現在の接続先を確認（プロキシ向きかZAI直結か）
echo "ANTHROPIC_BASE_URL: $ANTHROPIC_BASE_URL"

# 3. ステータス取得（/tmp がない場合は接続拒否 → パターン A）
curl -s http://127.0.0.1:8787/proxy/status | python3 -m json.tool

# 4. 直近ログ（WSL2再起動後はファイルが消えている場合あり → パターン A）
tail -60 /tmp/glm-proxy.log 2>/dev/null || echo "[ログなし: プロキシ未起動またはWSL2再起動後]"
```

**注意 — 複数プロセスが ps に表示された場合:**
```bash
# 全プロセスを一度停止してから再起動する
pkill -f "[g]lm_rate_proxy" && sleep 2
bash ~/.claude/scripts/llm/start-glm-proxy.sh
```

**注意 — last_request_mb が 28 以上の場合:**
次のリクエストで Claude Code がクライアント側（プロキシより手前）で 32MB 上限エラーを出す可能性がある。
プロキシにリクエストが届かないためフォールバックも発動しない。`/compact` または `/new-session` で履歴を圧縮すること。

---

## Phase 2: 症状分類

400 エラーが出ている場合の判定順序:
1. ログに `orphan tool_result` あり → **パターン B**
2. `peak_block=true` + orphan なし → **パターン D**
3. 全リクエストが即座にエラー（遅延なし）→ **パターン I（APIキー無効）**

---

### パターン A: proxy が停止 / WSL2 再起動後

判定: プロセスなし or curl が接続拒否 or ログファイルが存在しない

まず確認: **新しいターミナルでClaude Codeを起動すれば自動でZAI直結になる（何もしなくていい）。**
プロキシを再起動したい場合のみ以下を実行:

```bash
bash ~/.claude/scripts/llm/start-glm-proxy.sh
```

start-glm-proxy.sh が存在しない・失敗する場合の手動起動:
```bash
source ~/.secrets.env
cd ~/.claude/scripts/glm-rate-proxy
PYTHONPATH=src nohup python3 -m glm_rate_proxy > /tmp/glm-proxy.log 2>&1 &
sleep 2 && curl -s http://127.0.0.1:8787/proxy/status | python3 -m json.tool
```

---

### パターン B: 400 tool-id-not-found エラー

判定: ログに `orphan tool_result` または `tool id not found`

原因: GLM の thinking モードで tool_use が会話履歴から欠落し、
orphan な tool_result だけが MiniMax に送られている。

確認 (修正済みかチェック):
```bash
grep -n "removing.*orphan" ~/.claude/scripts/glm-rate-proxy/src/glm_rate_proxy/tool_sanitizer.py
```

- "removing" が見つかる → 修正済みだが別原因。ログ前後をさらに精査
- "removing" がない → 旧バージョン。ユーザーに確認の上で修正

proxy 再起動:
```bash
pkill -f "[g]lm_rate_proxy" && sleep 1
bash ~/.claude/scripts/llm/start-glm-proxy.sh
```

---

### パターン C: 429 レート制限が頻発

判定: ログに 429 / RateLimitError、usage_pct が高い

```bash
curl -s http://127.0.0.1:8787/proxy/status | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print('usage:', d['usage_pct'], '% / mode:', d['mode'])"
```

| usage_pct | 期待モード | 対処 |
|---|---|---|
| < 80% | normal | ZAI の一時制限。数分待つ |
| 80〜95% | economy (GLM-4.7) | 自動切替済み |
| >= 95% | emergency (GLM-4.7-Flash) | MiniMax 強制切替を検討 |

MiniMax 強制: config.json の peak_hours を start_hour=0 / end_hour=24 に設定 → proxy 再起動

---

### パターン D: peak_block 中の 400（MiniMax APIキー問題）

判定: peak_block=true かつ 400、ログに orphan の記録なし

原因: MiniMax の APIキーが無効・変更後に旧キーが残っている

対処: ~/.secrets.env の MINIMAX_API_KEY を更新 → proxy 再起動

緊急回避（GLM 直結に戻す）:
```bash
pkill -f "[g]lm_rate_proxy" && sleep 1
source ~/.secrets.env
cd ~/.claude/scripts/glm-rate-proxy
GLM_PEAK_BLOCK=false PYTHONPATH=src nohup python3 -m glm_rate_proxy > /tmp/glm-proxy.log 2>&1 &
```

---

### パターン E: タイムアウト / 応答が極端に遅い

判定: ログに timeout / ハング

原因候補: thinking モードの暴走（budget_tokens 超過）

確認:
```bash
CFG=~/.claude/scripts/glm-rate-proxy/config/config.json
python3 -c "import json; c=json.load(open('$CFG')); t=c.get('thinking',{}); print(t.get('mode'), t.get('budget_tokens'))"
```

対処: config.json の thinking.mode を "always_off" に変更 → proxy 再起動
```bash
pkill -f "[g]lm_rate_proxy" && sleep 1 && bash ~/.claude/scripts/llm/start-glm-proxy.sh
```

---

### パターン F: emergency mode (usage_pct 99%) に固定

判定: usage_pct が99%のまま変わらない、ZAIのダッシュボードでは実際の使用率がリセット済み

原因: 旧バグ（5/24修正済み）の再発 or 5時間リセット後に成功リクエストが届いていない

対処: proxy 再起動（成功レスポンスのヘッダーで使用率が自動更新される）
```bash
pkill -f "[g]lm_rate_proxy" && sleep 1 && bash ~/.claude/scripts/llm/start-glm-proxy.sh
```

---

### パターン G: settings.json が勝手にプロキシ向きに書き換わる

判定: Claude Code 起動のたびに ANTHROPIC_BASE_URL が http://127.0.0.1:8787 に戻る

原因: `start-glm-proxy.sh` の SessionStart フックが settings.json を強制書き換えしている（5/20 の既知問題）

確認:
```bash
grep "start-glm-proxy\|8787" ~/.claude/settings.json 2>/dev/null
python3 -c "import json; d=json.load(open('/home/yn4416/.claude/settings.json')); print(d.get('env',{}).get('ANTHROPIC_BASE_URL','未設定'))"
```

対処: SessionStart フックから start-glm-proxy.sh を削除、または以下で即時回避:
```bash
pkill -f glm_rate_proxy   # プロキシを止めれば書き換えが止まる
```

---

### パターン H: プロキシは起動しているが Claude Code が使っていない

判定: ps でプロセスあり・status 正常、しかし Claude Code のエラーが ZAI 直結のもの
（例: `ANTHROPIC_BASE_URL` が `https://api.z.ai/api/anthropic` のまま）

原因: `.bashrc` の `claude()` 関数がプロキシを検出できていない or 環境変数が上書きされていない

確認:
```bash
echo "ANTHROPIC_BASE_URL: $ANTHROPIC_BASE_URL"
# → https://api.z.ai/api/anthropic なら .bashrc の claude() が機能していない
# → http://127.0.0.1:8787 ならプロキシ経由になっている
```

対処: 現在のターミナルを閉じて新しいターミナルで claude を起動する（.bashrc が再実行される）

---

### パターン I: 401 Unauthorized（APIキーが無効・期限切れ）

判定: ログに 401 / unauthorized / authentication / invalid_api_key
症状: 全リクエストが遅延なく即座にエラーで返る

確認:
```bash
# ZAI APIキーが設定されているか（値は表示しない）
grep -E "^ANTHROPIC_AUTH_TOKEN=" ~/.secrets.env | sed 's/=.*/=<REDACTED>/'
```

原因候補:
- ZAI の APIキーが期限切れ / リセットされた（ZAI ダッシュボードで確認）
- MiniMax の APIキーが期限切れ（peak_block 中に401が出る場合）
- ~/.secrets.env の更新後に proxy が旧キーを保持している

対処:
1. ZAI または MiniMax のダッシュボードでキーを確認・再発行
2. `~/.secrets.env` を更新（値の直接確認・表示はセキュリティルール違反）
3. proxy 再起動で新しいキーを読み込む:
```bash
pkill -f "[g]lm_rate_proxy" && sleep 1
bash ~/.claude/scripts/llm/start-glm-proxy.sh
```

---

### パターン J: 正常

判定: プロセスあり、status 取得成功、ログにエラーなし、ANTHROPIC_BASE_URL がプロキシ向き

ステータスをそのまま表示して終了。

---

## Phase 3: 診断レポート出力フォーマット

```
## proxy-doctor 診断結果

プロセス      : 起動中 (PID: XXXX) / 停止中 / 複数起動
BASE_URL      : http://127.0.0.1:8787（プロキシ経由）/ https://api.z.ai/...（直結）
モード        : normal / peak_block / economy / emergency
プロバイダ    : zai / minimax
ZAI使用率     : XX.X%
直近リクエスト: X.XMB [28MB超の場合は警告]
ピークブロック: true / false

【検出された問題】 パターン X: ...
【原因】 1行で

【推奨対処】
（コマンドまたは手順）

実行しますか？
```

yes の場合のみ実行する。コードの自動書き換えはユーザーが明示的に依頼した場合のみ行う。

---

## 参考: よく使うコマンド

```bash
# 使用量・モード・モデルを1行で確認
curl -s http://127.0.0.1:8787/proxy/status | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(f\"usage:{d['usage_pct']}% mode:{d['mode']} model:{d['last_actual_model']} req:{d.get('last_request_mb',0)}MB\")"

# ログ監視
tail -f /tmp/glm-proxy.log

# 再起動（推奨）
pkill -f glm_rate_proxy && sleep 1 && bash ~/.claude/scripts/llm/start-glm-proxy.sh

# ZAI直結に戻す（プロキシを止めるだけ・新しいターミナルで自動切替）
pkill -f glm_rate_proxy
```

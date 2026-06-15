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
  - 400エラーが出る / 429が頻発 / proxy止まってる / プロキシを診断して
  - Claude Code CLIが動かない（LLMエラー系）
---

# proxy-doctor — glm-rate-proxy 診断スキル

glm-rate-proxy は Claude Code CLI が GLM (ZAI) / MiniMax へ接続するためのローカルプロキシ
（localhost:8787）。このスキルは「止まる・遅い・エラーが出る」を素早く診断し、
具体的な対処コマンドを提示する。

**スコープ**: 診断 + 案内のみ。ソースコードの自動書き換えはしない。
修正が必要な場合はコマンドを提示し、ユーザー確認後に実行する。

---

## Phase 1: 情報収集（必ず3つ全部実行）

```bash
# 1. プロセス確認（ブラケット技で自分自身を除外）
ps -eo pid,cmd | grep "[g]lm_rate_proxy"

# 2. ステータス取得
curl -s http://127.0.0.1:8787/proxy/status | python3 -m json.tool

# 3. 直近ログ
tail -60 /tmp/glm-proxy.log
```

---

## Phase 2: 症状分類

### パターン A: proxy が停止

判定: プロセスなし or curl が接続拒否

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

確認:
```bash
grep -n "removing.*orphan" ~/.claude/scripts/glm-rate-proxy/src/glm_rate_proxy/tool_sanitizer.py
```

- "removing" が見つかる → 修正済みだが別原因。ログ前後を精査
- "removing" がない → 旧バージョン。ユーザーに確認の上で修正

proxy 再起動:
```bash
pkill -f "[g]lm_rate_proxy" && sleep 1
source ~/.secrets.env
cd ~/.claude/scripts/glm-rate-proxy
PYTHONPATH=src nohup python3 -m glm_rate_proxy > /tmp/glm-proxy.log 2>&1 &
sleep 2 && curl -s http://127.0.0.1:8787/proxy/status
```

---

### パターン C: 429 レート制限が頻発

判定: ログに 429 / RateLimitError、usage_pct が高い

| usage_pct | 期待モード | 対処 |
|---|---|---|
| < 80% | normal | ZAI の一時制限。数分待つ |
| 80〜95% | economy (GLM-4.7) | 自動切替済み。last_actual_model を確認 |
| >= 95% | emergency (GLM-4.7-Flash) | MiniMax 強制切替を検討 |

MiniMax 強制: config.json の peak_hours を start_hour=0 / end_hour=24 に設定 → proxy 再起動

---

### パターン D: peak_block 中の 400（APIキー問題）

判定: peak_block=true かつ 400、ログに orphan の記録なし

原因: MiniMax の APIキーが無効・変更後に旧キーが残っている

対処: ~/.secrets.env の MINIMAX_API_KEY を更新 → proxy 再起動

緊急回避（GLM 直結）:
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

---

### パターン F: 正常

判定: プロセスあり、status 取得成功、ログにエラーなし

ステータスをそのまま表示して終了。

---

## Phase 3: 診断レポート出力フォーマット

```
## proxy-doctor 診断結果

プロセス      : 起動中 (PID: XXXX) / 停止中
モード        : normal / peak_block / economy / emergency
プロバイダ    : zai / minimax
ZAI使用率     : XX.X%
直近リクエスト: X.XMB
ピークブロック: true / false

【検出された問題】 パターン X: ...
【原因】 1行で

【推奨対処】
（コマンドまたは手順）

実行しますか？
```

yes の場合のみ実行する。コードの自動書き換えはユーザーが明示的に依頼した場合のみ行う。

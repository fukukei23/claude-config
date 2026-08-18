#!/bin/bash
# dryrun_check.sh — Step0: レビュー LLM API 疏通 fail-fast
#
# auto-loop が run_multi_llm_review() を呼ぶ前に、Gemini/MiniMax/OpenRouter の
# APIキー存在（毎タスク）と実疎通（セッション起動時1回）を確認する。
# 1つでも欠けたら即 abort（Windows 側の認証状態への暗黙依存を排除）。
#
# Usage:
#   dryrun_check.sh           # APIキー存在確認のみ（毎タスク・軽量）
#   dryrun_check.sh --full    # 実API疎通 health check も実行（approve.py 起動時等）
#
# 戻り値: 0=OK / 1=NG（欠け）
# ※ APIキー値は絶対に stdout/stderr に出さない（[[ -n ]] で存在確認のみ）
# ※ 責務分離: 本チェックは「検知層」。実行時（run_multi_llm_review）は
#    キー欠落・片系障害でも 2社縮退で継続する「耐性層」（3社化・2026-08-18）
set -uo pipefail

# ~/.secrets.env を source（値は環境変数に展開・echo しない）
set +u  # .secrets.env 内の未定義変数参照で set -u が exit するのを回避
# shellcheck disable=SC1091
source ~/.secrets.env 2>/dev/null
set -u

# --- APIキー存在確認（毎タスク） ---
for key in GEMINI_API_KEY MINIMAX_API_KEY OPENROUTER_API_KEY; do
  # ${!key} 間接展開で値を参照・[[ -n ]] で存在確認のみ（echo しない）
  if [[ -z "${!key:-}" ]]; then
    echo "[dryrun_check] NG: $key 未設定（~/.secrets.env 確認）" >&2
    exit 1
  fi
done

# --- 実API疎通（--full 指定時のみ・セッション起動時1回） ---
if [[ "${1:-}" == "--full" ]]; then
  # Gemini health check（gemini_text.py で短文応答確認・値は出さない）
  if ! python3 ~/projects/claude-config/scripts/api/gemini_text.py --prompt "reply ok" >/dev/null 2>&1; then
    echo "[dryrun_check] NG: Gemini API 疏通失敗（GEMINI_API_KEY / モデル退役確認）" >&2
    exit 1
  fi
  # MiniMax health check（ask-minimax.py で短文応答確認・値は出さない）
  if ! python3 ~/.claude/scripts/llm/ask-minimax.py "reply ok" >/dev/null 2>&1; then
    echo "[dryrun_check] NG: MiniMax API 疏通失敗（MINIMAX_API_KEY 確認）" >&2
    exit 1
  fi
  # OpenRouter health check（短文実呼出で200確認・値は出さない）
  # ※ /models は認証が甘く実証にならないため chat/completions を実呼出（採用D）
  OR_MODEL="${OPENROUTER_MODELS:-cohere/north-mini-code:free}"
  OR_MODEL="${OR_MODEL%%,*}"  # 先頭モデルのみ（カンマ区切り複数指定対応）
  OR_HTTP=$(python3 - "$OR_MODEL" <<'PYEOF' 2>/dev/null
import json, os, sys, urllib.request
model = sys.argv[1]
payload = json.dumps({"model": model, "max_tokens": 5,
                      "messages": [{"role": "user", "content": "reply ok"}]}).encode()
req = urllib.request.Request(
    "https://openrouter.ai/api/v1/chat/completions",
    data=payload,
    headers={"Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY','')}",
             "Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(resp.status)
except urllib.error.HTTPError as e:
    print(e.code)
except Exception:
    print("0")
PYEOF
)
  if [[ "$OR_HTTP" != "200" ]]; then
    echo "[dryrun_check] NG: OpenRouter API 疏通失敗（HTTP=$OR_HTTP・OPENROUTER_MODELS 退役確認: 環境変数で上書き可）" >&2
    exit 1
  fi
  echo "[dryrun_check] OK: 3ベンダー API 疏通確認済み"
else
  echo "[dryrun_check] OK: APIキー存在確認済み（実疎通は --full）"
fi

exit 0

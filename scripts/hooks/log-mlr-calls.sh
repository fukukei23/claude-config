#!/usr/bin/env bash
# log-mlr-calls.sh — PostToolUse Hook: multi-llm-review の外部LLM呼出を JSONL に1行記録する
#
# spec: obsidian-ssot/docs/superpowers/specs/2026-08-21-multi-llm-review-failure-log-design.md
# 設計原則: 失敗記録の網羅を、失敗しうる主体（自然言語で動くホストLLM）に依存させない
#
# 責務（hook が原理的に知り得る情報のみ）:
#   ts / llm / model / result(暫定) / reason(暫定) / http / finish_reason
# ホストが `bash ~/bin/mlr-log.sh annotate` で後から補記する（bash明示・実行ビット消失対策）:
#   round_id / topic / attempt / findings / status=annotated
#
# 必須条件（spec §6・レビュー3機の指摘）:
#   1. 対象ツール以外は即 exit 0（早期リターン・重い処理はコールドパスのみ）
#   2. append 1行のみ（集計・アラート等はやらない）
#   3. flock でファイルロック（無い環境では 1行 append の原子性に依拠）
#   4. 共通hook群とは別ファイルに隔離（本フックの事故を全体へ波及させない）
#   5. bash -n 構文チェック（test_log_mlr_calls.sh [1]）
#   6. 判別は allowlist 完全一致 + 除外リスト
#
# 機密: tool_input.command 全文はログに書かない（APIキー混入回避・ドメインとモデル名のみ抽出）
#
# テスト: bash scripts/hooks/test_log_mlr_calls.sh

set -uo pipefail

INPUT=$(cat 2>/dev/null) || exit 0
[ -z "$INPUT" ] && exit 0

# --- 早期リターン（ホットパス）------------------------------------------------
# allowlist のいずれの識別子も含まないなら python3 を起動せず即終了。
# 大半の PostToolUse はここで終わる（grep 1回・数百µs）。
case "$INPUT" in
  *minimax_ask*|*glm_ask*|*generativelanguage.googleapis.com*|*openrouter.ai*) ;;
  *) exit 0 ;;
esac

# --- 記録先の解決（$HOME 非依存・2026-08-22 の「静かな失敗」対策）-------------
# Windows Desktop 版から実行されると $HOME が C:\Users\... を指し WSL 側の
# ~/.claude/state に到達できない。候補を順に探して最初に実在したものを使う。
_state_dir() {
  local d
  # MLR_STATE_DIR は明示指定なので最優先（無ければ作る・テストの隔離にも使う）
  if [ -n "${MLR_STATE_DIR:-}" ]; then
    mkdir -p "$MLR_STATE_DIR" 2>/dev/null || return 1
    printf '%s' "$MLR_STATE_DIR"; return 0
  fi
  for d in "${HOME:-}/.claude/state" "/home/yn4416/.claude/state"; do
    [ -n "$d" ] && [ -d "$d" ] && { printf '%s' "$d"; return 0; }
  done
  # どれも実在しなければ $HOME 側に作成を試みる
  if [ -n "${HOME:-}" ] && mkdir -p "$HOME/.claude/state" 2>/dev/null; then
    printf '%s' "$HOME/.claude/state"; return 0
  fi
  return 1
}

STATE_DIR="$(_state_dir)" || exit 0
LOG_FILE="$STATE_DIR/multi-llm-review.jsonl"

# --- コールドパス: レコード組み立て -------------------------------------------
RECORD=$(printf '%s' "$INPUT" | PYTHONIOENCODING=utf-8 python3 -c '
import json, os, re, sys
from datetime import datetime

def out_nothing():
    raise SystemExit(0)

try:
    d = json.load(sys.stdin)
except Exception:
    out_nothing()
if not isinstance(d, dict):
    out_nothing()

tool_name = d.get("tool_name") or ""
tool_input = d.get("tool_input") or {}
if not isinstance(tool_input, dict):
    tool_input = {}
resp = d.get("tool_response")

# ---- allowlist 完全一致で llm を判別 ----------------------------------------
MCP_MAP = {
    "mcp__minimax__minimax_ask": "minimax",
    "mcp__glm__glm_ask": "glm",
}
# 誤検出除外（疎通確認・モデル一覧など「レビュー呼出でない」curl）
EXCLUDE_PATH = ("/api/v1/key", "/api/v1/models", "/api/v1/credits", "/rate_limit")

llm = None
model = None
via_mcp = False
command = ""

if tool_name in MCP_MAP:
    llm = MCP_MAP[tool_name]
    via_mcp = True
    m = tool_input.get("model")
    model = m if isinstance(m, str) and m else None
elif tool_name in ("Bash", "BashOutput"):
    command = tool_input.get("command") or ""
    if not isinstance(command, str):
        out_nothing()
    if any(p in command for p in EXCLUDE_PATH):
        out_nothing()
    if "generativelanguage.googleapis.com" in command:
        llm = "gemini"
        mm = re.search(r"models/([A-Za-z0-9._-]+):generateContent", command)
        model = mm.group(1) if mm else None
    elif "openrouter.ai" in command:
        llm = "openrouter"
        mm = re.search(r"[\"\x27]model[\"\x27]\s*:\s*[\"\x27]([^\"\x27]+)", command)
        if mm:
            model = mm.group(1)
        else:
            # ペイロードは -d @file 経由が標準手順。model フィールドのみ読む
            # （プロンプト本文は読まない＝機密をログに載せない）
            fm = re.search(r"-d\s+@(\S+)", command)
            if fm:
                path = fm.group(1).strip("\"\x27")
                try:
                    if os.path.getsize(path) < 5_000_000:
                        payload = json.load(open(path, encoding="utf-8"))
                        v = payload.get("model")
                        model = v if isinstance(v, str) and v else None
                except Exception:
                    model = None

if llm is None:
    out_nothing()

# ---- tool_response から本文・エラー情報を取り出す ----------------------------
def response_text(r):
    """MCP は文字列 or content ブロック、Bash は dict(stdout/...)。"""
    if r is None:
        return ""
    if isinstance(r, str):
        return r
    if isinstance(r, list):
        parts = []
        for b in r:
            if isinstance(b, dict):
                t = b.get("text")
                if isinstance(t, str):
                    parts.append(t)
            elif isinstance(b, str):
                parts.append(b)
        return "\n".join(parts)
    if isinstance(r, dict):
        for k in ("stdout", "output", "content", "text", "result"):
            v = r.get(k)
            if isinstance(v, str) and v.strip():
                return v
            if isinstance(v, list):
                return response_text(v)
        return ""
    return ""

def response_stderr(r):
    if isinstance(r, dict):
        for k in ("stderr", "error"):
            v = r.get(k)
            if isinstance(v, str):
                return v
    return ""

body = response_text(resp)
stderr = response_stderr(resp)

http = None
finish_reason = None
result = "fail"
reason = "other"

# ---- ok/fail 判定（spec §5・hook は暫定判定／ホストが annotate で確定）------
parsed = None
if body.strip():
    try:
        parsed = json.loads(body)
    except Exception:
        parsed = None

if via_mcp:
    # MCP 経由は HTTP コードも finish_reason も存在しない（spec §3）
    if body.strip():
        result, reason = "ok", None
    else:
        result, reason = "fail", "empty_body_keepalive_only"
elif parsed is None:
    if not body.strip():
        low = stderr.lower()
        reason = "timeout" if ("timeout" in low or "timed out" in low) else "other"
        result = "fail"
    else:
        # JSON にならない本文（HTMLエラーページ等）
        result, reason = "fail", "other"
else:
    err = parsed.get("error") if isinstance(parsed, dict) else None
    if isinstance(err, dict):
        code = err.get("code")
        if isinstance(code, int):
            http = code
        elif isinstance(code, str) and code.isdigit():
            http = int(code)
        result = "fail"
        reason = {
            401: "auth_401",
            403: "auth_401",
            429: "rate_limited_429",
            402: "payment_required_402",
        }.get(http, "other")
    elif llm == "gemini":
        cands = parsed.get("candidates") or []
        text = ""
        if cands and isinstance(cands[0], dict):
            finish_reason = cands[0].get("finishReason")
            content = cands[0].get("content") or {}
            for p in (content.get("parts") or []):
                if isinstance(p, dict) and isinstance(p.get("text"), str):
                    text += p["text"]
        if text.strip():
            result, reason = "ok", None
        elif finish_reason == "MAX_TOKENS":
            # 思考が枠を食い尽くし本文が空（2026-08-21 に実測した故障モード）
            result, reason = "fail", "thinking_overflow"
        else:
            result, reason = "fail", "empty_body_keepalive_only"
    elif llm == "openrouter":
        choices = parsed.get("choices") or []
        msg = {}
        if choices and isinstance(choices[0], dict):
            finish_reason = choices[0].get("finish_reason")
            msg = choices[0].get("message") or {}
            if not isinstance(msg, dict):
                msg = {}
        content = msg.get("content")
        thinking = msg.get("reasoning") or msg.get("reasoning_content")
        if isinstance(content, str) and content.strip():
            result, reason = "ok", None
        elif finish_reason == "length" and isinstance(thinking, str) and thinking.strip():
            # content ではなく reasoning に思考を出し max_tokens を使い切った
            result, reason = "fail", "thinking_overflow"
        elif finish_reason == "length":
            result, reason = "fail", "truncated"
        else:
            result, reason = "fail", "empty_body_keepalive_only"

rec = {
    "ts": datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"),
    "round_id": None,      # ホストが annotate で補記
    "topic": None,         # ホストが annotate で補記
    "llm": llm,
    "model": model,
    "attempt": None,       # ホストが annotate で補記（llm単位の連番）
    "result": result,
    "reason": reason,
    "http": http,
    "finish_reason": finish_reason,
    "findings": None,      # ホストが annotate で補記（件数のみ）
    "status": "raw",       # raw のまま残る行が「補記漏れ」の可視化そのもの
    "backlogged": False,
}
sys.stdout.write(json.dumps(rec, ensure_ascii=False))
' 2>/dev/null) || exit 0

[ -z "$RECORD" ] && exit 0

# --- append 1行（flock があれば使う）------------------------------------------
if command -v flock >/dev/null 2>&1; then
  (
    flock -w 2 9 || exit 0
    printf '%s\n' "$RECORD" >&9
  ) 9>>"$LOG_FILE" 2>/dev/null
else
  # flock 非搭載環境（Git Bash 等）。1行 append は十分小さく実質原子的
  printf '%s\n' "$RECORD" >>"$LOG_FILE" 2>/dev/null
fi

exit 0

#!/usr/bin/env python3
"""Gemini MCP Server - Google Gemini をレビュー/デバッグ用第2オピニオンとして提供
GLM動作中のCLI(GLM)から呼ばれる「逆MCP」。glm-mcp-server.py 構造踏襲 + Gemini固有制約."""

import json
import sys
import os
import urllib.request
import urllib.error
import time


def _load_key():
    """GEMINI_API_KEY を env → ~/.secrets.env フォールバックで取得."""
    key = os.environ.get('GEMINI_API_KEY', '')
    if key:
        return key
    secrets = os.path.expanduser('~/.secrets.env')
    if os.path.exists(secrets):
        with open(secrets) as f:
            for line in f:
                line = line.strip()
                if line.startswith('export GEMINI_API_KEY='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''


GEMINI_KEY = _load_key()
GEMINI_BASE = 'https://generativelanguage.googleapis.com/v1beta/models'
DEFAULT_MODEL = 'gemini-2.5-pro'
_STATUS_FILE = '/tmp/llm-last-used.txt'


def _write_status(label):
    """ステータスファイルを atomic write（tmp→rename）で記録・並列競合回避."""
    try:
        tmp = _STATUS_FILE + '.tmp'
        with open(tmp, 'w') as f:
            f.write(label)
        os.replace(tmp, _STATUS_FILE)
    except Exception:
        pass


def call_gemini(prompt, model=DEFAULT_MODEL, max_tokens=4000):
    """Gemini generateContent API を呼び、テキストを返す. safety/429/入力長エラー処理付き."""
    _write_status(f'💚 Gemini-{model}')
    if not GEMINI_KEY:
        return 'Error: GEMINI_API_KEY が設定されていません'
    truncated = False
    if len(prompt) > MAX_INPUT_CHARS:
        prompt = prompt[:MAX_INPUT_CHARS] + '\n\n[...入力長上限に達したため切り詰めました...]'
        truncated = True
    url = f'{GEMINI_BASE}/{model}:generateContent'
    data = json.dumps({
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {'maxOutputTokens': max_tokens}
    }).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json',
        'x-goog-api-key': GEMINI_KEY,
    })
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as res:
                r = json.loads(res.read())
            if _is_safety_blocked(r):
                return 'Error: Gemini safety filter でブロックされました（内容がセンシティブ判定）。GLMが代替判断してください。'
            for cand in r.get('candidates', []):
                for p in cand.get('content', {}).get('parts', []):
                    if 'text' in p:
                        text = p['text']
                        if truncated:
                            text = '[警告: 入力を切り詰めました]\n' + text
                        return text
            return ''
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429 and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return f'Error: Gemini API {e.code} - {e.reason}（GLMが代替判断してください）'
        except Exception as e:
            return f'Error: Gemini API 呼出失敗 - {e}'
    return f'Error: Gemini API 429 rate limit（再試行後も失敗: {last_err}）'


MAX_INPUT_CHARS = 24000  # 入力長上限（約8kトークン相当）


def _is_safety_blocked(r):
    """safety filter ブロックを検出."""
    if r.get('promptFeedback', {}).get('blockReason'):
        return True
    for cand in r.get('candidates', []):
        if cand.get('finishReason') == 'SAFETY':
            return True
    return False


TOOLS = [
    {
        "name": "review_with_gemini",
        "description": "Gemini でコードレビューを行う第2オピニオン。バグ検出・セキュリティ問題・改善点を指摘。"
                       "GLMとは別ベンダー(米国Google)で真の第2の目。ClaudeのAPIトークンを消費しない(無料枠)。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "レビュー対象のコード/差分"},
                "focus": {"type": "string",
                          "description": "重点項目: bug / security / performance / readability / all(省略時)",
                          "default": "all"},
                "model": {"type": "string",
                          "description": "Geminiモデル名(省略時 gemini-2.5-pro安定版)。preview系は許可ゲート確認",
                          "default": "gemini-2.5-pro"}
            },
            "required": ["code"]
        }
    }
]

FOCUS_MAP = {
    "bug": "バグ・論理エラー・境界ケース",
    "security": "セキュリティ脆弱性(OWASP・認証・入力検証)",
    "performance": "パフォーマンス・計算量・N+1",
    "readability": "可読性・命名・構造",
    "all": "バグ・セキュリティ・パフォーマンス・可読性の総合",
}


def handle_request(req):
    method = req.get('method', '')
    params = req.get('params', {})
    req_id = req.get('id')

    if method == 'initialize':
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "gemini-mcp", "version": "1.0.0"}
        }
    elif method in ('notifications/initialized', 'initialized'):
        return None
    elif method == 'tools/list':
        result = {"tools": TOOLS}
    elif method == 'tools/call':
        tool_name = params.get('name')
        args = params.get('arguments', {})
        if tool_name == 'review_with_gemini':
            code = args['code']
            focus = args.get('focus', 'all')
            model = args.get('model', DEFAULT_MODEL)
            focus_text = FOCUS_MAP.get(focus, FOCUS_MAP['all'])
            prompt = (
                f"以下のコードをレビューしてください。指摘は深刻度(高/中/低)付きで、"
                f"改善案を提示してください。観点: {focus_text}\n\n"
                f"---\n{code}\n---\n\n"
                f"出力形式: 日本語・指摘リスト(箇条書き)・各指摘に深刻度と修正案"
            )
            text = call_gemini(prompt, model=model)
            result = {"content": [{"type": "text", "text": text}]}
        else:
            result = {"content": [{"type": "text", "text": f"不明なツール: {tool_name}"}], "isError": True}
    else:
        result = None

    if req_id is not None and result is not None:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    return None


def run_loop():
    """JSON-RPC over stdio のメインループ."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            response = handle_request(req)
            if response:
                sys.stdout.write(json.dumps(response) + '\n')
                sys.stdout.flush()
        except Exception as e:
            try:
                req_id = json.loads(line).get('id')
            except Exception:
                req_id = None
            if req_id is not None:
                err = {"jsonrpc": "2.0", "id": req_id,
                       "error": {"code": -32603, "message": str(e)}}
                sys.stdout.write(json.dumps(err) + '\n')
                sys.stdout.flush()


if __name__ == '__main__':
    run_loop()

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
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
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

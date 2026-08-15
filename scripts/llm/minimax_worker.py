#!/usr/bin/env python3
"""MiniMax Worker - コマンドラインからMiniMaxを呼び出す
使い方:
  python3 minimax_worker.py "プロンプト"
  cat file.txt | python3 minimax_worker.py
"""

import json
import sys
import os
import urllib.request

MINIMAX_KEY = os.environ.get('MINIMAX_API_KEY', '')


def call_minimax(prompt, max_tokens=2000):
    data = json.dumps({
        'model': 'MiniMax-M3',
        'max_tokens': max_tokens,
        'messages': [{'role': 'user', 'content': prompt}]
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.minimax.io/anthropic/v1/messages',
        data=data,
        headers={
            'x-api-key': MINIMAX_KEY,
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json'
        }
    )
    with urllib.request.urlopen(req, timeout=120) as res:
        r = json.loads(res.read())
    for block in r.get('content', []):
        if block.get('type') == 'text':
            return block['text']
    return ''


if __name__ == '__main__':
    if len(sys.argv) > 1:
        prompt = ' '.join(sys.argv[1:])
    else:
        prompt = sys.stdin.read()
    print(call_minimax(prompt))

#!/usr/bin/env python3
"""MiniMax Token Plan wrapper - M3テキスト生成（Starter plan）
Anthropic互換エンドポイントを使用（Token Planサブスク用）
"""
import sys
import os
import json
import requests

def main():
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        print("ERROR: MINIMAX_API_KEY not set")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: ask-minimax.py <query> [--model MODEL]")
        print("  --model   Model name (default: MiniMax-M3)")
        sys.exit(1)

    args = sys.argv[1:]
    query_parts = []
    model_name = "MiniMax-M3"

    i = 0
    while i < len(args):
        if args[i] == "--model" and i + 1 < len(args):
            model_name = args[i + 1]
            i += 2
        else:
            query_parts.append(args[i])
            i += 1

    query = " ".join(query_parts)
    if not query:
        print("ERROR: No query provided")
        sys.exit(1)

    # Token Plan用エンドポイント（Anthropic互換）
    url = "https://api.minimax.io/anthropic/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "max_tokens": 4096,
        "messages": [
            {"role": "user", "content": query}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        # Anthropic Messages API形式のレスポンスをパース
        for block in data.get("content", []):
            if block.get("type") == "text":
                print(block["text"])

    except requests.exceptions.RequestException as e:
        print(f"ERROR: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Details: {e.response.text}")
        sys.exit(1)

if __name__ == "__main__":
    main()

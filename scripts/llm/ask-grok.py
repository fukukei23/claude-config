#!/usr/bin/env python3
"""Grok (xAI) API wrapper - Xのリアルタイム情報、テキスト生成"""
import sys
import os
import json
import requests

def main():
    api_key = os.environ.get("XAI_API_KEY", "")
    if not api_key:
        print("ERROR: XAI_API_KEY not set")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: ask-grok.py <query> [--model MODEL] [--search]")
        print("  --model   Model name (default: grok-3)")
        print("  --search  Enable live search (X posts, web)")
        sys.exit(1)

    args = sys.argv[1:]
    query_parts = []
    model_name = "grok-3"
    search_enabled = False

    i = 0
    while i < len(args):
        if args[i] == "--model" and i + 1 < len(args):
            model_name = args[i + 1]
            i += 2
        elif args[i] == "--search":
            search_enabled = True
            i += 1
        else:
            query_parts.append(args[i])
            i += 1

    query = " ".join(query_parts)
    if not query:
        print("ERROR: No query provided")
        sys.exit(1)

    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": query}],
    }

    # ライブ検索（X投稿・Web）
    if search_enabled:
        payload["search_parameters"] = {
            "mode": "auto",
            "sources": [{"type": "x"}, {"type": "web"}],
            "return_citations": True
        }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]
        print(content)

        # 検索結果の引用があれば表示
        if search_enabled and "citations" in data.get("search_results", {}):
            print("\n--- Sources ---")
            for cite in data["search_results"]["citations"]:
                print(f"  - {cite}")

    except requests.exceptions.RequestException as e:
        print(f"ERROR: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Details: {e.response.text}")
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Perplexity API wrapper - Web検索＋引用付き回答"""
import sys
import os
import json
import requests

def main():
    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not api_key:
        print("ERROR: PERPLEXITY_API_KEY not set")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: ask-perplexity.py <query> [--model MODEL]")
        print("  --model   Model name (default: sonar)")
        sys.exit(1)

    args = sys.argv[1:]
    query_parts = []
    model_name = "sonar"

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

    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "Be precise and concise. Cite sources. Respond in Japanese if the query is in Japanese."},
            {"role": "user", "content": query}
        ],
        "return_citations": True,
        "return_related_questions": True
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]
        print(content)

        # 引用表示
        if "citations" in data:
            print("\n--- Sources ---")
            for i, cite in enumerate(data["citations"], 1):
                print(f"  [{i}] {cite}")

        # 関連質問
        if "related_questions" in data:
            print("\n--- Related ---")
            for q in data["related_questions"]:
                print(f"  - {q}")

    except requests.exceptions.RequestException as e:
        print(f"ERROR: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Details: {e.response.text}")
        sys.exit(1)

if __name__ == "__main__":
    main()

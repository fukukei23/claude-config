#!/usr/bin/env python3
"""Gemini API wrapper - YouTube動画分析、テキスト生成など"""
import sys
import os
from google import genai
from google.genai import types

def main():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: ask-gemini.py <query> [--model MODEL] [--youtube URL]")
        print("  --model   Model name (default: gemini-2.0-flash)")
        print("  --youtube Analyze YouTube video URL")
        sys.exit(1)

    args = sys.argv[1:]
    query_parts = []
    model_name = "gemini-2.0-flash"
    youtube_url = None

    i = 0
    while i < len(args):
        if args[i] == "--model" and i + 1 < len(args):
            model_name = args[i + 1]
            i += 2
        elif args[i] == "--youtube" and i + 1 < len(args):
            youtube_url = args[i + 1]
            i += 2
        else:
            query_parts.append(args[i])
            i += 1

    query = " ".join(query_parts)
    if not query and not youtube_url:
        print("ERROR: No query provided")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    # YouTube動画分析
    if youtube_url:
        prompt = query if query else f"以下のYouTube動画の内容を要約してください（日本語で）:\n{youtube_url}"
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            print(response.text)
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)
        return

    # 通常のテキスト生成
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=query,
        )
        print(response.text)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

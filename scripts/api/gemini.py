#!/usr/bin/env python3
"""Gemini API経由でYouTube動画を真正解析し、統一JSONで結果を返す.

Usage:
    gemini.py --youtube <URL> [--prompt-file <path>] [--model <name>]

スキル（CC）は summary のみを受領し、full_data はキャッシュを参照する。
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

# リポジトリルートを import path に追加（lib.api_base 参照用）
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from lib.api_base import (  # noqa: E402
    make_error_result,
    make_success_result,
    run_api,
)

DEFAULT_PROMPT_FILE = (
    _REPO_ROOT
    / "skills"
    / "reverse-engineer-song"
    / "references"
    / "楽曲逆コンパイル_マスタープロンプト.md"
)
DEFAULT_MODEL = "gemini-2.0-flash"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数をパースする."""
    parser = argparse.ArgumentParser(description="Gemini YouTube動画解析")
    parser.add_argument("--youtube", required=True, help="解析対象のYouTube URL")
    parser.add_argument(
        "--prompt-file",
        default=str(DEFAULT_PROMPT_FILE),
        help="マスタープロンプトのファイルパス",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Geminiモデル名")
    return parser.parse_args(argv)


def _cache_key_for(youtube_url: str, model: str) -> str:
    """URL+モデルからキャッシュキーを生成する."""
    raw = f"{youtube_url}|{model}"
    return "gemini_" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def _analyze(youtube_url: str, prompt_text: str, model: str) -> str:
    """Gemini APIでYouTube動画を真正解析し、レスポンステキストを返す.

    types.Part.from_uri で動画を直接Geminiに渡す（文字列埋め込みではない）。
    """
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_uri(url=youtube_url, mime_type="video/*"),
            prompt_text,
        ],
    )
    text = response.text or ""
    if not text.strip():
        raise RuntimeError("empty response from Gemini (possible safety block)")
    return text


def _summarize(full_response: str, cache_key: str) -> dict:
    """Gemini生レスポンスを要約しキャッシュに保存する.

    現状は生レスポンスの先頭2000文字をsummaryとする（将来はLLM要約に拡張）。
    """
    summary = full_response[:2000]
    return make_success_result(
        summary=summary,
        full_data={"gemini_response": full_response},
        cache_key=cache_key,
    )


def main(argv: list[str] | None = None) -> int:
    """エントリポイント。JSON結果を標準出力に出す."""
    args = parse_args(argv)
    prompt_path = Path(args.prompt_file)
    if not prompt_path.exists():
        result = make_error_result(f"prompt-file not found: {args.prompt_file}")
        print(json.dumps(result, ensure_ascii=False))
        return 1
    prompt_text = prompt_path.read_text(encoding="utf-8")

    cache_key = _cache_key_for(args.youtube, args.model)

    def call_fn() -> str:
        return _analyze(args.youtube, prompt_text, args.model)

    result = run_api(call_fn, _summarize, cache_key=cache_key)

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())

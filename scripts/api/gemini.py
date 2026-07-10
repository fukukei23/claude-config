#!/usr/bin/env python3
"""Gemini API経由でYouTube動画を真正解析し、統一JSONで結果を返す.

Usage:
    gemini.py --youtube <URL> [--prompt-file <path>]

モデルは config/gemini-models.json の video 候補から自動選択（陳腐化耐性・DEFAULT_MODEL 固定は廃止）。
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
    _load_candidates,
    make_error_result,
    make_success_result,
    run_api_with_fallback,
)

DEFAULT_PROMPT_FILE = (
    _REPO_ROOT
    / "skills"
    / "reverse-engineer-song"
    / "references"
    / "楽曲逆コンパイル_マスタープロンプト.md"
)
# モデルは config/gemini-models.json の video 候補から自動選択（陳腐化耐性）。


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数をパースする."""
    parser = argparse.ArgumentParser(description="Gemini YouTube動画解析")
    parser.add_argument("--youtube", required=True, help="解析対象のYouTube URL")
    parser.add_argument(
        "--prompt-file",
        default=str(DEFAULT_PROMPT_FILE),
        help="マスタープロンプトのファイルパス",
    )
    return parser.parse_args(argv)


def _cache_key_for(youtube_url: str, candidates_key: str) -> str:
    """URL+候補からキャッシュキーを生成する."""
    raw = f"{youtube_url}|{candidates_key}"
    return "gemini_" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def _load_key() -> str:
    """Gemini APIキーを2段階で取得（os.environ → ~/.secrets.env パース）."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    secrets = Path.home() / ".secrets.env"
    if secrets.exists():
        for line in secrets.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("export ") and "=" in line:
                name, _, val = line[len("export "):].partition("=")
                if name.strip() == "GEMINI_API_KEY":
                    val = val.strip().strip('"').strip("'")
                    if val:
                        return val
    raise RuntimeError("GEMINI_API_KEY not found (env or ~/.secrets.env)")


def _call_factory(youtube_url: str, prompt_text: str, api_key: str):
    """モデル名を受け取り generate_content を実行する callable を返す（run_api_with_fallback 用）.

    types.Part.from_uri で動画を直接Geminiに渡す（文字列埋め込みではない）。
    """

    def factory(model: str):
        def call() -> str:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_uri(file_uri=youtube_url, mime_type="video/*"),
                    prompt_text,
                ],
            )
            text = response.text or ""
            if not text.strip():
                raise RuntimeError("empty response from Gemini (possible safety block)")
            return text

        return call

    return factory


def _summarize(full_response: str, cache_key: str, model: str) -> dict:
    """Gemini生レスポンスを要約しキャッシュに保存する（使用モデルも記録）.

    現状は生レスポンスの先頭2000文字をsummaryとする（将来はLLM要約に拡張）。
    """
    summary = full_response[:2000]
    return make_success_result(
        summary=summary,
        full_data={"gemini_response": full_response, "model": model},
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

    # モデルは config/gemini-models.json の video 候補から自動選択（陳腐化耐性）
    candidates = _load_candidates("video")
    if not candidates:
        result = make_error_result("no video candidates in config/gemini-models.json")
        print(json.dumps(result, ensure_ascii=False))
        return 1
    cache_key = _cache_key_for(args.youtube, "+".join(candidates))

    try:
        api_key = _load_key()
        model, text = run_api_with_fallback(
            _call_factory(args.youtube, prompt_text, api_key), candidates, api_key
        )
    except Exception as exc:  # 陳腐化警告・APIエラー・キーなし等
        result = make_error_result(f"{type(exc).__name__}: {exc}")
        print(json.dumps(result, ensure_ascii=False))
        return 1

    result = _summarize(text, cache_key, model)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())

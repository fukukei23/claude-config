#!/usr/bin/env python3
"""Gemini API経由でテキストプロンプトの応答を stdout に出力する軽量ユーティリティ.

gemini.py (YouTube解析) / gemini_vision.py (画像解析) と異なり、
テキスト-only プロンプトを投げて応答テキストをそのまま stdout に出力する。
エラー時は非0 exit で stderr にメッセージ（パイプライン向き・JSONではない）。

Usage:
    gemini_text.py --prompt <text>
    gemini_text.py <text>             # 位置引数
    echo "<text>" | gemini_text.py    # 標準入力

APIキー: GEMINI_API_KEY (env または ~/.secrets.env)。
モデルは config/gemini-models.json の text 候補から自動選択（陳腐化耐性）。
"""
import argparse
import os
import re
import sys
from pathlib import Path

# リポジトリルートを import path に追加（lib.api_base 参照用）
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from lib.api_base import (  # noqa: E402
    _load_candidates,
    run_api_with_fallback,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数をパースする."""
    parser = argparse.ArgumentParser(description="Gemini テキストプロンプト呼出")
    parser.add_argument("prompt", nargs="?", help="テキストプロンプト（位置引数）")
    parser.add_argument(
        "--prompt",
        dest="prompt_opt",
        help="テキストプロンプト（オプション形式）",
    )
    return parser.parse_args(argv)


def _load_key() -> str:
    """Gemini APIキーを2段階で取得（os.environ → ~/.secrets.env パース）.

    Returns:
        APIキー文字列

    Raises:
        RuntimeError: キーが見つからない場合
    """
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


def _call_factory(prompt_text: str, api_key: str):
    """モデル名を受け取り generate_content を実行する callable を返す.

    run_api_with_fallback に渡す call_fn_factory 引数用。
    """

    def factory(model: str):
        def call() -> str:
            from google import genai

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=prompt_text,
            )
            text = response.text or ""
            if not text.strip():
                raise RuntimeError(
                    "empty response from Gemini (possible safety block)"
                )
            return text

        return call

    return factory


def _extract_http_status(exc: Exception) -> int | None:
    """例外メッセージから HTTP ステータスコード(3桁)を抽出する.

    genai ClientError はステータスコードを文字列表現に含むため正規表現で取得。
    api_base.py の文字列マッチ方式と同じアプローチ（堅牢・依存属性なし）。

    Returns:
        ステータスコード(400-599)または None（抽出不可時）。
    """
    m = re.search(r"\b([45]\d{2})\b", str(exc))
    return int(m.group(1)) if m else None


def main(argv: list[str] | None = None) -> int:
    """エントリポイント。応答テキストを stdout に出す（エラー時 stderr + 非0 exit）."""
    args = parse_args(argv)
    # プロンプト優先順位: --prompt > 位置引数 > stdin
    if args.prompt_opt:
        prompt_text = args.prompt_opt
    elif args.prompt:
        prompt_text = args.prompt
    else:
        prompt_text = sys.stdin.read().strip()

    if not prompt_text:
        print("error: empty prompt", file=sys.stderr)
        return 1

    candidates = _load_candidates("text")
    if not candidates:
        print(
            "error: no text candidates in config/gemini-models.json",
            file=sys.stderr,
        )
        return 1

    try:
        api_key = _load_key()
        _model, text = run_api_with_fallback(
            _call_factory(prompt_text, api_key),
            candidates,
            api_key,
        )
    except Exception as exc:
        status = _extract_http_status(exc)
        if status:
            print(f"HTTP_STATUS:{status}", file=sys.stderr)
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        if status == 429:
            return 4
        if status is not None and 500 <= status < 600:
            return 3
        if status is not None and 400 <= status < 500:
            return 2
        return 1

    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

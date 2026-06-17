#!/usr/bin/env python3
"""Gemini API経由でYouTube動画を真正解析し、統一JSONで結果を返す.

Usage:
    gemini.py --youtube <URL> [--prompt-file <path>] [--model <name>]

スキル（CC）は summary のみを受領し、full_data はキャッシュを参照する。
"""
import argparse
import sys
from pathlib import Path

# リポジトリルートを import path に追加（lib.api_base 参照用）
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from lib.api_base import run_api  # noqa: E402

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


def main(argv: list[str] | None = None) -> int:
    """エントリポイント。JSON結果を標準出力に出す."""
    args = parse_args(argv)
    print(f"[DEBUG] youtube={args.youtube} model={args.model}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

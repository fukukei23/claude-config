#!/usr/bin/env python3
"""Gemini API経由で音声ファイル（MP3等）を真正解析し、統一JSONで結果を返す.

gemini.py の音声ファイル版。YouTube URL ではなくローカル音声を
inline_data (Part.from_bytes) で Gemini に直接渡す。
楽曲のキャラクター評価・比較評価・発音チェック等に用いる。

Usage:
    gemini-audio.py --audio <path> [<path> ...] [--prompt <text>] [--model <name>]

複数ファイルを指定すると比較評価する（順序は引数順・プロンプトで番号参照）。
"""
import argparse
import hashlib
import json
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

DEFAULT_MODEL = "gemini-3.5-flash"

DEFAULT_PROMPT = """以下の音声ファイルを順に聴き、楽曲評価を行ってください。
各ファイル（番号順）について以下を評価し、JSON形式で返答してください:

1. 音楽的キャラクター（ジャンル・時代・サウンドの質感）
2. ボーカル構成（性別・歌唱スタイル: ラップ/歌唱/ハミング等）
3. 発音の明瞭さ（日本語歌詞の聞き取りやすさ・タグや括弧の読み上げゴミの有無）
4. 総合品質（10点満点・簡評）

最後に「比較判定」として、どのファイルが
「Dragon Ash『Grateful Days』(1999) 風の90年代日本ミクスチャーロック・日本語ヒップホップ」
に最も近いかを理由付きで判定してください。

JSONスキーマ例:
{
  "files": [
    {"index": 1, "name": "...", "character": "...", "vocals": "...",
     "pronunciation": "...", "score": 8, "note": "..."}
  ],
  "comparison": {"closest_to_intent": 2, "reason": "..."}
}
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数をパースする."""
    parser = argparse.ArgumentParser(description="Gemini 音声ファイル解析")
    parser.add_argument(
        "--audio",
        nargs="+",
        required=True,
        help="解析対象の音声ファイルパス（複数可・比較評価）",
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="評価プロンプト")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Geminiモデル名")
    return parser.parse_args(argv)


def _mime_for(path: Path) -> str:
    """ファイル拡張子からMIMEタイプを判定する.

    Args:
        path: 音声ファイルのパス

    Returns:
        MIMEタイプ文字列（不明なら audio/mpeg）
    """
    ext = path.suffix.lower()
    return {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
    }.get(ext, "audio/mpeg")


def _cache_key_for(audio_paths: list[str], model: str) -> str:
    """ファイルパス群+モデルからキャッシュキーを生成する."""
    raw = "|".join(audio_paths) + f"|{model}"
    return "gemini_audio_" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def _analyze(audio_paths: list[Path], prompt_text: str, model: str) -> str:
    """Gemini APIで音声ファイルを真正解析し、レスポンステキストを返す.

    各ファイルを Part.from_bytes で inline_data として渡す（文字列埋め込みではない）。
    """
    from google import genai
    from google.genai import types

    api_key = __import__("os").environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")

    client = genai.Client(api_key=api_key)
    contents = []
    for i, p in enumerate(audio_paths, 1):
        data = p.read_bytes()
        contents.append(types.Part.from_bytes(data=data, mime_type=_mime_for(p)))
        contents.append(f"（ファイル{i}: {p.name}）")
    contents.append(prompt_text)

    response = client.models.generate_content(model=model, contents=contents)
    text = response.text or ""
    if not text.strip():
        raise RuntimeError("empty response from Gemini (possible safety block)")
    return text


def _summarize(full_response: str, cache_key: str) -> dict:
    """Gemini生レスポンスを要約しキャッシュに保存する."""
    summary = full_response[:3000]
    return make_success_result(
        summary=summary,
        full_data={"gemini_response": full_response},
        cache_key=cache_key,
    )


def main(argv: list[str] | None = None) -> int:
    """エントリポイント。JSON結果を標準出力に出す."""
    args = parse_args(argv)
    audio_paths = [Path(a) for a in args.audio]
    missing = [p for p in audio_paths if not p.exists()]
    if missing:
        result = make_error_result(f"audio file not found: {missing}")
        print(json.dumps(result, ensure_ascii=False))
        return 1

    cache_key = _cache_key_for(args.audio, args.model)

    def call_fn() -> str:
        return _analyze(audio_paths, args.prompt, args.model)

    result = run_api(call_fn, _summarize, cache_key=cache_key)

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())

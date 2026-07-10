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

# モデルは config/gemini-models.json の audio 候補から自動選択（陳腐化耐性）。
# DEFAULT_MODEL 固定は廃止（"gemini-3.5-flash" は実在しないモデル名だった）。

DEFAULT_PROMPT = """以下の音声ファイルを順に聴き、**厳しく**評価してください。
良さを探すより問題を積極的に指摘すること。見た目の雰囲気だけで点数をつけないこと。

各ファイル（番号順）について以下を評価し、JSON形式で返答:

1. **ボーカル構成（詳細に・重要）**:
   - ボーカル人数（1人/2人/3人以上）
   - 各ボーカルの性別（男性/女性/中性的。「聞き分け不能」なら明記）
   - 複数キャラの混在・衝突の有無（ごちゃついていないか）

2. **発音の問題（厳格に・最重要）**:
   - **歌詞以外の部分（英語タグ・括弧内・指示語）が歌われているか**。歌われていたら**その発言内容を具体的に書き出す**
   - 日本語歌詞の聞き取りやすさ
   - AI特有の不自然発音・造語の有無

3. **サウンド・キャラクター**: ジャンル・時代・質感

4. **総合品質（10点満点）**: 雰囲気の良さだけでなく、発音ゴミ・声の混在等の実用問題を反映した厳しい点数

最後に「比較判定」として、どのファイルが意図（指定があればそれ、なければ最も自然で聴きやすい曲）に近いかを**理由付き**で判定。雰囲気が良くても発音ゴミ・声の混在があれば減点して判定すること。

JSONスキーマ例:
{
  "files": [
    {"index": 1, "name": "...",
     "vocals": {"count": 2, "genders": ["male","female"], "clash": "なし"},
     "pronunciation_issues": "「male rap smooth and melodic」と歌詞外英文を歌っている",
     "character": "...", "score": 6, "note": "..."}
  ],
  "comparison": {"best": 2, "reason": "..."}
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


def _call_factory(audio_paths: list[Path], prompt_text: str, api_key: str):
    """モデル名を受け取り generate_content を実行する callable を返す（run_api_with_fallback 用）."""

    def factory(model: str):
        def call() -> str:
            from google import genai
            from google.genai import types

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

        return call

    return factory


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

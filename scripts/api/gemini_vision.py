#!/usr/bin/env python3
"""Gemini API経由で画像ファイル（PNG/JPEG等）を真正解析し、統一JSONで結果を返す.

gemini-audio.py の画像版。ローカル画像を inline_data (Part.from_bytes) で Gemini に直接渡す。
モデル陳腐化耐性（5層）付き: config/gemini-models.json の候補リストから実在モデルを自動選択し、
403/404/5xx で次候補へフォールバック（429はバックオフリトライ）。

Usage:
    gemini_vision.py --image <path> [<path> ...] [--prompt <text>] [--allow-paid]

複数ファイルを指定すると比較分析する（順序は引数順・プロンプトで番号参照）。
セキュリティ: ~/.claude/image-cache/ 配下の画像のみ許可（sandbox・path traversal対策）。
"""
import argparse
import hashlib
import json
import mimetypes
import os
import sys
from pathlib import Path

# リポジトリルートを import path に追加（lib.api_base 参照用）
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from lib.api_base import (  # noqa: E402
    make_error_result,
    make_success_result,
    resolve_gemini_model,
    run_api_with_fallback,
)

DEFAULT_PROMPT = """以下の画像を詳細に分析し、内容を日本語で構造化して返答してください:

1. **主要な被写体・シーン**: 何が写っているか、全体的な状況
2. **テキスト・文字（OCR）**: 画像内に文字があれば、見やすく書き出す（UIのラベル・ボタン・メニュー・ログ等すべて）
3. **色・構図・スタイル**: 配色・レイアウト・写真好き/イラスト/図表/UIスクショ の別
4. **技術的メタ情報**: UIスクショの場合はOS・アプリ名・ウィンドウ構成・ボタン等のUI要素を構造化して記述

複数画像がある場合は番号順に各々分析し、最後に比較・共通点・相違点をまとめる。
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数をパースする."""
    parser = argparse.ArgumentParser(description="Gemini 画像ファイル解析（モデル陳腐化耐性付き）")
    parser.add_argument(
        "--image",
        nargs="+",
        required=True,
        help="解析対象の画像ファイルパス（複数可・比較分析）",
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="分析プロンプト")
    parser.add_argument(
        "--allow-paid",
        action="store_true",
        help="有料モデル（paid_ok:true）の使用を許可（既定は無料枠のみ・課金事故防止）",
    )
    return parser.parse_args(argv)


_MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}

_ALLOWED_ROOT = (Path.home() / ".claude" / "image-cache").resolve()


def _mime_for(path: Path) -> str:
    """ファイル拡張子からMIMEタイプを判定する（mimetypes優先・辞書フォールバック）.

    Args:
        path: 画像ファイルのパス

    Returns:
        MIMEタイプ文字列（不明なら image/jpeg）
    """
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed:
        return guessed
    return _MIME_MAP.get(path.suffix.lower(), "image/jpeg")


def _is_safe_path(path: Path) -> None:
    """sandboxチェック: ~/.claude/image-cache/ 配下のみ許可（path traversal + symlink脱出対策）.

    Args:
        path: 検証する画像パス

    Raises:
        ValueError: 許可ディレクトリ外の場合
    """
    resolved = path.resolve()
    real = Path(os.path.realpath(resolved))
    allowed = _ALLOWED_ROOT
    if real != allowed and not str(real).startswith(str(allowed) + os.sep):
        raise ValueError(
            f"path not allowed outside image-cache (sandbox): {path}. "
            "許可されるのは ~/.claude/image-cache/ 配下のみ。"
        )


def _load_key() -> str:
    """Gemini APIキーを2段階で取得する（os.environ → ~/.secrets.env ファイルパース）.

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


def _cache_key_for(image_paths: list[str], candidates_key: str) -> str:
    """画像パス群+候補からキャッシュキーを生成する."""
    raw = "|".join(image_paths) + f"|{candidates_key}"
    return "gemini_vision_" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def _call_factory(image_paths: list[Path], prompt_text: str, api_key: str):
    """モデル名を受け取り「generate_content を実行する callable」を返す関数を生成する.

    run_api_with_fallback に渡す call_fn_factory 引数用。

    Args:
        image_paths: 画像Pathリスト
        prompt_text: 分析プロンプト
        api_key: Gemini APIキー

    Returns:
        model -> callable のファクトリ関数
    """

    def factory(model: str):
        def call() -> str:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            contents = []
            for i, p in enumerate(image_paths, 1):
                data = p.read_bytes()
                contents.append(
                    types.Part.from_bytes(data=data, mime_type=_mime_for(p))
                )
                contents.append(f"（画像{i}: {p.name}）")
            contents.append(prompt_text)
            response = client.models.generate_content(model=model, contents=contents)
            text = response.text or ""
            if not text.strip():
                raise RuntimeError("empty response from Gemini (possible safety block)")
            return text

        return call

    return factory


def _summarize(full_response: str, cache_key: str, model: str) -> dict:
    """Gemini生レスポンスを要約しキャッシュに保存する（使用モデルも記録）."""
    summary = full_response[:3000]
    return make_success_result(
        summary=summary,
        full_data={"gemini_response": full_response, "model": model},
        cache_key=cache_key,
    )


def main(argv: list[str] | None = None) -> int:
    """エントリポイント。JSON結果を標準出力に出す."""
    args = parse_args(argv)
    paths = [Path(a) for a in args.image]

    # exists チェック
    missing = [p for p in paths if not p.exists()]
    if missing:
        result = make_error_result(f"image file not found: {missing}")
        print(json.dumps(result, ensure_ascii=False))
        return 1

    # sandbox チェック
    for p in paths:
        try:
            _is_safe_path(p)
        except ValueError as e:
            result = make_error_result(str(e))
            print(json.dumps(result, ensure_ascii=False))
            return 1

    # 候補リスト読込（vision・paid_ok フィルタ）
    from lib.api_base import _load_candidates  # 遅延import

    candidates = _load_candidates("vision", paid_ok_limit=args.allow_paid)
    if not candidates:
        result = make_error_result(
            "no vision candidates in config/gemini-models.json (paid_ok filter?)"
        )
        print(json.dumps(result, ensure_ascii=False))
        return 1

    cache_key = _cache_key_for(args.image, "+".join(candidates))

    try:
        api_key = _load_key()
        # 実在確認（ListModels）後、フォールバック付き実行
        resolve_gemini_model(candidates, api_key)  # 陳腐化警告を早期に出すため
        model, text = run_api_with_fallback(
            _call_factory(paths, args.prompt, api_key), candidates, api_key
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

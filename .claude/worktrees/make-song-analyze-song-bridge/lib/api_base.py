"""API共通基盤: エラー処理・タイムアウト・JSON出力・キャッシュ保存.

全APIスクリプト（gemini.py, lastfm.py等）がこの基盤を経由して
統一されたJSON形式で結果を返す。
"""
import json
from pathlib import Path
from typing import Any


def make_error_result(error: str) -> dict:
    """例外を統一JSON形式のエラー結果に正規化する.

    Args:
        error: エラーメッセージ文字列

    Returns:
        {"status":"error","summary":null,"full_data":null,"error":<msg>}
    """
    return {
        "status": "error",
        "summary": None,
        "full_data": None,
        "error": error,
    }


def _cache_dir() -> Path:
    """full_dataキャッシュ保存ディレクトリ（~/tmp/api_cache/）を返す."""
    d = Path.home() / "tmp" / "api_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def make_success_result(summary: str, full_data: Any, cache_key: str) -> dict:
    """成功結果を統一JSON形式で生成し、full_dataをキャッシュに保存する.

    Args:
        summary: CCに渡す要約（500トークン以内推奨）
        full_data: Gemini/APIの生レスポンス（キャッシュに保存・CCには渡さない）
        cache_key: キャッシュファイル名の一意キー

    Returns:
        {"status":"ok","summary":<str>,"full_data":<cache_path>,"error":null}
    """
    cache_path = _cache_dir() / f"{cache_key}.json"
    cache_path.write_text(
        json.dumps(full_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "status": "ok",
        "summary": summary,
        "full_data": str(cache_path),
        "error": None,
    }


def run_api(
    call_fn: Any,
    summary_fn: Any,
    cache_key: str,
    timeout: int = 60,
) -> dict:
    """API呼び出しをラップし、例外を捕捉して統一JSONで返す.

    Args:
        call_fn: 引数なし・API呼び出しを行い結果を返す関数
        summary_fn: (result, cache_key)を受け取りmake_success_resultを返す関数
        cache_key: キャッシュファイル名の一意キー
        timeout: タイムアウト秒（現状はドキュメント目的・将来signalで適用）

    Returns:
        成功時はsummary_fnの戻り値、例外時はmake_error_resultの戻り値
    """
    try:
        result = call_fn()
        return summary_fn(result, cache_key)
    except Exception as exc:  # noqa: BLE001 - 共通基盤は全例外を統一形式へ
        return make_error_result(f"{type(exc).__name__}: {exc}")

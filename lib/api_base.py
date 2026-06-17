"""API共通基盤: エラー処理・タイムアウト・JSON出力・キャッシュ保存.

全APIスクリプト（gemini.py, lastfm.py等）がこの基盤を経由して
統一されたJSON形式で結果を返す。
"""


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
